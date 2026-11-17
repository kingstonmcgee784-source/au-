"""Turn metrics into per-category ratings (0.0 to 1.0) for the scoring methodology.

Pure functions. Each category averages the sub-ratings it has data for, and is
left unrated (None) when too few are available. A category without data is
never treated as zero or as average.

Version 1 limitation: thresholds are absolute, the same for every industry.
A 15% operating margin means something different for a grocer and for a
software company. Sector-relative comparison is a planned improvement.

Each threshold table lists (metric value, rating) points. Ratings between
points are interpolated linearly, and values outside the table take the
nearest end point.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.analysis.metrics import Metrics

Curve = Sequence[tuple[float, float]]


@dataclass(frozen=True)
class SubRating:
    metric: str
    curve: Curve
    label: str


def interpolate(value: float, curve: Curve) -> float:
    points = sorted(curve)
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        if x0 <= value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    raise AssertionError("unreachable")


# (key, minimum sub-ratings needed, sub-ratings)
CATEGORY_RULES: dict[str, tuple[int, tuple[SubRating, ...]]] = {
    "fundamentals": (
        3,
        (
            SubRating(
                "operating_margin", ((-0.10, 0.0), (0.0, 0.3), (0.25, 1.0)), "Operating margin"
            ),
            SubRating(
                "fcf_margin", ((-0.10, 0.0), (0.0, 0.3), (0.20, 1.0)), "Free cash flow margin"
            ),
            SubRating("roe", ((0.0, 0.0), (0.25, 1.0)), "Return on equity"),
            SubRating("current_ratio", ((0.8, 0.0), (1.2, 0.5), (2.0, 1.0)), "Current ratio"),
            SubRating("debt_to_equity", ((0.0, 1.0), (1.0, 0.5), (2.5, 0.0)), "Debt to equity"),
            SubRating(
                "share_change_yoy",
                ((-0.02, 1.0), (0.0, 0.9), (0.05, 0.4), (0.10, 0.0)),
                "Share dilution",
            ),
        ),
    ),
    "valuation": (
        2,
        (
            SubRating("pe_ttm", ((10, 1.0), (20, 0.7), (35, 0.35), (60, 0.0)), "P/E (TTM)"),
            SubRating("ev_to_ebitda", ((8, 1.0), (15, 0.6), (30, 0.2), (50, 0.0)), "EV/EBITDA"),
            SubRating("price_to_sales", ((1, 1.0), (4, 0.6), (10, 0.25), (20, 0.0)), "Price/sales"),
            SubRating(
                "fcf_yield", ((-0.02, 0.0), (0.0, 0.2), (0.04, 0.6), (0.08, 1.0)), "FCF yield"
            ),
        ),
    ),
    "technical": (
        2,
        (
            # Best in an established uptrend; penalised when far below the
            # 200-day average or stretched far above it.
            SubRating(
                "price_vs_sma200",
                ((-0.25, 0.0), (0.0, 0.5), (0.10, 1.0), (0.35, 1.0), (0.80, 0.3)),
                "Price vs 200-day average",
            ),
            SubRating("sma50_above_sma200", ((0.0, 0.0), (1.0, 1.0)), "50-day above 200-day"),
            SubRating(
                "rsi_14", ((25, 0.2), (45, 0.7), (55, 1.0), (68, 1.0), (80, 0.4)), "RSI (14)"
            ),
            SubRating(
                "relative_strength_6m",
                ((-0.25, 0.0), (0.0, 0.5), (0.25, 1.0)),
                "6-month return vs S&P 500",
            ),
        ),
    ),
    "growth": (
        2,
        (
            SubRating(
                "revenue_growth_yoy",
                ((-0.10, 0.0), (0.0, 0.25), (0.30, 1.0)),
                "Revenue growth (latest quarter)",
            ),
            SubRating(
                "revenue_growth_ttm",
                ((-0.10, 0.0), (0.0, 0.25), (0.30, 1.0)),
                "Revenue growth (TTM)",
            ),
            SubRating(
                "net_income_growth_ttm",
                ((-0.20, 0.0), (0.0, 0.3), (0.40, 1.0)),
                "Net income growth (TTM)",
            ),
            SubRating(
                "revenue_acceleration",
                ((-0.10, 0.0), (0.0, 0.5), (0.10, 1.0)),
                "Revenue growth acceleration",
            ),
        ),
    ),
    "risk_reward": (
        2,
        (
            SubRating(
                "volatility_1y", ((0.20, 1.0), (0.40, 0.6), (0.80, 0.0)), "Volatility (1 year)"
            ),
            SubRating(
                "max_drawdown_1y",
                ((-0.60, 0.0), (-0.30, 0.5), (-0.10, 1.0)),
                "Max drawdown (1 year)",
            ),
            SubRating(
                "from_52w_high",
                ((-0.50, 0.3), (-0.20, 0.8), (-0.05, 0.6), (0.0, 0.4)),
                "Distance from 52-week high",
            ),
        ),
    ),
    # Insider (Form 4) activity only: 13F institutional holdings are not
    # connected. Open-market buying is the strongest signal; selling outside
    # a pre-arranged 10b5-1 plan, relative to company size, counts against.
    "institutional": (
        1,
        (
            SubRating(
                "insider_buyers",
                ((0, 0.5), (1, 0.75), (3, 1.0)),
                "Insider open-market buyers (180 days)",
            ),
            SubRating(
                "insider_discretionary_sales_to_market_cap",
                ((0.0, 0.7), (0.001, 0.5), (0.01, 0.2), (0.03, 0.0)),
                "Insider sales outside 10b5-1 plans vs market cap (180 days)",
            ),
        ),
    ),
    # From SEC 8-K event types only (see app.analysis.catalysts): reliable red
    # flags count against, material agreements and acquisitions count for,
    # and an earnings release expected within 90 days is a near-term catalyst.
    "catalysts": (
        2,
        (
            SubRating(
                "catalyst_red_flags_365d",
                ((0, 0.8), (1, 0.3), (2, 0.0)),
                "Red-flag filings (12 months)",
            ),
            SubRating(
                "catalyst_material_events_180d",
                ((0, 0.5), (1, 0.7), (3, 0.9)),
                "Material agreements and acquisitions (6 months)",
            ),
            SubRating(
                "catalyst_earnings_within_90d",
                ((0, 0.4), (1, 0.7)),
                "Earnings release expected within 90 days",
            ),
        ),
    ),
    # Percentile against industry peers in the local database (see
    # app.analysis.industry); unrated when there are too few peers.
    "industry": (
        3,
        (
            SubRating(
                "industry_pct_revenue_growth_ttm", ((0, 0), (1, 1)), "Revenue growth vs peers"
            ),
            SubRating(
                "industry_pct_operating_margin", ((0, 0), (1, 1)), "Operating margin vs peers"
            ),
            SubRating("industry_pct_fcf_margin", ((0, 0), (1, 1)), "FCF margin vs peers"),
            SubRating("industry_pct_roe", ((0, 0), (1, 1)), "Return on equity vs peers"),
            SubRating("industry_pct_return_6m", ((0, 0), (1, 1)), "6-month return vs peers"),
        ),
    ),
}

UNRATED_REASON = {
    "catalysts": "SEC 8-K events have not been loaded for this stock.",
    "institutional": "Insider (Form 4) filings have not been loaded, and no 13F data is connected.",
    "industry": (
        "Fewer than 4 stocks with this industry code were scored within 45 days of this one. "
        "Scan more stocks from the same industry in the Screener."
    ),
}


@dataclass(frozen=True)
class InputRating:
    """One input to a category: its value, its rating and the scale used."""

    metric: str
    label: str
    value: float
    value_text: str
    rating: float
    scale: str


@dataclass(frozen=True)
class CategoryRating:
    rating: float | None
    used: dict[str, float]  # sub-rating label -> rating, for the inputs that had data
    breakdown: list[InputRating] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # inputs without data
    minimum: int = 1  # inputs needed to rate the category


def rate(metrics: Metrics) -> dict[str, CategoryRating]:
    out: dict[str, CategoryRating] = {}
    for key, (minimum, subs) in CATEGORY_RULES.items():
        breakdown: list[InputRating] = []
        missing: list[str] = []
        for sub in subs:
            value = metrics.get(sub.metric)
            if value is None:
                missing.append(sub.label)
                continue
            breakdown.append(
                InputRating(
                    metric=sub.metric,
                    label=sub.label,
                    value=value,
                    value_text=format_value(sub.metric, value),
                    rating=round(interpolate(value, sub.curve), 3),
                    scale=describe_scale(sub.metric, sub.curve),
                )
            )
        used = {b.label: b.rating for b in breakdown}
        rating = sum(used.values()) / len(used) if subs and len(used) >= minimum else None
        out[key] = CategoryRating(
            rating=rating, used=used, breakdown=breakdown, missing=missing, minimum=minimum
        )
    return out


# How each metric is shown. Anything not listed is a plain ratio.
UNITS: dict[str, str] = {
    "operating_margin": "percent",
    "fcf_margin": "percent",
    "roe": "percent",
    "share_change_yoy": "percent",
    "fcf_yield": "percent",
    "price_vs_sma200": "percent",
    "relative_strength_6m": "percent",
    "revenue_growth_yoy": "percent",
    "revenue_growth_ttm": "percent",
    "net_income_growth_ttm": "percent",
    "revenue_acceleration": "points",
    "volatility_1y": "percent",
    "max_drawdown_1y": "percent",
    "from_52w_high": "percent",
    "insider_discretionary_sales_to_market_cap": "percent",
    "pe_ttm": "multiple",
    "ev_to_ebitda": "multiple",
    "price_to_sales": "multiple",
    "sma50_above_sma200": "yesno",
    "rsi_14": "number",
    "insider_buyers": "count",
    "catalyst_red_flags_365d": "count",
    "catalyst_material_events_180d": "count",
    "catalyst_earnings_within_90d": "yesno",
}


def format_value(metric: str, value: float) -> str:
    unit = "percentile" if metric.startswith("industry_pct_") else UNITS.get(metric, "ratio")
    if unit == "percent":
        return f"{value * 100:.1f}%"
    if unit == "points":
        return f"{value * 100:+.1f} pts"
    if unit == "multiple":
        return f"{value:.1f}×"
    if unit == "count":
        return f"{value:.0f}"
    if unit == "yesno":
        return "Yes" if value >= 0.5 else "No"
    if unit == "percentile":
        return f"better than {value * 100:.0f}% of peers"
    if unit == "number":
        return f"{value:.0f}"
    return f"{value:.2f}"


def scale_point(metric: str, x: float) -> str:
    """A threshold as written in a scale description."""
    if metric.startswith("industry_pct_"):
        return f"{x * 100:.0f}th percentile"
    if UNITS.get(metric) == "yesno":
        return "Yes" if x >= 0.5 else "No"
    return format_value(metric, x)


def describe_scale(metric: str, curve: Curve) -> str:
    """Every threshold and its rating, e.g. '10.0× or lower: 100% · 60.0× or higher: 0%'.

    Ratings change smoothly between the listed thresholds.
    """
    points = sorted(curve)
    fmt = lambda x: scale_point(metric, x)  # noqa: E731
    if UNITS.get(metric) == "yesno":
        return " · ".join(f"{fmt(x)}: {y * 100:.0f}%" for x, y in reversed(points))
    if metric.startswith("industry_pct_"):
        return "Rating equals the peer percentile (50th percentile: 50%, best in group: 100%)"

    # Merge neighbouring thresholds with the same rating into a range.
    groups: list[tuple[float, float, float]] = []
    for x, y in points:
        if groups and groups[-1][2] == y:
            groups[-1] = (groups[-1][0], x, y)
        else:
            groups.append((x, x, y))
    parts = []
    for index, (start, end, y) in enumerate(groups):
        if start != end:
            where = f"{fmt(start)} to {fmt(end)}"
        else:
            where = fmt(start)
        if index == 0:
            if not (UNITS.get(metric) == "count" and start == 0):  # counts cannot go below 0
                where += " or lower" if start == end else " (and below)"
        elif index == len(groups) - 1:
            where += " or higher" if start == end else " (and above)"
        parts.append(f"{where}: {y * 100:.0f}%")
    return " · ".join(parts) + " (in between, the rating changes gradually)"


def risk_class(metrics: Metrics) -> str | None:
    """Low / Moderate / Elevated / High / Speculative from volatility and size."""
    volatility = metrics.get("volatility_1y")
    if volatility is None:
        return None
    if volatility > 0.70:
        level = 4
    elif volatility > 0.50:
        level = 3
    elif volatility > 0.35:
        level = 2
    elif volatility > 0.22:
        level = 1
    else:
        level = 0
    market_cap = metrics.get("market_cap")
    if market_cap is not None and market_cap < 300e6:
        level = max(level, 3)
    if (metrics.get("net_income_ttm") or 0) < 0:
        level = min(level + 1, 4)
    return ("Low", "Moderate", "Elevated", "High", "Speculative")[level]


# What each input measures and why it matters, in plain language.
MEANING: dict[str, str] = {
    "operating_margin": "share of revenue left after running the business; higher means a more "
    "profitable company",
    "fcf_margin": "share of revenue turned into free cash after investment; cash is harder to "
    "flatter than accounting profit",
    "roe": "profit earned per dollar of shareholders' equity; higher means capital is used well",
    "current_ratio": "short-term assets compared with bills due within a year; below 1 can "
    "mean cash pressure",
    "debt_to_equity": "debt compared with shareholders' equity; less debt means less financial "
    "risk",
    "share_change_yoy": "change in the number of shares over a year; a rising count dilutes "
    "existing shareholders",
    "pe_ttm": "price paid for each dollar of the last 12 months' earnings; lower is cheaper",
    "ev_to_ebitda": "company value including debt compared with operating cash earnings; "
    "lower is cheaper",
    "price_to_sales": "price paid for each dollar of the last 12 months' revenue; lower is cheaper",
    "fcf_yield": "free cash flow as a share of market value: the cash return at today's price",
    "price_vs_sma200": "distance above or below the 200-day average; above means an uptrend, "
    "but far above can mean the stock is stretched",
    "sma50_above_sma200": "whether the 50-day average is above the 200-day: the medium-term "
    "trend is up",
    "rsi_14": "momentum on a 0-100 scale; around 55-68 is healthy, above 70 is stretched, "
    "below 30 is oversold",
    "relative_strength_6m": "6-month return minus the S&P 500's: whether the stock is "
    "beating the market",
    "revenue_growth_yoy": "revenue in the latest quarter versus the same quarter a year ago",
    "revenue_growth_ttm": "revenue over the last 12 months versus the 12 months before",
    "net_income_growth_ttm": "profit over the last 12 months versus the 12 months before",
    "revenue_acceleration": "whether revenue growth sped up or slowed down versus the "
    "previous quarter",
    "volatility_1y": "how much the price swings in a year; higher means a bumpier ride",
    "max_drawdown_1y": "the largest fall from a peak in the last year",
    "from_52w_high": "how far the price is below its 52-week high; a modest pullback is often "
    "a better entry than the very top or a deep slump",
    "insider_buyers": "number of insiders who bought shares with their own money; insiders "
    "rarely buy unless they expect the stock to rise",
    "insider_discretionary_sales_to_market_cap": "insider sales outside pre-scheduled plans, "
    "relative to company size; heavy unplanned selling can be a warning",
    "catalyst_red_flags_365d": "filings such as restatements, impairments, auditor changes or "
    "bankruptcy in the last year",
    "catalyst_material_events_180d": "major contracts or acquisitions reported in the last "
    "six months",
    "catalyst_earnings_within_90d": "whether an earnings release is expected soon, a "
    "near-term event that can move the stock",
}


def verdict(rating: float) -> str:
    if rating >= 0.85:
        return "Strong"
    if rating >= 0.6:
        return "Good"
    if rating >= 0.4:
        return "Mixed"
    if rating >= 0.2:
        return "Weak"
    return "Poor"


def _pct(value: float) -> str:
    return f"{abs(value) * 100:.1f}%"


def what_it_shows(metric: str, value: float) -> str:
    """What this stock's number actually means, in one sentence."""
    if metric.startswith("industry_pct_"):
        return (
            f"It ranks better than {value * 100:.0f}% of its stored industry peers on this measure."
        )
    v = value
    match metric:
        case "operating_margin":
            return f"The company keeps {v * 100:.0f} cents of operating profit from every dollar of revenue."
        case "fcf_margin":
            return f"{v * 100:.0f} cents of every revenue dollar ends up as free cash after investment."
        case "roe":
            return f"It earns {_pct(v)} a year on shareholders' equity."
        case "current_ratio":
            return f"It has ${v:.2f} of short-term assets for every $1 of bills due within a year."
        case "debt_to_equity":
            return f"It carries ${v:.2f} of debt for every $1 of shareholders' equity."
        case "share_change_yoy":
            if v > 0:
                return f"The share count grew {_pct(v)} in a year, diluting existing shareholders."
            if v < 0:
                return f"The share count fell {_pct(v)} in a year (buybacks), which helps shareholders."
            return "The share count did not change over the year."
        case "pe_ttm":
            return (
                f"Buyers pay ${v:.0f} for every $1 of yearly profit, roughly {v:.0f} years of "
                "today's earnings."
            )
        case "ev_to_ebitda":
            return f"The whole company, debt included, costs {v:.1f} times its yearly operating cash earnings."
        case "price_to_sales":
            return f"Buyers pay ${v:.2f} for every $1 of yearly revenue."
        case "fcf_yield":
            return f"At today's price, the business produces {_pct(v)} of its market value in free cash a year."
        case "price_vs_sma200":
            side = "above" if v >= 0 else "below"
            extra = ", which is stretched" if v > 0.35 else ""
            return f"The price is {_pct(v)} {side} its 200-day average{extra}."
        case "sma50_above_sma200":
            return (
                "The 50-day average is above the 200-day: the medium-term trend is up."
                if v >= 0.5
                else "The 50-day average is below the 200-day: the medium-term trend is down."
            )
        case "rsi_14":
            if v >= 70:
                state = "stretched (overbought); short-term pullbacks are common from here"
            elif v <= 30:
                state = "oversold; selling may be overdone"
            elif v >= 55:
                state = "healthy and positive"
            else:
                state = "neutral to soft"
            return f"Momentum (RSI {v:.0f}) is {state}."
        case "relative_strength_6m":
            word = "beat" if v >= 0 else "lagged"
            return f"Over 6 months it {word} the S&P 500 by {_pct(v)}."
        case "revenue_growth_yoy":
            word = "grew" if v >= 0 else "fell"
            return f"Revenue {word} {_pct(v)} versus the same quarter last year."
        case "revenue_growth_ttm":
            word = "grew" if v >= 0 else "fell"
            return f"Revenue over the last 12 months {word} {_pct(v)} versus the 12 months before."
        case "net_income_growth_ttm":
            word = "grew" if v >= 0 else "fell"
            return f"Profit over the last 12 months {word} {_pct(v)} versus the 12 months before."
        case "revenue_acceleration":
            word = "sped up" if v >= 0 else "slowed"
            return f"Revenue growth {word} by {abs(v) * 100:.1f} points from the previous quarter."
        case "volatility_1y":
            return f"The price typically swings about {_pct(v)} over a year."
        case "max_drawdown_1y":
            return f"Its worst fall from a peak in the past year was {_pct(v)}."
        case "from_52w_high":
            if v >= -0.005:
                return "It trades at or near its 52-week high."
            return f"It trades {_pct(v)} below its 52-week high."
        case "insider_buyers":
            if v == 0:
                return "No insider bought shares on the open market in the last 180 days."
            return f"{v:.0f} insider(s) bought shares with their own money in the last 180 days."
        case "insider_discretionary_sales_to_market_cap":
            if v == 0:
                return "Insiders made no sales outside pre-scheduled 10b5-1 plans in 180 days."
            return (
                f"Insiders sold shares worth {v * 100:.2f}% of the company's value outside "
                "pre-scheduled plans in 180 days."
            )
        case "catalyst_red_flags_365d":
            if v == 0:
                return "No red-flag filings (restatements, impairments, auditor changes) in a year."
            return f"{v:g} weighted red-flag filing(s) in the last year."
        case "catalyst_material_events_180d":
            if v == 0:
                return "No major contracts or acquisitions were reported in six months."
            return f"{v:.0f} major contract or acquisition filing(s) in six months."
        case "catalyst_earnings_within_90d":
            return (
                "An earnings release is expected within 90 days, a near-term event."
                if v >= 0.5
                else "No earnings release is expected within 90 days."
            )
    return f"Value: {format_value(metric, value)}."


def why_this_rating(metric: str, value: float, curve: Curve) -> str:
    """How the value maps onto the scale, giving the rating it received."""
    points = sorted(curve)
    fmt = lambda x: scale_point(metric, x)  # noqa: E731
    rating = interpolate(value, curve)
    top = max(y for _, y in points)
    r = f"{rating * 100:.0f}%"

    if UNITS.get(metric) == "yesno":
        return f"{fmt(value)} earns {r} on this input."
    if metric.startswith("industry_pct_"):
        return f"Its peer rank converts directly into a {r} rating."
    if value <= points[0][0] or value >= points[-1][0]:
        edge_x, edge_y = points[0] if value <= points[0][0] else points[-1]
        if edge_y == top:
            what = "full marks" if top == 1.0 else f"the best rating this input can get ({r})"
            return f"That is at or past {fmt(edge_x)}, which earns {what}."
        return f"That is at or past {fmt(edge_x)}, where this end of the scale gives {r}."

    # Inside a flat top, e.g. a 10%-35% sweet spot.
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        if x0 <= value <= x1 and y0 == y1 == top:
            return f"That is inside the {fmt(x0)} to {fmt(x1)} range that earns full marks."
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        if x0 <= value <= x1:
            return (
                f"That falls between {fmt(x0)} (rated {y0 * 100:.0f}%) and {fmt(x1)} "
                f"(rated {y1 * 100:.0f}%) on the scale, so it rates {r}."
            )
    return f"It rates {r}."


def explain(metric: str, value: float, curve: Curve) -> str:
    """Why an input got its rating: what the number means, then where it sits on the scale."""
    rating = interpolate(value, curve)
    return (
        f"{verdict(rating)}. {what_it_shows(metric, value)} {why_this_rating(metric, value, curve)}"
    )


def meaning_of(metric: str) -> str:
    if metric.startswith("industry_pct_"):
        return "Rank against stored peers with the same SEC industry code."
    text = MEANING.get(metric, "")
    return text[:1].upper() + text[1:] + "." if text else ""


def input_details(
    category: str,
    values: Mapping[str, float],
    stored_ratings: Mapping[str, float] | None = None,
) -> tuple[list[dict], list[str]]:
    """Inputs of a category with value, rating, scale and explanation, plus missing labels.

    Works from metric values alone, so it can rebuild the breakdown of scores
    saved before breakdowns were stored.
    """
    _, subs = CATEGORY_RULES[category]
    details: list[dict] = []
    missing: list[str] = []
    for sub in subs:
        value = values.get(sub.metric)
        if value is None:
            missing.append(sub.label)
            continue
        current = round(interpolate(value, sub.curve), 3)
        rating = (stored_ratings or {}).get(sub.metric, current)
        text = format_value(sub.metric, value)
        if abs(rating - current) > 0.005:
            # Saved under different rules: keep the saved rating and say so.
            explanation = (
                f"{verdict(rating)}. {what_it_shows(sub.metric, value)} Rated under an earlier "
                "version of the scoring rules; recalculate the score to apply the current scale."
            )
        else:
            explanation = explain(sub.metric, value, sub.curve)
        details.append(
            {
                "metric": sub.metric,
                "label": sub.label,
                "value": value,
                "value_text": text,
                "rating": rating,
                "scale": describe_scale(sub.metric, sub.curve),
                "explanation": explanation,
                "meaning": meaning_of(sub.metric),
            }
        )
    return details, missing


def category_summary(inputs: list[dict]) -> str | None:
    if not inputs:
        return None
    best = max(inputs, key=lambda i: i["rating"])
    worst = min(inputs, key=lambda i: i["rating"])
    if best is worst or best["rating"] == worst["rating"]:
        return f"All inputs rate {round(best['rating'] * 100)}%."
    return (
        f"Strongest: {best['label']} ({best['value_text']}, "
        f"{round(best['rating'] * 100)}%). Weakest: {worst['label']} "
        f"({worst['value_text']}, {round(worst['rating'] * 100)}%)."
    )

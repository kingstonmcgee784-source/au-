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
        "Fewer than 4 scored stocks share this industry code. Scan more stocks from the "
        "same industry in the Screener."
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


def describe_scale(metric: str, curve: Curve) -> str:
    """Plain-language summary of a threshold table, e.g. 'Full marks at 10.0× or lower'."""
    points = sorted(curve)
    top = max(y for _, y in points)
    low = min(y for _, y in points)
    best = [x for x, y in points if y == top]
    worst = [x for x, y in points if y == low]
    fmt = lambda x: format_value(metric, x)  # noqa: E731

    def where(xs: list[float], is_top: bool) -> str:
        if len(xs) > 1:
            return f"between {fmt(xs[0])} and {fmt(xs[-1])}"
        x = xs[0]
        if x == points[0][0]:
            return f"at {fmt(x)} or lower"
        if x == points[-1][0]:
            return f"at {fmt(x)} or higher"
        return f"at {fmt(x)}"

    full = "Full marks" if top == 1.0 else f"Best ({top * 100:.0f}%)"
    if UNITS.get(metric) == "yesno":
        answer = "Yes" if points[-1][1] == top else "No"
        return f"{full} for {answer}, {low * 100:.0f}% otherwise"
    bottom = "zero" if low == 0.0 else f"lowest ({low * 100:.0f}%)"
    return f"{full} {where(best, True)}; {bottom} {where(worst, False)}"


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


def explain(metric: str, value_text: str, rating: float) -> str:
    """One sentence on what an input says about the stock."""
    if metric.startswith("industry_pct_"):
        meaning = "rank against peers with the same SEC industry code"
    else:
        meaning = MEANING.get(metric, "input to this category")
    return f"{verdict(rating)} ({value_text}). What it measures: {meaning}."


def input_details(category: str, values: Mapping[str, float]) -> tuple[list[dict], list[str]]:
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
        rating = round(interpolate(value, sub.curve), 3)
        text = format_value(sub.metric, value)
        details.append(
            {
                "metric": sub.metric,
                "label": sub.label,
                "value": value,
                "value_text": text,
                "rating": rating,
                "scale": describe_scale(sub.metric, sub.curve),
                "explanation": explain(sub.metric, text, rating),
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

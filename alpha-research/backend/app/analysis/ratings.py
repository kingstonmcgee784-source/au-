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

from collections.abc import Sequence
from dataclasses import dataclass

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
            SubRating("operating_margin", ((-0.10, 0.0), (0.0, 0.3), (0.25, 1.0)), "Operating margin"),
            SubRating("fcf_margin", ((-0.10, 0.0), (0.0, 0.3), (0.20, 1.0)), "Free cash flow margin"),
            SubRating("roe", ((0.0, 0.0), (0.25, 1.0)), "Return on equity"),
            SubRating("current_ratio", ((0.8, 0.0), (1.2, 0.5), (2.0, 1.0)), "Current ratio"),
            SubRating("debt_to_equity", ((0.0, 1.0), (1.0, 0.5), (2.5, 0.0)), "Debt to equity"),
            SubRating("share_change_yoy", ((-0.02, 1.0), (0.0, 0.9), (0.05, 0.4), (0.10, 0.0)), "Share dilution"),
        ),
    ),
    "valuation": (
        2,
        (
            SubRating("pe_ttm", ((10, 1.0), (20, 0.7), (35, 0.35), (60, 0.0)), "P/E (TTM)"),
            SubRating("ev_to_ebitda", ((8, 1.0), (15, 0.6), (30, 0.2), (50, 0.0)), "EV/EBITDA"),
            SubRating("price_to_sales", ((1, 1.0), (4, 0.6), (10, 0.25), (20, 0.0)), "Price/sales"),
            SubRating("fcf_yield", ((-0.02, 0.0), (0.0, 0.2), (0.04, 0.6), (0.08, 1.0)), "FCF yield"),
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
            SubRating("rsi_14", ((25, 0.2), (45, 0.7), (55, 1.0), (68, 1.0), (80, 0.4)), "RSI (14)"),
            SubRating("relative_strength_6m", ((-0.25, 0.0), (0.0, 0.5), (0.25, 1.0)), "6-month return vs S&P 500"),
        ),
    ),
    "growth": (
        2,
        (
            SubRating("revenue_growth_yoy", ((-0.10, 0.0), (0.0, 0.25), (0.30, 1.0)), "Revenue growth (latest quarter)"),
            SubRating("revenue_growth_ttm", ((-0.10, 0.0), (0.0, 0.25), (0.30, 1.0)), "Revenue growth (TTM)"),
            SubRating("net_income_growth_ttm", ((-0.20, 0.0), (0.0, 0.3), (0.40, 1.0)), "Net income growth (TTM)"),
            SubRating("revenue_acceleration", ((-0.10, 0.0), (0.0, 0.5), (0.10, 1.0)), "Revenue growth acceleration"),
        ),
    ),
    "risk_reward": (
        2,
        (
            SubRating("volatility_1y", ((0.20, 1.0), (0.40, 0.6), (0.80, 0.0)), "Volatility (1 year)"),
            SubRating("max_drawdown_1y", ((-0.60, 0.0), (-0.30, 0.5), (-0.10, 1.0)), "Max drawdown (1 year)"),
            SubRating("from_52w_high", ((-0.50, 0.3), (-0.20, 0.8), (-0.05, 0.6), (0.0, 0.4)), "Distance from 52-week high"),
        ),
    ),
    # Insider (Form 4) activity only: 13F institutional holdings are not
    # connected. Open-market buying is the strongest signal; selling outside
    # a pre-arranged 10b5-1 plan, relative to company size, counts against.
    "institutional": (
        1,
        (
            SubRating("insider_buyers", ((0, 0.5), (1, 0.75), (3, 1.0)), "Insider open-market buyers (180 days)"),
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
            SubRating("catalyst_red_flags_365d", ((0, 0.8), (1, 0.3), (2, 0.0)), "Red-flag filings (12 months)"),
            SubRating(
                "catalyst_material_events_180d",
                ((0, 0.5), (1, 0.7), (3, 0.9)),
                "Material agreements and acquisitions (6 months)",
            ),
            SubRating(
                "catalyst_earnings_within_90d", ((0, 0.4), (1, 0.7)), "Earnings release expected within 90 days"
            ),
        ),
    ),
    # No data source yet: always unrated.
    "industry": (1, ()),
}

UNRATED_REASON = {
    "catalysts": "SEC 8-K events have not been loaded for this stock.",
    "institutional": "Insider (Form 4) filings have not been loaded, and no 13F data is connected.",
    "industry": "No industry classification or peer data is connected.",
}


@dataclass(frozen=True)
class CategoryRating:
    rating: float | None
    used: dict[str, float]  # sub-rating label -> rating, for the inputs that had data


def rate(metrics: Metrics) -> dict[str, CategoryRating]:
    out: dict[str, CategoryRating] = {}
    for key, (minimum, subs) in CATEGORY_RULES.items():
        used = {
            sub.label: round(interpolate(value, sub.curve), 3)
            for sub in subs
            if (value := metrics.get(sub.metric)) is not None
        }
        rating = sum(used.values()) / len(used) if subs and len(used) >= minimum else None
        out[key] = CategoryRating(rating=rating, used=used)
    return out


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

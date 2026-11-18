"""A rules-based holding plan for a 1-3 month hold. Pure functions, no I/O.

This is guidance built from fixed rules, not a forecast:
  - Stop-loss: 2.5 times the stock's average daily range (ATR, 14 days)
    below the latest close, kept between 5% and 20%. Jumpy stocks get more
    room, steady ones less, so normal day-to-day noise does not trigger it.
  - Target: twice the stop distance above the close (2-to-1 reward to risk).
  - Typical 3-month move: one standard deviation of daily returns over the
    last year, scaled to 63 trading days. About two times in three, a
    3-month move has stayed within this range.
  - Fit checks: short holds depend mostly on the price trend, so the checks
    are trend and momentum checks.

Prices are adjusted for splits and dividends, so a split does not look like a
crash.
"""

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from app.analysis import sector, technical

HOLD_DAYS = 91  # about 3 months
CHECK_IN_DAYS = 30  # about 1 month
ATR_PERIOD = 14
STOP_ATR_MULTIPLE = 2.5
STOP_MIN = 0.05
STOP_MAX = 0.20
REWARD_TO_RISK = 2.0
TRADING_DAYS_3M = 63
EARNINGS_WARNING_DAYS = 14
# Categories that describe the business rather than the price trend.
BUSINESS_CATEGORIES = ("fundamentals", "valuation", "growth")
TREND_CATEGORIES = ("technical", "risk_reward")
# Shortest history for the 50-day average and a year of volatility.
MIN_BARS = 60


@dataclass(frozen=True)
class PriceBar:
    date: date
    high: float
    low: float
    close: float
    adjusted_close: float | None


@dataclass(frozen=True)
class Check:
    label: str
    passed: bool
    detail: str


def _adjusted(bars: Sequence[PriceBar]) -> tuple[list[float], list[float], list[float]]:
    """High, low and close series scaled by each day's adjustment factor."""
    highs, lows, closes = [], [], []
    for bar in bars:
        factor = (bar.adjusted_close / bar.close) if bar.adjusted_close and bar.close else 1.0
        highs.append(bar.high * factor)
        lows.append(bar.low * factor)
        closes.append(bar.close * factor)
    return highs, lows, closes


def atr(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int
) -> float | None:
    """Wilder's average true range for the latest bar."""
    if len(closes) <= period:
        return None
    ranges = [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(1, len(closes))
    ]
    value = sum(ranges[:period]) / period
    for r in ranges[period:]:
        value = (value * (period - 1) + r) / period
    return value


def typical_move(closes: Sequence[float], days: int = TRADING_DAYS_3M) -> float | None:
    returns = [closes[i] / closes[i - 1] - 1 for i in range(max(1, len(closes) - 252), len(closes))]
    if len(returns) < 20:
        return None
    return statistics.stdev(returns) * math.sqrt(days)


def fit_checks(closes: Sequence[float], relative_strength_6m: float | None) -> list[Check]:
    price = closes[-1]
    sma50 = technical.sma(closes, 50)[-1]
    sma200 = technical.sma(closes, 200)[-1] if len(closes) >= 200 else None
    rsi = technical.rsi(closes, 14)[-1]
    checks: list[Check] = []
    if sma50 is not None:
        checks.append(
            Check(
                "Price above its 50-day average",
                price > sma50,
                f"Price {price:,.2f} vs 50-day average {sma50:,.2f} "
                f"({(price / sma50 - 1) * 100:+.1f}%). Above it means the last few months' "
                "trend is up.",
            )
        )
    if sma50 is not None and sma200 is not None:
        checks.append(
            Check(
                "50-day average above 200-day average",
                sma50 > sma200,
                f"50-day {sma50:,.2f} vs 200-day {sma200:,.2f}. Above means the shorter "
                "trend is stronger than the longer one.",
            )
        )
    if rsi is not None:
        if rsi > 70:
            note = "above 70: it has risen fast and often pauses or pulls back."
        elif rsi < 40:
            note = "below 40: selling pressure has been stronger than buying."
        else:
            note = "between 40 and 70: not stretched in either direction."
        checks.append(
            Check("Momentum not stretched (RSI 40-70)", 40 <= rsi <= 70, f"RSI {rsi:.0f}, {note}")
        )
    if relative_strength_6m is not None:
        checks.append(
            Check(
                "Beat the S&P 500 over 6 months",
                relative_strength_6m > 0,
                f"{relative_strength_6m * 100:+.1f} points vs the S&P 500. Stocks that have "
                "led often keep leading for a few months.",
            )
        )
    return checks


def verdict(checks: Sequence[Check]) -> str:
    if not checks:
        return "unknown"
    share = sum(c.passed for c in checks) / len(checks)
    if share >= 0.75:
        return "good"
    if share >= 0.5:
        return "mixed"
    return "poor"


def score_driver(category_ratings: Mapping[str, float | None]) -> str | None:
    """A sentence on whether the score rests on the business or the trend."""
    business = [category_ratings.get(k) for k in BUSINESS_CATEGORIES]
    trend = [category_ratings.get(k) for k in TREND_CATEGORIES]
    business = [v for v in business if v is not None]
    trend = [v for v in trend if v is not None]
    if not business or not trend:
        return None
    b, t = sum(business) / len(business), sum(trend) / len(trend)
    if b - t >= 0.15:
        return (
            f"The score rests more on the business (rated {b:.0%}) than on the price trend "
            f"({t:.0%}). Business strength tends to pay off over years; over 1-3 months the "
            "trend matters more, so this may need longer than you plan to hold."
        )
    if t - b >= 0.15:
        return (
            f"The score rests more on the price trend (rated {t:.0%}) than on the business "
            f"({b:.0%}). That suits a 1-3 month hold, but trends can turn quickly, so follow "
            "the stop-loss."
        )
    return (
        f"The business (rated {b:.0%}) and the price trend ({t:.0%}) score about the same, "
        "so the score is not leaning on one side."
    )


def stop_and_target(bars: Sequence[PriceBar]) -> tuple[float, float] | None:
    """(stop_pct, target_pct), e.g. (-0.08, 0.16), or None with too little history."""
    if len(bars) < MIN_BARS:
        return None
    highs, lows, closes = _adjusted(bars)
    range_ = atr(highs, lows, closes, ATR_PERIOD)
    if range_ is None or closes[-1] <= 0:
        return None
    stop = min(max(STOP_ATR_MULTIPLE * range_ / closes[-1], STOP_MIN), STOP_MAX)
    return -stop, REWARD_TO_RISK * stop


def build_plan(
    bars: Sequence[PriceBar],
    *,
    today: date,
    category_ratings: Mapping[str, float | None],
    relative_strength_6m: float | None,
    next_earnings: date | None,
    trends: Sequence[sector.Trend] = (),
    market_level: str | None = None,
    market_warning: str | None = None,
) -> dict[str, object] | None:
    """The plan from bars sorted oldest first, or None with too little history."""
    if len(bars) < MIN_BARS:
        return None
    levels = stop_and_target(bars)
    if levels is None:
        return None
    highs, lows, closes = _adjusted(bars)
    price = closes[-1]
    raw_price = bars[-1].close
    range_ = atr(highs, lows, closes, ATR_PERIOD) or 0.0
    stop_pct, target_pct = -levels[0], levels[1]
    sma50 = technical.sma(closes, 50)[-1]
    checks = fit_checks(closes, relative_strength_6m)
    for t in trends:
        what = "Oil price" if t.kind == "oil" else t.label
        relative = (
            f" The stock did {t.stock_vs_1m * 100:+.1f} points vs it over the last month."
            if t.stock_vs_1m is not None
            else ""
        )
        checks.append(
            Check(
                f"{what} trending up",
                t.direction == "up",
                f"{t.label}: {sector.describe(t)}{relative}",
            )
        )

    if market_level in ("calm", "caution", "stress"):
        checks.append(
            Check(
                "Whole market not under stress",
                market_level != "stress",
                {
                    "calm": "Market gauges are calm: trend, fear, interest rates and credit.",
                    "caution": "Market gauges call for caution, but not stress.",
                    "stress": "Two or more market gauges show stress.",
                }[market_level],
            )
        )

    warnings: list[str] = ([market_warning] if market_warning else []) + sector.warnings(trends)
    ends = today + timedelta(days=HOLD_DAYS)
    if next_earnings and today <= next_earnings <= ends:
        days = (next_earnings - today).days
        warnings.append(
            f"Earnings are expected around {next_earnings.isoformat()} ({days} days away), "
            "inside your hold. Prices often jump 5-10% either way on earnings; decide "
            "beforehand whether to hold through it."
            if days > EARNINGS_WARNING_DAYS
            else f"Earnings are expected around {next_earnings.isoformat()}, only {days} days "
            "away. Buying right before earnings is closer to a coin flip than a plan; "
            "consider waiting until after the report."
        )
    move = typical_move(closes)
    if move is not None and target_pct > 1.5 * move:
        warnings.append(
            f"The target (+{target_pct:.0%}) is well above this stock's typical 3-month move "
            f"(about ±{move:.0%}), so it is unlikely to be reached in 3 months. Plan to exit "
            "at the time limit or on the trailing rule instead."
        )

    # Price levels are shown in today's (unadjusted) price terms.
    return {
        "as_of": bars[-1].date,
        "price": raw_price,
        "atr": range_ * raw_price / price,
        "stop_pct": -stop_pct,
        "stop_price": raw_price * (1 - stop_pct),
        "target_pct": target_pct,
        "target_price": raw_price * (1 + target_pct),
        "typical_move_3m": move,
        "sma_50": sma50 * raw_price / price if sma50 is not None else None,
        "check_in_on": today + timedelta(days=CHECK_IN_DAYS),
        "ends_on": ends,
        "next_earnings": next_earnings,
        "fit": verdict(checks),
        "checks": checks,
        "driver": score_driver(category_ratings),
        "warnings": warnings,
        "context": list(trends),
    }


def plan_status(
    reference_date: date,
    stop_pct: float | None,
    target_pct: float | None,
    horizon_days: int,
    closes_after: Sequence[tuple[date, float]],
    reference_price: float,
    today: date,
) -> tuple[str, date | None]:
    """Where a tracked call stands against its plan.

    Uses closing prices after the call (sorted oldest first), relative to the
    reference price. Returns (status, date): "stop_hit" or "target_hit" with
    the first close that reached it, "time_up" with the end date, "open" with
    the end date, or "no_plan".
    """
    if stop_pct is None or target_pct is None:
        return "no_plan", None
    ends = reference_date + timedelta(days=horizon_days)
    for day, close in closes_after:
        if day > ends:
            break
        change = close / reference_price - 1
        if change <= stop_pct:
            return "stop_hit", day
        if change >= target_pct:
            return "target_hit", day
    if today >= ends:
        return "time_up", ends
    return "open", ends

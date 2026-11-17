"""Performance of recorded calls, from stored daily prices. Pure functions.

Returns use adjusted closes, so dividends and splits are included. A horizon
(for example one month) is measured at the first trading day on or after the
reference date plus that many calendar days. If that day has not happened yet
in the stored prices, the result is None ("pending"), never a partial number.
"""

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

HORIZONS: dict[str, int] = {"1w": 7, "1m": 30, "3m": 91}


@dataclass(frozen=True)
class Bar:
    date: date
    close: float


def price_on_or_after(series: Sequence[Bar], day: date) -> Bar | None:
    return next((bar for bar in series if bar.date >= day), None)


def price_on_or_before(series: Sequence[Bar], day: date) -> Bar | None:
    earlier = [bar for bar in series if bar.date <= day]
    return earlier[-1] if earlier else None


def call_performance(
    reference_date: date,
    reference_price: float,
    series: Sequence[Bar],
    benchmarks: Mapping[str, Sequence[Bar]],
) -> dict[str, float | None]:
    """Returns since a call, at each horizon and now, with benchmark comparisons.

    `series` and each benchmark series are daily bars sorted oldest first.
    """
    out: dict[str, float | None] = {}
    after = [bar for bar in series if bar.date > reference_date]
    latest = after[-1] if after else None
    out["current_price"] = latest.close if latest else None
    out["return_now"] = latest.close / reference_price - 1 if latest else None
    out["days_tracked"] = float((latest.date - reference_date).days) if latest else 0.0
    out["max_gain"] = max(b.close for b in after) / reference_price - 1 if after else None
    out["max_drawdown"] = min(b.close for b in after) / reference_price - 1 if after else None

    windows: dict[str, date | None] = {"now": latest.date if latest else None}
    for name, days in HORIZONS.items():
        bar = price_on_or_after(after, reference_date + timedelta(days=days))
        out[f"return_{name}"] = bar.close / reference_price - 1 if bar else None
        windows[name] = bar.date if bar else None

    for symbol, bench in benchmarks.items():
        start = price_on_or_before(bench, reference_date)
        for name, end_day in windows.items():
            key = f"{symbol.lower()}_return_{name}"
            end = price_on_or_before(bench, end_day) if end_day else None
            bench_return = end.close / start.close - 1 if start and end and start.close else None
            out[key] = bench_return
            own = out.get(f"return_{name}")
            out[f"excess_vs_{symbol.lower()}_{name}"] = (
                own - bench_return if own is not None and bench_return is not None else None
            )
    return out


def summary(values: Sequence[float], excess: Sequence[float]) -> dict[str, float | None]:
    """Track-record statistics for one horizon. Empty input gives Nones and a zero count."""
    gains = [v for v in values if v > 0]
    losses = [v for v in values if v <= 0]
    return {
        "count": float(len(values)),
        "average": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "win_rate": len(gains) / len(values) if values else None,
        "average_gain": statistics.fmean(gains) if gains else None,
        "average_loss": statistics.fmean(losses) if losses else None,
        "worst": min(values) if values else None,
        "best": max(values) if values else None,
        "average_excess_vs_spy": statistics.fmean(excess) if excess else None,
        "beat_spy_rate": sum(1 for e in excess if e > 0) / len(excess) if excess else None,
    }

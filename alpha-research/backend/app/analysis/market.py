"""Market-wide stress gauges from daily ETF prices. Pure functions, no I/O.

The free market-data plan has no index (VIX) or interest-rate series, so each
gauge uses an ETF that follows one:

  - Trend:  SPY (the S&P 500) against its 50- and 200-day averages.
  - Fear:   VIXY, which holds VIX futures. Its level drifts down over time,
            so only its jump against its own 50-day average is used.
  - Rates:  TLT, 20+ year Treasury bonds. Bond prices fall when long-term
            interest rates rise, so a fast drop in TLT means rates jumping.
  - Credit: HYG (high-yield "junk" bonds) against IEF (7-10 year Treasuries).
            Junk bonds lagging safe bonds is an early sign of credit stress.

Each gauge is "calm", "caution" or "stress". Two or more stressed gauges
mean the whole market is under stress; one stressed or two in caution, that
it calls for caution.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.analysis import technical

SYMBOLS = ("SPY", "VIXY", "TLT", "HYG", "IEF")
ONE_MONTH = 21  # trading days

# Thresholds
FEAR_CAUTION = 0.15  # VIXY this far above its 50-day average
FEAR_STRESS = 0.35
RATES_CAUTION = -0.03  # TLT 1-month change
RATES_STRESS = -0.06
CREDIT_CAUTION = -0.01  # HYG/IEF ratio vs its 50-day average
CREDIT_STRESS = -0.025


@dataclass(frozen=True)
class Gauge:
    key: str
    label: str
    # calm | caution | stress
    level: str
    value: float
    summary: str


def _sma(closes: Sequence[float], period: int) -> float | None:
    return technical.sma(closes, period)[-1] if len(closes) >= period else None


def _month(closes: Sequence[float]) -> float | None:
    return closes[-1] / closes[-1 - ONE_MONTH] - 1 if len(closes) > ONE_MONTH else None


def trend(spy: Sequence[float]) -> Gauge | None:
    sma50, sma200 = _sma(spy, 50), _sma(spy, 200)
    if sma50 is None:
        return None
    vs50 = spy[-1] / sma50 - 1
    below200 = sma200 is not None and spy[-1] < sma200
    if below200:
        level, text = "stress", " and below its 200-day average: a market downtrend"
    elif vs50 < 0:
        level, text = "caution", " but still above its 200-day average: a pullback"
    else:
        level, text = "calm", ": an uptrend"
    return Gauge(
        "trend",
        "Market trend (S&P 500)",
        level,
        vs50,
        f"The S&P 500 is {abs(vs50) * 100:.1f}% {'above' if vs50 >= 0 else 'below'} its "
        f"50-day average{text}.",
    )


def fear(vixy: Sequence[float]) -> Gauge | None:
    sma50 = _sma(vixy, 50)
    if sma50 is None:
        return None
    jump = vixy[-1] / sma50 - 1
    if jump >= FEAR_STRESS:
        level, text = "stress", "fear has spiked; investors are paying up for protection"
    elif jump >= FEAR_CAUTION:
        level, text = "caution", "fear is rising"
    else:
        level, text = "calm", "fear is normal"
    return Gauge(
        "fear",
        "Fear (VIX futures, VIXY)",
        level,
        jump,
        f"VIXY is {abs(jump) * 100:.0f}% {'above' if jump >= 0 else 'below'} its 50-day "
        f"average: {text}.",
    )


def rates(tlt: Sequence[float]) -> Gauge | None:
    change = _month(tlt)
    if change is None:
        return None
    if change <= RATES_STRESS:
        level, text = "stress", "long-term interest rates are jumping, which pressures stock prices"
    elif change <= RATES_CAUTION:
        level, text = "caution", "long-term interest rates are rising"
    else:
        level, text = "calm", "long-term interest rates are steady or falling"
    return Gauge(
        "rates",
        "Long-term interest rates (TLT)",
        level,
        change,
        f"Long-term Treasury bonds (TLT) moved {change * 100:+.1f}% in a month: {text}.",
    )


def credit(hyg: Sequence[float], ief: Sequence[float]) -> Gauge | None:
    n = min(len(hyg), len(ief))
    if n < 50:
        return None
    ratio = [h / i for h, i in zip(hyg[-n:], ief[-n:], strict=True)]
    gap = ratio[-1] / (_sma(ratio, 50) or ratio[-1]) - 1
    if gap <= CREDIT_STRESS:
        level, text = "stress", "lenders are pulling back from risky companies"
    elif gap <= CREDIT_CAUTION:
        level, text = "caution", "riskier borrowers are falling out of favor"
    else:
        level, text = "calm", "credit markets are calm"
    return Gauge(
        "credit",
        "Credit (junk vs Treasury bonds)",
        level,
        gap,
        f"Junk bonds (HYG) are {abs(gap) * 100:.1f}% {'ahead of' if gap >= 0 else 'behind'} "
        f"safe Treasuries (IEF) against their 50-day average: {text}.",
    )


def gauges(closes: Mapping[str, Sequence[float]]) -> list[Gauge]:
    """All gauges that have enough data, from closes sorted oldest first."""
    out = [
        trend(closes.get("SPY", [])),
        fear(closes.get("VIXY", [])),
        rates(closes.get("TLT", [])),
        credit(closes.get("HYG", []), closes.get("IEF", [])),
    ]
    return [g for g in out if g is not None]


def overall(found: Sequence[Gauge]) -> str:
    """calm | caution | stress | unknown."""
    if not found:
        return "unknown"
    stressed = sum(g.level == "stress" for g in found)
    cautious = sum(g.level == "caution" for g in found)
    if stressed >= 2:
        return "stress"
    if stressed == 1 or cautious >= 2:
        return "caution"
    return "calm"


def warning(level: str, found: Sequence[Gauge]) -> str | None:
    if level != "stress":
        return None
    reasons = " ".join(g.summary for g in found if g.level == "stress")
    return (
        f"The whole market is under stress. {reasons} When the market is stressed, most "
        "stocks fall together, whatever their own score; consider smaller positions and "
        "keep to stop-losses."
    )

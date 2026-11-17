"""Sector and commodity context for a stock. Pure functions, no I/O.

Each stock is matched, by its SEC industry (SIC) code, to the SPDR sector ETF
that holds its kind of company, and oil and gas companies also to an oil ETF
(USO, which follows crude oil futures). The ETFs' stored daily prices show
whether the stock's sector, or oil, is trending up or down right now, which a
company's quarterly reports can only show months later.

The longest matching code prefix wins, so "2834" (drugs) is health care even
though "28" (chemicals) is materials.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.analysis import technical

OIL = ("USO", "Crude oil (USO)")

# SIC prefix -> (ETF, what it tracks)
SECTOR_ETFS: dict[str, tuple[str, str]] = {
    # Energy
    "13": ("XLE", "Energy stocks (XLE)"),
    "29": ("XLE", "Energy stocks (XLE)"),
    "4612": ("XLE", "Energy stocks (XLE)"),
    "4922": ("XLE", "Energy stocks (XLE)"),
    # Technology
    "357": ("XLK", "Technology stocks (XLK)"),
    "366": ("XLK", "Technology stocks (XLK)"),
    "367": ("XLK", "Technology stocks (XLK)"),
    "737": ("XLK", "Technology stocks (XLK)"),
    # Health care
    "283": ("XLV", "Health care stocks (XLV)"),
    "384": ("XLV", "Health care stocks (XLV)"),
    "385": ("XLV", "Health care stocks (XLV)"),
    "80": ("XLV", "Health care stocks (XLV)"),
    # Financials and real estate
    "60": ("XLF", "Financial stocks (XLF)"),
    "61": ("XLF", "Financial stocks (XLF)"),
    "62": ("XLF", "Financial stocks (XLF)"),
    "63": ("XLF", "Financial stocks (XLF)"),
    "64": ("XLF", "Financial stocks (XLF)"),
    "67": ("XLF", "Financial stocks (XLF)"),
    "6798": ("XLRE", "Real estate stocks (XLRE)"),
    # Utilities and communication
    "49": ("XLU", "Utility stocks (XLU)"),
    "48": ("XLC", "Communication stocks (XLC)"),
    "78": ("XLC", "Communication stocks (XLC)"),
    # Materials
    "10": ("XLB", "Materials stocks (XLB)"),
    "14": ("XLB", "Materials stocks (XLB)"),
    "26": ("XLB", "Materials stocks (XLB)"),
    "28": ("XLB", "Materials stocks (XLB)"),
    "33": ("XLB", "Materials stocks (XLB)"),
    # Consumer staples
    "20": ("XLP", "Consumer staples stocks (XLP)"),
    "21": ("XLP", "Consumer staples stocks (XLP)"),
    "2844": ("XLP", "Consumer staples stocks (XLP)"),
    "533": ("XLP", "Consumer staples stocks (XLP)"),
    "54": ("XLP", "Consumer staples stocks (XLP)"),
    # Consumer discretionary
    "15": ("XLY", "Consumer discretionary stocks (XLY)"),
    "23": ("XLY", "Consumer discretionary stocks (XLY)"),
    "25": ("XLY", "Consumer discretionary stocks (XLY)"),
    "371": ("XLY", "Consumer discretionary stocks (XLY)"),
    "52": ("XLY", "Consumer discretionary stocks (XLY)"),
    "53": ("XLY", "Consumer discretionary stocks (XLY)"),
    "56": ("XLY", "Consumer discretionary stocks (XLY)"),
    "57": ("XLY", "Consumer discretionary stocks (XLY)"),
    "58": ("XLY", "Consumer discretionary stocks (XLY)"),
    "59": ("XLY", "Consumer discretionary stocks (XLY)"),
    "70": ("XLY", "Consumer discretionary stocks (XLY)"),
    "79": ("XLY", "Consumer discretionary stocks (XLY)"),
    # Industrials
    "34": ("XLI", "Industrial stocks (XLI)"),
    "35": ("XLI", "Industrial stocks (XLI)"),
    "372": ("XLI", "Industrial stocks (XLI)"),
    "373": ("XLI", "Industrial stocks (XLI)"),
    "374": ("XLI", "Industrial stocks (XLI)"),
    "376": ("XLI", "Industrial stocks (XLI)"),
    "38": ("XLI", "Industrial stocks (XLI)"),
    "40": ("XLI", "Industrial stocks (XLI)"),
    "42": ("XLI", "Industrial stocks (XLI)"),
    "44": ("XLI", "Industrial stocks (XLI)"),
    "45": ("XLI", "Industrial stocks (XLI)"),
    "47": ("XLI", "Industrial stocks (XLI)"),
    "87": ("XLI", "Industrial stocks (XLI)"),
}
# Oil and gas producers, drillers, services and refiners move with crude oil.
OIL_PREFIXES = ("13", "29")

ONE_MONTH = 21  # trading days
THREE_MONTHS = 63
BIG_MONTHLY_MOVE = 0.15


def _match(sic: str, table: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    for length in range(len(sic), 1, -1):
        if sic[:length] in table:
            return table[sic[:length]]
    return None


def context_symbols(sic: str | None) -> list[tuple[str, str, str]]:
    """[(symbol, label, kind)] for a SIC code; kind is "sector" or "oil"."""
    if not sic:
        return []
    out: list[tuple[str, str, str]] = []
    sector = _match(sic, SECTOR_ETFS)
    if sector:
        out.append((*sector, "sector"))
    if sic.startswith(OIL_PREFIXES):
        out.append((*OIL, "oil"))
    return out


@dataclass(frozen=True)
class Trend:
    symbol: str
    label: str
    kind: str
    last: float
    sma_50: float
    vs_sma_50: float
    return_1m: float | None
    return_3m: float | None
    # up | down | mixed
    direction: str
    # The stock's 1-month return minus this ETF's, when both are known.
    stock_vs_1m: float | None


def _ret(closes: Sequence[float], days: int) -> float | None:
    return closes[-1] / closes[-1 - days] - 1 if len(closes) > days else None


def trend(
    symbol: str, label: str, kind: str, closes: Sequence[float], stock_closes: Sequence[float]
) -> Trend | None:
    """Trend of an ETF from closes sorted oldest first (None if under 50 days)."""
    sma = technical.sma(closes, 50)[-1] if len(closes) >= 50 else None
    if sma is None:
        return None
    last = closes[-1]
    r1 = _ret(closes, ONE_MONTH)
    vs = last / sma - 1
    if vs > 0 and (r1 is None or r1 >= 0):
        direction = "up"
    elif vs < 0 and (r1 is None or r1 < 0):
        direction = "down"
    else:
        direction = "mixed"
    stock_r1 = _ret(stock_closes, ONE_MONTH)
    return Trend(
        symbol=symbol,
        label=label,
        kind=kind,
        last=last,
        sma_50=sma,
        vs_sma_50=vs,
        return_1m=r1,
        return_3m=_ret(closes, THREE_MONTHS),
        direction=direction,
        stock_vs_1m=stock_r1 - r1 if stock_r1 is not None and r1 is not None else None,
    )


def describe(t: Trend) -> str:
    month = f", {t.return_1m * 100:+.1f}% in a month" if t.return_1m is not None else ""
    side = "above" if t.vs_sma_50 >= 0 else "below"
    return f"{abs(t.vs_sma_50) * 100:.1f}% {side} its 50-day average{month}."


def warnings(trends: Sequence[Trend]) -> list[str]:
    out: list[str] = []
    for t in trends:
        if t.kind == "oil":
            if t.direction == "down":
                out.append(
                    f"Oil is falling: USO is {describe(t)} An oil company's profits fall with "
                    "the oil price, and its stock usually follows within days or weeks. "
                    "Its last quarterly report does not show this yet."
                )
            if t.return_1m is not None and abs(t.return_1m) >= BIG_MONTHLY_MOVE:
                out.append(
                    f"Oil has moved {t.return_1m * 100:+.0f}% in a month, which is unusually "
                    "large. Expect bigger day-to-day swings in this stock than its history "
                    "suggests, and keep to the stop-loss."
                )
        elif t.direction == "down":
            out.append(
                f"Its sector is in a downtrend: {t.label} is {describe(t)} Stocks usually have "
                "a harder time rising while their whole sector is falling."
            )
    return out

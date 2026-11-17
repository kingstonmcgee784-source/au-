"""Compare a stock with its industry peers. Pure functions.

Peers are the other stocks in the local database with the same SEC industry
code (SIC). If there are too few, the group widens to the first three digits
of the code, then the first two (the SEC "major group"). So the comparison is
only as broad as the stocks you have scanned, which the results always state.

Each metric becomes a percentile: the share of peers this stock beats (ties
count half), so 1.0 means best in the group and 0.5 means middle.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

MIN_PEERS = 4

# metric -> True when a higher value is better
POSITIONING: dict[str, bool] = {
    "revenue_growth_ttm": True,
    "operating_margin": True,
    "fcf_margin": True,
    "roe": True,
    "return_6m": True,
}
VALUATION: dict[str, bool] = {
    "pe_ttm": False,
    "price_to_sales": False,
    "ev_to_sales": False,
    "fcf_yield": True,
}


@dataclass(frozen=True)
class PeerGroup:
    prefix: str  # the SIC digits shared by the group
    members: list[str]  # peer tickers, excluding the stock itself


def choose_group(sic: str | None, peers_by_ticker: Mapping[str, str | None]) -> PeerGroup | None:
    """The narrowest SIC group with at least MIN_PEERS other stocks."""
    if not sic:
        return None
    for digits in (4, 3, 2):
        prefix = sic[:digits]
        if len(prefix) < digits:
            continue
        members = [t for t, code in peers_by_ticker.items() if code and code.startswith(prefix)]
        if len(members) >= MIN_PEERS:
            return PeerGroup(prefix=prefix, members=sorted(members))
    return None


def percentile(value: float, others: Sequence[float], higher_is_better: bool) -> float:
    if not others:
        raise ValueError("percentile needs at least one peer value")
    beaten = sum(1 for o in others if (value > o if higher_is_better else value < o))
    ties = sum(1 for o in others if o == value)
    return (beaten + 0.5 * ties) / len(others)


def percentiles(
    target: Mapping[str, float | None],
    peers: Sequence[Mapping[str, float | None]],
    specs: Mapping[str, bool],
) -> dict[str, float | None]:
    """Percentile per metric. None when the stock or too few peers lack the metric."""
    out: dict[str, float | None] = {}
    for metric, higher in specs.items():
        value = target.get(metric)
        others = [v for p in peers if (v := p.get(metric)) is not None]
        out[metric] = (
            percentile(value, others, higher)
            if value is not None and len(others) >= MIN_PEERS
            else None
        )
    return out

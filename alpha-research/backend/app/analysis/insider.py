"""Summaries of insider (Form 4) activity. Pure functions, no I/O.

What counts:
  - Open-market purchases (code P): insiders spending their own money. The
    clearest positive signal, so the number of distinct buyers matters most.
  - Open-market sales (code S): split into sales under a pre-arranged Rule
    10b5-1 plan, which are scheduled in advance and say little, and other
    ("discretionary") sales.
  - Grants, option exercises, tax withholding and gifts are compensation or
    housekeeping, not trading decisions, so they are listed but not scored.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Trade:
    owner_name: str
    transaction_date: date
    code: str
    shares: float
    price: float | None
    under_10b5_1: bool | None

    @property
    def value(self) -> float | None:
        return self.shares * self.price if self.price is not None else None


def summarize(
    trades: Sequence[Trade], *, as_of: date, days: int, market_cap: float | None
) -> dict[str, float | None]:
    since = as_of - timedelta(days=days)
    recent = [t for t in trades if since < t.transaction_date <= as_of]
    buys = [t for t in recent if t.code == "P"]
    sales = [t for t in recent if t.code == "S"]
    discretionary_sales = [t for t in sales if t.under_10b5_1 is not True]

    def total(rows: list[Trade]) -> float:
        return float(sum(t.value or 0.0 for t in rows))

    buy_value = total(buys)
    sale_value = total(sales)
    discretionary_value = total(discretionary_sales)
    return {
        "insider_buyers": float(len({t.owner_name for t in buys})),
        "insider_buy_value": buy_value,
        "insider_sale_value": sale_value,
        "insider_planned_sale_value": sale_value - discretionary_value,
        "insider_discretionary_sale_value": discretionary_value,
        "insider_net_value": buy_value - sale_value,
        "insider_discretionary_sales_to_market_cap": (
            discretionary_value / market_cap if market_cap else None
        ),
    }

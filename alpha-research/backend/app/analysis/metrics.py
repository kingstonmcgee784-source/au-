"""Financial and price metrics calculated from stored data.

Pure functions, no I/O. Every metric is `None` when its inputs are missing
or not meaningful (for example P/E with negative earnings), never a guess.

Conventions:
  - Statements are passed as `Period` objects. Quarterly lists are ordered
    newest first.
  - TTM (trailing twelve months) sums the four most recent quarters, and only
    when they are four consecutive quarters.
  - Ratios are plain fractions (0.25 = 25%), except P/E style multiples.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.analysis import technical


@dataclass(frozen=True)
class Period:
    end: date
    items: dict[str, float | None]


@dataclass(frozen=True)
class PricePoint:
    date: date
    close: float


Metrics = dict[str, float | None]

TRADING_DAYS = 252


def compute_metrics(
    income: Sequence[Period],
    cashflow: Sequence[Period],
    balance: Sequence[Period],
    prices: Sequence[PricePoint],
    benchmark: Sequence[PricePoint] = (),
) -> Metrics:
    """All metrics for one stock. Lists of periods are quarterly, newest first."""
    m: Metrics = {}
    price = prices[-1].close if prices else None
    latest_balance = balance[0].items if balance else {}

    # -- Size and valuation ---------------------------------------------------
    shares = _first(latest_balance.get("shares_outstanding"), _latest(income, "diluted_shares"))
    market_cap = price * shares if price is not None and shares else None
    cash = _sum_known(
        latest_balance.get("cash_and_equivalents"), latest_balance.get("short_term_investments")
    )
    # Unknown debt is not assumed to be zero: debt-based metrics stay empty.
    debt = total_debt(latest_balance)
    enterprise_value = (
        market_cap + debt - (cash or 0.0) if market_cap is not None and debt is not None else None
    )
    m["price"] = price
    m["market_cap"] = market_cap
    m["enterprise_value"] = enterprise_value
    m["net_cash"] = cash - debt if cash is not None and debt is not None else None

    revenue = _ttm(income, "revenue")
    net_income = _ttm(income, "net_income")
    operating_income = _ttm(income, "operating_income")
    gross_profit = _ttm(income, "gross_profit")
    d_and_a = _ttm(cashflow, "depreciation_and_amortization")
    operating_cf = _ttm(cashflow, "operating_cash_flow")
    capex = _ttm(cashflow, "capital_expenditures")
    sbc = _ttm(cashflow, "share_based_compensation")
    free_cash_flow = (
        operating_cf - capex if operating_cf is not None and capex is not None else None
    )
    ebitda = (
        operating_income + d_and_a if operating_income is not None and d_and_a is not None else None
    )
    m["revenue_ttm"] = revenue
    m["net_income_ttm"] = net_income
    m["free_cash_flow_ttm"] = free_cash_flow
    m["ebitda_ttm"] = ebitda

    m["pe_ttm"] = _ratio(market_cap, net_income, positive_denominator=True)
    m["price_to_sales"] = _ratio(market_cap, revenue, positive_denominator=True)
    m["ev_to_sales"] = _ratio(enterprise_value, revenue, positive_denominator=True)
    m["ev_to_ebitda"] = _ratio(enterprise_value, ebitda, positive_denominator=True)
    m["price_to_book"] = _ratio(
        market_cap, latest_balance.get("stockholders_equity"), positive_denominator=True
    )
    m["fcf_yield"] = _ratio(free_cash_flow, market_cap, positive_denominator=True)

    # -- Profitability --------------------------------------------------------
    m["gross_margin"] = _ratio(gross_profit, revenue, positive_denominator=True)
    m["operating_margin"] = _ratio(operating_income, revenue, positive_denominator=True)
    m["net_margin"] = _ratio(net_income, revenue, positive_denominator=True)
    m["fcf_margin"] = _ratio(free_cash_flow, revenue, positive_denominator=True)
    m["roe"] = _ratio(
        net_income, latest_balance.get("stockholders_equity"), positive_denominator=True
    )
    m["sbc_to_revenue"] = _ratio(sbc, revenue, positive_denominator=True)

    # -- Balance sheet --------------------------------------------------------
    m["current_ratio"] = _ratio(
        latest_balance.get("current_assets"),
        latest_balance.get("current_liabilities"),
        positive_denominator=True,
    )
    m["debt_to_equity"] = _ratio(
        debt, latest_balance.get("stockholders_equity"), positive_denominator=True
    )
    m["share_change_yoy"] = _growth(
        latest_balance.get("shares_outstanding"), _year_ago(balance, "shares_outstanding")
    )

    # -- Growth ---------------------------------------------------------------
    m["revenue_growth_yoy"] = _growth(_latest(income, "revenue"), _year_ago(income, "revenue"))
    m["revenue_growth_ttm"] = _growth(revenue, _ttm(income, "revenue", offset=4))
    m["net_income_growth_ttm"] = _growth(
        net_income, _ttm(income, "net_income", offset=4), require_positive_base=True
    )
    previous_yoy = _growth(_value_at(income, 1, "revenue"), _value_at(income, 5, "revenue"))
    m["revenue_acceleration"] = (
        m["revenue_growth_yoy"] - previous_yoy
        if m["revenue_growth_yoy"] is not None and previous_yoy is not None
        else None
    )

    # -- Price behaviour ------------------------------------------------------
    m.update(price_metrics(prices, benchmark))
    return m


def price_metrics(prices: Sequence[PricePoint], benchmark: Sequence[PricePoint] = ()) -> Metrics:
    closes = [p.close for p in prices]
    m: Metrics = {}
    last = closes[-1] if closes else None
    sma50 = technical.sma(closes, 50)[-1] if len(closes) >= 50 else None
    sma200 = technical.sma(closes, 200)[-1] if len(closes) >= 200 else None
    m["sma_50"] = sma50
    m["sma_200"] = sma200
    m["price_vs_sma200"] = (last / sma200 - 1) if last is not None and sma200 else None
    m["sma50_above_sma200"] = (1.0 if sma50 > sma200 else 0.0) if sma50 and sma200 else None
    m["rsi_14"] = technical.rsi(closes, 14)[-1] if len(closes) > 14 else None
    m["return_3m"] = _period_return(closes, 63)
    m["return_6m"] = _period_return(closes, 126)
    bench_6m = _period_return([p.close for p in benchmark], 126)
    m["relative_strength_6m"] = (
        m["return_6m"] - bench_6m if m["return_6m"] is not None and bench_6m is not None else None
    )
    window = closes[-TRADING_DAYS:]
    m["volatility_1y"] = _annualized_volatility(window) if len(window) >= 60 else None
    m["max_drawdown_1y"] = _max_drawdown(window) if len(window) >= 60 else None
    m["from_52w_high"] = (
        (last / max(window) - 1) if last is not None and len(window) >= 200 else None
    )
    return m


def total_debt(balance: dict[str, float | None]) -> float | None:
    """All interest-bearing debt, including amounts due within a year.

    Uses the reported long-term total when there is one, otherwise the
    non-current and current parts; short-term borrowings are added either
    way. None when no long-term debt figure is reported at all.
    """
    reported_total = balance.get("total_long_term_debt")
    noncurrent = balance.get("long_term_debt")
    if reported_total is not None:
        long_term = reported_total
    elif noncurrent is not None:
        long_term = noncurrent + (balance.get("current_debt") or 0.0)
    else:
        return None
    return long_term + (balance.get("short_term_borrowings") or 0.0)


# -- helpers -------------------------------------------------------------------


def _consecutive(periods: Sequence[Period], start: int, count: int) -> bool:
    if len(periods) < start + count:
        return False
    chunk = periods[start : start + count]
    return all(70 <= (a.end - b.end).days <= 110 for a, b in zip(chunk, chunk[1:], strict=False))


def _ttm(periods: Sequence[Period], key: str, offset: int = 0) -> float | None:
    if not _consecutive(periods, offset, 4):
        return None
    values = [p.items.get(key) for p in periods[offset : offset + 4]]
    if any(v is None for v in values):
        return None
    return float(sum(v for v in values if v is not None))


def _latest(periods: Sequence[Period], key: str) -> float | None:
    return periods[0].items.get(key) if periods else None


def _value_at(periods: Sequence[Period], index: int, key: str) -> float | None:
    return periods[index].items.get(key) if len(periods) > index else None


def _year_ago(periods: Sequence[Period], key: str) -> float | None:
    """The value from the period about a year before the newest one."""
    if not periods:
        return None
    target = periods[0].end
    for period in periods[1:]:
        if 350 <= (target - period.end).days <= 380:
            return period.items.get(key)
    return None


def _ratio(
    numerator: float | None, denominator: float | None, *, positive_denominator: bool = False
) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    if positive_denominator and denominator < 0:
        return None
    return numerator / denominator


def _growth(
    current: float | None, prior: float | None, *, require_positive_base: bool = True
) -> float | None:
    """Fractional change. Undefined when the base is zero or negative."""
    if current is None or prior is None:
        return None
    if prior <= 0 if require_positive_base else prior == 0:
        return None
    return current / prior - 1


def _first(*values: float | None) -> float | None:
    return next((v for v in values if v is not None), None)


def _sum_known(*values: float | None) -> float | None:
    known = [v for v in values if v is not None]
    return float(sum(known)) if known else None


def _period_return(closes: Sequence[float], days: int) -> float | None:
    if len(closes) <= days or closes[-days - 1] <= 0:
        return None
    return closes[-1] / closes[-days - 1] - 1


def _annualized_volatility(closes: Sequence[float]) -> float | None:
    returns = [b / a - 1 for a, b in zip(closes, closes[1:], strict=False) if a > 0]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(TRADING_DAYS)


def _max_drawdown(closes: Sequence[float]) -> float:
    peak = closes[0]
    worst = 0.0
    for close in closes:
        peak = max(peak, close)
        worst = min(worst, close / peak - 1)
    return worst

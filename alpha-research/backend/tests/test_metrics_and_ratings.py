from datetime import date, timedelta

import pytest

from app.analysis import scoring
from app.analysis.metrics import Period, PricePoint, compute_metrics, price_metrics
from app.analysis.ratings import interpolate, rate, risk_class


def quarters(values: list[dict[str, float | None]], last_end: date = date(2026, 9, 30)) -> list[Period]:
    """Quarterly periods, newest first, about 91 days apart."""
    return [Period(end=last_end - timedelta(days=91 * i), items=v) for i, v in enumerate(values)]


def test_ttm_valuation_and_margins() -> None:
    income = quarters([{"revenue": 100, "net_income": 10, "operating_income": 20}] * 4)
    cashflow = quarters(
        [{"operating_cash_flow": 15, "capital_expenditures": 5, "depreciation_and_amortization": 5}]
        * 4
    )
    balance = quarters(
        [{"shares_outstanding": 10, "cash_and_equivalents": 50, "long_term_debt": 30,
          "stockholders_equity": 200, "current_assets": 300, "current_liabilities": 150}]
    )
    m = compute_metrics(income, cashflow, balance, [PricePoint(date(2026, 9, 30), 40.0)])

    assert m["market_cap"] == 400
    assert m["enterprise_value"] == 380  # 400 + 30 debt - 50 cash
    assert m["revenue_ttm"] == 400
    assert m["pe_ttm"] == pytest.approx(10)  # 400 / 40
    assert m["ev_to_ebitda"] == pytest.approx(380 / 100)  # EBITDA = 80 + 20
    assert m["fcf_yield"] == pytest.approx(40 / 400)
    assert m["operating_margin"] == pytest.approx(0.2)
    assert m["current_ratio"] == pytest.approx(2.0)
    assert m["debt_to_equity"] == pytest.approx(0.15)


def test_missing_inputs_give_none_not_zero() -> None:
    income = quarters([{"revenue": 100, "net_income": -10}] * 4)
    balance = quarters([{"shares_outstanding": 10, "stockholders_equity": 100}])
    m = compute_metrics(income, [], balance, [PricePoint(date(2026, 9, 30), 5.0)])
    assert m["pe_ttm"] is None  # negative earnings
    assert m["enterprise_value"] is None  # debt not reported: not assumed zero
    assert m["debt_to_equity"] is None
    assert m["free_cash_flow_ttm"] is None  # no cash flow statements


def test_ttm_needs_four_consecutive_quarters() -> None:
    income = [
        Period(date(2026, 9, 30), {"revenue": 1}),
        Period(date(2026, 6, 30), {"revenue": 1}),
        Period(date(2025, 12, 31), {"revenue": 1}),  # a quarter is missing
        Period(date(2025, 9, 30), {"revenue": 1}),
    ]
    assert compute_metrics(income, [], [], [])["revenue_ttm"] is None


def test_growth() -> None:
    revenue = [130, 120, 110, 105, 100, 95, 90, 85]
    income = quarters([{"revenue": r, "net_income": r / 10} for r in revenue])
    m = compute_metrics(income, [], [], [])
    assert m["revenue_growth_yoy"] == pytest.approx(130 / 100 - 1)
    assert m["revenue_growth_ttm"] == pytest.approx(465 / 370 - 1)
    assert m["revenue_acceleration"] == pytest.approx((130 / 100 - 1) - (120 / 95 - 1))


def test_growth_undefined_from_negative_base() -> None:
    income = quarters([{"revenue": 10, "net_income": 5}] * 4 + [{"revenue": 10, "net_income": -5}] * 4)
    assert compute_metrics(income, [], [], [])["net_income_growth_ttm"] is None


def test_price_metrics() -> None:
    start = date(2025, 1, 1)
    closes = [100 + i * 0.5 for i in range(260)]
    prices = [PricePoint(start + timedelta(days=i), c) for i, c in enumerate(closes)]
    bench = [PricePoint(start + timedelta(days=i), 100.0) for i in range(260)]
    m = price_metrics(prices, bench)
    assert m["sma50_above_sma200"] == 1.0
    assert m["price_vs_sma200"] is not None and m["price_vs_sma200"] > 0
    assert m["max_drawdown_1y"] == 0.0
    assert m["relative_strength_6m"] == pytest.approx(m["return_6m"])
    assert price_metrics(prices[:30])["sma_200"] is None


def test_interpolate() -> None:
    curve = ((0.0, 0.0), (10.0, 1.0))
    assert interpolate(-5, curve) == 0.0
    assert interpolate(5, curve) == pytest.approx(0.5)
    assert interpolate(50, curve) == 1.0


def test_categories_without_data_stay_unrated() -> None:
    ratings = rate({"operating_margin": 0.25, "fcf_margin": 0.2, "roe": 0.25})
    assert ratings["fundamentals"].rating == pytest.approx(1.0)
    assert ratings["valuation"].rating is None  # too few inputs
    assert ratings["catalysts"].rating is None  # no data source at all


def test_partial_score_scales_over_rated_weight() -> None:
    total, points, coverage = scoring.partial_score(
        {"fundamentals": 1.0, "valuation": 0.5, "catalysts": None}
    )
    assert points["fundamentals"] == 20 and points["valuation"] == 10
    assert points["catalysts"] is None and points["growth"] is None
    assert coverage == pytest.approx(0.4)
    assert total == pytest.approx(75.0)  # 30 of 40 available points

    with pytest.raises(ValueError):
        scoring.partial_score({"catalysts": None})


def test_risk_class() -> None:
    assert risk_class({"volatility_1y": 0.18, "market_cap": 5e9}) == "Low"
    assert risk_class({"volatility_1y": 0.45, "market_cap": 5e9}) == "Elevated"
    assert risk_class({"volatility_1y": 0.18, "market_cap": 1e8}) == "High"  # micro cap
    assert risk_class({"volatility_1y": 0.6, "market_cap": 5e9, "net_income_ttm": -1}) == "Speculative"
    assert risk_class({}) is None

"""Holding plan math and the plan on tracked calls."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analysis.holding import PriceBar, atr, build_plan, plan_status, verdict
from app.models import HistoricalPrice
from tests.test_performance import API_START, market, scored_stock  # noqa: F401

D0 = date(2026, 1, 1)


def wavy(count: int, swing: float, drift: float = 0.2) -> list[PriceBar]:
    """Bars rising by `drift` a day with a daily high-low range of 2*swing."""
    out = []
    for i in range(count):
        close = 100 + drift * i
        out.append(PriceBar(D0 + timedelta(days=i), close + swing, close - swing, close, None))
    return out


def test_atr_of_a_constant_range() -> None:
    bars = wavy(40, swing=1.0, drift=0.0)
    assert atr([b.high for b in bars], [b.low for b in bars], [b.close for b in bars], 14) == (
        pytest.approx(2.0)
    )


def test_stop_widens_with_volatility_and_is_clamped() -> None:
    today = D0 + timedelta(days=250)
    calm = build_plan(
        wavy(250, 0.2),
        today=today,
        category_ratings={},
        relative_strength_6m=None,
        next_earnings=None,
    )
    jumpy = build_plan(
        wavy(250, 3.0),
        today=today,
        category_ratings={},
        relative_strength_6m=None,
        next_earnings=None,
    )
    wild = build_plan(
        wavy(250, 20.0),
        today=today,
        category_ratings={},
        relative_strength_6m=None,
        next_earnings=None,
    )
    assert calm and jumpy and wild
    assert calm["stop_pct"] == pytest.approx(-0.05)  # floor
    assert -0.20 < jumpy["stop_pct"] < -0.05
    assert wild["stop_pct"] == pytest.approx(-0.20)  # cap
    # 2-to-1 reward to risk.
    assert jumpy["target_pct"] == pytest.approx(-2 * jumpy["stop_pct"])
    assert jumpy["ends_on"] == today + timedelta(days=91)


def test_split_does_not_look_like_a_crash() -> None:
    bars = wavy(250, 0.5)
    # A 2-for-1 split half way: raw prices halve, adjusted prices do not.
    split = [
        PriceBar(b.date, b.high / 2, b.low / 2, b.close / 2, b.close / 2)
        if i >= 125
        else PriceBar(b.date, b.high, b.low, b.close, b.close / 2)
        for i, b in enumerate(bars)
    ]
    plan = build_plan(
        split,
        today=bars[-1].date,
        category_ratings={},
        relative_strength_6m=None,
        next_earnings=None,
    )
    assert plan is not None
    assert plan["price"] == pytest.approx(bars[-1].close / 2)
    assert all(c.passed for c in plan["checks"] if "50-day average" in c.label)


def test_earnings_inside_the_hold_is_flagged() -> None:
    today = D0 + timedelta(days=250)
    plan = build_plan(
        wavy(250, 1.0),
        today=today,
        category_ratings={},
        relative_strength_6m=0.1,
        next_earnings=today + timedelta(days=5),
    )
    assert plan and any("only 5 days away" in w for w in plan["warnings"])


def test_score_driver_and_verdict() -> None:
    plan = build_plan(
        wavy(250, 1.0),
        today=D0 + timedelta(days=250),
        category_ratings={
            "fundamentals": 0.9,
            "valuation": 0.8,
            "growth": 0.9,
            "technical": 0.4,
            "risk_reward": 0.5,
        },
        relative_strength_6m=0.05,
        next_earnings=None,
    )
    assert plan and "rests more on the business" in str(plan["driver"])
    assert verdict([]) == "unknown"


def test_too_little_history() -> None:
    assert (
        build_plan(
            wavy(30, 1.0),
            today=D0,
            category_ratings={},
            relative_strength_6m=None,
            next_earnings=None,
        )
        is None
    )


def test_plan_status() -> None:
    closes = [(D0 + timedelta(days=i), p) for i, p in enumerate([101, 97, 94, 120], start=1)]
    assert plan_status(D0, -0.05, 0.10, 90, closes, 100, D0 + timedelta(days=4)) == (
        "stop_hit",
        D0 + timedelta(days=3),
    )
    assert plan_status(D0, -0.10, 0.10, 90, closes, 100, D0 + timedelta(days=4)) == (
        "target_hit",
        D0 + timedelta(days=4),
    )
    assert plan_status(D0, -0.50, 0.50, 90, closes, 100, D0 + timedelta(days=95)) == (
        "time_up",
        D0 + timedelta(days=90),
    )
    assert plan_status(D0, None, None, 90, closes, 100, D0)[0] == "no_plan"


# -- API ---------------------------------------------------------------------------


def test_plan_endpoint_and_tracked_call(
    client: TestClient,
    market,  # noqa: F811
    db: Session,
) -> None:
    stock = scored_stock(db, market)
    body = client.get("/api/v1/stocks/TEST/holding-plan").json()
    assert body["status"] == "ok"
    plan = body["data"]
    assert plan["stop_price"] < plan["price"] < plan["target_price"]
    assert plan["fit"] in {"good", "mixed", "poor"}
    assert plan["checks"]

    call = client.post("/api/v1/recommendations", json={"ticker": "TEST"}).json()["data"]
    assert call["stop_pct"] == pytest.approx(plan["stop_pct"])
    assert call["plan_status"] == "open"

    # The price falls through the stop the next day.
    db.add(
        HistoricalPrice(
            stock_id=stock.id,
            date=API_START + timedelta(days=250),
            open=1,
            high=1,
            low=1,
            close=call["reference_price"] * 0.5,
            volume=1,
            source="test",
        )
    )
    db.commit()
    tracked = client.get("/api/v1/recommendations").json()["calls"][0]
    assert tracked["plan_status"] == "stop_hit"


def test_plan_needs_stored_prices(client: TestClient) -> None:
    body = client.get("/api/v1/stocks/NOPE/holding-plan").json()
    assert body["status"] == "unavailable"


def test_older_calls_get_a_plan_from_call_date_prices(
    client: TestClient,
    market,  # noqa: F811
    db: Session,
) -> None:
    from sqlalchemy import update

    from app.models import Recommendation

    scored_stock(db, market)
    call = client.post("/api/v1/recommendations", json={"ticker": "TEST"}).json()["data"]
    db.execute(update(Recommendation).values(stop_pct=None, target_pct=None))
    db.commit()
    tracked = client.get("/api/v1/recommendations").json()["calls"][0]
    assert tracked["stop_pct"] == pytest.approx(call["stop_pct"])
    assert tracked["plan_status"] == "open"


# -- Sector and oil context -------------------------------------------------------


def test_context_symbols_by_industry_code() -> None:
    from app.analysis.sector import context_symbols

    assert [s for s, _, _ in context_symbols("1311")] == ["XLE", "USO"]  # oil producer
    assert [s for s, _, _ in context_symbols("2834")] == ["XLV"]  # drugs, not chemicals
    assert [s for s, _, _ in context_symbols("6798")] == ["XLRE"]  # REIT, not finance
    assert [s for s, _, _ in context_symbols("7372")] == ["XLK"]
    assert context_symbols(None) == [] and context_symbols("9999") == []


def test_falling_oil_is_a_failed_check_and_a_warning() -> None:
    from app.analysis.sector import trend

    oil = [100 - 0.3 * i for i in range(120)]  # steady fall
    stock = [b.close for b in wavy(250, 1.0)]
    t = trend("USO", "Crude oil (USO)", "oil", oil, stock)
    assert t is not None and t.direction == "down"
    plan = build_plan(
        wavy(250, 1.0),
        today=D0 + timedelta(days=250),
        category_ratings={},
        relative_strength_6m=None,
        next_earnings=None,
        trends=[t],
    )
    assert plan is not None
    oil_check = next(c for c in plan["checks"] if c.label == "Oil price trending up")
    assert not oil_check.passed
    assert any(w.startswith("Oil is falling") for w in plan["warnings"])


def test_plan_reports_missing_sector_prices(
    client: TestClient,
    market,  # noqa: F811
    db: Session,
) -> None:
    scored_stock(db, market)  # SIC 7372; the fake market has no XLK prices
    plan = client.get("/api/v1/stocks/TEST/holding-plan").json()["data"]
    assert plan["context_missing"] == ["XLK"]
    market.known["XLK"] = market.known["SPY"]
    scored_stock(db, market)
    plan = client.get("/api/v1/stocks/TEST/holding-plan").json()["data"]
    assert [c["symbol"] for c in plan["context"]] == ["XLK"]
    assert any(c["label"].startswith("Technology stocks") for c in plan["checks"])

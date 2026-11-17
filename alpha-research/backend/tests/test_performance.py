"""Performance math and the track-record API, with stored test prices."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.analysis.performance import Bar, call_performance, summary
from app.api.deps import market_data_provider
from app.main import app
from app.models import HistoricalPrice, Recommendation, Stock
from app.providers.base import ProviderError
from app.services.scoring_pipeline import score_stock
from tests.fakes import FakeProvider, bars
from tests.test_scoring_pipeline import FakeSec

START = date(2026, 1, 1)
# API tests need prices up to today, because calls are refused at stale prices.
API_START = date.today() - timedelta(days=249)


def series(closes: list[float], start: date = START) -> list[Bar]:
    return [Bar(start + timedelta(days=i), c) for i, c in enumerate(closes)]


def test_call_performance_horizons_and_excursions() -> None:
    stock = series([100, 95, 110] + [120] * 40)  # dips, then rises
    bench = series([50] * 3 + [55] * 40)
    p = call_performance(START, 100.0, stock, {"SPY": bench})
    assert p["return_now"] == pytest.approx(0.20)
    assert p["max_drawdown"] == pytest.approx(-0.05)
    assert p["max_gain"] == pytest.approx(0.20)
    assert p["return_1w"] == pytest.approx(0.20)
    assert p["return_1m"] == pytest.approx(0.20)
    assert p["return_3m"] is None  # 91 days have not passed in the data: pending
    assert p["spy_return_1w"] == pytest.approx(0.10)
    assert p["excess_vs_spy_1w"] == pytest.approx(0.10)
    assert p["excess_vs_spy_3m"] is None


def test_call_performance_without_later_prices() -> None:
    p = call_performance(START, 100.0, series([100]), {})
    assert p["return_now"] is None and p["days_tracked"] == 0.0


def test_summary_statistics() -> None:
    s = summary([0.10, -0.05, 0.20, 0.0], [0.05, -0.10, 0.08, -0.01])
    assert s["count"] == 4
    assert s["average"] == pytest.approx(0.0625)
    assert s["median"] == pytest.approx(0.05)
    assert s["win_rate"] == pytest.approx(0.5)
    assert s["average_gain"] == pytest.approx(0.15)
    assert s["average_loss"] == pytest.approx(-0.025)
    assert s["beat_spy_rate"] == pytest.approx(0.5)
    assert summary([], [])["average"] is None


# -- API ------------------------------------------------------------------------


@pytest.fixture
def market() -> Iterator[FakeProvider]:
    fake = FakeProvider({symbol: bars(API_START, 300, 100.0) for symbol in ("SPY", "QQQ", "IWM")})
    app.dependency_overrides[market_data_provider] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def scored_stock(db: Session, market: FakeProvider, days: int = 250) -> Stock:
    """A stock scored through the real pipeline (rising test prices, test SEC facts)."""
    market.known["TEST"] = bars(API_START, days, 50.0)
    result = score_stock(
        db, "TEST", market=market, fundamentals=FakeSec(), refresh=True, history_years=2
    )
    assert result.status == "ok", result.message
    return db.scalar(select(Stock).where(Stock.ticker == "TEST"))


def test_track_requires_a_score(client: TestClient, market: FakeProvider) -> None:
    body = client.post("/api/v1/recommendations", json={"ticker": "TEST"}).json()
    assert body["status"] == "unavailable"
    assert "Calculate a score" in body["message"]


def test_track_and_measure(client: TestClient, market: FakeProvider, db: Session) -> None:
    stock = scored_stock(db, market)
    created = client.post("/api/v1/recommendations", json={"ticker": "test", "thesis": "Cheap"})
    assert created.status_code == 201
    call = created.json()["data"]
    assert call["reference_price"] == 299.0  # last stored close
    assert call["score"] is not None and call["risk_class"] is not None
    assert call["performance"]["return_now"] is None  # no prices after the call yet

    # The same stock cannot be tracked twice from the same price date.
    assert client.post("/api/v1/recommendations", json={"ticker": "TEST"}).status_code == 409

    # Prices arrive later: +10% after a week.
    for i in range(250, 265):
        db.add(
            HistoricalPrice(
                stock_id=stock.id,
                date=API_START + timedelta(days=i),
                open=1,
                high=1,
                low=1,
                close=328.9,
                volume=1,
                source="test",
            )
        )
    db.commit()
    record = client.get("/api/v1/recommendations").json()
    perf = record["calls"][0]["performance"]
    assert perf["return_1w"] == pytest.approx(328.9 / 299 - 1)
    assert perf["return_1m"] is None
    assert perf["spy_return_1w"] is not None
    assert record["summary"]["1w"]["count"] == 1
    assert record["summary"]["1m"]["count"] == 0
    assert record["benchmarks_missing"] == []


def test_delete_only_within_24_hours(client: TestClient, market: FakeProvider, db: Session) -> None:
    scored_stock(db, market)
    call_id = client.post("/api/v1/recommendations", json={"ticker": "TEST"}).json()["data"]["id"]

    db.execute(
        update(Recommendation)
        .where(Recommendation.id == call_id)
        .values(created_at=datetime.now(UTC) - timedelta(days=2))
    )
    db.commit()
    refused = client.delete(f"/api/v1/recommendations/{call_id}")
    assert refused.status_code == 409
    assert "cannot be edited" in refused.json()["detail"]

    db.execute(update(Recommendation).values(created_at=datetime.now(UTC) - timedelta(hours=20)))
    db.commit()
    assert client.delete(f"/api/v1/recommendations/{call_id}").status_code == 204


def test_update_prices(client: TestClient, market: FakeProvider, db: Session) -> None:
    scored_stock(db, market)
    client.post("/api/v1/recommendations", json={"ticker": "TEST"})
    body = client.post("/api/v1/recommendations/update-prices").json()
    assert body["status"] == "ok"
    assert [r["ticker"] for r in body["data"]["results"]] == ["TEST", "SPY", "QQQ", "IWM"]


def test_track_refuses_a_stale_price(client: TestClient, market: FakeProvider, db: Session) -> None:
    scored_stock(db, market)
    market.fail_with = ProviderError("down")  # fresh prices cannot be loaded
    cutoff = date.today() - timedelta(days=30)
    db.execute(delete(HistoricalPrice).where(HistoricalPrice.date > cutoff))
    db.commit()
    body = client.post("/api/v1/recommendations", json={"ticker": "TEST"}).json()
    assert body["status"] == "unavailable"
    assert "days ago" in body["message"]

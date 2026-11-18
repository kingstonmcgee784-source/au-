"""Market-wide stress gauges."""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analysis import market
from app.api.deps import market_data_provider
from app.main import app
from app.providers.base import PriceBar
from tests.fakes import FakeProvider

START = date.today() - timedelta(days=299)


def series(values: list[float]) -> list[PriceBar]:
    return [
        PriceBar(
            date=START + timedelta(days=i),
            open=v,
            high=v,
            low=v,
            close=v,
            adjusted_close=v,
            volume=1,
        )
        for i, v in enumerate(values)
    ]


def flat(n: int = 300, v: float = 100.0) -> list[float]:
    return [v] * n


def test_calm_market() -> None:
    rising = [100 + 0.1 * i for i in range(300)]
    found = market.gauges(
        {"SPY": rising, "VIXY": flat(), "TLT": flat(), "HYG": flat(), "IEF": flat()}
    )
    assert [g.level for g in found] == ["calm"] * 4
    assert market.overall(found) == "calm"
    assert market.warning("calm", found) is None


def test_stressed_market() -> None:
    falling = [100 + 0.1 * i for i in range(240)] + [124 - 0.6 * i for i in range(60)]
    spike = flat(295, 20) + flat(5, 30)  # fear jumps 50%
    found = {
        g.key: g
        for g in market.gauges(
            {"SPY": falling, "VIXY": spike, "TLT": flat(), "HYG": flat(), "IEF": flat()}
        )
    }
    assert found["trend"].level == "stress"
    assert found["fear"].level == "stress"
    level = market.overall(list(found.values()))
    assert level == "stress"
    assert market.warning(level, list(found.values())).startswith(
        "The whole market is under stress"
    )


def test_rates_and_credit_gauges() -> None:
    tlt = flat(279) + [100 - 0.4 * i for i in range(21)]  # about -8% in a month
    hyg = flat(295) + flat(5, 96)  # junk bonds drop 4% while Treasuries hold
    found = {g.key: g.level for g in market.gauges({"TLT": tlt, "HYG": hyg, "IEF": flat()})}
    assert found == {"rates": "stress", "credit": "stress"}
    assert market.overall([]) == "unknown"


def test_conditions_endpoint_and_holding_plan(client: TestClient, db: Session) -> None:
    falling = [100 + 0.1 * i for i in range(240)] + [124 - 0.6 * i for i in range(60)]
    fake = FakeProvider(
        {
            "SPY": series(falling),
            "VIXY": series(flat(295, 20) + flat(5, 30)),
            "TLT": series(flat()),
            "HYG": series(flat()),
            "IEF": series(flat()),
        }
    )
    app.dependency_overrides[market_data_provider] = lambda: fake
    try:
        assert client.get("/api/v1/market/conditions").json()["status"] == "unavailable"
        body = client.post("/api/v1/market/conditions/refresh").json()
        assert body["status"] == "ok"
        assert body["data"]["level"] == "stress"
        assert {g["key"] for g in body["data"]["gauges"]} == {"trend", "fear", "rates", "credit"}
    finally:
        app.dependency_overrides.clear()

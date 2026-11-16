"""Market data flows with a fake provider: quotes, overview, profile and price sync."""

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import market_data_provider
from app.main import app
from app.models import HistoricalPrice, Stock
from app.providers.base import ProviderRateLimitError
from app.services.ingestion import sync_prices
from tests.fakes import FakeProvider, bars

TODAY = date(2026, 11, 16)


@pytest.fixture
def provider() -> Iterator[FakeProvider]:
    fake = FakeProvider(
        {
            "LIVN": bars(date(2026, 1, 1), 300),
            **{etf: bars(date(2026, 11, 1), 2) for etf in ("SPY", "QQQ", "IWM", "DIA")},
        }
    )
    app.dependency_overrides[market_data_provider] = lambda: fake
    yield fake
    app.dependency_overrides.pop(market_data_provider, None)


def test_quote_and_overview_from_provider(client: TestClient, provider: FakeProvider) -> None:
    quote = client.get("/api/v1/stocks/livn/quote").json()
    assert quote["status"] == "ok"
    assert quote["source"] == "fake"
    assert quote["data"]["feed"] == "fake feed"

    overview = client.get("/api/v1/market/overview").json()
    assert overview["status"] == "ok"
    assert [i["symbol"] for i in overview["data"]["indices"]] == ["SPY", "QQQ", "IWM", "DIA"]
    assert all("ETF" in i["name"] for i in overview["data"]["indices"])


def test_unknown_ticker_and_provider_errors(client: TestClient, provider: FakeProvider) -> None:
    assert client.get("/api/v1/stocks/ZZZZ/quote").json()["reason"] == "unknown_ticker"
    provider.fail_with = ProviderRateLimitError("limit reached")
    body = client.get("/api/v1/stocks/LIVN/quote").json()
    assert body["reason"] == "provider_error"
    assert body["message"] == "limit reached"


def test_profile_falls_back_to_provider(client: TestClient, provider: FakeProvider) -> None:
    body = client.get("/api/v1/stocks/LIVN").json()
    assert body["status"] == "ok"
    assert body["source"] == "fake"


def test_sync_then_technicals(client: TestClient, provider: FakeProvider, db: Session) -> None:
    synced = client.post("/api/v1/stocks/LIVN/sync-prices").json()
    assert synced["status"] == "ok"
    assert synced["data"]["bars_added"] > 0

    technicals = client.get("/api/v1/stocks/LIVN/technicals").json()
    assert technicals["status"] == "ok"
    assert technicals["source"] == "local_database"

    stored = db.scalars(select(HistoricalPrice)).all()
    assert {row.source for row in stored} == {"fake"}


def test_sync_is_incremental(provider: FakeProvider, db: Session) -> None:
    first = sync_prices(db, provider, "LIVN", history_years=2, today=date(2026, 6, 1))
    assert first.data is not None
    added_first = first.data.bars_added
    assert first.data.last_date == date(2026, 6, 1)

    second = sync_prices(db, provider, "LIVN", history_years=2, today=TODAY)
    assert second.data is not None
    # Only days after the newest stored bar are requested and stored.
    assert provider.price_requests[-1][1] == date(2026, 6, 2)
    assert second.data.bars_stored == added_first + second.data.bars_added

    again = sync_prices(db, provider, "LIVN", history_years=2, today=TODAY)
    assert again.data is not None and again.data.bars_added == 0
    assert db.scalar(select(Stock).where(Stock.ticker == "LIVN")).name == "LIVN Test Co"


def test_sync_failure_stores_nothing(provider: FakeProvider, db: Session) -> None:
    result = sync_prices(db, provider, "ZZZZ", history_years=2, today=TODAY)
    assert result.reason == "unknown_ticker"
    assert db.scalars(select(Stock)).all() == []


def test_sync_without_provider(client: TestClient) -> None:
    body = client.post("/api/v1/stocks/LIVN/sync-prices").json()
    assert body["reason"] == "provider_not_configured"

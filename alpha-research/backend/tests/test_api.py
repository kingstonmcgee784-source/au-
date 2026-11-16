from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import HistoricalPrice, Stock, StockScore


def test_health_reports_migrated_database(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["database"]["connected"] is True
    assert body["database"]["up_to_date"] is True
    assert body["database"]["revision"] == body["database"]["head_revision"]
    assert body["integrations"] == {
        "market_data": "not_configured",
        "ai_research": "not_configured",
    }


@pytest.mark.parametrize(
    ("method", "path", "reason"),
    [
        ("get", "/api/v1/stocks/MSFT/quote", "provider_not_configured"),
        ("get", "/api/v1/market/overview", "provider_not_configured"),
        ("get", "/api/v1/stocks/search?q=micro", "provider_not_configured"),
        ("get", "/api/v1/stocks/MSFT", "no_stored_data"),
        ("get", "/api/v1/stocks/MSFT/financials", "no_stored_data"),
        ("get", "/api/v1/stocks/MSFT/technicals", "no_stored_data"),
        ("get", "/api/v1/stocks/MSFT/score", "no_stored_data"),
    ],
)
def test_unavailable_data_is_reported_not_invented(
    client: TestClient, method: str, path: str, reason: str
) -> None:
    response = getattr(client, method)(path)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["reason"] == reason
    assert body["data"] is None
    assert body["message"]


def test_generate_report_requires_ai(client: TestClient) -> None:
    body = client.post("/api/v1/reports/generate", json={"ticker": "msft"}).json()
    assert body == {
        "status": "unavailable",
        "data": None,
        "reason": "ai_not_configured",
        "message": body["message"],
        "source": None,
        "as_of": None,
    }


def test_invalid_ticker_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/stocks/not a ticker!/quote").status_code == 422
    assert client.post("/api/v1/reports/generate", json={"ticker": "$$$"}).status_code == 422


def test_search_and_profile_use_stored_stocks(client: TestClient, db: Session) -> None:
    db.add(Stock(ticker="TEST", name="Test Holdings Inc", exchange="NASDAQ"))
    db.commit()

    search = client.get("/api/v1/stocks/search?q=holdings").json()
    assert search["status"] == "ok"
    assert search["source"] == "local_database"
    assert [s["ticker"] for s in search["data"]] == ["TEST"]

    profile = client.get("/api/v1/stocks/test").json()
    assert profile["status"] == "ok"
    assert profile["data"]["name"] == "Test Holdings Inc"


def test_technicals_computed_from_stored_prices(client: TestClient, db: Session) -> None:
    stock = Stock(ticker="TEST", name="Test Holdings Inc")
    db.add(stock)
    db.flush()
    start = date(2026, 1, 1)
    for i in range(60):
        close = float(100 + i)
        db.add(
            HistoricalPrice(
                stock_id=stock.id,
                date=start + timedelta(days=i),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000,
                source="test_fixture",
            )
        )
    db.commit()

    body = client.get("/api/v1/stocks/TEST/technicals").json()
    assert body["status"] == "ok"
    snapshot = body["data"]
    assert snapshot["bars_available"] == 60
    assert snapshot["last_close"] == 159.0
    values = {item["name"]: item["value"] for item in snapshot["indicators"]}
    assert values["sma_50"] == pytest.approx(sum(range(110, 160)) / 50)
    assert values["rsi_14"] == pytest.approx(100.0)
    # Not enough history for the 200-day average: reported as null, not guessed.
    assert values["sma_200"] is None


def test_technicals_need_history(client: TestClient, db: Session) -> None:
    db.add(Stock(ticker="TEST", name="Test Holdings Inc"))
    db.commit()
    body = client.get("/api/v1/stocks/TEST/technicals").json()
    assert body["reason"] == "insufficient_history"


def test_rankings_unavailable_until_scored(client: TestClient) -> None:
    assert client.get("/api/v1/rankings").json()["reason"] == "no_stored_data"


def test_rankings_use_latest_score_per_stock(client: TestClient, db: Session) -> None:
    alpha = Stock(ticker="AAA", name="Alpha Test Co")
    beta = Stock(ticker="BBB", name="Beta Test Co")
    db.add_all([alpha, beta])
    db.flush()

    def score(stock: Stock, day: int, total: float) -> StockScore:
        return StockScore(
            stock_id=stock.id,
            as_of=date(2026, 11, day),
            total_score=total,
            category_scores={},
            methodology_version="1.0",
        )

    db.add_all([score(alpha, 1, 90), score(alpha, 2, 40), score(beta, 2, 70)])
    db.commit()

    body = client.get("/api/v1/rankings").json()
    assert body["status"] == "ok"
    assert [(r["rank"], r["ticker"], r["total_score"]) for r in body["data"]] == [
        (1, "BBB", 70),
        (2, "AAA", 40),
    ]


def test_scoring_methodology(client: TestClient) -> None:
    body = client.get("/api/v1/scoring/methodology").json()
    assert sum(c["weight"] for c in body["categories"]) == 100
    assert body["bands"][0] == {"min_score": 90, "label": "Exceptional research candidate"}


def test_reports_list_empty_and_missing_report(client: TestClient) -> None:
    assert client.get("/api/v1/reports").json() == []
    response = client.get("/api/v1/reports/999")
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


def test_watchlist_lifecycle(client: TestClient) -> None:
    created = client.post("/api/v1/watchlists", json={"name": "Core ideas"})
    assert created.status_code == 201
    watchlist_id = created.json()["id"]

    duplicate = client.post("/api/v1/watchlists", json={"name": "Core ideas"})
    assert duplicate.status_code == 409

    added = client.post(f"/api/v1/watchlists/{watchlist_id}/items", json={"ticker": "livn"})
    assert added.status_code == 201
    assert [i["ticker"] for i in added.json()["items"]] == ["LIVN"]

    again = client.post(f"/api/v1/watchlists/{watchlist_id}/items", json={"ticker": "LIVN"})
    assert again.status_code == 409

    removed = client.delete(f"/api/v1/watchlists/{watchlist_id}/items/LIVN")
    assert removed.json()["items"] == []
    assert client.delete(f"/api/v1/watchlists/{watchlist_id}/items/LIVN").status_code == 404

    assert client.delete(f"/api/v1/watchlists/{watchlist_id}").status_code == 204
    assert client.get("/api/v1/watchlists").json() == []
    assert client.delete(f"/api/v1/watchlists/{watchlist_id}").status_code == 404

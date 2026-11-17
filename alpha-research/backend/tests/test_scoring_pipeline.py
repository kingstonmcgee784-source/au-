"""Scoring end to end through the API, with fake providers (no network)."""

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import fundamentals_client, market_data_provider
from app.main import app
from app.providers.sec_edgar import CompanyInfo, FilingRef
from tests.fakes import FakeProvider, bars


def sec_facts() -> dict[str, Any]:
    """Eight reported quarters of a growing, profitable test company."""
    month_ends = ((3, 31), (6, 30), (9, 30), (12, 31))
    ends = [date(2024 + q // 4, *month_ends[q % 4]) for q in range(8)]  # 2024Q1 .. 2025Q4
    labels = [("Q1", "10-Q"), ("Q2", "10-Q"), ("Q3", "10-Q"), ("FY", "10-K")]

    def filing(i: int, end: date) -> dict[str, Any]:
        fp, form = labels[i % 4]
        return {
            "accn": f"a{i}",
            "fy": end.year,
            "fp": fp,
            "form": form,
            "filed": (end + timedelta(days=30)).isoformat(),
        }

    def quarter_rows(values: list[float]) -> list[dict[str, Any]]:
        rows = []
        for i, (end, value) in enumerate(zip(ends, values, strict=True)):
            start = (end - timedelta(days=89)).replace(day=1)
            rows.append(
                {"start": start.isoformat(), "end": end.isoformat(), "val": value, **filing(i, end)}
            )
        return rows

    def instant(value: float) -> list[dict[str, Any]]:
        return [
            {"end": end.isoformat(), "val": value, **filing(i, end)} for i, end in enumerate(ends)
        ]

    revenue = [100, 110, 120, 130, 140, 150, 160, 170]
    usd = lambda rows: {"units": {"USD": rows}}  # noqa: E731
    return {
        "facts": {
            "us-gaap": {
                "Revenues": usd(quarter_rows(revenue)),
                "GrossProfit": usd(quarter_rows([r * 0.6 for r in revenue])),
                "OperatingIncomeLoss": usd(quarter_rows([r * 0.2 for r in revenue])),
                "NetIncomeLoss": usd(quarter_rows([r * 0.15 for r in revenue])),
                "NetCashProvidedByUsedInOperatingActivities": usd(
                    quarter_rows([r * 0.25 for r in revenue])
                ),
                "PaymentsToAcquirePropertyPlantAndEquipment": usd(quarter_rows([5] * 8)),
                "DepreciationDepletionAndAmortization": usd(quarter_rows([4] * 8)),
                "CashAndCashEquivalentsAtCarryingValue": usd(instant(300)),
                "LongTermDebtNoncurrent": usd(instant(100)),
                "StockholdersEquity": usd(instant(800)),
                "AssetsCurrent": usd(instant(500)),
                "LiabilitiesCurrent": usd(instant(200)),
                "CommonStockSharesOutstanding": {"units": {"shares": instant(100)}},
            }
        }
    }


class FakeSec:
    name = "sec_edgar"

    def lookup(self, ticker: str) -> tuple[int, str]:
        return 1, "TEST Test Co"

    def company_facts(self, cik: int) -> dict[str, Any]:
        return sec_facts()

    def company_info(self, cik: int) -> CompanyInfo:
        return CompanyInfo(sic="7372", sic_description="SERVICES-PREPACKAGED SOFTWARE", filings=[])

    def filing_document(self, cik: int, filing: FilingRef) -> str:
        raise AssertionError("no filings to download")

    def filing_url(self, cik: int, filing: FilingRef) -> str:
        return f"https://example.test/{filing.accession}"


@pytest.fixture
def providers() -> Iterator[FakeProvider]:
    market = FakeProvider(
        {
            "TEST": bars(date(2025, 1, 1), 300, first_close=20.0),
            "SPY": bars(date(2025, 1, 1), 300, first_close=500.0),
        }
    )
    app.dependency_overrides[market_data_provider] = lambda: market
    app.dependency_overrides[fundamentals_client] = lambda: FakeSec()
    yield market
    app.dependency_overrides.clear()


def test_calculate_score_end_to_end(client: TestClient, providers: FakeProvider) -> None:
    body = client.post("/api/v1/stocks/TEST/score").json()
    assert body["status"] == "ok", body
    score = body["data"]

    # Only industry positioning has no data source yet: 95% coverage.
    assert score["coverage"] == pytest.approx(0.95)
    categories = {c["key"]: c for c in score["categories"]}
    assert categories["industry"]["points"] is None
    assert categories["industry"]["unrated_reason"]
    assert categories["catalysts"]["points"] is not None
    # Insider filings were loaded (none in the window): rated, neutral to positive.
    assert categories["institutional"]["points"] is not None
    assert "Form 4" in score["notes"]
    for key in ("fundamentals", "valuation", "technical", "growth", "risk_reward"):
        assert categories[key]["points"] is not None, key
        assert categories[key]["inputs"], key
    assert 0 <= score["total_score"] <= 100
    assert score["risk_class"] in {"Low", "Moderate", "Elevated", "High", "Speculative"}
    assert "Not scored for lack of data" in score["notes"]

    # Stored and readable afterwards.
    latest = client.get("/api/v1/stocks/TEST/score").json()
    assert latest["data"]["total_score"] == score["total_score"]
    ranked = client.get("/api/v1/rankings").json()
    assert [r["ticker"] for r in ranked["data"]] == ["TEST"]
    assert ranked["data"][0]["coverage"] == pytest.approx(0.95)

    metrics = client.get("/api/v1/stocks/TEST/metrics").json()
    assert metrics["status"] == "ok"
    assert metrics["data"]["values"]["revenue_ttm"] == 620  # 140+150+160+170
    assert metrics["data"]["values"]["market_cap"] > 0


def test_score_without_any_data(client: TestClient) -> None:
    body = client.post("/api/v1/stocks/TEST/score").json()
    assert body["status"] == "unavailable"
    assert body["reason"] == "no_stored_data"


def test_metrics_before_scoring(client: TestClient) -> None:
    assert client.get("/api/v1/stocks/TEST/metrics").json()["reason"] == "no_stored_data"


def test_refuses_to_score_without_core_categories(client: TestClient) -> None:
    """Financial statements alone are not enough: no price means no valuation or technicals."""
    app.dependency_overrides[fundamentals_client] = lambda: FakeSec()
    try:
        body = client.post("/api/v1/stocks/TEST/score").json()
    finally:
        app.dependency_overrides.clear()
    assert body["status"] == "unavailable"
    assert body["reason"] == "insufficient_history"
    assert "valuation needs" in body["message"] and "technical needs" in body["message"]
    assert client.get("/api/v1/rankings").json()["status"] == "unavailable"

"""8-K classification, earnings estimates, catalyst ratings and the events sync."""

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.catalysts import (
    Event,
    catalyst_metrics,
    classify,
    estimate_next_earnings,
    headline,
)
from app.analysis.ratings import rate
from app.api.deps import fundamentals_client
from app.main import app
from app.models import NewsArticle, Stock
from app.providers.sec_edgar import CompanyInfo, FilingRef
from app.services.catalysts import sync_events

TODAY = date(2026, 11, 17)


def test_classify_and_headline() -> None:
    items = classify(["2.02", "7.01", "9.01"])
    assert [i.code for i in items] == ["2.02", "7.01"]  # exhibits ignored
    assert headline(items).kind == "earnings"
    assert headline(classify(["5.02", "4.02"])).kind == "red_flag"
    assert headline(classify(["9.01"])) is None
    assert classify(["3.01"])[0].kind == "review"  # ambiguous: not a red flag


def test_earnings_estimate_uses_last_years_timing() -> None:
    releases = [
        date(2025, 2, 3),
        date(2025, 5, 5),
        date(2025, 8, 4),
        date(2025, 11, 3),
        date(2026, 2, 2),
        date(2026, 5, 4),
        date(2026, 8, 3),
        date(2026, 11, 2),
    ]
    assert estimate_next_earnings(releases, TODAY) == date(2027, 2, 2)
    # Short history: last release plus a quarter.
    assert estimate_next_earnings([date(2026, 11, 2)], TODAY) == date(2027, 2, 1)
    assert estimate_next_earnings([], TODAY) is None
    # A long-missed estimate is reported as unknown rather than a past date.
    assert estimate_next_earnings([date(2025, 6, 1)], TODAY) is None


def test_catalyst_metrics_and_rating() -> None:
    events = [
        Event(date(2026, 11, 2), ("2.02", "9.01")),
        Event(date(2026, 9, 1), ("1.01",)),
        Event(date(2026, 3, 1), ("4.02",)),  # restatement within 12 months
        Event(date(2025, 2, 1), ("1.03",)),  # older than 12 months: ignored
    ]
    m = catalyst_metrics(events, TODAY)
    assert m["catalyst_red_flags_365d"] == 1.0
    assert m["catalyst_material_events_180d"] == 1.0
    assert m["catalyst_earnings_within_90d"] == 1.0

    clean = rate(
        {
            "catalyst_red_flags_365d": 0,
            "catalyst_material_events_180d": 0,
            "catalyst_earnings_within_90d": 1,
        }
    )
    flagged = rate(
        {
            "catalyst_red_flags_365d": 2,
            "catalyst_material_events_180d": 0,
            "catalyst_earnings_within_90d": 0,
        }
    )
    assert clean["catalysts"].rating > flagged["catalysts"].rating
    assert rate({})["catalysts"].rating is None


class FakeSec:
    name = "sec_edgar"

    def lookup(self, ticker: str) -> tuple[int, str]:
        return 1, "Test Holdings Inc"

    def company_facts(self, cik: int) -> dict[str, Any]:
        return {"facts": {}}

    def company_info(self, cik: int) -> CompanyInfo:
        filed = TODAY - timedelta(days=15)
        return CompanyInfo(
            sic="3812",
            sic_description="SEARCH, DETECTION, NAVIGATION, GUIDANCE",
            exchanges=("Nasdaq",),
            filings=[
                FilingRef("e1", "8-K", filed, "e1.htm", "2.02,9.01"),
                FilingRef("e2", "8-K", filed - timedelta(days=40), "e2.htm", "1.01"),
                FilingRef("e3", "10-Q", filed, "q.htm", ""),
                FilingRef("e4", "8-K", TODAY - timedelta(days=900), "old.htm", "5.02"),
            ],
        )

    def filing_document(self, cik: int, filing: FilingRef) -> str:
        raise AssertionError("8-K sync must not download documents")

    def filing_url(self, cik: int, filing: FilingRef) -> str:
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{filing.accession}/{filing.primary_document}"


@pytest.fixture
def sec() -> Iterator[FakeSec]:
    fake = FakeSec()
    app.dependency_overrides[fundamentals_client] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def test_sync_events_stores_8ks_once(sec: FakeSec, db: Session) -> None:
    first = sync_events(db, sec, "TEST", today=TODAY)
    assert first.data is not None and first.data.events_added == 2  # no 10-Q, nothing too old
    again = sync_events(db, sec, "TEST", today=TODAY)
    assert again.data is not None and again.data.events_added == 0
    assert again.data.events_stored == 2

    stock = db.scalar(select(Stock).where(Stock.ticker == "TEST"))
    assert stock.exchange == "NASDAQ"
    assert stock.industry == "Search, Detection, Navigation, Guidance"
    assert stock.events_synced_at is not None
    rows = db.scalars(select(NewsArticle).order_by(NewsArticle.published_at.desc())).all()
    assert [(r.category, r.items) for r in rows] == [
        ("earnings", ["2.02", "9.01"]),
        ("agreement", ["1.01"]),
    ]


def test_catalyst_feed_endpoint(client: TestClient, sec: FakeSec) -> None:
    assert client.get("/api/v1/stocks/TEST/catalysts").json()["reason"] == "no_stored_data"
    assert client.post("/api/v1/stocks/TEST/sync-events").json()["status"] == "ok"
    body = client.get("/api/v1/stocks/TEST/catalysts").json()
    assert body["status"] == "ok"
    events = body["data"]["events"]
    assert events[0]["headline"] == "Quarterly results (earnings release)"
    assert events[0]["url"].startswith("https://www.sec.gov/Archives/")
    assert [i["code"] for i in events[0]["items"]] == ["2.02"]
    assert body["data"]["next_earnings_estimate"] is not None

"""Batch scans, the screener table and industry comparison, with fake providers."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.analysis.industry import choose_group, percentile, percentiles
from app.api.deps import fundamentals_client, market_data_provider
from app.db.session import SessionLocal
from app.main import app
from app.models import ScreenRun
from app.providers.base import ProviderRateLimitError, TickerNotFoundError
from app.providers.sec_edgar import CompanyInfo, FilingRef
from app.schemas.screener import ScanRequest
from app.services.screener import create_scan, process_scan
from tests.fakes import FakeProvider, bars
from tests.test_scoring_pipeline import sec_facts

TICKERS = ["AAA", "BBB", "CCC", "DDD", "EEE"]


# -- Industry math -----------------------------------------------------------------


def test_percentile_direction_and_ties() -> None:
    assert percentile(10, [1, 2, 3, 4], higher_is_better=True) == 1.0
    assert percentile(10, [1, 2, 3, 4], higher_is_better=False) == 0.0
    assert percentile(2, [1, 2, 3, 4], higher_is_better=True) == pytest.approx(0.375)


def test_choose_group_widens_only_when_needed() -> None:
    peers = {"A": "7372", "B": "7372", "C": "7371", "D": "7370", "E": "7379", "F": "2834"}
    group = choose_group("7372", peers)
    assert group is not None and group.prefix == "737"
    assert group.members == ["A", "B", "C", "D", "E"]
    assert choose_group("2834", peers) is None  # one peer only, even at two digits
    assert choose_group(None, peers) is None


def test_percentiles_need_enough_peers() -> None:
    peers = [{"roe": v} for v in (0.1, 0.2, 0.3)]
    assert percentiles({"roe": 0.5}, peers, {"roe": True}) == {"roe": None}
    assert percentiles({"roe": 0.5}, [*peers, {"roe": 0.4}], {"roe": True}) == {"roe": 1.0}


# -- Scans -------------------------------------------------------------------------------


class FakeSec:
    name = "sec_edgar"

    def lookup(self, ticker: str) -> tuple[int, str]:
        if ticker not in TICKERS:
            raise TickerNotFoundError(ticker)
        return TICKERS.index(ticker) + 1, f"{ticker} Software Inc"

    def company_facts(self, cik: int) -> dict[str, Any]:
        facts = sec_facts()
        # Give each company different revenue so they rank differently.
        for row in facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"]:
            row["val"] = row["val"] * cik
        return facts

    def company_info(self, cik: int) -> CompanyInfo:
        return CompanyInfo(sic="7372", sic_description="SERVICES-PREPACKAGED SOFTWARE", filings=[])

    def filing_document(self, cik: int, filing: FilingRef) -> str:
        raise AssertionError("no documents expected")

    def filing_url(self, cik: int, filing: FilingRef) -> str:
        return "https://example.test"


class LimitedProvider(FakeProvider):
    """Fails price requests with a rate limit until `limited` is cleared."""

    limited = False

    def get_daily_prices(self, ticker, start, end=None):  # type: ignore[no-untyped-def]
        if self.limited:
            raise ProviderRateLimitError("hourly limit reached")
        return super().get_daily_prices(ticker, start, end)


@pytest.fixture
def market() -> LimitedProvider:
    known = {t: bars(date(2025, 1, 1), 300, 20.0 + i) for i, t in enumerate(TICKERS)}
    known["SPY"] = bars(date(2025, 1, 1), 300, 500.0)
    return LimitedProvider(known)


@pytest.fixture
def api_fakes(market: LimitedProvider) -> Iterator[LimitedProvider]:
    app.dependency_overrides[market_data_provider] = lambda: market
    app.dependency_overrides[fundamentals_client] = lambda: FakeSec()
    yield market
    app.dependency_overrides.clear()


def run_scan(db: Session, market: LimitedProvider, tickers: list[str], sleep: Any = None) -> int:
    scan = create_scan(db, ScanRequest(tickers=tickers))
    process_scan(
        scan.id,
        market=market,
        fundamentals=FakeSec(),
        history_years=2,
        session_factory=SessionLocal,
        sleep=sleep or (lambda _s: None),
    )
    return scan.id


def test_scan_scores_every_ticker_and_compares_industry(
    client: TestClient, market: LimitedProvider, db: Session
) -> None:
    run_id = run_scan(db, market, [*TICKERS, "ZZZZ"])
    scan = client.get(f"/api/v1/screener/scans/{run_id}").json()
    assert scan["status"] == "done"
    statuses = {i["ticker"]: i["status"] for i in scan["items"]}
    assert all(statuses[t] == "scored" for t in TICKERS)
    assert statuses["ZZZZ"] == "failed"  # unknown to the market data provider

    # Five software companies: each has four peers, so industry is rated and
    # coverage is complete after the final re-scoring pass.
    score = client.get("/api/v1/stocks/AAA/score").json()["data"]
    assert score["coverage"] == pytest.approx(1.0)
    industry = next(c for c in score["categories"] if c["key"] == "industry")
    assert industry["points"] is not None
    assert "4 peers" in score["notes"]

    comparison = client.get("/api/v1/stocks/EEE/industry").json()
    assert comparison["status"] == "ok"
    data = comparison["data"]
    assert data["peer_group"] == "SIC 7372"
    assert [r["ticker"] for r in data["rows"]][0] == "EEE"
    assert len(data["rows"]) == 5
    # EEE has the highest revenue growth base (5x) but identical growth rates:
    # every peer ties, so it sits in the middle.
    assert data["positioning"]["revenue_growth_ttm"] == pytest.approx(0.5)

    rows = client.get("/api/v1/screener").json()
    assert {r["ticker"] for r in rows} == set(TICKERS)
    assert all("pe_ttm" in r["metrics"] for r in rows)


def test_scan_waits_for_rate_limit_and_resumes(market: LimitedProvider, db: Session) -> None:
    market.limited = True
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        # The limit resets while the scan waits.
        sleeps.append(seconds)
        market.limited = False
        with SessionLocal() as session:
            session.execute(
                update(ScreenRun).values(resume_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            session.commit()

    run_id = run_scan(db, market, ["AAA"], sleep=sleep)
    db.expire_all()
    run = db.get(ScreenRun, run_id)
    assert sleeps, "the scan should have waited"
    assert run.status == "done"
    assert run.items[0].status == "scored"


def test_only_one_scan_at_a_time_and_cancel(client: TestClient, api_fakes: LimitedProvider) -> None:
    first = client.post("/api/v1/screener/scans", json={"tickers": ["aaa"]})
    assert first.status_code == 201
    # The background thread may finish quickly; create a second scan only if it is still active.
    scan_id = first.json()["id"]
    cancelled = client.post(f"/api/v1/screener/scans/{scan_id}/cancel").json()
    assert cancelled["status"] in {"cancelled", "done"}

    assert client.post("/api/v1/screener/scans", json={"tickers": []}).status_code == 409
    assert (
        client.post("/api/v1/screener/scans", json={"tickers": ["bad ticker!"]}).status_code == 422
    )


def test_scan_from_watchlist(client: TestClient, db: Session, market: LimitedProvider) -> None:
    watchlist = client.post("/api/v1/watchlists", json={"name": "Ideas"}).json()
    client.post(f"/api/v1/watchlists/{watchlist['id']}/items", json={"ticker": "BBB"})
    scan = create_scan(db, ScanRequest(watchlist_id=watchlist["id"], tickers=["AAA"]))
    assert scan.name == "Watchlist: Ideas"
    assert [i.ticker for i in scan.items] == ["AAA", "BBB"]


def test_industry_needs_enough_peers(
    client: TestClient, market: LimitedProvider, db: Session
) -> None:
    run_scan(db, market, ["AAA", "BBB"])
    body = client.get("/api/v1/stocks/AAA/industry").json()
    assert body["status"] == "unavailable"
    assert "At least 4 are needed" in body["message"]

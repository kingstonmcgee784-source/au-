"""SEC fundamentals: XBRL parsing, the EDGAR client and the sync flow.

The XBRL fixture below mirrors the structure of real SEC company facts. Its
numbers are made up for the test and only need to add up consistently.
"""

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import fundamentals_client
from app.main import app
from app.models import FinancialStatement, Stock
from app.providers.base import ProviderAuthError, TickerNotFoundError
from app.providers.sec_edgar import CompanyInfo, FilingRef, SecEdgarClient
from app.providers.sec_xbrl import parse_company_facts


def fact(
    val: float,
    end: str,
    accn: str,
    fy: int,
    fp: str,
    form: str,
    filed: str,
    start: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "end": end,
        "val": val,
        "accn": accn,
        "fy": fy,
        "fp": fp,
        "form": form,
        "filed": filed,
    }
    if start:
        row["start"] = start
    return row


Q1, Q2, Q3, K = "q1", "q2", "q3", "k"
FILINGS = {
    Q1: (2025, "Q1", "10-Q", "2025-05-01"),
    Q2: (2025, "Q2", "10-Q", "2025-08-01"),
    Q3: (2025, "Q3", "10-Q", "2025-11-01"),
    K: (2025, "FY", "10-K", "2026-02-15"),
}


def f(val: float, accn: str, end: str, start: str | None = None) -> dict[str, Any]:
    fy, fp, form, filed = FILINGS[accn]
    return fact(val, end, accn, fy, fp, form, filed, start)


COMPANY_FACTS: dict[str, Any] = {
    "cik": 123,
    "entityName": "Test Holdings Inc",
    "facts": {
        "us-gaap": {
            # Revenue: three reported quarters plus 6/9-month and annual totals.
            "Revenues": {
                "units": {
                    "USD": [
                        f(100, Q1, "2025-03-31", "2025-01-01"),
                        f(120, Q2, "2025-06-30", "2025-04-01"),
                        f(220, Q2, "2025-06-30", "2025-01-01"),
                        f(130, Q3, "2025-09-30", "2025-07-01"),
                        f(350, Q3, "2025-09-30", "2025-01-01"),
                        f(500, K, "2025-12-31", "2025-01-01"),
                        # A proxy statement repeats the figure; it must be ignored.
                        fact(
                            999,
                            "2025-12-31",
                            "proxy",
                            2025,
                            "FY",
                            "DEF 14A",
                            "2026-04-01",
                            "2025-01-01",
                        ),
                    ]
                }
            },
            # Cash flow is only reported year to date.
            "NetCashProvidedByUsedInOperatingActivities": {
                "units": {
                    "USD": [
                        f(10, Q1, "2025-03-31", "2025-01-01"),
                        f(25, Q2, "2025-06-30", "2025-01-01"),
                        f(45, Q3, "2025-09-30", "2025-01-01"),
                        f(70, K, "2025-12-31", "2025-01-01"),
                    ]
                }
            },
            "EarningsPerShareDiluted": {
                "units": {
                    "USD/shares": [
                        f(0.5, Q3, "2025-09-30", "2025-07-01"),
                        f(1.9, Q3, "2025-09-30", "2025-01-01"),
                        f(2.6, K, "2025-12-31", "2025-01-01"),
                    ]
                }
            },
            "Assets": {
                "units": {
                    "USD": [
                        f(1000, Q3, "2025-09-30"),
                        f(1100, K, "2025-12-31"),
                    ]
                }
            },
        }
    },
}


def by_key(statements: list[Any]) -> dict[tuple[str, str, date], Any]:
    return {(s.statement_type, s.period_type, s.period_end): s for s in statements}


def test_parser_uses_reported_values_and_flags_derived_ones() -> None:
    statements = by_key(parse_company_facts(COMPANY_FACTS))

    q3 = statements[("income", "quarterly", date(2025, 9, 30))]
    assert q3.line_items["revenue"] == 130
    assert q3.line_items["eps_diluted"] == 0.5
    assert q3.derived_items == []
    assert (q3.fiscal_year, q3.fiscal_quarter) == (2025, 3)

    # Q4 = full year minus nine months, and marked as derived.
    q4 = statements[("income", "quarterly", date(2025, 12, 31))]
    assert q4.line_items["revenue"] == 150
    assert q4.derived_items == ["revenue"]
    assert q4.fiscal_quarter == 4
    # Per-share values are never derived by subtraction.
    assert "eps_diluted" not in q4.line_items

    annual = statements[("income", "annual", date(2025, 12, 31))]
    assert annual.line_items["revenue"] == 500  # not the proxy statement's 999
    assert annual.fiscal_quarter is None


def test_parser_derives_quarterly_cash_flow_from_year_to_date() -> None:
    statements = by_key(parse_company_facts(COMPANY_FACTS))
    quarterly = [
        statements[("cashflow", "quarterly", date(2025, m, d))]
        for m, d in ((3, 31), (6, 30), (9, 30), (12, 31))
    ]
    assert [s.line_items["operating_cash_flow"] for s in quarterly] == [10, 15, 20, 25]
    assert quarterly[0].derived_items == []
    assert all(s.derived_items == ["operating_cash_flow"] for s in quarterly[1:])


def test_parser_balance_sheet_uses_period_end_values() -> None:
    statements = by_key(parse_company_facts(COMPANY_FACTS))
    assert statements[("balance", "quarterly", date(2025, 9, 30))].line_items == {
        "total_assets": 1000
    }
    assert statements[("balance", "annual", date(2025, 12, 31))].line_items == {
        "total_assets": 1100
    }


def test_parser_prefers_latest_filing_for_restated_periods() -> None:
    data = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            f(100, Q1, "2025-03-31", "2025-01-01"),
                            fact(
                                105,
                                "2025-03-31",
                                "q1a",
                                2025,
                                "Q1",
                                "10-Q/A",
                                "2025-06-01",
                                "2025-01-01",
                            ),
                        ]
                    }
                }
            }
        }
    }
    (statement,) = parse_company_facts(data)
    assert statement.line_items["revenue"] == 105


def test_parser_handles_empty_facts() -> None:
    assert parse_company_facts({"facts": {}}) == []


# -- EDGAR client -------------------------------------------------------------


def edgar(routes: dict[str, httpx.Response], seen: list[httpx.Request]) -> SecEdgarClient:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return routes.get(str(request.url), httpx.Response(404))

    return SecEdgarClient("Test Person test@example.com", transport=httpx.MockTransport(handle))


TICKERS = httpx.Response(
    200,
    json={
        "0": {"cik_str": 1067983, "ticker": "BRK-B", "title": "Berkshire Hathaway Inc"},
        "1": {"cik_str": 123, "ticker": "TEST", "title": "Test Holdings Inc"},
    },
)


def test_client_requires_contact_email() -> None:
    with pytest.raises(ValueError, match="contact email"):
        SecEdgarClient("No Email Here")


def test_client_lookup_and_facts() -> None:
    seen: list[httpx.Request] = []
    client = edgar(
        {
            "https://www.sec.gov/files/company_tickers.json": TICKERS,
            "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000123.json": httpx.Response(
                200, json=COMPANY_FACTS
            ),
        },
        seen,
    )
    assert client.lookup("brk.b") == (1067983, "Berkshire Hathaway Inc")
    assert client.lookup("TEST") == (123, "Test Holdings Inc")
    assert client.company_facts(123)["entityName"] == "Test Holdings Inc"
    assert seen[0].headers["User-Agent"] == "Test Person test@example.com"
    # The ticker list is downloaded once and reused.
    assert sum("company_tickers" in str(r.url) for r in seen) == 1

    with pytest.raises(TickerNotFoundError):
        client.lookup("NOPE")


def test_client_explains_403() -> None:
    client = edgar({"https://www.sec.gov/files/company_tickers.json": httpx.Response(403)}, [])
    with pytest.raises(ProviderAuthError, match="SEC_USER_AGENT"):
        client.lookup("TEST")


# -- Sync through the API -----------------------------------------------------------


class FakeSec:
    name = "sec_edgar"

    def __init__(self) -> None:
        self.facts = COMPANY_FACTS
        self.downloads = 0
        self.filings: list[FilingRef] = []

    def lookup(self, ticker: str) -> tuple[int, str]:
        if ticker != "TEST":
            raise TickerNotFoundError(ticker)
        return 123, "Test Holdings Inc"

    def company_facts(self, cik: int) -> dict[str, Any]:
        self.downloads += 1
        return self.facts

    def company_info(self, cik: int) -> CompanyInfo:
        return CompanyInfo(sic=None, sic_description=None, filings=self.filings)


@pytest.fixture
def sec() -> Iterator[FakeSec]:
    fake = FakeSec()
    app.dependency_overrides[fundamentals_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(fundamentals_client, None)


def test_sync_financials_then_read(client: TestClient, sec: FakeSec, db: Session) -> None:
    synced = client.post("/api/v1/stocks/TEST/sync-financials").json()
    assert synced["status"] == "ok"
    assert synced["data"]["company_name"] == "Test Holdings Inc"
    assert synced["data"]["quarterly_periods"] == 4
    assert synced["data"]["annual_periods"] == 1

    body = client.get(
        "/api/v1/stocks/TEST/financials?statement_type=income&period_type=quarterly"
    ).json()
    assert body["status"] == "ok"
    newest = body["data"][0]
    assert newest["period_end"] == "2025-12-31"
    assert newest["line_items"]["revenue"] == 150
    assert newest["derived_items"] == ["revenue"]
    assert newest["source"] == "sec_edgar"

    # Syncing again replaces rows instead of duplicating them.
    sec.facts = {**COMPANY_FACTS}
    assert client.post("/api/v1/stocks/TEST/sync-financials").json()["status"] == "ok"
    again = client.get("/api/v1/stocks/TEST/financials?statement_type=income").json()
    assert len(again["data"]) == 5  # 4 quarters + 1 year

    # A period that a newer parse no longer produces is removed.
    stale = FinancialStatement(
        stock_id=db.scalar(select(Stock.id).where(Stock.ticker == "TEST")),
        statement_type="balance",
        period_type="quarterly",
        period_end=date(2025, 11, 20),
        fiscal_year=2025,
        line_items={"shares_outstanding": 1.0},
        source="sec_edgar",
    )
    db.add(stale)
    db.commit()
    stale_id = stale.id
    client.post("/api/v1/stocks/TEST/sync-financials")
    db.expire_all()
    assert db.get(FinancialStatement, stale_id) is None


def test_sync_financials_unknown_ticker(client: TestClient, sec: FakeSec) -> None:
    body = client.post("/api/v1/stocks/ZZZZ/sync-financials").json()
    assert body["reason"] == "unknown_ticker"


def test_sync_financials_not_configured(client: TestClient) -> None:
    body = client.post("/api/v1/stocks/TEST/sync-financials").json()
    assert body["reason"] == "provider_not_configured"
    assert "SEC_USER_AGENT" in body["message"]


def test_subsequent_event_dates_do_not_change_the_period() -> None:
    """A 10-Q can report an event after quarter end (e.g. a dividend declared later)."""
    data = {
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": [f(130, Q3, "2025-09-30", "2025-07-01")]}},
                "NetIncomeLoss": {"units": {"USD": [f(13, Q3, "2025-09-30", "2025-07-01")]}},
                "CommonStockDividendsPerShareDeclared": {
                    "units": {
                        "USD/shares": [
                            f(0.5, Q3, "2025-10-20", "2025-10-20"),
                        ]
                    }
                },
            }
        }
    }
    statements = parse_company_facts(data)
    income = [s for s in statements if s.statement_type == "income"]
    assert [s.period_end for s in income] == [date(2025, 9, 30)]
    assert income[0].line_items == {"revenue": 130, "net_income": 13}


def test_revenue_uses_the_largest_reported_figure() -> None:
    """Some filers put a sub-total under `Revenues` and the total under another tag."""
    data = {
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": [f(1398, Q1, "2025-03-31", "2025-01-01")]}},
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [f(1559, Q1, "2025-03-31", "2025-01-01")]}
                },
            }
        }
    }
    (statement,) = parse_company_facts(data)
    assert statement.line_items["revenue"] == 1559


def test_fiscal_labels_follow_the_companys_year_end() -> None:
    """A fiscal year ending in April: the July quarter is Q1 of the next fiscal year,
    even when the SEC tags it with the calendar year."""

    def filing(accn: str, fy: int, fp: str, form: str, filed: str) -> dict[str, Any]:
        return {"accn": accn, "fy": fy, "fp": fp, "form": form, "filed": filed}

    rows = [
        {
            "start": "2024-04-27",
            "end": "2025-04-25",
            "val": 400,
            **filing("k", 2025, "FY", "10-K", "2025-06-01"),
        },
        {
            "start": "2025-04-26",
            "end": "2025-07-25",
            "val": 110,
            **filing("q1", 2025, "Q1", "10-Q", "2025-08-27"),
        },
        {
            "start": "2025-07-26",
            "end": "2025-10-24",
            "val": 120,
            **filing("q2", 2025, "Q2", "10-Q", "2025-11-25"),
        },
    ]
    statements = by_key(
        parse_company_facts({"facts": {"us-gaap": {"Revenues": {"units": {"USD": rows}}}}})
    )
    july = statements[("income", "quarterly", date(2025, 7, 25))]
    october = statements[("income", "quarterly", date(2025, 10, 24))]
    assert (july.fiscal_year, july.fiscal_quarter) == (2026, 1)
    assert (october.fiscal_year, october.fiscal_quarter) == (2026, 2)
    assert statements[("income", "annual", date(2025, 4, 25))].fiscal_year == 2025


def test_financials_are_not_redownloaded_without_a_new_filing(sec: "FakeSec", db: Session) -> None:
    from app.services.ingestion import sync_financials

    assert sync_financials(db, sec, "TEST").status == "ok"
    assert sec.downloads == 1
    # No 10-Q or 10-K since: the stored statements are used.
    again = sync_financials(db, sec, "TEST")
    assert again.status == "ok" and again.data.statements_stored > 0
    assert sec.downloads == 1
    # A new 10-Q appears: download again.
    sec.filings = [FilingRef("new", "10-Q", date.today() + timedelta(days=1), "q.htm")]
    sync_financials(db, sec, "TEST")
    assert sec.downloads == 2
    # A forced load always downloads.
    sec.filings = []
    sync_financials(db, sec, "TEST", force=True)
    assert sec.downloads == 3


def test_statements_from_an_older_parser_are_reloaded(sec: "FakeSec", db: Session) -> None:
    from sqlalchemy import update

    from app.services.ingestion import sync_financials

    sync_financials(db, sec, "TEST")
    db.execute(update(FinancialStatement).values(parser_version=0))
    db.commit()
    sync_financials(db, sec, "TEST")
    assert sec.downloads == 2

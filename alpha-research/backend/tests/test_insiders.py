"""Form 4 parsing, insider summaries and the insider sync, with no network.

The XML fixtures follow the EDGAR ownership document schema; people and
numbers are made up.
"""

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.insider import Trade, summarize
from app.analysis.ratings import rate
from app.api.deps import fundamentals_client
from app.main import app
from app.models import InsiderFiling, Stock
from app.providers.sec_edgar import CompanyInfo, FilingRef
from app.providers.sec_form4 import Form4ParseError, parse_form4
from app.services.insiders import sync_insiders


def form4(
    rows: str, *, owner: str = "Doe Jane", relationship: str = "", plan_box: str | None = None,
    footnotes: str = "",
) -> str:
    plan = f"<aff10b5One>{plan_box}</aff10b5One>" if plan_box is not None else ""
    relationship = relationship or (
        "<isDirector>0</isDirector><isOfficer>1</isOfficer>"
        "<officerTitle>Chief Financial Officer</officerTitle><isTenPercentOwner>0</isTenPercentOwner>"
    )
    return f"""<?xml version="1.0"?>
<ownershipDocument>
  <schemaVersion>X0508</schemaVersion>
  <documentType>4</documentType>
  <periodOfReport>2026-11-10</periodOfReport>
  {plan}
  <issuer><issuerCik>0000000001</issuerCik><issuerTradingSymbol>TEST</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>0000000002</rptOwnerCik><rptOwnerName>{owner}</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>{relationship}</reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>{rows}</nonDerivativeTable>
  <derivativeTable>
    <derivativeTransaction>
      <securityTitle><value>Stock Option</value></securityTitle>
      <transactionDate><value>2026-11-10</value></transactionDate>
      <transactionCoding><transactionCode>A</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>99999</value></transactionShares>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts>
    </derivativeTransaction>
  </derivativeTable>
  <footnotes>{footnotes}</footnotes>
</ownershipDocument>"""


def row(code: str, shares: float, price: float | None, direction: str, day: str = "2026-11-10",
        footnote: str = "") -> str:
    price_xml = f"<transactionPricePerShare><value>{price}</value>{footnote}</transactionPricePerShare>" if price is not None else ""
    return f"""<nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>{day}</value></transactionDate>
      <transactionCoding><transactionFormType>4</transactionFormType><transactionCode>{code}</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>{shares}</value></transactionShares>
        {price_xml}
        <transactionAcquiredDisposedCode><value>{direction}</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>5000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>"""


def test_parses_trades_and_ignores_derivatives() -> None:
    parsed = parse_form4(form4(row("P", 1000, 20.5, "A") + row("F", 300, 21.0, "D"), plan_box="0"))
    assert parsed.owner_name == "Doe Jane"
    assert parsed.owner_role == "Chief Financial Officer"
    assert [(t.code, t.shares, t.price, t.acquired) for t in parsed.trades] == [
        ("P", 1000, 20.5, True),
        ("F", 300, 21.0, False),
    ]
    assert parsed.trades[0].under_10b5_1 is False  # checkbox present and unticked
    assert parsed.trades[0].shares_after == 5000 and parsed.trades[0].direct is True


def test_10b5_1_from_checkbox_or_footnote() -> None:
    by_box = parse_form4(form4(row("S", 10, 30, "D"), plan_box="1"))
    assert by_box.trades[0].under_10b5_1 is True

    by_note = parse_form4(
        form4(
            row("S", 10, 30, "D", footnote='<footnoteId id="F1"/>'),
            footnotes='<footnote id="F1">Sold under a Rule 10b5-1 trading plan adopted May 1.</footnote>',
        )
    )
    assert by_note.trades[0].under_10b5_1 is True

    unknown = parse_form4(form4(row("S", 10, 30, "D")))  # old filing: no checkbox, no note
    assert unknown.trades[0].under_10b5_1 is None


def test_roles_for_directors_and_large_holders() -> None:
    parsed = parse_form4(
        form4("", relationship="<isDirector>1</isDirector><isTenPercentOwner>true</isTenPercentOwner>")
    )
    assert parsed.owner_role == "Director, 10% owner"
    assert parsed.trades == []


def test_rejects_entity_declarations_and_bad_xml() -> None:
    with pytest.raises(Form4ParseError):
        parse_form4('<!DOCTYPE x [<!ENTITY a "aaaa">]><ownershipDocument/>')
    with pytest.raises(Form4ParseError):
        parse_form4("<ownershipDocument><unclosed>")
    with pytest.raises(Form4ParseError):
        parse_form4("<html></html>")


def test_summary_separates_planned_and_discretionary_sales() -> None:
    as_of = date(2026, 11, 15)
    trades = [
        Trade("A", date(2026, 11, 1), "P", 100, 10.0, False),
        Trade("B", date(2026, 10, 1), "P", 50, 10.0, False),
        Trade("A", date(2026, 9, 1), "S", 200, 10.0, True),
        Trade("C", date(2026, 8, 1), "S", 300, 10.0, None),
        Trade("C", date(2026, 8, 1), "F", 999, 10.0, None),  # tax withholding: not counted
        Trade("D", date(2025, 1, 1), "P", 999, 10.0, None),  # outside the window
    ]
    s = summarize(trades, as_of=as_of, days=180, market_cap=1_000_000)
    assert s["insider_buyers"] == 2
    assert s["insider_buy_value"] == 1500
    assert s["insider_sale_value"] == 5000
    assert s["insider_planned_sale_value"] == 2000
    assert s["insider_discretionary_sale_value"] == 3000
    assert s["insider_discretionary_sales_to_market_cap"] == pytest.approx(0.003)


def test_insider_rating() -> None:
    buying = rate({"insider_buyers": 3, "insider_discretionary_sales_to_market_cap": 0.0})
    selling = rate({"insider_buyers": 0, "insider_discretionary_sales_to_market_cap": 0.05})
    assert buying["institutional"].rating == pytest.approx(0.85)
    assert selling["institutional"].rating == pytest.approx(0.25)
    assert rate({})["institutional"].rating is None  # not loaded: unrated, not zero


# -- Sync with a fake SEC ---------------------------------------------------------


class FakeSec:
    name = "sec_edgar"

    def __init__(self, documents: dict[str, str], filed: date) -> None:
        self.documents = documents
        self.filed = filed
        self.downloads: list[str] = []

    def lookup(self, ticker: str) -> tuple[int, str]:
        return 1, "Test Holdings Inc"

    def company_facts(self, cik: int) -> dict[str, Any]:
        return {"facts": {}}

    def company_info(self, cik: int) -> CompanyInfo:
        filings = [FilingRef(acc, "4", self.filed, f"xslF345X05/{acc}.xml") for acc in self.documents]
        filings.append(FilingRef("old", "4", self.filed - timedelta(days=400), "old.xml"))
        filings.append(FilingRef("10q", "10-Q", self.filed, "q.htm"))
        return CompanyInfo(sic="7372", sic_description="SERVICES-PREPACKAGED SOFTWARE", filings=filings)

    def filing_document(self, cik: int, filing: FilingRef) -> str:
        self.downloads.append(filing.accession)
        return self.documents[filing.accession]


TODAY = date(2026, 11, 15)


@pytest.fixture
def sec() -> Iterator[FakeSec]:
    fake = FakeSec(
        {
            "a1": form4(row("P", 1000, 20.0, "A", day="2026-11-01")),
            "a2": form4(row("S", 500, 22.0, "D", day="2026-10-01"), owner="Roe Rick", plan_box="1"),
            "bad": "<html>not a form</html>",
        },
        filed=TODAY - timedelta(days=5),
    )
    app.dependency_overrides[fundamentals_client] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def test_sync_stores_filings_once(sec: FakeSec, db: Session) -> None:
    result = sync_insiders(db, sec, "TEST", today=TODAY)
    assert result.data is not None
    assert (result.data.filings_added, result.data.transactions_added) == (3, 2)
    assert result.data.unreadable_filings == 1
    assert sorted(sec.downloads) == ["a1", "a2", "bad"]  # not the old filing or the 10-Q

    stock = db.scalar(select(Stock).where(Stock.ticker == "TEST"))
    assert stock.insiders_synced_at is not None
    assert stock.industry == "Services-Prepackaged Software"

    again = sync_insiders(db, sec, "TEST", today=TODAY)
    assert again.data is not None and again.data.filings_added == 0
    assert len(sec.downloads) == 3  # nothing downloaded twice
    assert len(db.scalars(select(InsiderFiling)).all()) == 3


def test_activity_endpoint(client: TestClient, sec: FakeSec) -> None:
    assert client.get("/api/v1/stocks/TEST/insiders").json()["reason"] == "no_stored_data"
    synced = client.post("/api/v1/stocks/TEST/sync-insiders").json()
    assert synced["status"] == "ok"

    body = client.get("/api/v1/stocks/TEST/insiders?days=180").json()
    assert body["status"] == "ok"
    rows = body["data"]["transactions"]
    assert [(r["owner_name"], r["description"], r["under_10b5_1"]) for r in rows] == [
        ("Doe Jane", "Open-market purchase", None),
        ("Roe Rick", "Open-market sale", True),
    ]
    assert rows[0]["value"] == 20000
    assert body["data"]["summary"]["insider_buyers"] == 1

"""Turn SEC XBRL "company facts" into income, balance sheet and cash flow statements.

Pure functions with no I/O. Input is the JSON from
https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

How values are chosen:
  - Only 10-K and 10-Q filings (and their amendments) are used.
  - When a period is reported in several filings, the latest filing wins,
    so restatements replace the original figures.
  - For each line item, the first XBRL tag in its preference list that has a
    value for that period is used, because companies change tags over time.

Derived values: 10-Qs report cash flows only year-to-date, and no filing
reports a fourth quarter on its own. For additive items (revenue, net income,
cash flows) a missing quarter is calculated as the difference of two
year-to-date figures with the same start date, e.g. Q4 = full year minus nine
months. Every such value is listed in the statement's `derived_items`.
Per-share figures and share counts are never derived this way, because they
do not add up across quarters.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

StatementType = Literal["income", "balance", "cashflow"]
PeriodType = Literal["quarterly", "annual"]

ALLOWED_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "10-KT", "10-KT/A"}


@dataclass(frozen=True)
class LineItem:
    key: str
    tags: tuple[str, ...]
    unit: str = "USD"
    # Flow items can be summed across quarters; per-share values and counts cannot.
    additive: bool = True


INCOME_ITEMS: tuple[LineItem, ...] = (
    LineItem(
        "revenue",
        (
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "SalesRevenueNet",
            "RevenuesNetOfInterestExpense",
        ),
    ),
    LineItem("cost_of_revenue", ("CostOfRevenue", "CostOfGoodsAndServicesSold")),
    LineItem("gross_profit", ("GrossProfit",)),
    LineItem("research_and_development", ("ResearchAndDevelopmentExpense",)),
    LineItem("selling_general_and_administrative", ("SellingGeneralAndAdministrativeExpense",)),
    LineItem("sales_and_marketing", ("SellingAndMarketingExpense",)),
    LineItem("general_and_administrative", ("GeneralAndAdministrativeExpense",)),
    LineItem("operating_income", ("OperatingIncomeLoss",)),
    LineItem("interest_expense", ("InterestExpense", "InterestExpenseNonoperating")),
    LineItem(
        "pretax_income",
        (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ),
    ),
    LineItem("income_tax", ("IncomeTaxExpenseBenefit",)),
    LineItem("net_income", ("NetIncomeLoss", "ProfitLoss")),
    LineItem("eps_basic", ("EarningsPerShareBasic",), unit="USD/shares", additive=False),
    LineItem(
        "eps_diluted",
        ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"),
        unit="USD/shares",
        additive=False,
    ),
    LineItem(
        "diluted_shares",
        ("WeightedAverageNumberOfDilutedSharesOutstanding",),
        unit="shares",
        additive=False,
    ),
)

BALANCE_ITEMS: tuple[LineItem, ...] = (
    LineItem(
        "cash_and_equivalents",
        (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
    ),
    LineItem("short_term_investments", ("ShortTermInvestments", "MarketableSecuritiesCurrent")),
    LineItem("current_assets", ("AssetsCurrent",)),
    LineItem("total_assets", ("Assets",)),
    LineItem("current_liabilities", ("LiabilitiesCurrent",)),
    LineItem("total_liabilities", ("Liabilities",)),
    LineItem(
        "long_term_debt",
        (
            "LongTermDebtNoncurrent",
            "LongTermDebt",
            "LongTermDebtAndCapitalLeaseObligations",
            "LongTermNotesPayable",
        ),
    ),
    LineItem(
        "stockholders_equity",
        (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
    ),
    LineItem("shares_outstanding", ("CommonStockSharesOutstanding",), unit="shares"),
)

CASHFLOW_ITEMS: tuple[LineItem, ...] = (
    LineItem(
        "operating_cash_flow",
        (
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ),
    ),
    LineItem("capital_expenditures", ("PaymentsToAcquirePropertyPlantAndEquipment",)),
    LineItem(
        "investing_cash_flow",
        (
            "NetCashProvidedByUsedInInvestingActivities",
            "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
        ),
    ),
    LineItem(
        "financing_cash_flow",
        (
            "NetCashProvidedByUsedInFinancingActivities",
            "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
        ),
    ),
    LineItem(
        "depreciation_and_amortization",
        ("DepreciationDepletionAndAmortization", "DepreciationAndAmortization"),
    ),
    LineItem(
        "share_based_compensation", ("ShareBasedCompensation", "AllocatedShareBasedCompensationExpense")
    ),
    LineItem("share_repurchases", ("PaymentsForRepurchaseOfCommonStock",)),
    LineItem("dividends_paid", ("PaymentsOfDividends", "PaymentsOfDividendsCommonStock")),
)


@dataclass
class ParsedStatement:
    statement_type: StatementType
    period_type: PeriodType
    period_end: date
    fiscal_year: int
    fiscal_quarter: int | None
    filing_date: date | None
    line_items: dict[str, float] = field(default_factory=dict)
    derived_items: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Fact:
    start: date | None
    end: date
    value: float
    filed: date


@dataclass(frozen=True)
class _Period:
    """A reporting period end taken from a filing's own main period."""

    end: date
    fiscal_year: int
    fiscal_period: str  # Q1, Q2, Q3 or FY
    filed: date


def parse_company_facts(data: dict[str, Any]) -> list[ParsedStatement]:
    gaap = data.get("facts", {}).get("us-gaap", {})
    periods = _reporting_periods(gaap)
    if not periods:
        return []

    statements: list[ParsedStatement] = []
    for period in periods.values():
        quarter = {"Q1": 1, "Q2": 2, "Q3": 3, "FY": 4}.get(period.fiscal_period)
        statements += _build(gaap, period, "quarterly", quarter)
        if period.fiscal_period == "FY":
            statements += _build(gaap, period, "annual", None)
    statements.sort(key=lambda s: (s.statement_type, s.period_type, s.period_end))
    return statements


def _build(
    gaap: dict[str, Any], period: _Period, period_type: PeriodType, quarter: int | None
) -> list[ParsedStatement]:
    out: list[ParsedStatement] = []
    for statement_type, items, instant in (
        ("income", INCOME_ITEMS, False),
        ("balance", BALANCE_ITEMS, True),
        ("cashflow", CASHFLOW_ITEMS, False),
    ):
        statement = ParsedStatement(
            statement_type=statement_type,  # type: ignore[arg-type]
            period_type=period_type,
            period_end=period.end,
            fiscal_year=period.fiscal_year,
            fiscal_quarter=quarter,
            filing_date=period.filed,
        )
        for item in items:
            found = _value(gaap, item, period.end, period_type, instant)
            if found is None:
                continue
            value, derived = found
            statement.line_items[item.key] = value
            if derived:
                statement.derived_items.append(item.key)
        if statement.line_items:
            out.append(statement)
    return out


def _value(
    gaap: dict[str, Any], item: LineItem, end: date, period_type: PeriodType, instant: bool
) -> tuple[float, bool] | None:
    """Value of `item` for the period ending `end`, and whether it was derived."""
    for tag in item.tags:
        facts = _facts(gaap, tag, item.unit)
        if not facts:
            continue
        if instant:
            match = next((f for f in facts if f.start is None and f.end == end), None)
            if match:
                return match.value, False
            continue

        durations = [f for f in facts if f.start is not None]
        wanted = (80, 100) if period_type == "quarterly" else (350, 380)
        direct = next(
            (f for f in durations if f.end == end and wanted[0] <= _days(f) <= wanted[1]), None
        )
        if direct:
            return direct.value, False
        if period_type == "quarterly" and item.additive:
            derived = _derive_quarter(durations, end)
            if derived is not None:
                return derived, True
    return None


def _derive_quarter(durations: list[_Fact], end: date) -> float | None:
    """Quarter ending `end` as (year-to-date to `end`) minus (year-to-date one quarter earlier)."""
    for longer in (f for f in durations if f.end == end and _days(f) > 100):
        for shorter in durations:
            if shorter.start != longer.start or shorter.end >= end:
                continue
            gap = (end - shorter.end).days
            if 80 <= gap <= 100:
                return longer.value - shorter.value
    return None


def _facts(gaap: dict[str, Any], tag: str, unit: str) -> list[_Fact]:
    """Facts for one tag and unit from 10-K/10-Q filings, latest filing per period."""
    rows = gaap.get(tag, {}).get("units", {}).get(unit, [])
    latest: dict[tuple[date | None, date], _Fact] = {}
    for row in rows:
        if row.get("form") not in ALLOWED_FORMS:
            continue
        try:
            end = date.fromisoformat(row["end"])
            start = date.fromisoformat(row["start"]) if row.get("start") else None
            filed = date.fromisoformat(row["filed"])
            value = float(row["val"])
        except (KeyError, TypeError, ValueError):
            continue
        key = (start, end)
        if key not in latest or filed > latest[key].filed:
            latest[key] = _Fact(start=start, end=end, value=value, filed=filed)
    return list(latest.values())


def _reporting_periods(gaap: dict[str, Any]) -> dict[date, _Period]:
    """Each 10-K/10-Q's own period end, with its fiscal year and period label.

    Within one filing the latest `end` date is the period the filing covers;
    earlier dates in it are comparatives from prior periods.
    """
    by_filing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for concept in gaap.values():
        for rows in concept.get("units", {}).values():
            for row in rows:
                if row.get("form") in ALLOWED_FORMS and row.get("accn") and row.get("end"):
                    by_filing[row["accn"]].append(row)

    periods: dict[date, _Period] = {}
    for rows in by_filing.values():
        try:
            end = max(date.fromisoformat(r["end"]) for r in rows)
        except ValueError:
            continue
        current = next((r for r in rows if r["end"] == end.isoformat()), rows[0])
        fiscal_year, fiscal_period = current.get("fy"), current.get("fp")
        if not isinstance(fiscal_year, int) or fiscal_period not in {"Q1", "Q2", "Q3", "FY"}:
            continue
        filed = date.fromisoformat(current["filed"])
        existing = periods.get(end)
        # Keep the original filing's labels; amendments only re-report the period.
        if existing is None or filed < existing.filed:
            periods[end] = _Period(end, fiscal_year, fiscal_period, filed)
    return periods


def _days(fact: _Fact) -> int:
    assert fact.start is not None
    return (fact.end - fact.start + timedelta(days=1)).days

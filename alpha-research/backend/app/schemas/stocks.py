"""Schemas for stock reference data, quotes, financials, technicals and scores."""

from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class StockSummary(ORMModel):
    ticker: str
    name: str
    exchange: str | None
    sector: str | None
    industry: str | None
    currency: str


class Quote(BaseModel):
    ticker: str
    price: float
    change: float | None
    change_percent: float | None
    previous_close: float | None
    volume: int | None
    timestamp: datetime
    # Which price feed this is, so nobody mistakes it for a consolidated quote.
    feed: str


class PriceSyncResult(BaseModel):
    ticker: str
    bars_added: int
    bars_stored: int
    first_date: date | None
    last_date: date | None


class FinancialsSyncResult(BaseModel):
    ticker: str
    cik: int
    company_name: str
    statements_stored: int
    quarterly_periods: int
    annual_periods: int
    latest_period_end: date | None


class FinancialStatementOut(ORMModel):
    statement_type: str
    period_type: str
    fiscal_year: int
    fiscal_quarter: int | None
    period_end: date
    filing_date: date | None
    currency: str
    line_items: dict[str, float | None]
    derived_items: list[str]
    source: str
    retrieved_at: datetime


class IndicatorValue(BaseModel):
    """Latest value of one indicator. `value` is null when history is too short."""

    name: str
    value: float | None
    required_bars: int


class TechnicalSnapshot(BaseModel):
    ticker: str
    as_of_date: date
    bars_available: int
    last_close: float
    indicators: list[IndicatorValue]


class ScoreCategory(BaseModel):
    key: str
    label: str
    weight: float


class ScoringMethodology(BaseModel):
    version: str
    categories: list[ScoreCategory]
    bands: list[dict[str, str | int]]


class RankingEntry(BaseModel):
    rank: int
    ticker: str
    name: str
    total_score: float
    coverage: float
    interpretation: str
    risk_class: str | None
    as_of: date


class ScoreInput(BaseModel):
    """One input to a category score."""

    metric: str
    label: str
    value: float | None
    value_text: str | None  # e.g. "24.6×"; None for scores saved before breakdowns
    rating: float  # 0-1
    scale: str | None  # e.g. "Full marks at 10.0× or lower; zero at 60.0× or higher"
    explanation: str | None = None  # what the value says about the stock, in plain language


class CategoryScore(BaseModel):
    key: str
    label: str
    weight: float
    points: float | None  # None when the category could not be rated
    inputs: dict[str, float]  # sub-rating label -> rating (0-1) for inputs that had data
    breakdown: list[ScoreInput]
    missing: list[str]  # inputs that had no data
    minimum_inputs: int  # inputs needed to rate the category
    summary: str | None = None  # strongest and weakest inputs
    unrated_reason: str | None


class StockScoreOut(BaseModel):
    ticker: str
    as_of: date
    total_score: float
    interpretation: str
    coverage: float
    categories: list[CategoryScore]
    methodology_version: str
    risk_class: str | None
    notes: str | None
    calculated_at: datetime


class MetricsSnapshot(BaseModel):
    ticker: str
    as_of: date
    values: dict[str, float | None]


class InsiderSyncResult(BaseModel):
    ticker: str
    filings_checked: int
    filings_added: int
    transactions_added: int
    filings_remaining: int
    unreadable_filings: int
    # Form 4s where this company reported trades in another company's shares.
    other_issuer_filings: int = 0


class InsiderTransactionOut(BaseModel):
    transaction_date: date
    filed_on: date
    owner_name: str
    owner_role: str
    code: str
    description: str
    acquired: bool
    shares: float
    price: float | None
    value: float | None
    shares_after: float | None
    under_10b5_1: bool | None


class InsiderActivity(BaseModel):
    ticker: str
    days: int
    synced_at: datetime
    summary: dict[str, float | None]
    transactions: list[InsiderTransactionOut]


class EventsSyncResult(BaseModel):
    ticker: str
    events_added: int
    events_stored: int


class EventItem(BaseModel):
    code: str
    label: str
    kind: str


class CatalystEvent(BaseModel):
    filed_on: date
    form: str
    headline: str
    kind: str
    items: list[EventItem]
    url: str


class CatalystFeed(BaseModel):
    ticker: str
    synced_at: datetime
    # Estimated from the timing of past earnings releases, not announced.
    next_earnings_estimate: date | None
    days_to_next_earnings: int | None
    events: list[CatalystEvent]


class PeerRow(BaseModel):
    ticker: str
    name: str
    is_subject: bool
    score: float | None
    metrics: dict[str, float | None]


class IndustryComparison(BaseModel):
    ticker: str
    industry: str | None
    sic_code: str
    peer_group: str  # e.g. "SIC 7372" or "SIC 73xx" when widened
    # metric -> percentile among peers (1 = best), None when not comparable
    positioning: dict[str, float | None]
    valuation: dict[str, float | None]
    rows: list[PeerRow]  # the stock first, then its peers

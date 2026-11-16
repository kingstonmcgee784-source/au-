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
    volume: int | None
    timestamp: datetime
    is_delayed: bool


class FinancialStatementOut(ORMModel):
    statement_type: str
    period_type: str
    fiscal_year: int
    fiscal_quarter: int | None
    period_end: date
    filing_date: date | None
    currency: str
    line_items: dict[str, float | None]
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
    interpretation: str
    risk_class: str | None
    as_of: date


class StockScoreOut(BaseModel):
    ticker: str
    as_of: date
    total_score: float
    interpretation: str
    category_scores: dict[str, float]
    methodology_version: str
    risk_class: str | None
    notes: str | None

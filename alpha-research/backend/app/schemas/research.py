"""Schemas for research reports, market overview and watchlists."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, Ticker


class ResearchReportSummary(ORMModel):
    id: int
    title: str
    summary: str | None
    origin: str
    status: str
    report_date: date
    created_at: datetime


class ResearchReportOut(ResearchReportSummary):
    body_markdown: str


class GenerateReportRequest(BaseModel):
    ticker: Ticker


class IndexLevel(BaseModel):
    symbol: str
    name: str
    level: float
    change_percent: float | None


class MarketOverview(BaseModel):
    indices: list[IndexLevel]


class WatchlistItemOut(ORMModel):
    id: int
    ticker: str
    notes: str | None
    added_at: datetime


class WatchlistOut(ORMModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    items: list[WatchlistItemOut]


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)


class WatchlistItemCreate(BaseModel):
    ticker: Ticker
    notes: str | None = Field(default=None, max_length=2000)

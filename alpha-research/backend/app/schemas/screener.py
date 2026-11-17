"""Schemas for batch scans and the screener."""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import normalize_ticker

MAX_TICKERS = 200


class ScanRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    tickers: list[str] = Field(default_factory=list)
    watchlist_id: int | None = None

    @field_validator("tickers")
    @classmethod
    def _clean(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(normalize_ticker(v) for v in values if v.strip()))
        if len(cleaned) > MAX_TICKERS:
            raise ValueError(f"A scan can include at most {MAX_TICKERS} tickers")
        return cleaned


class ScanItemOut(BaseModel):
    ticker: str
    status: str
    score: float | None
    message: str | None


class ScanOut(BaseModel):
    id: int
    name: str
    status: str
    resume_at: datetime | None
    message: str | None
    created_at: datetime
    finished_at: datetime | None
    total: int
    completed: int
    items: list[ScanItemOut]


class ScreenerRow(BaseModel):
    ticker: str
    name: str
    industry: str | None
    score: float
    coverage: float
    interpretation: str
    risk_class: str | None
    scored_on: date
    metrics: dict[str, float | None]

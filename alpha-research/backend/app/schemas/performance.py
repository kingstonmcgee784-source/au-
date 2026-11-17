"""Schemas for recorded calls (recommendations) and their track record."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import Ticker


class TrackCallRequest(BaseModel):
    ticker: Ticker
    thesis: str | None = Field(default=None, max_length=2000)
    horizon_days: int = Field(default=90, ge=7, le=365)


class CallOut(BaseModel):
    id: int
    ticker: str
    name: str
    recommended_on: date
    reference_price: float
    reference_price_source: str
    score: float | None
    risk_class: str | None
    thesis: str | None
    horizon_days: int
    created_at: datetime
    # True only on the day the call was recorded (see services.performance).
    deletable: bool
    # return_now, return_1w/1m/3m, max_gain, max_drawdown, benchmark returns
    # and excess returns; None means pending or not available.
    performance: dict[str, float | None]


class TrackRecord(BaseModel):
    calls: list[CallOut]
    # horizon ("1w", "1m", "3m", "now") -> statistics over calls that reached it
    summary: dict[str, dict[str, float | None]]
    benchmarks_missing: list[str]


class PriceUpdate(BaseModel):
    ticker: str
    ok: bool
    message: str


class PriceUpdateResult(BaseModel):
    results: list[PriceUpdate]

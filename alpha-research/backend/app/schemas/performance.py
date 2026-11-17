"""Schemas for recorded calls (recommendations) and their track record."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import Ticker


class TrackCallRequest(BaseModel):
    ticker: Ticker
    thesis: str | None = Field(default=None, max_length=2000)
    horizon_days: int = Field(default=91, ge=7, le=365)  # about 3 months


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
    # True only within 24 hours of the call being recorded (see services.performance).
    deletable: bool
    # The holding plan recorded with the call (None for older calls).
    stop_pct: float | None = None
    target_pct: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    # open | stop_hit | target_hit | time_up | no_plan; the date is when the
    # stop or target was first reached, or when the hold period ends.
    plan_status: str = "no_plan"
    plan_status_date: date | None = None
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

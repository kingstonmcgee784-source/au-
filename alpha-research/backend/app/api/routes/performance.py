"""Recorded calls and their track record."""

from fastapi import APIRouter, Response, status

from app.api.deps import AppSettings, DbSession, MarketData
from app.schemas.common import DataResponse
from app.schemas.performance import CallOut, PriceUpdateResult, TrackCallRequest, TrackRecord
from app.services import performance

router = APIRouter(prefix="/recommendations", tags=["performance"])


@router.get("", response_model=TrackRecord)
def track_record(db: DbSession) -> TrackRecord:
    return performance.track_record(db)


@router.post("", response_model=DataResponse[CallOut], status_code=status.HTTP_201_CREATED)
def track_call(
    db: DbSession, market: MarketData, settings: AppSettings, payload: TrackCallRequest
) -> DataResponse[CallOut]:
    """Record a call at the latest stored price, re-scoring the stock at that price first."""
    return performance.track_call(db, market, payload, history_years=settings.price_history_years)


@router.delete("/{call_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_call(db: DbSession, call_id: int) -> Response:
    """Allowed only within 24 hours of the call being recorded."""
    performance.delete_call(db, call_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/update-prices", response_model=DataResponse[PriceUpdateResult])
def update_prices(
    db: DbSession, market: MarketData, settings: AppSettings
) -> DataResponse[PriceUpdateResult]:
    """Refresh prices for every tracked stock and the benchmarks (at most every 6 hours each)."""
    return performance.update_prices(db, market, history_years=settings.price_history_years)

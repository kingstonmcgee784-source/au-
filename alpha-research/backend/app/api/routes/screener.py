"""Batch scans and the screener table."""

from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.deps import DbSession
from app.schemas.screener import ScanOut, ScanRequest, ScreenerRow
from app.services import screener

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("", response_model=list[ScreenerRow])
def screener_table(db: DbSession) -> list[ScreenerRow]:
    """Every scored stock with its latest score and metrics. Filter and sort on the client."""
    return screener.screener_rows(db)


@router.get("/scans", response_model=list[ScanOut])
def list_scans(db: DbSession, limit: Annotated[int, Query(ge=1, le=50)] = 10) -> list[ScanOut]:
    return screener.list_scans(db, limit)


@router.post("/scans", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
def start_scan(db: DbSession, request: Request, payload: ScanRequest) -> ScanOut:
    """Score a list of tickers (or a watchlist) in the background."""
    scan = screener.create_scan(db, payload)
    request.app.state.scan_runner.start(scan.id)
    return scan


@router.get("/scans/{run_id}", response_model=ScanOut)
def get_scan(db: DbSession, run_id: int) -> ScanOut:
    return screener.get_scan(db, run_id)


@router.post("/scans/{run_id}/cancel", response_model=ScanOut)
def cancel_scan(db: DbSession, run_id: int) -> ScanOut:
    return screener.cancel_scan(db, run_id)

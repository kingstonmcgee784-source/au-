"""Batch scans that score many tickers, and the screener table.

A scan runs in a background thread inside the API process, one ticker at a
time. When the market data provider's request limit is reached, the scan
waits (status "waiting") and resumes on its own. Scans survive a restart:
unfinished ones are picked up again when the API starts.

After every ticker is processed, each scored stock is re-scored from stored
data (no network), so stocks scanned early can be compared with industry
peers that were scanned after them.
"""

import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis import scoring
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.db.session import SessionLocal
from app.models import ScreenRun, ScreenRunItem, Stock, StockScore, Watchlist
from app.providers.base import FundamentalsSource, MarketDataProvider
from app.providers.registry import get_fundamentals_client, get_market_data_provider
from app.schemas.common import DataStatus, UnavailableReason
from app.schemas.screener import ScanItemOut, ScanOut, ScanRequest, ScreenerRow
from app.services import ingestion, scoring_pipeline
from app.services.industry import latest_metrics_by_stock

logger = logging.getLogger(__name__)

RATE_LIMIT_WAIT = timedelta(minutes=10)
ACTIVE = ("queued", "running", "waiting")


# -- Creating and reading scans --------------------------------------------------


def create_scan(db: Session, request: ScanRequest) -> ScanOut:
    tickers = list(request.tickers)
    name = request.name
    if request.watchlist_id is not None:
        watchlist = db.get(Watchlist, request.watchlist_id)
        if watchlist is None:
            raise NotFoundError(f"Watchlist {request.watchlist_id} does not exist")
        tickers = list(dict.fromkeys([*tickers, *(item.ticker for item in watchlist.items)]))
        name = name or f"Watchlist: {watchlist.name}"
    if not tickers:
        raise ConflictError("Add at least one ticker, or choose a watchlist with tickers on it")
    if db.scalar(select(func.count(ScreenRun.id)).where(ScreenRun.status.in_(ACTIVE))):
        raise ConflictError("A scan is already in progress. Wait for it to finish or cancel it.")

    run = ScreenRun(name=name or f"{len(tickers)} tickers", status="queued")
    run.items = [ScreenRunItem(position=i, ticker=t) for i, t in enumerate(tickers)]
    db.add(run)
    db.commit()
    return scan_out(run)


def list_scans(db: Session, limit: int) -> list[ScanOut]:
    runs = db.scalars(select(ScreenRun).order_by(ScreenRun.id.desc()).limit(limit)).all()
    return [scan_out(r) for r in runs]


def get_scan(db: Session, run_id: int) -> ScanOut:
    return scan_out(_get(db, run_id))


def cancel_scan(db: Session, run_id: int) -> ScanOut:
    run = _get(db, run_id)
    if run.status in ACTIVE:
        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)
        run.message = "Cancelled."
        db.commit()
    return scan_out(run)


def scan_out(run: ScreenRun) -> ScanOut:
    return ScanOut(
        id=run.id,
        name=run.name,
        status=run.status,
        resume_at=run.resume_at,
        message=run.message,
        created_at=run.created_at,
        finished_at=run.finished_at,
        total=len(run.items),
        completed=sum(1 for i in run.items if i.status != "pending"),
        items=[
            ScanItemOut(ticker=i.ticker, status=i.status, score=i.score, message=i.message)
            for i in run.items
        ],
    )


def _get(db: Session, run_id: int) -> ScreenRun:
    run = db.get(ScreenRun, run_id)
    if run is None:
        raise NotFoundError(f"Scan {run_id} does not exist")
    return run


# -- Running a scan --------------------------------------------------------------


def process_scan(
    run_id: int,
    *,
    market: MarketDataProvider | None,
    fundamentals: FundamentalsSource | None,
    history_years: int,
    session_factory: Callable[[], Session] = SessionLocal,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Work through a scan until it is done or cancelled. Blocking."""
    while True:
        with session_factory() as db:
            run = db.get(ScreenRun, run_id)
            if run is None or run.status not in ACTIVE:
                return
            now = datetime.now(UTC)
            if run.resume_at and run.resume_at > now:
                wait = (run.resume_at - now).total_seconds()
                db.close()
                sleep(min(wait, 30.0))  # wake up regularly to notice a cancel
                continue

            item = next((i for i in run.items if i.status == "pending"), None)
            if item is None:
                _rescore(db, run)
                run.status = "done"
                run.finished_at = datetime.now(UTC)
                scored = sum(1 for i in run.items if i.status == "scored")
                run.message = f"Scored {scored} of {len(run.items)} tickers."
                db.commit()
                return

            run.status, run.resume_at, run.message = "running", None, f"Scoring {item.ticker}…"
            db.commit()

            prices = ingestion.sync_prices(db, market, item.ticker, history_years=history_years)
            if prices.reason == UnavailableReason.RATE_LIMITED:
                run.status = "waiting"
                run.resume_at = datetime.now(UTC) + RATE_LIMIT_WAIT
                run.message = (
                    "Waiting for the market data provider's hourly request limit to reset. "
                    "The scan continues automatically."
                )
                db.commit()
                continue
            if prices.reason == UnavailableReason.UNKNOWN_TICKER:
                item.status, item.message = "failed", prices.message
                item.finished_at = datetime.now(UTC)
                db.commit()
                continue

            result = scoring_pipeline.score_stock(
                db,
                item.ticker,
                market=market,
                fundamentals=fundamentals,
                refresh=True,
                history_years=history_years,
            )
            item.finished_at = datetime.now(UTC)
            if result.status == DataStatus.OK and result.data:
                item.status, item.score, item.message = "scored", result.data.total_score, None
            elif result.reason in (
                UnavailableReason.INSUFFICIENT_HISTORY,
                UnavailableReason.NO_STORED_DATA,
            ):
                item.status, item.message = "not_scored", result.message
            else:
                item.status, item.message = "failed", result.message or prices.message
            db.commit()


def _rescore(db: Session, run: ScreenRun) -> None:
    """Re-score from stored data so industry comparisons include later peers."""
    for item in run.items:
        if item.status != "scored":
            continue
        result = scoring_pipeline.score_stock(
            db, item.ticker, market=None, fundamentals=None, refresh=False, history_years=1
        )
        if result.status == DataStatus.OK and result.data:
            item.score = result.data.total_score


class ScanRunner:
    """Starts scans in background threads; one thread per scan at most."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._threads: dict[int, threading.Thread] = {}
        self._lock = threading.Lock()

    def start(self, run_id: int) -> None:
        with self._lock:
            existing = self._threads.get(run_id)
            if existing and existing.is_alive():
                return
            thread = threading.Thread(
                target=self._run, args=(run_id,), name=f"scan-{run_id}", daemon=True
            )
            self._threads[run_id] = thread
            thread.start()

    def resume_unfinished(self) -> None:
        with SessionLocal() as db:
            ids = db.scalars(select(ScreenRun.id).where(ScreenRun.status.in_(ACTIVE))).all()
        for run_id in ids:
            self.start(run_id)

    def _run(self, run_id: int) -> None:
        try:
            process_scan(
                run_id,
                market=get_market_data_provider(self._settings),
                fundamentals=get_fundamentals_client(self._settings),
                history_years=self._settings.price_history_years,
            )
        except Exception:  # keep the API alive; record the failure on the scan
            logger.exception("Scan %s stopped unexpectedly", run_id)
            with SessionLocal() as db:
                run = db.get(ScreenRun, run_id)
                if run is not None and run.status in ACTIVE:
                    run.status = "done"
                    run.finished_at = datetime.now(UTC)
                    run.message = (
                        "The scan stopped because of an unexpected error; see the API log."
                    )
                    db.commit()


# -- The screener table -----------------------------------------------------------


def screener_rows(db: Session) -> list[ScreenerRow]:
    """Every scored stock with its latest score and metrics."""
    newest_first = select(
        StockScore.id,
        func.row_number()
        .over(
            partition_by=StockScore.stock_id,
            order_by=(StockScore.as_of.desc(), StockScore.id.desc()),
        )
        .label("position"),
    ).subquery()
    rows = db.execute(
        select(StockScore, Stock)
        .join(newest_first, StockScore.id == newest_first.c.id)
        .join(Stock, Stock.id == StockScore.stock_id)
        .where(newest_first.c.position == 1)
        .order_by(StockScore.total_score.desc())
    ).all()
    metrics = latest_metrics_by_stock(db)
    return [
        ScreenerRow(
            ticker=stock.ticker,
            name=stock.name,
            industry=stock.industry,
            score=score.total_score,
            coverage=score.coverage,
            interpretation=scoring.interpret(score.total_score),
            risk_class=score.risk_class,
            scored_on=score.as_of,
            metrics=metrics.get(stock.id, {}),
        )
        for score, stock in rows
    ]

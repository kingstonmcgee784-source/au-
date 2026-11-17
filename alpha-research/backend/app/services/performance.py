"""Record calls and measure them against later prices and the benchmarks.

Recorded calls are never edited. A call can be deleted only on the day it was
recorded, to fix a mistake; after that it stays in the track record, good or
bad.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.performance import HORIZONS, Bar, call_performance, summary
from app.core.errors import ConflictError, NotFoundError
from app.models import HistoricalPrice, Recommendation, Stock, StockScore
from app.providers.base import MarketDataProvider
from app.schemas.common import DataResponse, DataStatus, UnavailableReason, ok, unavailable
from app.schemas.performance import (
    CallOut,
    PriceUpdate,
    PriceUpdateResult,
    TrackCallRequest,
    TrackRecord,
)
from app.services import ingestion
from app.services.stocks import LOCAL_SOURCE, find_stock

BENCHMARKS = ("SPY", "QQQ", "IWM")


def track_call(
    db: Session,
    market: MarketDataProvider | None,
    request: TrackCallRequest,
    *,
    history_years: int,
) -> DataResponse[CallOut]:
    ticker = request.ticker
    stock = find_stock(db, ticker)
    score = (
        db.scalar(
            select(StockScore)
            .where(StockScore.stock_id == stock.id)
            .order_by(StockScore.as_of.desc(), StockScore.id.desc())
            .limit(1)
        )
        if stock
        else None
    )
    if stock is None or score is None:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"Calculate a score for {ticker} before tracking it, so the call records what "
            "the score was.",
        )
    latest = db.scalar(
        select(HistoricalPrice)
        .where(HistoricalPrice.stock_id == stock.id)
        .order_by(HistoricalPrice.date.desc())
        .limit(1)
    )
    if latest is None:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"No stored price for {ticker}. Load its price history first.",
        )
    exists = db.scalar(
        select(Recommendation.id).where(
            Recommendation.stock_id == stock.id, Recommendation.recommended_on == latest.date
        )
    )
    if exists:
        raise ConflictError(f"{ticker} is already tracked from {latest.date.isoformat()}")

    # Benchmarks need prices from the call date onward.
    for symbol in BENCHMARKS:
        ingestion.sync_prices(db, market, symbol, history_years=history_years)

    reference = latest.adjusted_close if latest.adjusted_close is not None else latest.close
    call = Recommendation(
        stock_id=stock.id,
        recommended_on=latest.date,
        reference_price=reference,
        reference_price_source=f"{latest.source} adjusted close on {latest.date.isoformat()}",
        horizon_days=request.horizon_days,
        score_at_recommendation=score.total_score,
        risk_class=score.risk_class,
        thesis=request.thesis,
        status="open",
    )
    db.add(call)
    db.commit()
    return ok(_call_out(db, call, stock), source=LOCAL_SOURCE, as_of=call.created_at)


def track_record(db: Session) -> TrackRecord:
    rows = db.execute(
        select(Recommendation, Stock)
        .join(Stock, Stock.id == Recommendation.stock_id)
        .order_by(Recommendation.recommended_on.desc(), Recommendation.id.desc())
    ).all()
    benchmarks = {symbol: _series_for(db, symbol) for symbol in BENCHMARKS}
    calls = [_call_out(db, call, stock, benchmarks) for call, stock in rows]

    stats: dict[str, dict[str, float | None]] = {}
    for horizon in [*HORIZONS, "now"]:
        values = [c.performance[f"return_{horizon}"] for c in calls]
        excess = [c.performance.get(f"excess_vs_spy_{horizon}") for c in calls]
        stats[horizon] = summary(
            [v for v in values if v is not None], [e for e in excess if e is not None]
        )
    return TrackRecord(
        calls=calls,
        summary=stats,
        benchmarks_missing=[s for s, series in benchmarks.items() if not series],
    )


def delete_call(db: Session, call_id: int) -> None:
    call = db.get(Recommendation, call_id)
    if call is None:
        raise NotFoundError(f"Tracked call {call_id} does not exist")
    if call.created_at.date() != datetime.now(UTC).date():
        raise ConflictError(
            "Recorded calls can only be removed on the day they were made, so the track "
            "record cannot be edited after the fact."
        )
    db.delete(call)
    db.commit()


def update_prices(
    db: Session, market: MarketDataProvider | None, *, history_years: int
) -> DataResponse[PriceUpdateResult]:
    if market is None:
        return unavailable(
            UnavailableReason.PROVIDER_NOT_CONFIGURED,
            "Updating prices needs a market data provider, and none is configured.",
        )
    tickers = sorted(
        set(
            db.scalars(
                select(Stock.ticker).join(Recommendation, Recommendation.stock_id == Stock.id)
            )
        )
    )
    results = []
    for ticker in [*tickers, *BENCHMARKS]:
        result = ingestion.sync_prices(db, market, ticker, history_years=history_years)
        if result.status == DataStatus.OK and result.data:
            results.append(
                PriceUpdate(
                    ticker=ticker, ok=True, message=f"{result.data.bars_added} new daily bars"
                )
            )
        else:
            results.append(PriceUpdate(ticker=ticker, ok=False, message=result.message or ""))
    return ok(PriceUpdateResult(results=results), source=market.name, as_of=datetime.now(UTC))


def _series_for(db: Session, ticker: str) -> list[Bar]:
    stock = find_stock(db, ticker)
    return _series(db, stock.id) if stock else []


def _series(db: Session, stock_id: int) -> list[Bar]:
    rows = db.execute(
        select(HistoricalPrice.date, HistoricalPrice.close, HistoricalPrice.adjusted_close)
        .where(HistoricalPrice.stock_id == stock_id)
        .order_by(HistoricalPrice.date)
    ).all()
    return [Bar(d, adj if adj is not None else c) for d, c, adj in rows]


def _call_out(
    db: Session,
    call: Recommendation,
    stock: Stock,
    benchmarks: dict[str, list[Bar]] | None = None,
) -> CallOut:
    benchmarks = benchmarks or {symbol: _series_for(db, symbol) for symbol in BENCHMARKS}
    return CallOut(
        id=call.id,
        ticker=stock.ticker,
        name=stock.name,
        recommended_on=call.recommended_on,
        reference_price=call.reference_price,
        reference_price_source=call.reference_price_source,
        score=call.score_at_recommendation,
        risk_class=call.risk_class,
        thesis=call.thesis,
        horizon_days=call.horizon_days,
        created_at=call.created_at,
        deletable=call.created_at.date() == datetime.now(UTC).date(),
        performance=call_performance(
            call.recommended_on, call.reference_price, _series(db, stock.id), benchmarks
        ),
    )

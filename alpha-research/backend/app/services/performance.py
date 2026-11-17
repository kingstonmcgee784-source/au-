"""Record calls and measure them against later prices and the benchmarks.

Recorded calls are never edited. A call can be deleted only within 24 hours of
being recorded, to fix a mistake; after that it stays in the track record,
good or bad.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import sector
from app.analysis.holding import plan_status
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
from app.services import holding, ingestion, scoring_pipeline
from app.services.stocks import LOCAL_SOURCE, find_stock

BENCHMARKS = ("SPY", "QQQ", "IWM")
# Long enough to fix a mistake, short enough that results cannot be curated.
DELETE_WINDOW = timedelta(hours=24)
# A long weekend plus a holiday is at most 4 days without a new close.
MAX_PRICE_AGE_DAYS = 5
RATE_LIMIT_SKIP = "Not updated: Tiingo's hourly request limit was reached."


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
    # Load the newest prices first, so the call is not backdated to an old
    # stored price (which would let a call "predict" moves already seen).
    ingestion.sync_prices(db, market, ticker, history_years=history_years)
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
    age = (datetime.now(UTC).date() - latest.date).days
    if age > MAX_PRICE_AGE_DAYS:
        return unavailable(
            UnavailableReason.INSUFFICIENT_HISTORY,
            f"The latest stored price for {ticker} is from {latest.date.isoformat()}, "
            f"{age} days ago, and fresh prices could not be loaded. A call must be recorded "
            "at a current price; try again when market data is available.",
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
    # Re-score from stored data (no network), so the recorded score is the one
    # for this price date rather than an older score.
    current = scoring_pipeline.score_stock(
        db, ticker, market=None, fundamentals=None, refresh=False, history_years=history_years
    )
    if current.status != DataStatus.OK or current.data is None:
        return unavailable(
            current.reason or UnavailableReason.NO_STORED_DATA,
            f"Could not score {ticker} at its latest price: {current.message}",
        )
    # Record the holding plan as it stood when the call was made, so later
    # changes to the rules or prices cannot move the goalposts.
    plan = holding.get_plan(db, ticker)
    stop_pct = plan.data.stop_pct if plan.status == DataStatus.OK and plan.data else None
    target_pct = plan.data.target_pct if plan.status == DataStatus.OK and plan.data else None
    call = Recommendation(
        stock_id=stock.id,
        recommended_on=latest.date,
        reference_price=reference,
        reference_price_source=f"{latest.source} adjusted close on {latest.date.isoformat()}",
        horizon_days=request.horizon_days,
        score_at_recommendation=current.data.total_score,
        risk_class=current.data.risk_class,
        thesis=request.thesis,
        stop_pct=stop_pct,
        target_pct=target_pct,
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
    # Calls recorded before holding plans existed get one from the prices
    # known on the call date, never later ones.
    filled = False
    for call, _stock in rows:
        if call.stop_pct is None:
            levels = holding.levels_as_of(db, call.stock_id, call.recommended_on)
            if levels:
                call.stop_pct, call.target_pct = levels
                filled = True
    if filled:
        db.commit()
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
    if datetime.now(UTC) - call.created_at > DELETE_WINDOW:
        raise ConflictError(
            "Recorded calls can only be removed within 24 hours of being made, so the track "
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
    tracked = db.execute(
        select(Stock.ticker, Stock.sic_code).join(
            Recommendation, Recommendation.stock_id == Stock.id
        )
    ).all()
    tickers = sorted({ticker for ticker, _ in tracked})
    # Sector and oil ETFs, so the holding plans' warnings stay current.
    context = sorted(
        {symbol for _, sic in tracked for symbol, _l, _k in sector.context_symbols(sic)}
        - set(BENCHMARKS)
    )
    results = []
    limited = False
    for ticker in [*tickers, *BENCHMARKS, *context]:
        if limited:
            # More requests would only fail too, and still count against the limit.
            results.append(PriceUpdate(ticker=ticker, ok=False, message=RATE_LIMIT_SKIP))
            continue
        result = ingestion.sync_prices(db, market, ticker, history_years=history_years)
        if result.reason == UnavailableReason.RATE_LIMITED:
            limited = True
            results.append(PriceUpdate(ticker=ticker, ok=False, message=RATE_LIMIT_SKIP))
            continue
        if result.status == DataStatus.OK and result.data:
            results.append(
                PriceUpdate(
                    ticker=ticker, ok=True, message=f"{result.data.bars_added} new daily bars"
                )
            )
        else:
            results.append(PriceUpdate(ticker=ticker, ok=False, message=result.message or ""))
    return ok(
        PriceUpdateResult(results=results, rate_limited=limited),
        source=market.name,
        as_of=datetime.now(UTC),
    )


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
    series = _series(db, stock.id)
    status, status_date = plan_status(
        call.recommended_on,
        call.stop_pct,
        call.target_pct,
        call.horizon_days,
        [(b.date, b.close) for b in series if b.date > call.recommended_on],
        call.reference_price,
        datetime.now(UTC).date(),
    )
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
        deletable=datetime.now(UTC) - call.created_at <= DELETE_WINDOW,
        stop_pct=call.stop_pct,
        target_pct=call.target_pct,
        stop_price=call.reference_price * (1 + call.stop_pct)
        if call.stop_pct is not None
        else None,
        target_price=(
            call.reference_price * (1 + call.target_pct) if call.target_pct is not None else None
        ),
        plan_status=status,
        plan_status_date=status_date,
        performance=call_performance(call.recommended_on, call.reference_price, series, benchmarks),
    )

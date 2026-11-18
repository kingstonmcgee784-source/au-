"""Market-wide conditions from stored ETF prices."""

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import market
from app.models import HistoricalPrice
from app.providers.base import MarketDataProvider
from app.schemas.common import DataResponse, DataStatus, UnavailableReason, ok, unavailable
from app.schemas.stocks import MarketConditions, MarketGauge
from app.services import ingestion
from app.services.stocks import LOCAL_SOURCE, find_stock

MAX_BARS = 300


def sync(db: Session, provider: MarketDataProvider | None, *, history_years: int) -> list[str]:
    """Load new prices for the gauge ETFs (each at most every 6 hours).

    Stops at the provider's rate limit. Returns messages for failures."""
    problems: list[str] = []
    for symbol in market.SYMBOLS:
        result = ingestion.sync_prices(db, provider, symbol, history_years=history_years)
        if result.status != DataStatus.OK:
            problems.append(f"{symbol}: {result.message}")
            if result.reason == UnavailableReason.RATE_LIMITED:
                break
    return problems


def conditions(db: Session) -> MarketConditions:
    closes: dict[str, list[float]] = {}
    newest = None
    missing: list[str] = []
    for symbol in market.SYMBOLS:
        stock = find_stock(db, symbol)
        rows = (
            db.execute(
                select(HistoricalPrice.date, HistoricalPrice.close, HistoricalPrice.adjusted_close)
                .where(HistoricalPrice.stock_id == stock.id)
                .order_by(HistoricalPrice.date.desc())
                .limit(MAX_BARS)
            ).all()
            if stock
            else []
        )
        if len(rows) < 50:
            missing.append(symbol)
            continue
        closes[symbol] = [adj if adj is not None else close for _, close, adj in reversed(rows)]
        newest = max(newest, rows[0][0]) if newest else rows[0][0]
    found = market.gauges(closes)
    level = market.overall(found)
    return MarketConditions(
        level=level,
        gauges=[MarketGauge(**asdict(g)) for g in found],
        warning=market.warning(level, found),
        as_of=newest,
        missing=missing,
    )


def get_conditions(db: Session) -> DataResponse[MarketConditions]:
    result = conditions(db)
    if not result.gauges:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            "Market gauges need about 2 months of prices for SPY, VIXY, TLT, HYG and IEF. "
            "Use Refresh market gauges to load them.",
        )
    return ok(result, source=LOCAL_SOURCE)


def refresh(
    db: Session, provider: MarketDataProvider | None, *, history_years: int
) -> DataResponse[MarketConditions]:
    if provider is None:
        return unavailable(
            UnavailableReason.PROVIDER_NOT_CONFIGURED,
            "Loading market gauges needs a market data provider, and none is configured.",
        )
    problems = sync(db, provider, history_years=history_years)
    response = get_conditions(db)
    if problems and response.status == DataStatus.OK:
        response.message = "Some gauge prices could not be refreshed: " + "; ".join(problems)
    elif problems:
        response.message = (response.message or "") + " " + "; ".join(problems)
    return response

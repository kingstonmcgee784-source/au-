"""Stock reference data, search and quotes."""

import logging

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Stock
from app.providers.base import MarketDataProvider, ProviderError, TickerNotFoundError
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import Quote, StockSummary

logger = logging.getLogger(__name__)

LOCAL_SOURCE = "local_database"


def find_stock(db: Session, ticker: str) -> Stock | None:
    return db.scalar(select(Stock).where(Stock.ticker == ticker))


def no_stored_stock(ticker: str) -> str:
    return f"{ticker} is not in the local database yet."


def provider_failure[T](exc: ProviderError, ticker: str | None = None) -> DataResponse[T]:
    """Turn a provider exception into an 'unavailable' response."""
    if isinstance(exc, TickerNotFoundError):
        return unavailable(
            UnavailableReason.UNKNOWN_TICKER,
            f"The data provider does not recognize {ticker}." if ticker else str(exc),
        )
    logger.warning("Provider error: %s", exc)
    return unavailable(UnavailableReason.PROVIDER_ERROR, str(exc))


def search_stocks(
    db: Session, provider: MarketDataProvider | None, query: str, limit: int
) -> DataResponse[list[StockSummary]]:
    if provider is not None:
        try:
            return ok(provider.search(query, limit), source=provider.name)
        except ProviderError as exc:
            logger.warning("Provider search failed, falling back to local database: %s", exc)

    pattern = f"%{query.strip()}%"
    rows = db.scalars(
        select(Stock)
        .where(or_(Stock.ticker.ilike(pattern), Stock.name.ilike(pattern)))
        .order_by(Stock.ticker)
        .limit(limit)
    ).all()
    if rows or provider is not None:
        return ok([StockSummary.model_validate(row) for row in rows], source=LOCAL_SOURCE)
    return unavailable(
        UnavailableReason.PROVIDER_NOT_CONFIGURED,
        "No matching stocks in the local database and no market data provider is configured.",
    )


def get_profile(
    db: Session, provider: MarketDataProvider | None, ticker: str
) -> DataResponse[StockSummary]:
    stock = find_stock(db, ticker)
    if stock is not None:
        return ok(StockSummary.model_validate(stock), source=LOCAL_SOURCE, as_of=stock.updated_at)
    if provider is None:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"{no_stored_stock(ticker)} No market data provider is configured.",
        )
    try:
        return ok(provider.get_profile(ticker), source=provider.name)
    except ProviderError as exc:
        return provider_failure(exc, ticker)


def get_quote(provider: MarketDataProvider | None, ticker: str) -> DataResponse[Quote]:
    if provider is None:
        return unavailable(
            UnavailableReason.PROVIDER_NOT_CONFIGURED,
            "Live quotes need a market data provider, and none is configured.",
        )
    try:
        quote = provider.get_quote(ticker)
    except ProviderError as exc:
        return provider_failure(exc, ticker)
    return ok(quote, source=provider.name, as_of=quote.timestamp)

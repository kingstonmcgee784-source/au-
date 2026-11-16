"""Stock reference data, search and quotes."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Stock
from app.providers.base import MarketDataProvider
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import Quote, StockSummary

LOCAL_SOURCE = "local_database"


def find_stock(db: Session, ticker: str) -> Stock | None:
    return db.scalar(select(Stock).where(Stock.ticker == ticker))


def no_stored_stock(ticker: str) -> str:
    return f"{ticker} is not in the local database yet, and no data provider is configured."


def search_stocks(
    db: Session, provider: MarketDataProvider | None, query: str, limit: int
) -> DataResponse[list[StockSummary]]:
    pattern = f"%{query.strip()}%"
    rows = db.scalars(
        select(Stock)
        .where(or_(Stock.ticker.ilike(pattern), Stock.name.ilike(pattern)))
        .order_by(Stock.ticker)
        .limit(limit)
    ).all()
    if rows:
        return ok([StockSummary.model_validate(row) for row in rows], source=LOCAL_SOURCE)
    if provider is not None:
        return ok(provider.search(query, limit), source=provider.name)
    return unavailable(
        UnavailableReason.PROVIDER_NOT_CONFIGURED,
        "No matching stocks in the local database and no market data provider is configured.",
    )


def get_profile(db: Session, ticker: str) -> DataResponse[StockSummary]:
    stock = find_stock(db, ticker)
    if stock is None:
        return unavailable(UnavailableReason.NO_STORED_DATA, no_stored_stock(ticker))
    return ok(StockSummary.model_validate(stock), source=LOCAL_SOURCE, as_of=stock.updated_at)


def get_quote(provider: MarketDataProvider | None, ticker: str) -> DataResponse[Quote]:
    if provider is None:
        return unavailable(
            UnavailableReason.PROVIDER_NOT_CONFIGURED,
            "Live quotes need a market data provider, and none is configured.",
        )
    quote = provider.get_quote(ticker)
    return ok(quote, source=provider.name, as_of=quote.timestamp)

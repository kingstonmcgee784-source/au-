"""Load data from providers into the database.

Only retrieval and storage happen here. Calculations run later on the stored
data, so every number the platform shows can be traced to a stored row with
its source and retrieval time.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import HistoricalPrice, Stock
from app.providers.base import MarketDataProvider, ProviderError
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import PriceSyncResult
from app.services.stocks import find_stock, provider_failure


def sync_prices(
    db: Session,
    provider: MarketDataProvider | None,
    ticker: str,
    *,
    history_years: int,
    today: date | None = None,
) -> DataResponse[PriceSyncResult]:
    """Store any daily bars for `ticker` that are not stored yet.

    The first sync loads `history_years` of history; later syncs fetch only
    the days after the newest stored bar. The stock's reference data is
    created or refreshed from the provider at the same time.
    """
    if provider is None:
        return unavailable(
            UnavailableReason.PROVIDER_NOT_CONFIGURED,
            "Loading prices needs a market data provider, and none is configured.",
        )
    today = today or datetime.now(UTC).date()

    try:
        profile = provider.get_profile(ticker)
    except ProviderError as exc:
        return provider_failure(exc, ticker)

    stock = find_stock(db, ticker)
    if stock is None:
        stock = Stock(ticker=ticker, name=profile.name)
        db.add(stock)
    stock.name = profile.name
    stock.exchange = profile.exchange or stock.exchange
    db.flush()

    newest = db.scalar(
        select(func.max(HistoricalPrice.date)).where(HistoricalPrice.stock_id == stock.id)
    )
    start = newest + timedelta(days=1) if newest else today - timedelta(days=365 * history_years)

    added = 0
    if start <= today:
        try:
            bars = provider.get_daily_prices(ticker, start, today)
        except ProviderError as exc:
            db.rollback()
            return provider_failure(exc, ticker)

        retrieved_at = datetime.now(UTC)
        for bar in bars:
            if newest is not None and bar.date <= newest:
                continue
            db.add(
                HistoricalPrice(
                    stock_id=stock.id,
                    date=bar.date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    adjusted_close=bar.adjusted_close,
                    volume=bar.volume,
                    source=provider.name,
                    retrieved_at=retrieved_at,
                )
            )
            added += 1
    db.commit()

    count, first, last = db.execute(
        select(
            func.count(HistoricalPrice.id),
            func.min(HistoricalPrice.date),
            func.max(HistoricalPrice.date),
        ).where(HistoricalPrice.stock_id == stock.id)
    ).one()
    return ok(
        PriceSyncResult(
            ticker=ticker, bars_added=added, bars_stored=count, first_date=first, last_date=last
        ),
        source=provider.name,
        as_of=datetime.now(UTC),
    )

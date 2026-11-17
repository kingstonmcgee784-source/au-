"""Load data from providers into the database.

Only retrieval and storage happen here. Calculations run later on the stored
data, so every number the platform shows can be traced to a stored row with
its source and retrieval time.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FinancialStatement, HistoricalPrice, Stock
from app.providers.base import FundamentalsSource, MarketDataProvider, ProviderError
from app.providers.sec_xbrl import parse_company_facts
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import FinancialsSyncResult, PriceSyncResult
from app.services.stocks import find_stock, provider_failure

# Prices are daily bars: refreshing more often than this only spends the
# provider's request allowance (Tiingo's free plan allows 50 an hour).
PRICE_REFRESH_INTERVAL = timedelta(hours=6)


def sync_prices(
    db: Session,
    provider: MarketDataProvider | None,
    ticker: str,
    *,
    history_years: int,
    today: date | None = None,
    force: bool = False,
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

    stock = find_stock(db, ticker)
    if stock is None or stock.exchange is None:
        # New stock, or one first created from SEC data, which has no exchange:
        # fetch the market data profile once.
        try:
            profile = provider.get_profile(ticker)
        except ProviderError as exc:
            return provider_failure(exc, ticker)
        if stock is None:
            stock = Stock(ticker=ticker, name=profile.name)
            db.add(stock)
        stock.exchange = profile.exchange
        db.flush()
    if not force:
        last_retrieved = db.scalar(
            select(func.max(HistoricalPrice.retrieved_at)).where(
                HistoricalPrice.stock_id == stock.id
            )
        )
        if last_retrieved and datetime.now(UTC) - last_retrieved < PRICE_REFRESH_INTERVAL:
            return _price_summary(db, provider.name, ticker, stock.id, added=0)

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
    return _price_summary(db, provider.name, ticker, stock.id, added=added)


def _price_summary(
    db: Session, source: str, ticker: str, stock_id: int, *, added: int
) -> DataResponse[PriceSyncResult]:
    count, first, last, retrieved = db.execute(
        select(
            func.count(HistoricalPrice.id),
            func.min(HistoricalPrice.date),
            func.max(HistoricalPrice.date),
            func.max(HistoricalPrice.retrieved_at),
        ).where(HistoricalPrice.stock_id == stock_id)
    ).one()
    return ok(
        PriceSyncResult(
            ticker=ticker, bars_added=added, bars_stored=count, first_date=first, last_date=last
        ),
        source=source,
        as_of=retrieved or datetime.now(UTC),
    )


def sync_financials(
    db: Session, source: FundamentalsSource | None, ticker: str
) -> DataResponse[FinancialsSyncResult]:
    """Load reported financial statements for `ticker` and store them.

    Statements already stored for the same period are replaced, so restated
    figures from later filings take effect.
    """
    if source is None:
        return unavailable(
            UnavailableReason.PROVIDER_NOT_CONFIGURED,
            "Financial statements come from SEC EDGAR, which needs SEC_USER_AGENT "
            "(your name and email) in backend/.env.",
        )
    try:
        cik, company_name = source.lookup(ticker)
        facts = source.company_facts(cik)
    except ProviderError as exc:
        return provider_failure(exc, ticker)

    parsed = parse_company_facts(facts)
    if not parsed:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"The SEC has no 10-K or 10-Q financial data for {ticker} in a format we can read.",
        )

    stock = find_stock(db, ticker)
    if stock is None:
        stock = Stock(ticker=ticker, name=company_name)
        db.add(stock)
        db.flush()

    existing = {
        (row.statement_type, row.period_type, row.period_end): row
        for row in db.scalars(
            select(FinancialStatement).where(FinancialStatement.stock_id == stock.id)
        )
    }
    retrieved_at = datetime.now(UTC)
    for statement in parsed:
        key = (statement.statement_type, statement.period_type, statement.period_end)
        row = existing.get(key)
        if row is None:
            row = FinancialStatement(
                stock_id=stock.id,
                statement_type=statement.statement_type,
                period_type=statement.period_type,
                period_end=statement.period_end,
            )
            db.add(row)
        row.fiscal_year = statement.fiscal_year
        row.fiscal_quarter = statement.fiscal_quarter
        row.filing_date = statement.filing_date
        row.currency = "USD"
        row.line_items = statement.line_items
        row.derived_items = statement.derived_items
        row.source = source.name
        row.retrieved_at = retrieved_at
    # Remove stored periods the latest parse no longer produces, so statements
    # from an earlier, mistaken parse cannot linger.
    current = {(s.statement_type, s.period_type, s.period_end) for s in parsed}
    for key, row in existing.items():
        if key not in current:
            db.delete(row)
    db.commit()

    period_ends = {s.period_end for s in parsed}
    return ok(
        FinancialsSyncResult(
            ticker=ticker,
            cik=cik,
            company_name=company_name,
            statements_stored=len(parsed),
            quarterly_periods=len({s.period_end for s in parsed if s.period_type == "quarterly"}),
            annual_periods=len({s.period_end for s in parsed if s.period_type == "annual"}),
            latest_period_end=max(period_ends),
        ),
        source=source.name,
        as_of=retrieved_at,
    )

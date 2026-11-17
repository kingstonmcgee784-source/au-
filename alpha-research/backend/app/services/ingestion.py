"""Load data from providers into the database.

Only retrieval and storage happen here. Calculations run later on the stored
data, so every number the platform shows can be traced to a stored row with
its source and retrieval time.
"""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import FinancialStatement, HistoricalPrice, Stock
from app.providers.base import FundamentalsSource, MarketDataProvider, PriceBar, ProviderError
from app.providers.sec_xbrl import PARSER_VERSION, parse_company_facts
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import FinancialsSyncResult, PriceSyncResult
from app.services.stocks import find_stock, get_or_create_stock, provider_failure

# Prices are daily bars: refreshing more often than this only spends the
# provider's request allowance (Tiingo's free plan allows 50 an hour).
logger = logging.getLogger(__name__)

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
    if stock is not None and not force:
        # Checked first, so a recent sync spends no provider requests at all.
        last_retrieved = db.scalar(
            select(func.max(HistoricalPrice.retrieved_at)).where(
                HistoricalPrice.stock_id == stock.id
            )
        )
        if last_retrieved and datetime.now(UTC) - last_retrieved < PRICE_REFRESH_INTERVAL:
            return _price_summary(db, provider.name, ticker, stock.id, added=0)

    if stock is None or stock.exchange is None:
        # New stock, or one first created from SEC data, which has no exchange.
        # Limited by the refresh interval above, so a provider that reports no
        # exchange for a symbol is not asked again on every sync.
        try:
            profile = provider.get_profile(ticker)
        except ProviderError as exc:
            return provider_failure(exc, ticker)
        stock = get_or_create_stock(db, ticker, profile.name)
        stock.exchange = stock.exchange or profile.exchange
        db.flush()

    newest = db.scalar(
        select(HistoricalPrice)
        .where(HistoricalPrice.stock_id == stock.id)
        .order_by(HistoricalPrice.date.desc())
        .limit(1)
    )
    full_start = today - timedelta(days=365 * history_years)
    # Ask again for the newest stored day as well: if its adjusted price has
    # changed, a split or dividend has re-based the whole history.
    start = newest.date if newest else full_start

    try:
        bars = provider.get_daily_prices(ticker, start, today)
    except ProviderError as exc:
        db.rollback()
        return provider_failure(exc, ticker)

    if newest is not None and _rebased(newest, bars):
        logger.info("Adjusted prices for %s changed; reloading its full history", ticker)
        try:
            bars = provider.get_daily_prices(ticker, full_start, today)
        except ProviderError as exc:
            db.rollback()
            return provider_failure(exc, ticker)
        db.execute(delete(HistoricalPrice).where(HistoricalPrice.stock_id == stock.id))
        newest = None

    retrieved_at = datetime.now(UTC)
    added = 0
    for bar in bars:
        if newest is not None and bar.date <= newest.date:
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


STATEMENT_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "10-KT", "10-KT/A"}


def _stored_financials(
    db: Session, ticker: str, cik: int, company_name: str, source: FundamentalsSource
) -> DataResponse[FinancialsSyncResult] | None:
    """A summary of the statements already stored, or None if there are none."""
    stock = find_stock(db, ticker)
    if stock is None:
        return None
    rows = db.execute(
        select(
            FinancialStatement.period_type,
            FinancialStatement.period_end,
            FinancialStatement.retrieved_at,
        ).where(FinancialStatement.stock_id == stock.id)
    ).all()
    if not rows:
        return None
    return ok(
        FinancialsSyncResult(
            ticker=ticker,
            cik=cik,
            company_name=company_name,
            statements_stored=len(rows),
            quarterly_periods=len({end for kind, end, _ in rows if kind == "quarterly"}),
            annual_periods=len({end for kind, end, _ in rows if kind == "annual"}),
            latest_period_end=max(end for _, end, _ in rows),
        ),
        source=source.name,
        as_of=min(retrieved for _, _, retrieved in rows),
    )


def _rebased(stored: HistoricalPrice, bars: list[PriceBar]) -> bool:
    """True when the provider's adjusted price for a stored day no longer matches."""
    fresh = next((b for b in bars if b.date == stored.date), None)
    if fresh is None or fresh.adjusted_close is None or stored.adjusted_close is None:
        return False
    return abs(fresh.adjusted_close - stored.adjusted_close) > 1e-6 * max(
        abs(stored.adjusted_close), 1.0
    )


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
    db: Session, source: FundamentalsSource | None, ticker: str, *, force: bool = False
) -> DataResponse[FinancialsSyncResult]:
    """Load reported financial statements for `ticker` and store them.

    The full company facts (several megabytes) are downloaded only when the
    company has filed a 10-K or 10-Q, or an amendment, since the last load,
    or when `force` is set. A company's stored statements are replaced as a
    set, so restated figures from later filings take effect.
    """
    if source is None:
        return unavailable(
            UnavailableReason.PROVIDER_NOT_CONFIGURED,
            "Financial statements come from SEC EDGAR, which needs SEC_USER_AGENT "
            "(your name and email) in backend/.env.",
        )
    try:
        cik, company_name = source.lookup(ticker)
        if not force:
            stored = _stored_financials(db, ticker, cik, company_name, source)
            if stored is not None:
                info = source.company_info(cik)
                latest_filing = max(
                    (f.filed for f in info.filings if f.form in STATEMENT_FORMS), default=None
                )
                loaded = stored.as_of
                current_parser = (
                    db.scalar(
                        select(func.min(FinancialStatement.parser_version))
                        .join(Stock, Stock.id == FinancialStatement.stock_id)
                        .where(Stock.ticker == ticker)
                    )
                    == PARSER_VERSION
                )
                no_new_filing = latest_filing is None or (
                    loaded is not None and latest_filing < loaded.date()
                )
                if current_parser and no_new_filing:
                    return stored
        facts = source.company_facts(cik)
    except ProviderError as exc:
        return provider_failure(exc, ticker)

    parsed = parse_company_facts(facts)
    if not parsed:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"The SEC has no 10-K or 10-Q financial data for {ticker} in a format we can read.",
        )

    stock = get_or_create_stock(db, ticker, company_name)

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
        row.parser_version = PARSER_VERSION
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

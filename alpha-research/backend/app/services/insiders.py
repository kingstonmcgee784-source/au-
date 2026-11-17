"""Insider trading (SEC Form 4): load filings and read stored activity."""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.insider import Trade, summarize
from app.models import FinancialMetric, InsiderFiling, InsiderTransaction, Stock
from app.providers.base import FundamentalsSource, ProviderError
from app.providers.sec_form4 import TRANSACTION_CODES, Form4ParseError, parse_form4
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import InsiderActivity, InsiderSyncResult, InsiderTransactionOut
from app.services.stocks import LOCAL_SOURCE, find_stock, provider_failure

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 180
# Each Form 4 is one request; cap a single sync so it stays quick. Later
# syncs pick up where this one stopped.
MAX_FILINGS_PER_SYNC = 60
FORM_TYPES = {"4"}  # amendments (4/A) restate earlier trades and would double count


def sync_insiders(
    db: Session, source: FundamentalsSource | None, ticker: str, *, today: date | None = None
) -> DataResponse[InsiderSyncResult]:
    if source is None:
        return unavailable(
            UnavailableReason.PROVIDER_NOT_CONFIGURED,
            "Insider filings come from SEC EDGAR, which needs SEC_USER_AGENT "
            "(your name and email) in backend/.env.",
        )
    today = today or datetime.now(UTC).date()
    try:
        cik, company_name = source.lookup(ticker)
        info = source.company_info(cik)
    except ProviderError as exc:
        return provider_failure(exc, ticker)

    stock = find_stock(db, ticker)
    if stock is None:
        stock = Stock(ticker=ticker, name=company_name)
        db.add(stock)
    stock.sic_code = info.sic or stock.sic_code
    if info.sic_description and not stock.industry:
        stock.industry = info.sic_description.title()
    db.flush()

    since = today - timedelta(days=LOOKBACK_DAYS)
    candidates = [f for f in info.filings if f.form in FORM_TYPES and f.filed >= since]
    known = set(
        db.scalars(select(InsiderFiling.accession).where(InsiderFiling.stock_id == stock.id))
    )
    pending = [f for f in candidates if f.accession not in known]
    batch = pending[:MAX_FILINGS_PER_SYNC]

    added_filings = added_trades = unreadable = 0
    retrieved_at = datetime.now(UTC)
    for filing in batch:
        try:
            document = source.filing_document(cik, filing)
        except ProviderError as exc:
            db.commit()  # keep what was loaded so far
            return provider_failure(exc, ticker)
        try:
            form = parse_form4(document)
            owner_name, owner_role, trades = form.owner_name, form.owner_role, form.trades
        except Form4ParseError as exc:
            logger.warning("Skipping unreadable Form 4 %s: %s", filing.accession, exc)
            owner_name, owner_role, trades = "Unreadable filing", "Unknown", []
            unreadable += 1
        row = InsiderFiling(
            stock_id=stock.id,
            accession=filing.accession,
            filed_on=filing.filed,
            owner_name=owner_name[:255],
            owner_role=owner_role[:255],
            source=source.name,
            retrieved_at=retrieved_at,
        )
        for trade in trades:
            row.transactions.append(
                InsiderTransaction(
                    stock_id=stock.id,
                    transaction_date=trade.transaction_date,
                    code=trade.code,
                    acquired=trade.acquired,
                    shares=trade.shares,
                    price=trade.price,
                    shares_after=trade.shares_after,
                    direct=trade.direct,
                    under_10b5_1=trade.under_10b5_1,
                    security=trade.security[:255],
                )
            )
        db.add(row)
        added_filings += 1
        added_trades += len(trades)

    stock.insiders_synced_at = retrieved_at
    db.commit()
    return ok(
        InsiderSyncResult(
            ticker=ticker,
            filings_checked=len(candidates),
            filings_added=added_filings,
            transactions_added=added_trades,
            filings_remaining=len(pending) - len(batch),
            unreadable_filings=unreadable,
        ),
        source=source.name,
        as_of=retrieved_at,
    )


def stored_trades(
    db: Session, stock_id: int, since: date
) -> list[tuple[InsiderTransaction, InsiderFiling]]:
    rows = db.execute(
        select(InsiderTransaction, InsiderFiling)
        .join(InsiderFiling, InsiderFiling.id == InsiderTransaction.filing_id)
        .where(InsiderTransaction.stock_id == stock_id, InsiderTransaction.transaction_date > since)
        .order_by(InsiderTransaction.transaction_date.desc(), InsiderTransaction.id.desc())
    ).all()
    return [(transaction, filing) for transaction, filing in rows]


def insider_metrics(
    db: Session, stock: Stock, *, as_of: date, market_cap: float | None
) -> dict[str, float | None]:
    """Summary metrics for scoring; empty when filings were never loaded."""
    if stock.insiders_synced_at is None:
        return {}
    rows = stored_trades(db, stock.id, as_of - timedelta(days=LOOKBACK_DAYS))
    return summarize(
        [_trade(t, f) for t, f in rows], as_of=as_of, days=LOOKBACK_DAYS, market_cap=market_cap
    )


def get_activity(db: Session, ticker: str, days: int) -> DataResponse[InsiderActivity]:
    stock = find_stock(db, ticker)
    if stock is None or stock.insiders_synced_at is None:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"Insider filings for {ticker} have not been loaded. Use Load insider filings.",
        )
    today = datetime.now(UTC).date()
    rows = stored_trades(db, stock.id, today - timedelta(days=days))
    market_cap = db.scalar(
        select(FinancialMetric.value)
        .where(FinancialMetric.stock_id == stock.id, FinancialMetric.metric == "market_cap")
        .order_by(FinancialMetric.as_of.desc())
        .limit(1)
    )
    return ok(
        InsiderActivity(
            ticker=ticker,
            days=days,
            synced_at=stock.insiders_synced_at,
            summary=summarize(
                [_trade(t, f) for t, f in rows], as_of=today, days=days, market_cap=market_cap
            ),
            transactions=[
                InsiderTransactionOut(
                    transaction_date=t.transaction_date,
                    filed_on=f.filed_on,
                    owner_name=f.owner_name,
                    owner_role=f.owner_role,
                    code=t.code,
                    description=TRANSACTION_CODES.get(t.code, f"Other ({t.code})"),
                    acquired=t.acquired,
                    shares=t.shares,
                    price=t.price,
                    value=t.shares * t.price if t.price is not None else None,
                    shares_after=t.shares_after,
                    under_10b5_1=t.under_10b5_1,
                )
                for t, f in rows
            ],
        ),
        source=LOCAL_SOURCE,
        as_of=stock.insiders_synced_at,
    )


def _trade(t: InsiderTransaction, f: InsiderFiling) -> Trade:
    return Trade(
        owner_name=f.owner_name,
        transaction_date=t.transaction_date,
        code=t.code,
        shares=t.shares,
        price=t.price,
        under_10b5_1=t.under_10b5_1,
    )

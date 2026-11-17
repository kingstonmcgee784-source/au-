"""Company events (SEC 8-K filings): load, read, and summarise for scoring."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis.catalysts import (
    Event,
    catalyst_metrics,
    classify,
    estimate_next_earnings,
    headline,
)
from app.models import NewsArticle, Stock
from app.providers.base import FundamentalsSource, ProviderError
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import CatalystEvent, CatalystFeed, EventItem, EventsSyncResult
from app.services.stocks import LOCAL_SOURCE, find_stock, provider_failure

LOOKBACK_DAYS = 400  # a little over a year, enough to estimate the earnings rhythm
FORMS = {"8-K", "8-K/A"}
SOURCE = "sec_edgar"


def sync_events(
    db: Session, source: FundamentalsSource | None, ticker: str, *, today: date | None = None
) -> DataResponse[EventsSyncResult]:
    """Store 8-K filings from the SEC filing index. One request, no downloads."""
    if source is None:
        return unavailable(
            UnavailableReason.PROVIDER_NOT_CONFIGURED,
            "Company events come from SEC EDGAR, which needs SEC_USER_AGENT "
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
    if info.exchanges and not stock.exchange:
        stock.exchange = info.exchanges[0].upper()
    if info.sic_description and not stock.industry:
        stock.industry = info.sic_description.title()
    stock.sic_code = info.sic or stock.sic_code
    db.flush()

    since = today - timedelta(days=LOOKBACK_DAYS)
    known = set(db.scalars(select(NewsArticle.url).where(NewsArticle.stock_id == stock.id)))
    retrieved_at = datetime.now(UTC)
    added = 0
    for filing in info.filings:
        if filing.form not in FORMS or filing.filed < since:
            continue
        url = source.filing_url(cik, filing)
        if url in known:
            continue
        codes = [c.strip() for c in filing.items.split(",") if c.strip()]
        items = classify(codes)
        top = headline(items)
        db.add(
            NewsArticle(
                stock_id=stock.id,
                headline=(top.label if top else "Filing with exhibits only")[:512],
                url=url,
                publisher="SEC EDGAR",
                published_at=datetime(filing.filed.year, filing.filed.month, filing.filed.day, tzinfo=UTC),
                summary=", ".join(f"{i.code} {i.label}" for i in items) or None,
                category=top.kind if top else "other",
                form=filing.form,
                items=codes,
                source=SOURCE,
                retrieved_at=retrieved_at,
            )
        )
        known.add(url)
        added += 1

    stock.events_synced_at = retrieved_at
    db.commit()
    stored = db.scalar(
        select(func.count(NewsArticle.id)).where(
            NewsArticle.stock_id == stock.id, NewsArticle.source == SOURCE
        )
    )
    return ok(
        EventsSyncResult(ticker=ticker, events_added=added, events_stored=stored or 0),
        source=SOURCE,
        as_of=retrieved_at,
    )


def _events(db: Session, stock_id: int) -> list[NewsArticle]:
    return list(
        db.scalars(
            select(NewsArticle)
            .where(NewsArticle.stock_id == stock_id, NewsArticle.source == SOURCE)
            .order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc())
        )
    )


def event_metrics(db: Session, stock: Stock, *, today: date) -> dict[str, float | None]:
    """Catalyst metrics for scoring; empty when events were never loaded."""
    if stock.events_synced_at is None:
        return {}
    events = [Event(row.published_at.date(), tuple(row.items or [])) for row in _events(db, stock.id)]
    return catalyst_metrics(events, today)


def get_catalysts(db: Session, ticker: str) -> DataResponse[CatalystFeed]:
    stock = find_stock(db, ticker)
    if stock is None or stock.events_synced_at is None:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"Company events for {ticker} have not been loaded. Use Load SEC events.",
        )
    rows = _events(db, stock.id)
    today = datetime.now(UTC).date()
    releases = [r.published_at.date() for r in rows if "2.02" in (r.items or [])]
    events = []
    for row in rows:
        items = classify(row.items or [])
        events.append(
            CatalystEvent(
                filed_on=row.published_at.date(),
                form=row.form or "8-K",
                headline=row.headline,
                kind=row.category or "other",
                items=[EventItem(code=i.code, label=i.label, kind=i.kind) for i in items],
                url=row.url,
            )
        )
    estimate = estimate_next_earnings(releases, today)
    return ok(
        CatalystFeed(
            ticker=ticker,
            synced_at=stock.events_synced_at,
            next_earnings_estimate=estimate,
            days_to_next_earnings=(estimate - today).days if estimate else None,
            events=events,
        ),
        source=LOCAL_SOURCE,
        as_of=stock.events_synced_at,
    )

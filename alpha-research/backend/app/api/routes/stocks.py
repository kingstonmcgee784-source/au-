"""Per-stock endpoints: search, profile, quote, financials, technicals, score."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AppSettings, DbSession, Fundamentals, MarketData, TickerPath
from app.schemas.common import DataResponse
from app.schemas.stocks import (
    FinancialsSyncResult,
    FinancialStatementOut,
    InsiderActivity,
    InsiderSyncResult,
    MetricsSnapshot,
    PriceSyncResult,
    Quote,
    StockScoreOut,
    StockSummary,
    TechnicalSnapshot,
)
from app.services import (
    financials,
    ingestion,
    insiders,
    scores,
    scoring_pipeline,
    stocks,
    technicals,
)

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/search", response_model=DataResponse[list[StockSummary]])
def search(
    db: DbSession,
    provider: MarketData,
    q: Annotated[str, Query(min_length=1, max_length=64, description="Ticker or company name")],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> DataResponse[list[StockSummary]]:
    return stocks.search_stocks(db, provider, q, limit)


@router.get("/{ticker}", response_model=DataResponse[StockSummary])
def profile(db: DbSession, provider: MarketData, ticker: TickerPath) -> DataResponse[StockSummary]:
    return stocks.get_profile(db, provider, ticker)


@router.get("/{ticker}/quote", response_model=DataResponse[Quote])
def quote(provider: MarketData, ticker: TickerPath) -> DataResponse[Quote]:
    return stocks.get_quote(provider, ticker)


@router.get("/{ticker}/financials", response_model=DataResponse[list[FinancialStatementOut]])
def financial_statements(
    db: DbSession,
    ticker: TickerPath,
    statement_type: financials.StatementType | None = None,
    period_type: financials.PeriodType | None = None,
    limit: Annotated[int, Query(ge=1, le=40)] = 12,
) -> DataResponse[list[FinancialStatementOut]]:
    return financials.get_statements(db, ticker, statement_type, period_type, limit)


@router.get("/{ticker}/technicals", response_model=DataResponse[TechnicalSnapshot])
def technical_snapshot(db: DbSession, ticker: TickerPath) -> DataResponse[TechnicalSnapshot]:
    return technicals.get_snapshot(db, ticker)


@router.get("/{ticker}/score", response_model=DataResponse[StockScoreOut])
def score(db: DbSession, ticker: TickerPath) -> DataResponse[StockScoreOut]:
    return scores.get_latest_score(db, ticker)


@router.post("/{ticker}/sync-prices", response_model=DataResponse[PriceSyncResult])
def sync_prices(
    db: DbSession, provider: MarketData, settings: AppSettings, ticker: TickerPath
) -> DataResponse[PriceSyncResult]:
    """Fetch daily prices from the market data provider and store the new ones."""
    return ingestion.sync_prices(
        db, provider, ticker, history_years=settings.price_history_years
    )


@router.post("/{ticker}/sync-financials", response_model=DataResponse[FinancialsSyncResult])
def sync_financials(
    db: DbSession, source: Fundamentals, ticker: TickerPath
) -> DataResponse[FinancialsSyncResult]:
    """Fetch reported financial statements from SEC EDGAR and store them."""
    return ingestion.sync_financials(db, source, ticker)


@router.post("/{ticker}/score", response_model=DataResponse[StockScoreOut])
def calculate_score(
    db: DbSession,
    market: MarketData,
    source: Fundamentals,
    settings: AppSettings,
    ticker: TickerPath,
    refresh: bool = True,
) -> DataResponse[StockScoreOut]:
    """Refresh the stock's data (unless refresh=false), calculate metrics and score it."""
    return scoring_pipeline.score_stock(
        db,
        ticker,
        market=market,
        fundamentals=source,
        refresh=refresh,
        history_years=settings.price_history_years,
    )


@router.get("/{ticker}/metrics", response_model=DataResponse[MetricsSnapshot])
def metrics(db: DbSession, ticker: TickerPath) -> DataResponse[MetricsSnapshot]:
    """The most recently calculated metrics (valuation, margins, growth, price behaviour)."""
    return scoring_pipeline.latest_metrics(db, ticker)


@router.post("/{ticker}/sync-insiders", response_model=DataResponse[InsiderSyncResult])
def sync_insiders(
    db: DbSession, source: Fundamentals, ticker: TickerPath
) -> DataResponse[InsiderSyncResult]:
    """Load the last 180 days of Form 4 insider filings from SEC EDGAR."""
    return insiders.sync_insiders(db, source, ticker)


@router.get("/{ticker}/insiders", response_model=DataResponse[InsiderActivity])
def insider_activity(
    db: DbSession, ticker: TickerPath, days: Annotated[int, Query(ge=7, le=180)] = 180
) -> DataResponse[InsiderActivity]:
    """Stored insider transactions and a summary for the last `days` days."""
    return insiders.get_activity(db, ticker, days)

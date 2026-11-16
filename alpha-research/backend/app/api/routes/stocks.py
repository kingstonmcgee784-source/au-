"""Per-stock endpoints: search, profile, quote, financials, technicals, score."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession, MarketData, TickerPath
from app.schemas.common import DataResponse
from app.schemas.stocks import (
    FinancialStatementOut,
    Quote,
    StockScoreOut,
    StockSummary,
    TechnicalSnapshot,
)
from app.services import financials, scores, stocks, technicals

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
def profile(db: DbSession, ticker: TickerPath) -> DataResponse[StockSummary]:
    return stocks.get_profile(db, ticker)


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

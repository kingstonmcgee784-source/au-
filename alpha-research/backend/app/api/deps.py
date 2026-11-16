"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.orm import Session

from app.ai.research_writer import ResearchWriter, get_research_writer
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.providers.base import FundamentalsSource, MarketDataProvider
from app.providers.registry import get_fundamentals_client, get_market_data_provider
from app.schemas.common import Ticker

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def market_data_provider(settings: AppSettings) -> MarketDataProvider | None:
    return get_market_data_provider(settings)


def fundamentals_client(settings: AppSettings) -> FundamentalsSource | None:
    return get_fundamentals_client(settings)


def research_writer(settings: AppSettings) -> ResearchWriter | None:
    return get_research_writer(settings)


MarketData = Annotated[MarketDataProvider | None, Depends(market_data_provider)]
Fundamentals = Annotated[FundamentalsSource | None, Depends(fundamentals_client)]
Writer = Annotated[ResearchWriter | None, Depends(research_writer)]
TickerPath = Annotated[Ticker, Path(description="Ticker symbol, e.g. MSFT or BRK.B")]

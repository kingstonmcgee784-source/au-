"""ORM models. Importing this package registers every table on `Base.metadata`."""

from app.models.analysis import StockScore, TechnicalIndicator
from app.models.base import Base
from app.models.fundamentals import FinancialMetric, FinancialStatement
from app.models.research import (
    BacktestResult,
    InsiderFiling,
    InsiderTransaction,
    NewsArticle,
    Recommendation,
    ResearchReport,
)
from app.models.screener import ScreenRun, ScreenRunItem
from app.models.stock import HistoricalPrice, Stock
from app.models.watchlist import Watchlist, WatchlistItem

__all__ = [
    "BacktestResult",
    "Base",
    "FinancialMetric",
    "FinancialStatement",
    "HistoricalPrice",
    "InsiderFiling",
    "InsiderTransaction",
    "NewsArticle",
    "Recommendation",
    "ResearchReport",
    "ScreenRun",
    "ScreenRunItem",
    "Stock",
    "StockScore",
    "TechnicalIndicator",
    "Watchlist",
    "WatchlistItem",
]

"""Interfaces for external data providers.

Providers only *retrieve* data. They do no analysis and no scoring. Each
concrete integration (for example a market-data vendor) implements one of
these protocols and is selected in `app.providers.registry`.
"""

from datetime import date
from typing import Protocol

from pydantic import BaseModel

from app.schemas.stocks import Quote, StockSummary


class ProviderError(Exception):
    """A configured provider failed to return data."""


class ProviderAuthError(ProviderError):
    """The provider rejected the API key."""


class ProviderRateLimitError(ProviderError):
    """The provider's request limit was reached."""


class TickerNotFoundError(ProviderError):
    """The provider does not know this ticker."""


class PriceBar(BaseModel):
    """One daily OHLCV bar as reported by a provider."""

    date: date
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float | None
    volume: int


class MarketDataProvider(Protocol):
    name: str

    def search(self, query: str, limit: int) -> list[StockSummary]: ...

    def get_profile(self, ticker: str) -> StockSummary: ...

    def get_quote(self, ticker: str) -> Quote: ...

    def get_daily_prices(self, ticker: str, start: date, end: date | None = None) -> list[PriceBar]:
        """Daily bars from `start` to `end` (inclusive), oldest first."""
        ...

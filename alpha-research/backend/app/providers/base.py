"""Interfaces for external data providers.

Providers only *retrieve* data. They do no analysis and no scoring. Each
concrete integration (for example a market-data vendor) implements one of
these protocols and is selected in `app.providers.registry`.
"""

from typing import Protocol

from app.schemas.stocks import Quote, StockSummary


class ProviderError(Exception):
    """Raised when a configured provider fails to return data."""


class MarketDataProvider(Protocol):
    name: str

    def search(self, query: str, limit: int) -> list[StockSummary]: ...

    def get_quote(self, ticker: str) -> Quote: ...

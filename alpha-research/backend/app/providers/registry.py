"""Select the configured data provider, if any."""

from functools import lru_cache

from app.core.config import Settings
from app.providers.base import MarketDataProvider
from app.providers.sec_edgar import SecEdgarClient
from app.providers.tiingo import TiingoProvider


def get_market_data_provider(settings: Settings) -> MarketDataProvider | None:
    """Return the configured market-data provider, or None if none is set up."""
    if settings.market_data_provider == "tiingo" and settings.market_data_api_key:
        return _tiingo(settings.market_data_api_key.get_secret_value().strip())
    return None


@lru_cache(maxsize=1)
def _tiingo(api_key: str) -> TiingoProvider:
    # One shared client, so connections and the quote cache are reused.
    return TiingoProvider(api_key)


def get_fundamentals_client(settings: Settings) -> SecEdgarClient | None:
    """Return the SEC EDGAR client, or None if SEC_USER_AGENT is not set."""
    if settings.sec_user_agent:
        return _sec(settings.sec_user_agent)
    return None


@lru_cache(maxsize=1)
def _sec(user_agent: str) -> SecEdgarClient:
    # Shared so the ticker list is downloaded once a day, not on every request.
    return SecEdgarClient(user_agent)

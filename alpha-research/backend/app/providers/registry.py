"""Select the configured data provider, if any."""

from app.core.config import Settings
from app.providers.base import MarketDataProvider


def get_market_data_provider(settings: Settings) -> MarketDataProvider | None:
    """Return the configured market-data provider, or None if none is set up.

    No integration exists yet, so `market_data_provider` can only be "none".
    When a vendor is added, extend that setting's Literal and branch on it here.
    """
    _ = settings.market_data_provider
    return None

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.providers.registry import get_market_data_provider
from app.providers.tiingo import TiingoProvider


def test_tiingo_requires_api_key() -> None:
    with pytest.raises(ValidationError, match="MARKET_DATA_API_KEY"):
        Settings(market_data_provider="tiingo", market_data_api_key="  ", _env_file=None)


def test_registry_builds_tiingo_when_configured() -> None:
    settings = Settings(market_data_provider="tiingo", market_data_api_key="abc", _env_file=None)
    assert isinstance(get_market_data_provider(settings), TiingoProvider)


def test_registry_returns_none_without_provider() -> None:
    assert get_market_data_provider(Settings(market_data_provider="none", _env_file=None)) is None

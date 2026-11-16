"""Tiingo client tests against a mocked HTTP transport (no network, no real key)."""

from datetime import date

import httpx
import pytest

from app.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    TickerNotFoundError,
)
from app.providers.tiingo import TiingoProvider

Handler = dict[str, httpx.Response]


def provider_with(routes: Handler, seen: list[httpx.Request] | None = None) -> TiingoProvider:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        response = routes.get(request.url.path)
        return response if response is not None else httpx.Response(404, json={"detail": "nope"})

    return TiingoProvider("test-key", transport=httpx.MockTransport(handle))


def test_sends_token_header_and_parses_prices() -> None:
    seen: list[httpx.Request] = []
    provider = provider_with(
        {
            "/tiingo/daily/msft/prices": httpx.Response(
                200,
                json=[
                    {"date": "2026-11-13T00:00:00.000Z", "open": 2, "high": 3, "low": 1,
                     "close": 2.5, "volume": 100, "adjClose": 2.4},
                    {"date": "2026-11-12T00:00:00.000Z", "open": 1, "high": 2, "low": 0.5,
                     "close": 1.5, "volume": 90, "adjClose": 1.4},
                    {"date": "2026-11-11T00:00:00.000Z", "open": None, "high": 2, "low": 1,
                     "close": 1, "volume": 1},
                ],
            )
        },
        seen,
    )
    bars = provider.get_daily_prices("MSFT", date(2026, 11, 1), date(2026, 11, 13))

    assert seen[0].headers["Authorization"] == "Token test-key"
    assert seen[0].url.params["startDate"] == "2026-11-01"
    assert seen[0].url.params["endDate"] == "2026-11-13"
    # Sorted oldest first; the incomplete bar is dropped rather than filled in.
    assert [b.date for b in bars] == [date(2026, 11, 12), date(2026, 11, 13)]
    assert bars[1].close == 2.5 and bars[1].adjusted_close == 2.4


def test_quote_uses_reference_price_and_previous_close() -> None:
    provider = provider_with(
        {
            "/iex/livn": httpx.Response(
                200,
                json=[{"ticker": "LIVN", "tngoLast": 110.0, "last": None, "prevClose": 100.0,
                       "volume": 5000, "timestamp": "2026-11-16T20:00:00+00:00"}],
            )
        }
    )
    quote = provider.get_quote("LIVN")
    assert quote.price == 110.0
    assert quote.change == pytest.approx(10.0)
    assert quote.change_percent == pytest.approx(10.0)
    assert "not consolidated" in quote.feed


def test_quote_is_cached() -> None:
    seen: list[httpx.Request] = []
    provider = provider_with(
        {"/iex/spy": httpx.Response(200, json=[{"tngoLast": 1.0, "prevClose": 1.0}])}, seen
    )
    provider.get_quote("SPY")
    provider.get_quote("SPY")
    assert len(seen) == 1


def test_share_class_uses_hyphen() -> None:
    seen: list[httpx.Request] = []
    provider = provider_with(
        {"/tiingo/daily/brk-b": httpx.Response(200, json={"ticker": "brk-b", "name": "Berkshire"})},
        seen,
    )
    assert provider.get_profile("BRK.B").name == "Berkshire"
    assert seen[0].url.path == "/tiingo/daily/brk-b"


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, ProviderAuthError),
        (403, ProviderAuthError),
        (404, TickerNotFoundError),
        (429, ProviderRateLimitError),
        (500, ProviderError),
    ],
)
def test_http_errors_map_to_provider_errors(status: int, error: type[Exception]) -> None:
    provider = provider_with({"/iex/x": httpx.Response(status, json={})})
    with pytest.raises(error):
        provider.get_quote("X")


def test_not_found_detail_in_success_body() -> None:
    provider = provider_with(
        {"/tiingo/daily/zzzz": httpx.Response(200, json={"detail": "Error: Ticker 'ZZZZ' not found"})}
    )
    with pytest.raises(TickerNotFoundError):
        provider.get_profile("ZZZZ")


def test_network_failure_is_a_provider_error() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    provider = TiingoProvider("k", transport=httpx.MockTransport(fail))
    with pytest.raises(ProviderError, match="Could not reach Tiingo"):
        provider.get_quote("SPY")


def test_search_skips_inactive_and_foreign_listings() -> None:
    provider = provider_with(
        {
            "/tiingo/utilities/search": httpx.Response(
                200,
                json=[
                    {"ticker": "AAPL", "name": "Apple Inc", "assetType": "Stock", "isActive": True,
                     "countryCode": "US"},
                    {"ticker": "OLD", "name": "Old Co", "isActive": False, "countryCode": "US"},
                    {"ticker": "APC", "name": "Apple (DE)", "isActive": True, "countryCode": "DE"},
                ],
            )
        }
    )
    assert [s.ticker for s in provider.search("apple", 10)] == ["AAPL"]

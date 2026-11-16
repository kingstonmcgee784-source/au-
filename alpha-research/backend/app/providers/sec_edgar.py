"""SEC EDGAR client: ticker-to-CIK lookup and XBRL company facts.

Free, no API key. The SEC requires every automated request to carry a
User-Agent naming the requester with a contact email, and allows at most 10
requests per second: https://www.sec.gov/os/accessing-edgar-data

This module only retrieves data. Turning facts into statements happens in
`app.providers.sec_xbrl`.
"""

import threading
import time
from typing import Any

import httpx

from app.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    TickerNotFoundError,
)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
TICKER_CACHE_SECONDS = 24 * 60 * 60


class SecEdgarClient:
    name = "sec_edgar"

    def __init__(
        self,
        user_agent: str,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if "@" not in user_agent:
            raise ValueError("The SEC requires a User-Agent with a contact email address")
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=timeout_seconds,
            transport=transport,
        )
        self._lock = threading.Lock()
        self._tickers: dict[str, tuple[int, str]] = {}
        self._tickers_loaded_at = 0.0

    def lookup(self, ticker: str) -> tuple[int, str]:
        """Return (CIK, company name) for a ticker."""
        with self._lock:
            stale = time.monotonic() - self._tickers_loaded_at > TICKER_CACHE_SECONDS
            if stale or not self._tickers:
                self._tickers = self._load_tickers()
                self._tickers_loaded_at = time.monotonic()
            # SEC writes share classes with a hyphen (BRK-B).
            match = self._tickers.get(ticker.upper().replace(".", "-"))
        if match is None:
            raise TickerNotFoundError(f"The SEC has no company registered under {ticker}")
        return match

    def company_facts(self, cik: int) -> dict[str, Any]:
        data = self._get_json(FACTS_URL.format(cik=cik))
        if not isinstance(data, dict) or "facts" not in data:
            raise ProviderError("Unexpected company facts response from the SEC")
        return data

    def _load_tickers(self) -> dict[str, tuple[int, str]]:
        data = self._get_json(TICKERS_URL)
        if not isinstance(data, dict):
            raise ProviderError("Unexpected ticker list response from the SEC")
        tickers: dict[str, tuple[int, str]] = {}
        for row in data.values():
            try:
                tickers[str(row["ticker"]).upper()] = (int(row["cik_str"]), str(row["title"]))
            except (KeyError, TypeError, ValueError):
                continue
        return tickers

    def _get_json(self, url: str) -> Any:
        try:
            response = self._client.get(url)
        except httpx.TimeoutException as exc:
            raise ProviderError("The SEC did not respond in time") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Could not reach the SEC ({exc.__class__.__name__})") from exc

        if response.status_code == 403:
            raise ProviderAuthError(
                "The SEC refused the request. Set SEC_USER_AGENT to your name and email, "
                'e.g. "Jane Doe jane@example.com".'
            )
        if response.status_code == 404:
            raise TickerNotFoundError("The SEC has no XBRL financial data for this company")
        if response.status_code == 429:
            raise ProviderRateLimitError("The SEC's request limit was reached. Try again shortly.")
        if response.status_code >= 400:
            raise ProviderError(f"The SEC returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("The SEC returned a response that is not JSON") from exc

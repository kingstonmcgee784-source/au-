"""Tiingo market data provider.

Docs: https://www.tiingo.com/documentation/general/connecting

Endpoints used:
  - GET /tiingo/daily/{ticker}             ticker metadata
  - GET /tiingo/daily/{ticker}/prices      end-of-day OHLCV history
  - GET /iex/{ticker}                      latest IEX-derived price
  - GET /tiingo/utilities/search?query=    ticker search (beta at Tiingo)

The free plan allows 50 requests an hour, so quotes are cached in memory. If
the limit is reached, the last cached quote is returned (its timestamp shows
its age) rather than an error.
"""

import logging
import threading
import time
from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.providers.base import (
    PriceBar,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    TickerNotFoundError,
)
from app.schemas.stocks import Quote, StockSummary

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tiingo.com"
QUOTE_FEED = "Tiingo IEX reference price (single venue, not consolidated tape)"


class TiingoProvider:
    name = "tiingo"

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 15.0,
        quote_cache_seconds: float = 600.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Tiingo requires an API key")
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
            timeout=timeout_seconds,
            transport=transport,
        )
        self._quote_cache_seconds = quote_cache_seconds
        self._quote_cache: dict[str, tuple[float, Quote]] = {}
        self._lock = threading.Lock()

    # -- public API -----------------------------------------------------------

    def search(self, query: str, limit: int) -> list[StockSummary]:
        rows = self._get_json("/tiingo/utilities/search", params={"query": query})
        results: list[StockSummary] = []
        for row in _as_list(rows):
            if not row.get("isActive", True):
                continue
            if row.get("countryCode") not in (None, "US"):
                continue
            ticker = str(row.get("ticker") or "").upper()
            if not ticker:
                continue
            results.append(
                StockSummary(
                    ticker=ticker,
                    name=str(row.get("name") or ticker),
                    exchange=None,
                    sector=None,
                    industry=row.get("assetType"),
                    currency="USD",
                )
            )
            if len(results) >= limit:
                break
        return results

    def get_profile(self, ticker: str) -> StockSummary:
        data = self._get_json(f"/tiingo/daily/{_path(ticker)}", ticker=ticker)
        if not isinstance(data, dict):
            raise ProviderError("Unexpected metadata response from Tiingo")
        return StockSummary(
            ticker=str(data.get("ticker") or ticker).upper(),
            name=str(data.get("name") or ticker).strip(),
            exchange=data.get("exchangeCode"),
            sector=None,
            industry=None,
            currency="USD",
        )

    def get_quote(self, ticker: str) -> Quote:
        now = time.monotonic()
        with self._lock:
            cached = self._quote_cache.get(ticker)
            if cached and now - cached[0] < self._quote_cache_seconds:
                return cached[1]

        try:
            rows = _as_list(self._get_json(f"/iex/{_path(ticker)}", ticker=ticker))
        except ProviderRateLimitError:
            if cached:
                logger.info("Tiingo rate limit reached; serving cached quote for %s", ticker)
                return cached[1]
            raise
        if not rows:
            raise TickerNotFoundError(f"Tiingo has no IEX price for {ticker}")
        row = rows[0]
        price = _float(row.get("tngoLast")) or _float(row.get("last"))
        if price is None:
            raise ProviderError(f"Tiingo returned no price for {ticker}")
        prev_close = _float(row.get("prevClose"))
        change = price - prev_close if prev_close else None
        quote = Quote(
            ticker=ticker,
            price=price,
            change=change,
            change_percent=(change / prev_close * 100) if change is not None and prev_close else None,
            previous_close=prev_close,
            volume=_int(row.get("volume")),
            timestamp=_datetime(row.get("timestamp")) or datetime.now(UTC),
            feed=QUOTE_FEED,
        )
        with self._lock:
            self._quote_cache[ticker] = (now, quote)
        return quote

    def get_daily_prices(self, ticker: str, start: date, end: date | None = None) -> list[PriceBar]:
        params = {"startDate": start.isoformat()}
        if end is not None:
            params["endDate"] = end.isoformat()
        rows = self._get_json(f"/tiingo/daily/{_path(ticker)}/prices", params=params, ticker=ticker)
        bars: list[PriceBar] = []
        for row in _as_list(rows):
            parsed = _datetime(row.get("date"))
            values = [_float(row.get(k)) for k in ("open", "high", "low", "close")]
            volume = _int(row.get("volume"))
            if parsed is None or any(v is None for v in values) or volume is None:
                logger.warning("Skipping incomplete Tiingo bar for %s: %s", ticker, row)
                continue
            open_, high, low, close = values
            bars.append(
                PriceBar(
                    date=parsed.date(),
                    open=open_,  # type: ignore[arg-type]
                    high=high,  # type: ignore[arg-type]
                    low=low,  # type: ignore[arg-type]
                    close=close,  # type: ignore[arg-type]
                    adjusted_close=_float(row.get("adjClose")),
                    volume=volume,
                )
            )
        bars.sort(key=lambda bar: bar.date)
        return bars

    def close(self) -> None:
        self._client.close()

    # -- HTTP -----------------------------------------------------------------

    def _get_json(
        self, path: str, *, params: dict[str, str] | None = None, ticker: str | None = None
    ) -> Any:
        try:
            response = self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderError("Tiingo did not respond in time") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Could not reach Tiingo ({exc.__class__.__name__})") from exc

        if response.status_code in (401, 403):
            raise ProviderAuthError("Tiingo rejected the API key. Check MARKET_DATA_API_KEY.")
        if response.status_code == 404:
            raise TickerNotFoundError(f"Tiingo does not recognize {ticker or 'this request'}")
        if response.status_code == 429:
            raise ProviderRateLimitError("Tiingo's request limit was reached. Try again later.")
        if response.status_code >= 400:
            raise ProviderError(f"Tiingo returned HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError("Tiingo returned a response that is not JSON") from exc

        # Tiingo sometimes reports errors in a 200 body, e.g. {"detail": "..."}.
        if isinstance(data, dict) and "detail" in data and len(data) == 1:
            detail = str(data["detail"])
            if "not found" in detail.lower():
                raise TickerNotFoundError(f"Tiingo does not recognize {ticker or 'this request'}")
            raise ProviderError(f"Tiingo error: {detail}")
        return data


def _path(ticker: str) -> str:
    # Tiingo writes share classes with a hyphen (BRK-B), not a dot.
    return ticker.replace(".", "-").lower()


def _as_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

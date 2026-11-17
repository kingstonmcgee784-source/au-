"""An in-memory market data provider for tests. Its numbers are test fixtures only."""

from datetime import UTC, date, datetime, timedelta

from app.providers.base import PriceBar, ProviderError, TickerNotFoundError
from app.schemas.stocks import Quote, StockSummary


class FakeProvider:
    name = "fake"

    def __init__(self, known: dict[str, list[PriceBar]] | None = None) -> None:
        self.known = known or {}
        self.fail_with: ProviderError | None = None
        self.price_requests: list[tuple[str, date, date | None]] = []

    def _check(self, ticker: str) -> None:
        if self.fail_with:
            raise self.fail_with
        if ticker not in self.known:
            raise TickerNotFoundError(ticker)

    def search(self, query: str, limit: int) -> list[StockSummary]:
        return [self.get_profile(t) for t in self.known if query.upper() in t][:limit]

    def get_profile(self, ticker: str) -> StockSummary:
        self._check(ticker)
        return StockSummary(
            ticker=ticker,
            name=f"{ticker} Test Co",
            exchange="NASDAQ",
            sector=None,
            industry=None,
            currency="USD",
        )

    def get_quote(self, ticker: str) -> Quote:
        self._check(ticker)
        bars = self.known[ticker]
        last = bars[-1].close if bars else 1.0
        return Quote(
            ticker=ticker,
            price=last,
            change=None,
            change_percent=None,
            previous_close=None,
            volume=None,
            timestamp=datetime(2026, 11, 16, tzinfo=UTC),
            feed="fake feed",
        )

    def get_daily_prices(self, ticker: str, start: date, end: date | None = None) -> list[PriceBar]:
        self._check(ticker)
        self.price_requests.append((ticker, start, end))
        return [b for b in self.known[ticker] if b.date >= start and (end is None or b.date <= end)]


def bars(
    start: date, count: int, first_close: float = 100.0, adjust: float = 1.0
) -> list[PriceBar]:
    """Rising daily bars. `adjust` scales adjusted closes, e.g. 0.5 after a 2-for-1 split."""
    return [
        PriceBar(
            date=start + timedelta(days=i),
            open=first_close + i,
            high=first_close + i,
            low=first_close + i,
            close=first_close + i,
            adjusted_close=(first_close + i) * adjust,
            volume=1000,
        )
        for i in range(count)
    ]

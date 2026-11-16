"""Technical snapshot computed from stored daily prices."""

from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import technical
from app.models import HistoricalPrice
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import IndicatorValue, TechnicalSnapshot
from app.services.stocks import LOCAL_SOURCE, find_stock, no_stored_stock

# Enough bars for the longest indicator (200-day SMA) plus headroom.
MAX_BARS = 400
MIN_BARS = 2

Series = Sequence[float]
IndicatorFn = Callable[[Series], list[float | None]]

INDICATORS: tuple[tuple[str, int, IndicatorFn], ...] = (
    ("ema_9", 9, lambda c: technical.ema(c, 9)),
    ("ema_20", 20, lambda c: technical.ema(c, 20)),
    ("ema_21", 21, lambda c: technical.ema(c, 21)),
    ("sma_50", 50, lambda c: technical.sma(c, 50)),
    ("sma_100", 100, lambda c: technical.sma(c, 100)),
    ("sma_200", 200, lambda c: technical.sma(c, 200)),
    ("rsi_14", 15, lambda c: technical.rsi(c, 14)),
    ("macd", 26, lambda c: technical.macd(c)[0]),
    ("macd_signal", 34, lambda c: technical.macd(c)[1]),
    ("macd_histogram", 34, lambda c: technical.macd(c)[2]),
)


def get_snapshot(db: Session, ticker: str) -> DataResponse[TechnicalSnapshot]:
    stock = find_stock(db, ticker)
    if stock is None:
        return unavailable(UnavailableReason.NO_STORED_DATA, no_stored_stock(ticker))

    newest_first = db.scalars(
        select(HistoricalPrice)
        .where(HistoricalPrice.stock_id == stock.id)
        .order_by(HistoricalPrice.date.desc())
        .limit(MAX_BARS)
    ).all()
    if len(newest_first) < MIN_BARS:
        return unavailable(
            UnavailableReason.INSUFFICIENT_HISTORY,
            f"{ticker} has {len(newest_first)} stored daily bars; "
            f"at least {MIN_BARS} are needed. Price ingestion has not been built yet.",
        )

    bars = list(reversed(newest_first))
    closes = [bar.adjusted_close if bar.adjusted_close is not None else bar.close for bar in bars]
    indicators = [
        IndicatorValue(name=name, value=compute(closes)[-1], required_bars=required)
        for name, required, compute in INDICATORS
    ]
    latest = bars[-1]
    return ok(
        TechnicalSnapshot(
            ticker=ticker,
            as_of_date=latest.date,
            bars_available=len(bars),
            last_close=closes[-1],
            indicators=indicators,
        ),
        source=LOCAL_SOURCE,
        as_of=latest.retrieved_at,
    )

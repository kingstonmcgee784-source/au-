"""The holding plan for a stock, from stored prices and its latest score."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.holding import PriceBar, build_plan, stop_and_target
from app.analysis.scoring import CATEGORIES
from app.models import FinancialMetric, HistoricalPrice, StockScore
from app.schemas.common import DataResponse, DataStatus, UnavailableReason, ok, unavailable
from app.schemas.stocks import HoldingPlan, PlanCheck
from app.services import catalysts
from app.services.stocks import LOCAL_SOURCE, find_stock, no_stored_stock

MAX_BARS = 300


def get_plan(db: Session, ticker: str) -> DataResponse[HoldingPlan]:
    stock = find_stock(db, ticker)
    if stock is None:
        return unavailable(UnavailableReason.NO_STORED_DATA, no_stored_stock(ticker))
    rows = db.scalars(
        select(HistoricalPrice)
        .where(HistoricalPrice.stock_id == stock.id)
        .order_by(HistoricalPrice.date.desc())
        .limit(MAX_BARS)
    ).all()
    bars = [PriceBar(r.date, r.high, r.low, r.close, r.adjusted_close) for r in reversed(rows)]
    score = db.scalar(
        select(StockScore)
        .where(StockScore.stock_id == stock.id)
        .order_by(StockScore.as_of.desc(), StockScore.id.desc())
        .limit(1)
    )
    ratings: dict[str, float | None] = {}
    relative_strength = None
    if score is not None:
        ratings = {
            key: (value / weight if value is not None else None)
            for key, value, weight in _category_points(score)
        }
        relative_strength = db.scalar(
            select(FinancialMetric.value).where(
                FinancialMetric.stock_id == stock.id,
                FinancialMetric.as_of == score.as_of,
                FinancialMetric.metric == "relative_strength_6m",
                FinancialMetric.source == "alpha_research",
            )
        )
    feed = catalysts.get_catalysts(db, ticker)
    next_earnings = (
        feed.data.next_earnings_estimate if feed.status == DataStatus.OK and feed.data else None
    )
    plan = build_plan(
        bars,
        today=datetime.now(UTC).date(),
        category_ratings=ratings,
        relative_strength_6m=relative_strength,
        next_earnings=next_earnings,
    )
    if plan is None:
        return unavailable(
            UnavailableReason.INSUFFICIENT_HISTORY,
            f"{ticker} has {len(bars)} stored daily prices; a holding plan needs at least 60. "
            "Load its price history first.",
        )
    checks = [
        PlanCheck(label=c.label, passed=c.passed, detail=c.detail) for c in plan.pop("checks")
    ]
    return ok(
        HoldingPlan(
            ticker=ticker,
            checks=checks,
            score=score.total_score if score else None,
            **plan,
        ),
        source=LOCAL_SOURCE,
        as_of=rows[0].retrieved_at if rows else None,
    )


def _category_points(score: StockScore) -> list[tuple[str, float | None, float]]:
    points = score.category_scores or {}
    return [(c.key, points.get(c.key), c.weight) for c in CATEGORIES]


def levels_as_of(db: Session, stock_id: int, as_of: date) -> tuple[float, float] | None:
    """Stop and target percentages from prices on or before `as_of` only, for
    calls recorded before holding plans existed."""
    rows = db.scalars(
        select(HistoricalPrice)
        .where(HistoricalPrice.stock_id == stock_id, HistoricalPrice.date <= as_of)
        .order_by(HistoricalPrice.date.desc())
        .limit(MAX_BARS)
    ).all()
    bars = [PriceBar(r.date, r.high, r.low, r.close, r.adjusted_close) for r in reversed(rows)]
    return stop_and_target(bars)

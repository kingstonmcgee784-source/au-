"""Stored stock scores, rankings and the scoring methodology."""

from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis import ratings, scoring
from app.models import FinancialMetric, Stock, StockScore
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import (
    CategoryScore,
    RankingEntry,
    ScoreCategory,
    ScoreInput,
    ScoringMethodology,
    StockScoreOut,
)
from app.services.stocks import LOCAL_SOURCE, find_stock


def methodology() -> ScoringMethodology:
    return ScoringMethodology(
        version=scoring.METHODOLOGY_VERSION,
        categories=[
            ScoreCategory(key=c.key, label=c.label, weight=c.weight) for c in scoring.CATEGORIES
        ],
        bands=[{"min_score": minimum, "label": label} for minimum, label in scoring.BANDS],
    )


def score_out(
    ticker: str, row: StockScore, metrics: Mapping[str, float | None] | None = None
) -> StockScoreOut:
    """A stored score with a full breakdown per category.

    Input values come from the breakdown stored with the score, or, for scores
    saved before breakdowns existed, from the metrics calculated for the same
    date. Scales and explanations are always rebuilt from the rating rules.
    """
    details = row.details or {}
    categories = []
    for category in scoring.CATEGORIES:
        detail = details.get(category.key)
        detail = detail if isinstance(detail, dict) else {}
        stored = {
            b["metric"]: b["value"]
            for b in detail.get("breakdown") or []
            if b.get("value") is not None
        }
        values = {**{k: v for k, v in (metrics or {}).items() if v is not None}, **stored}
        rated = row.category_scores.get(category.key) is not None
        saved = {
            b["metric"]: b["rating"]
            for b in detail.get("breakdown") or []
            if b.get("rating") is not None
        }
        breakdown, missing = ratings.input_details(category.key, values, saved)
        if not rated:
            breakdown = []  # too few inputs: only list what is missing
        categories.append(
            CategoryScore(
                key=category.key,
                label=category.label,
                weight=category.weight,
                points=row.category_scores.get(category.key),
                inputs=detail.get("inputs") or {},
                breakdown=[ScoreInput.model_validate(b) for b in breakdown],
                missing=missing,
                minimum_inputs=ratings.CATEGORY_RULES[category.key][0],
                summary=_with_adjustment(ratings.category_summary(breakdown), detail),
                unrated_reason=detail.get("unrated_reason"),
            )
        )
    return StockScoreOut(
        ticker=ticker,
        as_of=row.as_of,
        total_score=row.total_score,
        interpretation=scoring.interpret(row.total_score),
        coverage=row.coverage,
        categories=categories,
        methodology_version=row.methodology_version,
        risk_class=row.risk_class,
        notes=row.notes,
        calculated_at=row.calculated_at,
    )


def rankings(db: Session, limit: int) -> DataResponse[list[RankingEntry]]:
    """Each stock's most recent score, highest first."""
    newest_first = (
        select(
            StockScore.id,
            func.row_number()
            .over(
                partition_by=StockScore.stock_id,
                order_by=(StockScore.as_of.desc(), StockScore.id.desc()),
            )
            .label("position"),
        )
    ).subquery()
    rows = db.execute(
        select(StockScore, Stock)
        .join(newest_first, StockScore.id == newest_first.c.id)
        .join(Stock, Stock.id == StockScore.stock_id)
        .where(newest_first.c.position == 1)
        .order_by(StockScore.total_score.desc(), Stock.ticker)
        .limit(limit)
    ).all()
    if not rows:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            "No stocks have been scored yet. Open a stock in Stock Analysis and use "
            "Calculate score.",
        )
    entries = [
        RankingEntry(
            rank=index,
            ticker=stock.ticker,
            name=stock.name,
            total_score=score.total_score,
            coverage=score.coverage,
            interpretation=scoring.interpret(score.total_score),
            risk_class=score.risk_class,
            as_of=score.as_of,
        )
        for index, (score, stock) in enumerate(rows, start=1)
    ]
    return ok(entries, source=LOCAL_SOURCE, as_of=max(score.calculated_at for score, _ in rows))


def get_latest_score(db: Session, ticker: str) -> DataResponse[StockScoreOut]:
    stock = find_stock(db, ticker)
    score = (
        db.scalar(
            select(StockScore)
            .where(StockScore.stock_id == stock.id)
            .order_by(StockScore.as_of.desc(), StockScore.id.desc())
            .limit(1)
        )
        if stock
        else None
    )
    if score is None:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"{ticker} has not been scored yet. Use Calculate score to load its data and score it.",
        )
    metrics = {
        m.metric: m.value
        for m in db.scalars(
            select(FinancialMetric).where(
                FinancialMetric.stock_id == stock.id,
                FinancialMetric.as_of == score.as_of,
                FinancialMetric.source == "alpha_research",
            )
        )
    }
    return ok(score_out(ticker, score, metrics), source=LOCAL_SOURCE, as_of=score.calculated_at)


def _with_adjustment(summary: str | None, detail: Mapping[str, object]) -> str | None:
    """Add the reason a category was adjusted after its inputs were rated."""
    adjustment = detail.get("adjustment")
    if not isinstance(adjustment, dict) or not adjustment.get("note"):
        return summary
    return f"{summary} {adjustment['note']}" if summary else str(adjustment["note"])

"""Stored stock scores and the scoring methodology."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis import scoring
from app.models import Stock, StockScore
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import RankingEntry, ScoreCategory, ScoringMethodology, StockScoreOut
from app.services.stocks import LOCAL_SOURCE, find_stock, no_stored_stock


def methodology() -> ScoringMethodology:
    return ScoringMethodology(
        version=scoring.METHODOLOGY_VERSION,
        categories=[
            ScoreCategory(key=c.key, label=c.label, weight=c.weight) for c in scoring.CATEGORIES
        ],
        bands=[{"min_score": minimum, "label": label} for minimum, label in scoring.BANDS],
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
            "No stocks have been scored yet. Scoring needs fundamental and price data, "
            "which is not ingested yet.",
        )
    entries = [
        RankingEntry(
            rank=index,
            ticker=stock.ticker,
            name=stock.name,
            total_score=score.total_score,
            interpretation=scoring.interpret(score.total_score),
            risk_class=score.risk_class,
            as_of=score.as_of,
        )
        for index, (score, stock) in enumerate(rows, start=1)
    ]
    return ok(entries, source=LOCAL_SOURCE, as_of=max(score.calculated_at for score, _ in rows))


def get_latest_score(db: Session, ticker: str) -> DataResponse[StockScoreOut]:
    stock = find_stock(db, ticker)
    if stock is None:
        return unavailable(UnavailableReason.NO_STORED_DATA, no_stored_stock(ticker))

    score = db.scalar(
        select(StockScore)
        .where(StockScore.stock_id == stock.id)
        .order_by(StockScore.as_of.desc(), StockScore.id.desc())
        .limit(1)
    )
    if score is None:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"No score has been calculated for {ticker}. "
            "The scoring pipeline needs fundamental and price data first.",
        )
    return ok(
        StockScoreOut(
            ticker=ticker,
            as_of=score.as_of,
            total_score=score.total_score,
            interpretation=scoring.interpret(score.total_score),
            category_scores=score.category_scores,
            methodology_version=score.methodology_version,
            risk_class=score.risk_class,
            notes=score.notes,
        ),
        source=LOCAL_SOURCE,
        as_of=score.calculated_at,
    )

"""Score a stock: optionally refresh its data, calculate metrics, rate and store.

Steps (each in its own layer):
  1. Retrieval: sync prices and SEC statements into the database (ingestion).
  2. Calculation: metrics from the stored rows (analysis.metrics).
  3. Rating: metrics to category ratings and a 0-100 score (analysis.ratings,
     analysis.scoring).
  4. Storage: the score with its breakdown, and the metrics, so every number
     shown later can be traced back.
"""

import logging
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import scoring
from app.analysis.metrics import Metrics, Period, PricePoint, compute_metrics
from app.analysis.ratings import UNRATED_REASON, rate, risk_class
from app.models import FinancialMetric, FinancialStatement, HistoricalPrice, StockScore
from app.providers.base import FundamentalsSource, MarketDataProvider
from app.schemas.common import DataResponse, DataStatus, UnavailableReason, ok, unavailable
from app.schemas.stocks import MetricsSnapshot, StockScoreOut
from app.services import ingestion, insiders
from app.services.scores import score_out
from app.services.stocks import LOCAL_SOURCE, find_stock

logger = logging.getLogger(__name__)

BENCHMARK = "SPY"
# A score is only produced when these are all rated. Without them a total
# would mostly reflect whichever categories happened to have data.
REQUIRED_CATEGORIES = ("fundamentals", "valuation", "technical", "growth")
WHAT_IS_NEEDED = {
    "fundamentals": "quarterly financial statements (Load financials)",
    "valuation": "financial statements plus a current price",
    "technical": "about 200 days of price history (Load price history)",
    "growth": "at least five quarters of financial statements",
}
METRICS_SOURCE = "alpha_research"
PRICE_BARS = 400
QUARTERS = 12


def score_stock(
    db: Session,
    ticker: str,
    *,
    market: MarketDataProvider | None,
    fundamentals: FundamentalsSource | None,
    refresh: bool,
    history_years: int,
) -> DataResponse[StockScoreOut]:
    warnings: list[str] = []
    if refresh:
        for label, result in (
            ("prices", ingestion.sync_prices(db, market, ticker, history_years=history_years)),
            (
                "S&P 500 benchmark prices",
                ingestion.sync_prices(db, market, BENCHMARK, history_years=history_years),
            ),
            ("financial statements", ingestion.sync_financials(db, fundamentals, ticker)),
            ("insider filings", insiders.sync_insiders(db, fundamentals, ticker)),
        ):
            if result.status != DataStatus.OK:
                warnings.append(f"Could not refresh {label}: {result.message}")

    stock = find_stock(db, ticker)
    if stock is None:
        detail = " ".join(warnings) or f"{ticker} has no stored data."
        return unavailable(UnavailableReason.NO_STORED_DATA, f"Cannot score {ticker}. {detail}")

    prices = _prices(db, stock.id)
    benchmark = find_stock(db, BENCHMARK)
    metrics = compute_metrics(
        income=_statements(db, stock.id, "income"),
        cashflow=_statements(db, stock.id, "cashflow"),
        balance=_statements(db, stock.id, "balance"),
        prices=prices,
        benchmark=_prices(db, benchmark.id) if benchmark and benchmark.id != stock.id else [],
    )
    metrics.update(
        insiders.insider_metrics(
            db,
            stock,
            as_of=prices[-1].date if prices else datetime.now(UTC).date(),
            market_cap=metrics.get("market_cap"),
        )
    )
    ratings = rate(metrics)
    missing = [key for key in REQUIRED_CATEGORIES if ratings[key].rating is None]
    if missing:
        needs = "; ".join(f"{key.replace('_', ' ')} needs {WHAT_IS_NEEDED[key]}" for key in missing)
        return unavailable(
            UnavailableReason.INSUFFICIENT_HISTORY,
            f"Not enough data to score {ticker}: {needs}. " + " ".join(warnings),
        )

    total, points, coverage = scoring.partial_score({k: r.rating for k, r in ratings.items()})
    as_of = prices[-1].date if prices else datetime.now(UTC).date()
    details: dict[str, object] = {
        key: {
            "inputs": rating.used,
            "unrated_reason": None
            if rating.rating is not None
            else UNRATED_REASON.get(key, "Not enough data for this category."),
        }
        for key, rating in ratings.items()
    }
    unrated = [c.label for c in scoring.CATEGORIES if points[c.key] is None]
    notes = (
        f"Not scored for lack of data: {', '.join(unrated)}. " if unrated else ""
    ) + "Thresholds are absolute, not sector-relative (methodology v1)."
    if points["institutional"] is not None:
        notes += " Institutional and insider activity uses Form 4 insider trades only (no 13F)."
    if warnings:
        notes += " " + " ".join(warnings)

    row = StockScore(
        stock_id=stock.id,
        as_of=as_of,
        total_score=total,
        category_scores=points,
        coverage=coverage,
        details=details,
        methodology_version=scoring.METHODOLOGY_VERSION,
        risk_class=risk_class(metrics),
        notes=notes,
    )
    db.add(row)
    _store_metrics(db, stock.id, as_of, metrics)
    db.commit()
    return ok(score_out(ticker, row), source=METRICS_SOURCE, as_of=row.calculated_at)


def latest_metrics(db: Session, ticker: str) -> DataResponse[MetricsSnapshot]:
    stock = find_stock(db, ticker)
    newest = (
        db.scalar(
            select(FinancialMetric.as_of)
            .where(FinancialMetric.stock_id == stock.id, FinancialMetric.source == METRICS_SOURCE)
            .order_by(FinancialMetric.as_of.desc())
            .limit(1)
        )
        if stock
        else None
    )
    if stock is None or newest is None:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"No metrics have been calculated for {ticker}. Use Calculate score first.",
        )
    rows = db.scalars(
        select(FinancialMetric).where(
            FinancialMetric.stock_id == stock.id,
            FinancialMetric.as_of == newest,
            FinancialMetric.source == METRICS_SOURCE,
        )
    ).all()
    return ok(
        MetricsSnapshot(ticker=ticker, as_of=newest, values={r.metric: r.value for r in rows}),
        source=LOCAL_SOURCE,
        as_of=max(r.retrieved_at for r in rows),
    )


def _statements(db: Session, stock_id: int, statement_type: str) -> list[Period]:
    rows = db.scalars(
        select(FinancialStatement)
        .where(
            FinancialStatement.stock_id == stock_id,
            FinancialStatement.statement_type == statement_type,
            FinancialStatement.period_type == "quarterly",
        )
        .order_by(FinancialStatement.period_end.desc())
        .limit(QUARTERS)
    ).all()
    return [Period(end=r.period_end, items=dict(r.line_items)) for r in rows]


def _prices(db: Session, stock_id: int) -> list[PricePoint]:
    rows = db.execute(
        select(HistoricalPrice.date, HistoricalPrice.close, HistoricalPrice.adjusted_close)
        .where(HistoricalPrice.stock_id == stock_id)
        .order_by(HistoricalPrice.date.desc())
        .limit(PRICE_BARS)
    ).all()
    return [PricePoint(date=d, close=adj if adj is not None else c) for d, c, adj in reversed(rows)]


def _store_metrics(db: Session, stock_id: int, as_of: date, metrics: Metrics) -> None:
    existing = {
        m.metric: m
        for m in db.scalars(
            select(FinancialMetric).where(
                FinancialMetric.stock_id == stock_id,
                FinancialMetric.as_of == as_of,
                FinancialMetric.source == METRICS_SOURCE,
            )
        )
    }
    now = datetime.now(UTC)
    for name, value in metrics.items():
        row = existing.get(name)
        if row is None:
            row = FinancialMetric(
                stock_id=stock_id, metric=name, as_of=as_of, source=METRICS_SOURCE
            )
            db.add(row)
        row.value = value
        row.period = "TTM / latest"
        row.data_kind = "calculated"
        row.retrieved_at = now

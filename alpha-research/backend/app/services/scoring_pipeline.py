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
from dataclasses import asdict, replace
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import commodity, scoring, sector
from app.analysis.metrics import Metrics, Period, PricePoint, compute_metrics
from app.analysis.ratings import UNRATED_REASON, rate, risk_class
from app.models import FinancialMetric, FinancialStatement, HistoricalPrice, Stock, StockScore
from app.providers.base import FundamentalsSource, MarketDataProvider
from app.schemas.common import DataResponse, DataStatus, UnavailableReason, ok, unavailable
from app.schemas.stocks import MetricsSnapshot, StockScoreOut
from app.services import catalysts, industry, ingestion, insiders
from app.services import market as market_gauges
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
    sec_unknown = False
    if refresh:
        for label, result in (
            ("prices", ingestion.sync_prices(db, market, ticker, history_years=history_years)),
            (
                "S&P 500 benchmark prices",
                ingestion.sync_prices(db, market, BENCHMARK, history_years=history_years),
            ),
            ("financial statements", ingestion.sync_financials(db, fundamentals, ticker)),
            ("insider filings", insiders.sync_all_insiders(db, fundamentals, ticker)),
            ("SEC 8-K events", catalysts.sync_events(db, fundamentals, ticker)),
        ):
            if result.status != DataStatus.OK:
                if result.reason == UnavailableReason.UNKNOWN_TICKER and label != "prices":
                    sec_unknown = True
                warnings.append(f"Could not refresh {label}: {result.message}")

    stock = find_stock(db, ticker)
    if refresh and stock is not None:
        # Sector and oil ETFs for the holding plan (each refreshed at most every 6 hours).
        for symbol, _label, _kind in sector.context_symbols(stock.sic_code):
            ingestion.sync_prices(db, market, symbol, history_years=history_years)
        # Market-wide gauges for the holding plan.
        market_gauges.sync(db, market, history_years=history_years)
    if stock is None:
        detail = " ".join(warnings) or f"{ticker} has no stored data."
        return unavailable(UnavailableReason.NO_STORED_DATA, f"Cannot score {ticker}. {detail}")

    if sec_unknown and not _statements(db, stock.id, "income"):
        return unavailable(
            UnavailableReason.UNKNOWN_TICKER,
            f"The SEC has no company with the ticker {ticker}, so it cannot be scored. Check "
            "the spelling, or type the company's name in the search box at the top to find "
            "its ticker. Only US-listed companies that file reports with the SEC can be "
            "scored; ETFs, funds and most foreign companies cannot.",
        )

    prices = _prices(db, stock.id)
    benchmark = find_stock(db, BENCHMARK)
    metrics = compute_metrics(
        income=_statements(db, stock.id, "income"),
        cashflow=_statements(db, stock.id, "cashflow"),
        balance=_statements(db, stock.id, "balance"),
        prices=prices,
        benchmark=_prices(db, benchmark.id) if benchmark and benchmark.id != stock.id else [],
    )
    metrics.update(catalysts.event_metrics(db, stock, today=datetime.now(UTC).date()))
    metrics.update(
        insiders.insider_metrics(
            db,
            stock,
            as_of=prices[-1].date if prices else datetime.now(UTC).date(),
            market_cap=metrics.get("market_cap"),
        )
    )
    as_of = prices[-1].date if prices else datetime.now(UTC).date()
    peer_metrics, peer_prefix, _ = industry.industry_metrics(db, stock, metrics, as_of)
    metrics.update(peer_metrics)
    ratings = rate(metrics)
    missing = [key for key in REQUIRED_CATEGORIES if ratings[key].rating is None]
    if missing:
        needs = "; ".join(f"{key.replace('_', ' ')} needs {WHAT_IS_NEEDED[key]}" for key in missing)
        return unavailable(
            UnavailableReason.INSUFFICIENT_HISTORY,
            f"Not enough data to score {ticker}: {needs}. " + " ".join(warnings),
        )

    adjustments, oil_note = _oil_adjustment(db, stock, as_of, metrics)
    for key, multiplier in adjustments.items():
        if ratings[key].rating is not None:
            ratings[key] = replace(ratings[key], rating=ratings[key].rating * multiplier)

    total, points, coverage = scoring.partial_score({k: r.rating for k, r in ratings.items()})
    details: dict[str, object] = {
        key: {
            "inputs": rating.used,
            "breakdown": [asdict(b) for b in rating.breakdown],
            "missing": rating.missing,
            "minimum": rating.minimum,
            "unrated_reason": None
            if rating.rating is not None
            else UNRATED_REASON.get(key, "Not enough data for this category."),
            "adjustment": (
                {"multiplier": adjustments[key], "note": oil_note}
                if key in adjustments and rating.rating is not None
                else None
            ),
        }
        for key, rating in ratings.items()
    }
    unrated = [c.label for c in scoring.CATEGORIES if points[c.key] is None]
    notes = (
        f"Not scored for lack of data: {', '.join(unrated)}. " if unrated else ""
    ) + "Thresholds are absolute, not sector-relative (methodology v1)."
    if points["institutional"] is not None:
        notes += " Institutional and insider activity uses Form 4 insider trades only (no 13F)."
    if points["industry"] is not None:
        notes += (
            f" Industry positioning compares {int(metrics['industry_peer_count'] or 0)} peers "
            f"stored locally with SEC industry code {peer_prefix}"
            f"{'x' * (4 - len(peer_prefix or ''))}."
        )
    if points["catalysts"] is not None:
        notes += (
            " Catalysts reflect SEC 8-K event types and an estimated earnings date; they cannot"
            " judge the size of a contract or the outcome of earnings."
        )
    if oil_note:
        lowered = any(m < 1.0 for m in adjustments.values())
        notes += (
            f" Oil adjustment (valuation and growth): {oil_note}" if lowered else f" {oil_note}"
        )
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
    response = ok(score_out(ticker, row, metrics), source=METRICS_SOURCE, as_of=row.calculated_at)
    if warnings:
        # Scored, but partly from older stored data: say which refreshes failed.
        response.message = " ".join(warnings)
    return response


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


def _oil_adjustment(
    db: Session, stock: Stock, as_of: date, metrics: Metrics
) -> tuple[dict[str, float], str | None]:
    """Multipliers for the categories that lag the oil price, for oil and gas
    companies only (see app.analysis.commodity), and a note explaining them."""
    if not (stock.sic_code or "").startswith(sector.OIL_PREFIXES):
        return {}, None
    oil = find_stock(db, sector.OIL[0])
    closes = (
        [
            adj if adj is not None else close
            for close, adj in db.execute(
                select(HistoricalPrice.close, HistoricalPrice.adjusted_close)
                .where(HistoricalPrice.stock_id == oil.id, HistoricalPrice.date <= as_of)
                .order_by(HistoricalPrice.date.desc())
                .limit(commodity.QUARTER)
            ).all()
        ][::-1]
        if oil
        else []
    )
    gap = commodity.oil_gap(closes)
    metrics["oil_vs_quarter_avg"] = gap
    if gap is None:
        return {key: 1.0 for key in commodity.ADJUSTED}, (
            "Oil check: oil prices (USO) are not loaded yet, so this rating is not adjusted "
            "for oil. Calculate the score again once they load (Tiingo allows 50 requests "
            "an hour)."
        )
    multiplier = commodity.factor(gap)
    # Always returned for oil companies, so the explanation says what was
    # checked even when nothing changed (a multiplier of 1).
    return {key: multiplier for key in commodity.ADJUSTED}, commodity.note(gap, multiplier)

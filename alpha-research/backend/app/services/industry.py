"""Industry peers and comparison, from stocks stored in the local database."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis.industry import POSITIONING, VALUATION, choose_group, percentiles
from app.analysis.metrics import Metrics
from app.models import FinancialMetric, Stock, StockScore
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import IndustryComparison, PeerRow
from app.services.stocks import LOCAL_SOURCE, find_stock

METRICS_SOURCE = "alpha_research"
# Peers scored longer ago than this are left out of comparisons.
PEER_MAX_AGE = timedelta(days=45)
SHOWN = ["market_cap", *POSITIONING, *VALUATION]


def latest_metrics_by_stock(db: Session) -> dict[int, Metrics]:
    """Each stock's most recently calculated metrics."""
    newest = (
        select(FinancialMetric.stock_id, func.max(FinancialMetric.as_of).label("as_of"))
        .where(FinancialMetric.source == METRICS_SOURCE)
        .group_by(FinancialMetric.stock_id)
        .subquery()
    )
    rows = db.execute(
        select(FinancialMetric.stock_id, FinancialMetric.metric, FinancialMetric.value)
        .join(
            newest,
            (FinancialMetric.stock_id == newest.c.stock_id)
            & (FinancialMetric.as_of == newest.c.as_of),
        )
        .where(FinancialMetric.source == METRICS_SOURCE)
    ).all()
    out: dict[int, Metrics] = {}
    for stock_id, metric, value in rows:
        out.setdefault(stock_id, {})[metric] = value
    return out


def latest_metric_dates(db: Session) -> dict[int, date]:
    """The date of each stock's most recently calculated metrics."""
    rows = db.execute(
        select(FinancialMetric.stock_id, func.max(FinancialMetric.as_of))
        .where(FinancialMetric.source == METRICS_SOURCE)
        .group_by(FinancialMetric.stock_id)
    ).all()
    return {stock_id: as_of for stock_id, as_of in rows}


def industry_metrics(
    db: Session, stock: Stock, metrics: Metrics, as_of: date
) -> tuple[dict[str, float | None], str | None, list[Stock]]:
    """Percentiles against peers, to be added to a stock's metrics for scoring.

    Only peers whose metrics were calculated within PEER_MAX_AGE of `as_of`
    are compared, so returns and growth are measured over similar periods.
    Returns ({industry_pct_<metric>: percentile, industry_peer_count: n}, the
    SIC prefix used, the peer stocks). Empty when there are too few peers.
    """
    stocks = {s.id: s for s in db.scalars(select(Stock).where(Stock.sic_code.is_not(None)))}
    peer_metrics = latest_metrics_by_stock(db)
    dates = latest_metric_dates(db)
    candidates = {
        s.ticker: s.sic_code
        for sid, s in stocks.items()
        if sid != stock.id
        and sid in peer_metrics
        and abs((dates[sid] - as_of).days) <= PEER_MAX_AGE.days
    }
    group = choose_group(stock.sic_code, candidates)
    if group is None:
        return {}, None, []
    by_ticker = {s.ticker: s for s in stocks.values()}
    peers = [by_ticker[t] for t in group.members]
    pct = percentiles(metrics, [peer_metrics[p.id] for p in peers], POSITIONING)
    out: dict[str, float | None] = {f"industry_pct_{k}": v for k, v in pct.items()}
    out["industry_peer_count"] = float(len(peers))
    return out, group.prefix, peers


def comparison(db: Session, ticker: str) -> DataResponse[IndustryComparison]:
    stock = find_stock(db, ticker)
    all_metrics = latest_metrics_by_stock(db)
    if stock is None or stock.id not in all_metrics:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"{ticker} has no calculated metrics yet. Use Calculate score first.",
        )
    if not stock.sic_code:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"The SEC industry code for {ticker} is not known yet. Calculate its score to load it.",
        )
    own = all_metrics[stock.id]
    _, prefix, peers = industry_metrics(db, stock, own, latest_metric_dates(db)[stock.id])
    if prefix is None:
        same = db.scalar(
            select(func.count(Stock.id)).where(
                Stock.sic_code == stock.sic_code, Stock.id != stock.id
            )
        )
        return unavailable(
            UnavailableReason.INSUFFICIENT_HISTORY,
            f"Only {same or 0} other scored stocks share {ticker}'s industry (SIC "
            f"{stock.sic_code}, {stock.industry or 'unknown'}), and peers count only if scored "
            f"within {PEER_MAX_AGE.days} days of it. At least 4 are needed: scan more stocks "
            "from this industry in the Screener.",
        )
    scores = _latest_scores(db, [stock.id, *(p.id for p in peers)])
    peer_values = [all_metrics[p.id] for p in peers]
    return ok(
        IndustryComparison(
            ticker=ticker,
            industry=stock.industry,
            sic_code=stock.sic_code,
            peer_group=f"SIC {prefix}{'x' * (4 - len(prefix))}",
            positioning=percentiles(own, peer_values, POSITIONING),
            valuation=percentiles(own, peer_values, VALUATION),
            rows=[
                PeerRow(
                    ticker=s.ticker,
                    name=s.name,
                    is_subject=s.id == stock.id,
                    score=scores.get(s.id),
                    metrics={k: all_metrics[s.id].get(k) for k in SHOWN},
                )
                for s in [stock, *peers]
            ],
        ),
        source=LOCAL_SOURCE,
    )


def _latest_scores(db: Session, stock_ids: list[int]) -> dict[int, float]:
    rows = db.execute(
        select(StockScore.stock_id, StockScore.total_score)
        .where(StockScore.stock_id.in_(stock_ids))
        .order_by(StockScore.as_of, StockScore.id)
    ).all()
    return {stock_id: score for stock_id, score in rows}  # later rows overwrite earlier

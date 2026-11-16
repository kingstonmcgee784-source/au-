"""Research reports and market overview."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.research_writer import ResearchWriter
from app.core.errors import NotFoundError
from app.models import ResearchReport
from app.providers.base import MarketDataProvider, ProviderError
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.research import (
    IndexLevel,
    MarketOverview,
    ResearchReportOut,
    ResearchReportSummary,
)
from app.services.stocks import provider_failure


def list_reports(db: Session, limit: int) -> list[ResearchReportSummary]:
    rows = db.scalars(
        select(ResearchReport)
        .order_by(ResearchReport.report_date.desc(), ResearchReport.id.desc())
        .limit(limit)
    ).all()
    return [ResearchReportSummary.model_validate(row) for row in rows]


def get_report(db: Session, report_id: int) -> ResearchReportOut:
    report = db.get(ResearchReport, report_id)
    if report is None:
        raise NotFoundError(f"Research report {report_id} does not exist")
    return ResearchReportOut.model_validate(report)


def generate_report(writer: ResearchWriter | None, ticker: str) -> DataResponse[ResearchReportOut]:
    if writer is None:
        return unavailable(
            UnavailableReason.AI_NOT_CONFIGURED,
            "AI report generation is not configured. It also needs stored financial "
            "and price data, which is not ingested yet.",
        )
    # Report generation will gather stored data, run the analysis modules and
    # pass the results to the writer. Until that pipeline exists, refuse.
    return unavailable(
        UnavailableReason.NO_STORED_DATA,
        f"The research pipeline for {ticker} has not been built yet.",
    )


# Index levels themselves need a licensed index feed. Liquid ETFs that track
# each index are used instead, and labelled as ETFs so nobody mistakes them.
INDEX_PROXIES: tuple[tuple[str, str], ...] = (
    ("SPY", "S&P 500 (SPY ETF)"),
    ("QQQ", "Nasdaq 100 (QQQ ETF)"),
    ("IWM", "Russell 2000 (IWM ETF)"),
    ("DIA", "Dow Jones (DIA ETF)"),
)


def market_overview(provider: MarketDataProvider | None) -> DataResponse[MarketOverview]:
    if provider is None:
        return unavailable(
            UnavailableReason.PROVIDER_NOT_CONFIGURED,
            "Market prices need a market data provider, and none is configured.",
        )
    levels: list[IndexLevel] = []
    timestamps = []
    for symbol, name in INDEX_PROXIES:
        try:
            quote = provider.get_quote(symbol)
        except ProviderError as exc:
            return provider_failure(exc, symbol)
        levels.append(
            IndexLevel(
                symbol=symbol, name=name, level=quote.price, change_percent=quote.change_percent
            )
        )
        timestamps.append(quote.timestamp)
    return ok(MarketOverview(indices=levels), source=provider.name, as_of=min(timestamps))

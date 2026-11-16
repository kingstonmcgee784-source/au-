"""Research reports and market overview."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.research_writer import ResearchWriter
from app.core.errors import NotFoundError
from app.models import ResearchReport
from app.providers.base import MarketDataProvider
from app.schemas.common import DataResponse, UnavailableReason, unavailable
from app.schemas.research import MarketOverview, ResearchReportOut, ResearchReportSummary


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


def market_overview(provider: MarketDataProvider | None) -> DataResponse[MarketOverview]:
    _ = provider
    return unavailable(
        UnavailableReason.PROVIDER_NOT_CONFIGURED,
        "Index levels need a market data provider, and none is configured.",
    )

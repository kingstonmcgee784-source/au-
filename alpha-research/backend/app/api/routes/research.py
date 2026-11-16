"""Research reports, scoring methodology and market overview."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession, MarketData, Writer
from app.schemas.common import DataResponse
from app.schemas.research import (
    GenerateReportRequest,
    MarketOverview,
    ResearchReportOut,
    ResearchReportSummary,
)
from app.schemas.stocks import RankingEntry, ScoringMethodology
from app.services import research, scores

router = APIRouter()


@router.get("/scoring/methodology", response_model=ScoringMethodology, tags=["scoring"])
def scoring_methodology() -> ScoringMethodology:
    return scores.methodology()


@router.get("/rankings", response_model=DataResponse[list[RankingEntry]], tags=["scoring"])
def rankings(
    db: DbSession, limit: Annotated[int, Query(ge=1, le=100)] = 10
) -> DataResponse[list[RankingEntry]]:
    return scores.rankings(db, limit)


@router.get("/market/overview", response_model=DataResponse[MarketOverview], tags=["market"])
def market_overview(provider: MarketData) -> DataResponse[MarketOverview]:
    return research.market_overview(provider)


@router.get("/reports", response_model=list[ResearchReportSummary], tags=["reports"])
def list_reports(
    db: DbSession, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[ResearchReportSummary]:
    return research.list_reports(db, limit)


@router.get("/reports/{report_id}", response_model=ResearchReportOut, tags=["reports"])
def get_report(db: DbSession, report_id: int) -> ResearchReportOut:
    return research.get_report(db, report_id)


@router.post(
    "/reports/generate", response_model=DataResponse[ResearchReportOut], tags=["reports"]
)
def generate_report(
    writer: Writer, payload: GenerateReportRequest
) -> DataResponse[ResearchReportOut]:
    return research.generate_report(writer, payload.ticker)

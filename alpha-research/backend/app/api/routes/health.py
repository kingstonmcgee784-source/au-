"""Health check: is the API up, is the database reachable and migrated."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import AppSettings, DbSession
from app.db.migrations import current_revision, head_revision

router = APIRouter(tags=["health"])


class DatabaseHealth(BaseModel):
    connected: bool
    revision: str | None
    head_revision: str | None
    up_to_date: bool
    error: str | None = None


class IntegrationStatus(BaseModel):
    market_data: Literal["configured", "not_configured"]
    ai_research: Literal["configured", "not_configured"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    environment: str
    database: DatabaseHealth
    integrations: IntegrationStatus


@router.get("/health", response_model=HealthResponse)
def health(db: DbSession, settings: AppSettings) -> HealthResponse:
    head = head_revision(settings.database_url)
    try:
        db.execute(text("SELECT 1"))
        revision = current_revision(db.connection())
        database = DatabaseHealth(
            connected=True, revision=revision, head_revision=head, up_to_date=revision == head
        )
    except SQLAlchemyError as exc:
        database = DatabaseHealth(
            connected=False,
            revision=None,
            head_revision=head,
            up_to_date=False,
            error=exc.__class__.__name__,
        )

    def integration(name: str) -> Literal["configured", "not_configured"]:
        return "not_configured" if name == "none" else "configured"

    return HealthResponse(
        status="ok" if database.connected and database.up_to_date else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database=database,
        integrations=IntegrationStatus(
            market_data=integration(settings.market_data_provider),
            ai_research=integration(settings.ai_provider),
        ),
    )

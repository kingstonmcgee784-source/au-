"""Versioned API router."""

from fastapi import APIRouter

from app.api.routes import health, performance, research, stocks, watchlists

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(stocks.router)
api_router.include_router(research.router)
api_router.include_router(watchlists.router)
api_router.include_router(performance.router)

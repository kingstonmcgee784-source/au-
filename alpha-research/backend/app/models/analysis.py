"""Stored results of calculations: technical indicators and stock scores."""

from datetime import date, datetime

from sqlalchemy import JSON, Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"
    __table_args__ = (
        UniqueConstraint("stock_id", "indicator", "date", name="uq_technical_indicators_point"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    indicator: Mapped[str] = mapped_column(String(32))  # e.g. "sma_50", "rsi_14"
    date: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float | None] = mapped_column(Float)
    calculated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class StockScore(Base):
    """A 0-100 composite score with its per-category breakdown."""

    __tablename__ = "stock_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    as_of: Mapped[date] = mapped_column(Date, index=True)
    total_score: Mapped[float] = mapped_column(Float)
    # Category name -> points awarded (out of that category's weight).
    category_scores: Mapped[dict[str, float]] = mapped_column(JSON)
    methodology_version: Mapped[str] = mapped_column(String(16))
    risk_class: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str | None]
    calculated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

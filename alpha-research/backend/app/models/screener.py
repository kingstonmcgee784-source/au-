"""Batch scans: score a list of tickers in the background."""

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UTCDateTime


class ScreenRun(TimestampMixin, Base):
    __tablename__ = "screen_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    # queued | running | waiting | done | cancelled
    status: Mapped[str] = mapped_column(String(16), default="queued")
    # Set while waiting out a provider's request limit.
    resume_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    message: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    items: Mapped[list["ScreenRunItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ScreenRunItem.position"
    )


class ScreenRunItem(Base):
    __tablename__ = "screen_run_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("screen_runs.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    ticker: Mapped[str] = mapped_column(String(16))
    # pending | scored | not_scored | failed
    status: Mapped[str] = mapped_column(String(16), default="pending")
    score: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    run: Mapped[ScreenRun] = relationship(back_populates="items")

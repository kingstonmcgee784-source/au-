"""Research output: reports, news, recommendations and backtests."""

from datetime import date, datetime

from sqlalchemy import JSON, Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SourcedMixin, TimestampMixin, UTCDateTime, utcnow


class ResearchReport(TimestampMixin, Base):
    __tablename__ = "research_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("stocks.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    body_markdown: Mapped[str] = mapped_column(Text)
    # manual | ai_generated
    origin: Mapped[str] = mapped_column(String(16), default="manual")
    # draft | published | archived
    status: Mapped[str] = mapped_column(String(16), default="draft")
    report_date: Mapped[date] = mapped_column(Date)


class NewsArticle(SourcedMixin, Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), index=True
    )
    headline: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024), unique=True)
    publisher: Mapped[str | None] = mapped_column(String(128))
    published_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    # earnings | contract | regulatory | analyst | other
    category: Mapped[str | None] = mapped_column(String(32))


class Recommendation(TimestampMixin, Base):
    """A recorded call. Never edited after the fact: outcomes go in new fields."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_reports.id", ondelete="SET NULL")
    )
    recommended_on: Mapped[date] = mapped_column(Date, index=True)
    reference_price: Mapped[float] = mapped_column(Float)
    reference_price_source: Mapped[str] = mapped_column(String(64))
    horizon_days: Mapped[int]
    score_at_recommendation: Mapped[float | None] = mapped_column(Float)
    risk_class: Mapped[str | None] = mapped_column(String(16))
    thesis: Mapped[str | None] = mapped_column(Text)
    # open | closed | invalidated
    status: Mapped[str] = mapped_column(String(16), default="open")


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(128))
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    benchmark: Mapped[str | None] = mapped_column(String(16))
    # Computed statistics, e.g. {"total_return": ..., "max_drawdown": ...}.
    metrics: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

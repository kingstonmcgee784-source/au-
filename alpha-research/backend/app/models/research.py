"""Research output: reports, news, recommendations and backtests."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    # Kind of the headline item, e.g. earnings, agreement, red_flag.
    category: Mapped[str | None] = mapped_column(String(32))
    # For SEC filings: the form (8-K, 8-K/A) and its item numbers.
    form: Mapped[str | None] = mapped_column(String(16))
    items: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")


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
    # The holding plan at the time of the call, relative to reference_price
    # (e.g. -0.08 and 0.16). None for calls recorded before plans existed.
    stop_pct: Mapped[float | None] = mapped_column(Float)
    target_pct: Mapped[float | None] = mapped_column(Float)
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


class InsiderFiling(SourcedMixin, Base):
    """A processed Form 4, stored even when it has no share transactions so it
    is not downloaded again."""

    __tablename__ = "insider_filings"
    # One Form 4 can appear in two companies' filing indexes (the issuer's and
    # a corporate owner's), so an accession is unique per stock only.
    __table_args__ = (
        UniqueConstraint("stock_id", "accession", name="uq_insider_filings_stock_accession"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    accession: Mapped[str] = mapped_column(String(32))
    filed_on: Mapped[date] = mapped_column(Date, index=True)
    owner_name: Mapped[str] = mapped_column(String(255))
    owner_role: Mapped[str] = mapped_column(String(255))

    transactions: Mapped[list["InsiderTransaction"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )


class InsiderTransaction(Base):
    """One non-derivative share transaction reported on a Form 4."""

    __tablename__ = "insider_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(
        ForeignKey("insider_filings.id", ondelete="CASCADE"), index=True
    )
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    code: Mapped[str] = mapped_column(String(4))
    acquired: Mapped[bool] = mapped_column(Boolean)
    shares: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)
    shares_after: Mapped[float | None] = mapped_column(Float)
    direct: Mapped[bool | None] = mapped_column(Boolean)
    under_10b5_1: Mapped[bool | None] = mapped_column(Boolean)
    security: Mapped[str] = mapped_column(String(255))

    filing: Mapped[InsiderFiling] = relationship(back_populates="transactions")

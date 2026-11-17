"""Reported financial statements and derived financial metrics."""

from datetime import date

from sqlalchemy import JSON, Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SourcedMixin


class FinancialStatement(SourcedMixin, Base):
    """One statement (income, balance sheet or cash flow) for one fiscal period.

    Line items are stored as a JSON object keyed by line-item name, because
    the set of reported items varies between companies and filings.
    """

    __tablename__ = "financial_statements"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "statement_type",
            "period_type",
            "period_end",
            name="uq_financial_statements_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    statement_type: Mapped[str] = mapped_column(String(16))  # income | balance | cashflow
    period_type: Mapped[str] = mapped_column(String(16))  # annual | quarterly | ttm
    fiscal_year: Mapped[int]
    fiscal_quarter: Mapped[int | None]
    period_end: Mapped[date] = mapped_column(Date)
    filing_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    line_items: Mapped[dict[str, float | None]] = mapped_column(JSON, default=dict)
    # Line items calculated from other reported figures (e.g. Q4 = year minus
    # nine months) rather than reported directly for this period.
    derived_items: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    # Version of the SEC parser that produced this row (0 = before versions).
    parser_version: Mapped[int] = mapped_column(default=0, server_default="0")


class FinancialMetric(SourcedMixin, Base):
    """A single metric (e.g. forward P/E) for a stock as of a date."""

    __tablename__ = "financial_metrics"
    __table_args__ = (
        UniqueConstraint("stock_id", "metric", "as_of", name="uq_financial_metrics_point"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[float | None] = mapped_column(Float)
    as_of: Mapped[date] = mapped_column(Date)
    period: Mapped[str | None] = mapped_column(String(32))  # e.g. "TTM", "FY2026Q3"
    # reported | estimate | calculated
    data_kind: Mapped[str] = mapped_column(String(16), default="reported")

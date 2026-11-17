"""Securities and their price history."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SourcedMixin, TimestampMixin, UTCDateTime


class Stock(TimestampMixin, Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    exchange: Mapped[str | None] = mapped_column(String(32))
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sic_code: Mapped[str | None] = mapped_column(String(8))
    # When Form 4 filings were last loaded; None means never, which is
    # different from "loaded, and there were no insider trades".
    insiders_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # When 8-K events were last loaded (None = never).
    events_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    prices: Mapped[list["HistoricalPrice"]] = relationship(
        back_populates="stock", cascade="all, delete-orphan"
    )


class HistoricalPrice(SourcedMixin, Base):
    """One daily OHLCV bar."""

    __tablename__ = "historical_prices"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_historical_prices_stock_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    adjusted_close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)

    stock: Mapped[Stock] = relationship(back_populates="prices")

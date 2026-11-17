"""The oil-price adjustment for oil and gas companies."""

from datetime import date, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.analysis.commodity import factor, oil_gap
from app.models import HistoricalPrice, Stock
from app.providers.base import PriceBar
from app.providers.sec_edgar import CompanyInfo
from app.services.scoring_pipeline import score_stock
from tests.fakes import FakeProvider, bars
from tests.test_scoring_pipeline import FakeSec

START = date.today() - timedelta(days=299)


def test_factor_steps() -> None:
    assert factor(None) == 1.0
    assert factor(-0.04) == 1.0  # small dips are noise
    assert factor(-0.10) == pytest.approx(0.8)
    assert factor(-0.40) == 0.5  # floor
    assert factor(0.20) == 1.0  # no bonus for rising oil
    assert oil_gap([1.0] * 10) is None  # under a quarter of history
    assert oil_gap([100.0] * 62 + [80.0]) == pytest.approx(80 / (100 * 62 / 63 + 80 / 63) - 1)


class OilSec(FakeSec):
    def company_info(self, cik: int) -> CompanyInfo:
        return CompanyInfo(sic="1311", sic_description="CRUDE PETROLEUM & NATURAL GAS", filings=[])


def oil_prices(fall: bool) -> list[PriceBar]:
    out = []
    for i in range(300):
        price = 70.0 - (0.2 * (i - 230) if fall and i > 230 else 0.0)
        out.append(
            PriceBar(
                date=START + timedelta(days=i),
                open=price,
                high=price,
                low=price,
                close=price,
                adjusted_close=price,
                volume=1,
            )
        )
    return out


def score_with(db: Session, fall: bool, ticker: str) -> dict:
    market = FakeProvider(
        {
            ticker: bars(START, 300, 50.0),
            "SPY": bars(START, 300, 500.0),
            "XLE": bars(START, 300, 90.0),
            "USO": oil_prices(fall),
        }
    )
    result = score_stock(
        db, ticker, market=market, fundamentals=OilSec(), refresh=True, history_years=2
    )
    assert result.status == "ok", result.message
    return result.data.model_dump()


def test_falling_oil_lowers_valuation_and_growth(db: Session) -> None:
    steady = score_with(db, fall=False, ticker="OILA")
    # Drop the stored oil prices so the falling series is loaded fresh.
    uso = db.scalar(select(Stock.id).where(Stock.ticker == "USO"))
    db.execute(delete(HistoricalPrice).where(HistoricalPrice.stock_id == uso))
    db.commit()
    falling = score_with(db, fall=True, ticker="OILB")
    assert falling["total_score"] < steady["total_score"]

    def cat(score: dict, key: str) -> dict:
        return next(c for c in score["categories"] if c["key"] == key)

    for key in ("valuation", "growth"):
        assert cat(falling, key)["points"] < cat(steady, key)["points"]
        assert "because oil (USO)" in cat(falling, key)["summary"]
    # Other categories are untouched.
    assert cat(falling, "fundamentals")["points"] == cat(steady, "fundamentals")["points"]
    assert "Oil adjustment" in falling["notes"]
    assert "Oil adjustment" not in steady["notes"]

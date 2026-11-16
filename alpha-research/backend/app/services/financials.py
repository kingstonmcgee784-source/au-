"""Stored financial statements."""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FinancialStatement
from app.schemas.common import DataResponse, UnavailableReason, ok, unavailable
from app.schemas.stocks import FinancialStatementOut
from app.services.stocks import LOCAL_SOURCE, find_stock, no_stored_stock

StatementType = Literal["income", "balance", "cashflow"]
PeriodType = Literal["annual", "quarterly", "ttm"]


def get_statements(
    db: Session,
    ticker: str,
    statement_type: StatementType | None,
    period_type: PeriodType | None,
    limit: int,
) -> DataResponse[list[FinancialStatementOut]]:
    stock = find_stock(db, ticker)
    if stock is None:
        return unavailable(UnavailableReason.NO_STORED_DATA, no_stored_stock(ticker))

    query = select(FinancialStatement).where(FinancialStatement.stock_id == stock.id)
    if statement_type:
        query = query.where(FinancialStatement.statement_type == statement_type)
    if period_type:
        query = query.where(FinancialStatement.period_type == period_type)
    rows = db.scalars(query.order_by(FinancialStatement.period_end.desc()).limit(limit)).all()

    if not rows:
        return unavailable(
            UnavailableReason.NO_STORED_DATA,
            f"No financial statements are stored for {ticker}. "
            "Statement ingestion has not been built yet.",
        )
    newest = max(row.retrieved_at for row in rows)
    return ok(
        [FinancialStatementOut.model_validate(row) for row in rows],
        source=LOCAL_SOURCE,
        as_of=newest,
    )

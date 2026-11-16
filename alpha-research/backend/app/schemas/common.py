"""Shared response envelope.

Every data endpoint answers with a `DataResponse`. When data cannot be
provided (no provider configured, nothing stored yet, too little history),
the endpoint returns `status="unavailable"` with a machine-readable `reason`
and `data=null`. It never substitutes placeholder numbers.
"""

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


class DataStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


class UnavailableReason(StrEnum):
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    AI_NOT_CONFIGURED = "ai_not_configured"
    NO_STORED_DATA = "no_stored_data"
    INSUFFICIENT_HISTORY = "insufficient_history"
    UNKNOWN_TICKER = "unknown_ticker"
    PROVIDER_ERROR = "provider_error"


class DataResponse[T](BaseModel):
    status: DataStatus
    data: T | None = None
    reason: UnavailableReason | None = None
    message: str | None = None
    # Where the data came from (e.g. "local_database") and when it was valid.
    source: str | None = None
    as_of: datetime | None = None


def ok[T](data: T, *, source: str, as_of: datetime | None = None) -> DataResponse[T]:
    return DataResponse[T](status=DataStatus.OK, data=data, source=source, as_of=as_of)


def unavailable[T](reason: UnavailableReason, message: str) -> DataResponse[T]:
    return DataResponse[T](status=DataStatus.UNAVAILABLE, reason=reason, message=message)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


_TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{0,9}([.\-][A-Z0-9]{1,4})?$")


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper()
    if not _TICKER_PATTERN.fullmatch(ticker):
        raise ValueError(f"'{value}' is not a valid ticker symbol")
    return ticker


Ticker = Annotated[str, AfterValidator(normalize_ticker)]

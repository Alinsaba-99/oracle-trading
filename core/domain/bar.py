"""Tick and Bar data models."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, model_validator

from core.domain.enums import TimeFrame


class Tick(BaseModel):
    instrument_id: str
    timestamp: datetime
    price: Decimal
    volume: Decimal
    side: str | None = None
    exchange: str = ""
    trade_id: str | None = None

    @model_validator(mode="after")
    def validate_non_negative(self) -> "Tick":
        if not self.price > 0:
            raise ValueError("Price must be positive")
        if not self.volume >= 0:
            raise ValueError("Volume must be non-negative")
        return self


class Bar(BaseModel):
    instrument_id: str
    timestamp: datetime
    timeframe: TimeFrame
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trades: int | None = None
    vwap: Decimal | None = None
    open_interest: int | None = None
    complete: bool = False

    @model_validator(mode="after")
    def validate_ohlc(self) -> "Bar":
        if not self.open > 0:
            raise ValueError("Open must be positive")
        if not self.high >= self.low:
            raise ValueError("High must be >= Low")
        if not self.high >= self.open:
            raise ValueError("High must be >= Open")
        if not self.high >= self.close:
            raise ValueError("High must be >= Close")
        if not self.low <= self.open:
            raise ValueError("Low must be <= Open")
        if not self.low <= self.close:
            raise ValueError("Low must be <= Close")
        if not self.volume >= 0:
            raise ValueError("Volume must be non-negative")
        return self

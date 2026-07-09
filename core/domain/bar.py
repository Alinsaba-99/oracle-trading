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
        assert self.price > 0, "Price must be positive"
        assert self.volume >= 0, "Volume must be non-negative"
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
        assert self.open > 0, "Open must be positive"
        assert self.high >= self.low, "High must be >= Low"
        assert self.high >= self.open, "High must be >= Open"
        assert self.high >= self.close, "High must be >= Close"
        assert self.low <= self.open, "Low must be <= Open"
        assert self.low <= self.close, "Low must be <= Close"
        assert self.volume >= 0, "Volume must be non-negative"
        return self

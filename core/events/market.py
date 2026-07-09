"""Market data event models."""

from decimal import Decimal
from typing import Any

from pydantic import Field

from core.domain.events import Event


class MarketTickEvent(Event):
    instrument_id: str
    asset_class: str = ""
    exchange: str = ""
    bid: Decimal
    ask: Decimal
    last: Decimal | None = None
    volume: Decimal = Decimal("0")
    bid_size: Decimal | None = None
    ask_size: Decimal | None = None


class MarketBarEvent(Event):
    instrument_id: str
    asset_class: str = ""
    exchange: str = ""
    timeframe: str = "1m"
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trades: int | None = None
    vwap: Decimal | None = None


class MarketOrderBookEvent(Event):
    instrument_id: str
    asset_class: str = ""
    exchange: str = ""
    bids: list[dict[str, Any]] = Field(default_factory=list)
    asks: list[dict[str, Any]] = Field(default_factory=list)
    bid_depth: int = 0
    ask_depth: int = 0


class MarketTradeEvent(Event):
    instrument_id: str
    asset_class: str = ""
    exchange: str = ""
    price: Decimal
    volume: Decimal
    side: str | None = None
    trade_id: str | None = None

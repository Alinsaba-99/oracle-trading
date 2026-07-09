"""Trade event models."""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from core.domain.events import Event


class TradeOpenedEvent(Event):
    trade_id: str
    instrument_id: str
    direction: str
    entry_price: Decimal
    quantity: Decimal
    entry_time: datetime
    strategy_id: str = ""
    signal_id: str = ""
    initial_stop_loss: Decimal | None = None
    initial_take_profit: Decimal | None = None


class TradeClosedEvent(Event):
    trade_id: str
    instrument_id: str
    direction: str
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    entry_time: datetime
    exit_time: datetime
    pnl: Decimal
    pnl_pct: float = 0.0
    exit_reason: str = ""
    strategy_id: str = ""
    agents_involved: list[str] = Field(default_factory=list)
    regime_at_entry: str | None = None
    regime_at_exit: str | None = None

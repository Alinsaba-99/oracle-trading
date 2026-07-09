"""Trade model with lifecycle (opened → closed → audited)."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field

from core.domain.enums import TradeDirection, TradeStatus


class Trade(BaseModel):
    trade_id: str = Field(default_factory=lambda: str(uuid4()))
    instrument_id: str
    portfolio_id: str = ""
    strategy_id: str = ""
    signal_id: str = ""
    direction: TradeDirection
    status: TradeStatus = TradeStatus.open

    entry_price: Decimal
    exit_price: Decimal | None = None
    quantity: Decimal
    pnl: Decimal | None = None
    pnl_pct: float | None = None

    entry_time: datetime
    exit_time: datetime | None = None
    exit_reason: str | None = None

    initial_stop_loss: Decimal | None = None
    initial_take_profit: Decimal | None = None
    regime_at_entry: str | None = None
    regime_at_exit: str | None = None
    agents_involved: list[str] = Field(default_factory=list)
    orders: list[str] = Field(default_factory=list)

    @property
    def duration_hours(self) -> float | None:
        if self.exit_time:
            return (self.exit_time - self.entry_time).total_seconds() / 3600
        return None

    @property
    def is_profitable(self) -> bool | None:
        if self.pnl is not None:
            return self.pnl > 0
        return None

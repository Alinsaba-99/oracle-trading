"""Position model."""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class Position(BaseModel):
    instrument_id: str
    portfolio_id: str = ""
    quantity: Decimal = Decimal("0")
    avg_entry_price: Decimal = Decimal("0")
    current_price: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    weight: float = 0.0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

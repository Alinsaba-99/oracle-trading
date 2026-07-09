"""Portfolio event models."""

from decimal import Decimal
from typing import Any

from pydantic import Field

from core.domain.events import Event


class PortfolioUpdatedEvent(Event):
    portfolio_id: str
    total_value: Decimal
    cash: Decimal
    exposure: float = 0.0
    day_pnl: Decimal = Decimal("0")
    total_pnl: Decimal = Decimal("0")
    positions: list[dict[str, Any]] = Field(default_factory=list)

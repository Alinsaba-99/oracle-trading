"""Portfolio model."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field

from core.domain.enums import PortfolioType
from core.domain.position import Position
from core.domain.risk_metrics import RiskMetrics


class Portfolio(BaseModel):
    portfolio_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Default"
    type: PortfolioType = PortfolioType.paper
    initial_capital: Decimal = Decimal("100000")
    total_value: Decimal = Decimal("0")
    cash: Decimal = Decimal("0")
    exposure: float = 0.0
    leverage: float = 1.0
    day_pnl: Decimal = Decimal("0")
    total_pnl: Decimal = Decimal("0")
    total_return: float = 0.0
    positions: dict[str, Position] = Field(default_factory=dict)
    risk_metrics: RiskMetrics | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

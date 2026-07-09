"""Risk metrics model."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class RiskMetrics(BaseModel):
    portfolio_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    var_95: float | None = None
    var_99: float | None = None
    cvar_95: float | None = None
    max_drawdown: float | None = None
    current_drawdown: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    calmar_ratio: float | None = None
    volatility: float | None = None
    beta: float | None = None
    correlation_to_benchmark: float | None = None
    concentration: float | None = None

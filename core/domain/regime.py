"""Market regime model."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from core.domain.enums import (
    MarketPhase,
    RegimeCorrelation,
    RegimeLiquidity,
    RegimeTrend,
    RegimeVolatility,
)


class Regime(BaseModel):
    instrument_id: str = "global"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    volatility: RegimeVolatility = RegimeVolatility.medium
    trend: RegimeTrend = RegimeTrend.sideways
    liquidity: RegimeLiquidity = RegimeLiquidity.normal
    correlation: RegimeCorrelation = RegimeCorrelation.mixed
    phase: MarketPhase = MarketPhase.accumulation
    scores: dict[str, float] = Field(default_factory=dict)
    methods: list[str] = Field(default_factory=list)

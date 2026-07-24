"""Application-layer contracts — authority boundary types.

These types are shared between the intelligence plane (agents) and the
safety control plane (execution).  No package outside ``application``
owns these contracts; they are inward-facing types that both layers
depend on.

Re-introduced during audit-remediation-beta (B5).  The previous
version was lost in an uncommitted refactor; this is a faithful copy
of the most recent known good version, with a class-level freeze on
mutability and pydantic validators.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class TradingMode(StrEnum):
    """Operational authority granted to a portfolio plan."""

    REPLAY = "replay"
    PAPER = "paper"
    SHADOW = "shadow"
    LIVE = "live"


class OrderStyle(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    PASSIVE_LIMIT = "passive_limit"
    TWAP = "twap"
    VWAP = "vwap"


class Urgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    IMMEDIATE = "immediate"


class IntentAction(StrEnum):
    OPEN = "open"
    INCREASE = "increase"
    REDUCE = "reduce"
    CLOSE = "close"
    REVERSE = "reverse"


class ExecutionPreference(BaseModel, frozen=True):
    """Execution preferences selected by the LLM execution agent."""

    order_style: OrderStyle = OrderStyle.LIMIT
    urgency: Urgency = Urgency.MEDIUM
    limit_price: float | None = Field(default=None, gt=0.0)
    stop_price: float | None = Field(default=None, gt=0.0)
    take_profit_price: float | None = Field(default=None, gt=0.0)
    max_slippage_bps: float = Field(default=10.0, ge=0.0)


class PositionTarget(BaseModel, frozen=True):
    """Desired reconciled position for one tradable instrument."""

    instrument_id: str
    target_contracts: int
    confidence: float = Field(ge=0.0, le=1.0)
    thesis: str
    time_horizon: str
    invalidation_conditions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    execution: ExecutionPreference = Field(default_factory=ExecutionPreference)


class PortfolioPlan(BaseModel, frozen=True):
    """Complete portfolio decision emitted by the LLM fund manager."""

    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    mode: TradingMode
    objective: str
    portfolio_thesis: str
    targets: list[PositionTarget]
    cash_buffer_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    gross_risk_budget_pct: float = Field(default=0.01, gt=0.0, le=1.0)
    source_observation_ids: list[str] = Field(default_factory=list)
    agents_contributing: list[str] = Field(default_factory=list)
    model: str = ""
    prompt_version: str = ""

    @model_validator(mode="after")
    def validate_plan(self) -> PortfolioPlan:
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        instruments = [target.instrument_id for target in self.targets]
        if len(instruments) != len(set(instruments)):
            raise ValueError("portfolio targets must be unique by instrument")
        return self


class TradeIntent(BaseModel, frozen=True):
    """Broker-neutral intent compiled from a portfolio target delta."""

    intent_id: str = Field(default_factory=lambda: str(uuid4()))
    decision_id: str
    instrument_id: str
    action: IntentAction
    side: str
    quantity: int = Field(gt=0)
    execution: ExecutionPreference
    rationale: str


__all__ = [
    "ExecutionPreference",
    "IntentAction",
    "OrderStyle",
    "PortfolioPlan",
    "PositionTarget",
    "TradeIntent",
    "TradingMode",
    "Urgency",
]

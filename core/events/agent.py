"""Agent event models."""

from typing import Any

from pydantic import Field

from core.domain.events import Event


class AgentAnalysisCompletedEvent(Event):
    agent: str
    instrument_id: str
    signal: str = "neutral"
    confidence: float = 0.0
    summary: str = ""
    key_metrics: dict[str, Any] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)


class AgentDebateCompletedEvent(Event):
    instrument_id: str
    round: int = 1
    bull_case: str = ""
    bear_case: str = ""
    devils_advocate: str = ""
    consensus: str = ""
    no_trade_recommended: bool = False


class AgentDecisionProposedEvent(Event):
    instrument_id: str
    portfolio_manager: str = ""
    decision: str = "hold"
    quantity: int = 0
    order_type: str = "market"
    price_limit: float | None = None
    confidence: float = 0.0
    timeframe: str = ""
    rationale: str = ""
    agents_consulted: list[str] = Field(default_factory=list)
    regime_at_decision: str | None = None

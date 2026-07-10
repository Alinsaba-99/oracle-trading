"""Core protocol interfaces for Oracle's Multi-Agent System."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    import polars as pl  # noqa: F401


class AgentVote(BaseModel):
    """Vote from a single agent on a trading decision."""

    direction: Literal["buy", "sell", "hold"]
    confidence: float  # 0.0-1.0
    reasoning: str
    risk_score: float | None = None


class AnalystInput(BaseModel):
    """Input data provided to an analyst agent."""

    instrument: str
    market_state: Any  # MarketState (forward ref)
    agent_specific_data: dict[str, Any]


class AnalystSignal(BaseModel):
    """Signal output from an analyst agent."""

    source: Literal["macro", "technical", "sentiment"]
    vote: AgentVote
    metadata: dict[str, Any]
    blind_spot: str
    prompt_hash: str = ""
    model: str = ""
    tokens_used: int = 0


class DebateResult(BaseModel, frozen=True):
    """Result of a multi-agent debate round."""

    round_1: dict[str, Any]
    round_2: dict[str, Any] | None = None
    consensus: AgentVote | None = None
    disagreements: list[str] = []
    debate_quality: float = 0.0


class MarketState(BaseModel, frozen=True):
    """Current market state snapshot."""

    regime: str
    phase: str
    volatility: str
    liquidity: str
    risk_appetite: str
    narrative: str = ""


class RiskAssessment(BaseModel, frozen=True):
    """Risk assessment result from the risk manager."""

    approved: bool
    max_position_size: float
    kelly_fraction: float
    var_95: float
    reasons: list[str]


class PortfolioDecision(BaseModel, frozen=True):
    """Final portfolio decision after debate and risk check."""

    direction: Literal["buy", "sell", "hold", "no_trade"]
    instrument: str
    position_size: float
    confidence: float
    reasoning: str
    agents_contributing: list[str]
    regime_at_decision: str
    risk_approved: bool
    escalated: bool = False

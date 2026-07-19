"""Typed intelligence observations received from external agent runtimes."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class OpportunityDirection(StrEnum):
    """Directional implication of an intelligence observation."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    HEDGE = "hedge"


class EvidenceReference(BaseModel, frozen=True):
    """Auditable reference supporting an external observation."""

    source: str
    source_url: str = ""
    observed_at: datetime
    available_at: datetime
    content_hash: str
    credibility: float = Field(ge=0.0, le=1.0)
    excerpt: str = ""

    @model_validator(mode="after")
    def validate_availability(self) -> EvidenceReference:
        if self.available_at < self.observed_at:
            raise ValueError("available_at cannot precede observed_at")
        return self


class OpportunityObservation(BaseModel, frozen=True):
    """Read-only intelligence proposal produced by ElizaOS or another scout."""

    observation_id: str
    agent_id: str
    event_time: datetime
    available_at: datetime
    instruments: list[str]
    observation_type: str
    direction: OpportunityDirection
    confidence: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    time_horizon: str
    summary: str
    evidence: list[EvidenceReference] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    prompt_version: str = ""
    model: str = ""

    @model_validator(mode="after")
    def validate_temporal_integrity(self) -> OpportunityObservation:
        if self.available_at < self.event_time:
            raise ValueError("available_at cannot precede event_time")
        if not self.instruments:
            raise ValueError("at least one instrument is required")
        if self.direction is not OpportunityDirection.NEUTRAL and not self.evidence:
            raise ValueError("directional observations require evidence")
        return self

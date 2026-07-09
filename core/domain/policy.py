"""Policy model for the Policy Engine."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from core.domain.enums import PolicyDecision, PolicyType


class PolicyCondition(BaseModel):
    metric: str
    operator: str
    value: float
    unit: str = "absolute"


class Policy(BaseModel):
    policy_id: str
    name: str = ""
    type: PolicyType = PolicyType.hard_limit
    enabled: bool = True
    priority: int = 0
    conditions: list[PolicyCondition] = Field(default_factory=list)
    action: str = "block"
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class PolicyResult(BaseModel):
    decision: PolicyDecision
    policy_id: str
    policy_name: str = ""
    policy_type: str = ""
    reason: str | None = None
    details: dict[str, Any] | None = None
    warning: str | None = None
    evaluated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    evaluation_time_ms: float = 0.0

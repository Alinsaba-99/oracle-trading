"""Policy event models."""

from typing import Any

from pydantic import Field

from core.domain.events import Event


class PolicyApprovedEvent(Event):
    policy_id: str
    policy_type: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    evaluation_time_ms: float = 0.0


class PolicyRejectedEvent(Event):
    policy_id: str
    policy_type: str = ""
    reason: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class PolicyWarningEvent(Event):
    policy_id: str
    policy_type: str = ""
    warning: str = ""
    context: dict[str, Any] = Field(default_factory=dict)

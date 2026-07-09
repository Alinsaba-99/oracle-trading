"""Experiment event models."""

from typing import Any

from pydantic import Field

from core.domain.events import Event


class ExperimentCompletedEvent(Event):
    experiment_id: str
    status: str = "completed"
    duration_seconds: float = 0.0
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_path: str = ""

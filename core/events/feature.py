"""Feature event models."""

from typing import Any

from pydantic import Field

from core.domain.events import Event


class FeatureUpdatedEvent(Event):
    instrument_id: str
    feature_set: str = ""
    features: dict[str, Any] = Field(default_factory=dict)

"""Regime event models."""

from typing import Any

from pydantic import Field

from core.domain.events import Event


class RegimeUpdatedEvent(Event):
    instrument_id: str = "global"
    regime: dict[str, Any] = Field(default_factory=dict)
    scores: dict[str, Any] = Field(default_factory=dict)

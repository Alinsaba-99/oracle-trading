"""Base event models for NATS communication."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Event(BaseModel):
    """Base event payload. All domain events inherit from this."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = 1


class EventEnvelope(BaseModel):
    """NATS event envelope - wraps every event published on the bus."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    version: int = 1
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    data: dict[str, Any]

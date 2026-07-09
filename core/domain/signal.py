"""Signal model - output of strategy/agent analysis."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class Signal(BaseModel):
    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    instrument_id: str
    strategy_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    direction: str = Field(..., pattern="^(long|short|neutral)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    timeframe: str = "1d"
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return round(v, 4)

"""Strategy model - evolved or manually defined."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from core.domain.enums import StrategyStatus


class Strategy(BaseModel):
    strategy_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = ""
    version: str = "0.1.0"
    status: StrategyStatus = StrategyStatus.developing
    genome: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    experiment_id: str | None = None
    tags: list[str] = Field(default_factory=list)

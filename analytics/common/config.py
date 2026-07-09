"""Settings model for analytics modules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyticsSettings(BaseModel):
    """Configuration for analytics subsystem."""

    enabled: bool = True
    feature_store_path: str = "data/features"
    cache_size: int = Field(default=1000, ge=1)
    cache_ttl_seconds: int = Field(default=300, ge=1)
    backpressure_max_queue: int = Field(default=1000, ge=1)
    backpressure_drop_policy: str = Field(default="oldest", pattern="^(oldest|newest|drop)$")

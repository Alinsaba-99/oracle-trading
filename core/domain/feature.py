"""Feature and Feature Store models."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class Feature(BaseModel):
    feature_id: str = Field(default_factory=lambda: str(uuid4()))
    instrument_id: str
    timestamp: datetime
    feature_set: str
    name: str
    value: float
    version: str = "0.1.0"
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    computation_time_ms: float = 0.0


class FeatureSetVersion(BaseModel):
    feature_set: str
    version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    git_commit: str = ""
    features: list[str] = Field(default_factory=list)
    description: str = ""

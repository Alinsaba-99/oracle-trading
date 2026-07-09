"""Base schema models for analytics domain."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class UTCModel(BaseModel):
    """Base model enforcing timezone-aware UTC datetimes."""

    @field_validator("*", mode="before")
    @classmethod
    def ensure_utc(cls, v: object) -> object:
        """Validate and preserve UTC-aware datetimes."""
        if isinstance(v, datetime) and v.tzinfo is None:
            msg = f"Naive datetime not allowed: {v}. Use timezone-aware UTC."
            raise ValueError(msg)
        return v

"""Feature set version schema model for M3 Feature Store."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from pydantic import BaseModel, field_validator


class FeatureSetVersion(BaseModel):
    """Schema definition for a versioned feature set.

    Tracks the canonical feature names, instrument coverage, and
    metadata for one version of a feature set stored in Parquet.
    """

    version_id: str
    feature_names: list[str]
    instrument_ids: list[str]
    created_at: datetime
    schema_hash: str
    feature_count: int
    row_count: int

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: object) -> object:
        """Reject naive datetimes — only timezone-aware UTC is allowed."""
        if isinstance(v, datetime) and v.tzinfo is None:
            msg = f"Naive datetime not allowed: {v}. Use timezone-aware UTC."
            raise ValueError(msg)
        return v

    @classmethod
    def create(
        cls, version_id: str, feature_names: list[str], instrument_ids: list[str]
    ) -> FeatureSetVersion:
        """Factory: deduplicates + sorts names/ids and computes derived fields."""
        unique_features = sorted(set(feature_names))
        unique_instruments = sorted(set(instrument_ids))

        created_at = datetime.now(UTC)
        raw = f"{version_id}:{unique_features}:{unique_instruments}"
        schema_hash = sha256(raw.encode()).hexdigest()[:16]

        return cls(
            version_id=version_id,
            feature_names=unique_features,
            instrument_ids=unique_instruments,
            created_at=created_at,
            schema_hash=schema_hash,
            feature_count=len(unique_features),
            row_count=len(unique_features) * len(unique_instruments),
        )

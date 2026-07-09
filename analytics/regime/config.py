"""Regime detection configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegimeSettings(BaseModel):
    """Configuration for regime detection ensemble."""

    hmm_n_states: int = 4
    ensemble_min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    ensemble_min_bars: int = Field(default=5, ge=1)
    vol_cluster_n: int = Field(default=3, ge=2, le=5)
    correlation_window: int = Field(default=20, ge=5)

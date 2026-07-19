"""Tests for deterministic multi-asset hedge allocation."""

import numpy as np
import pytest

from agents.committee import HedgeAllocationOptimizer


def test_allocator_prefers_better_risk_adjusted_instrument() -> None:
    result = HedgeAllocationOptimizer().allocate(
        instruments=["MES", "MNQ"],
        expected_returns=np.array([0.08, 0.08]),
        covariance=np.array([[0.01, 0.0], [0.0, 0.04]]),
        cvar=np.array([0.02, 0.05]),
        variance_aversion=1.0,
        cvar_aversion=1.0,
    )

    assert sum(result.weights.values()) == pytest.approx(1.0)
    assert result.weights["MES"] > result.weights["MNQ"]


def test_allocator_respects_desk_caps() -> None:
    result = HedgeAllocationOptimizer().allocate(
        instruments=["MES", "MGC"],
        expected_returns=np.array([0.20, 0.01]),
        covariance=np.eye(2) * 0.001,
        cvar=np.zeros(2),
        max_weights=np.array([0.6, 1.0]),
        variance_aversion=0.0,
        cvar_aversion=0.0,
    )

    assert result.weights["MES"] == pytest.approx(0.6, abs=1e-6)
    assert result.weights["MGC"] == pytest.approx(0.4, abs=1e-6)


def test_allocator_rejects_invalid_covariance() -> None:
    with pytest.raises(ValueError, match="covariance"):
        HedgeAllocationOptimizer().allocate(
            instruments=["MES", "MNQ"],
            expected_returns=np.array([0.1, 0.2]),
            covariance=np.array([0.1, 0.2]),
            cvar=np.array([0.1, 0.2]),
        )

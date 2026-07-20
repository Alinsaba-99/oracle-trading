"""Tests for M31 statistical diagnostics."""

from __future__ import annotations

import numpy as np
import pytest

from analytics.qualification.statistics import (
    bootstrap_luck_p_value,
    factor_attribution,
    returns_from_values,
)


def test_returns_from_values() -> None:
    returns = returns_from_values([100.0, 110.0, 99.0])

    assert returns.tolist() == pytest.approx([0.1, -0.1])


def test_factor_attribution_recovers_beta() -> None:
    market = np.asarray([-0.02, -0.01, 0.0, 0.01, 0.02, 0.03])
    strategy = 0.001 + 1.5 * market

    attribution = factor_attribution(strategy, market)

    assert attribution["market_beta"] == pytest.approx(1.5)
    assert attribution["r_squared"] == pytest.approx(1.0)


def test_bootstrap_luck_p_value_is_deterministic_and_bounded() -> None:
    returns = np.asarray([0.01, -0.002, 0.008, 0.003, -0.001, 0.009, 0.004, 0.002] * 4)

    first = bootstrap_luck_p_value(returns, samples=100, seed=7)
    second = bootstrap_luck_p_value(returns, samples=100, seed=7)

    assert first == second
    assert first is not None
    assert 0.0 <= first <= 1.0

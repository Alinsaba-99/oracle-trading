"""Tests for GA constraint functions — _apply_constraints, _extract_fitness."""
from __future__ import annotations

import pytest

from genetics.fitness.evaluator import (
    _EMPTY_FITNESS,
    _apply_constraints,
    _extract_fitness,
)


class TestExtractFitness:
    """_extract_fitness extracts 4-objective vector from combined metrics."""

    def test_basic_extraction(self) -> None:
        combined = {
            "sharpe_ratio_mean": 1.5,
            "sortino_ratio_mean": 2.0,
            "calmar_ratio_mean": 1.0,
            "max_drawdown_mean": 0.15,
        }
        fitness = _extract_fitness(combined)
        assert fitness == (1.5, 2.0, 1.0, 0.15)

    def test_missing_keys_default_to_minus_one(self) -> None:
        fitness = _extract_fitness({})
        assert fitness[0] == -1.0  # sharpe default
        assert fitness[1] == -1.0  # sortino default
        assert fitness[2] == -1.0  # calmar default
        assert fitness[3] == 1.0  # max_dd default

    def test_nan_replaced_with_default(self) -> None:
        combined = {
            "sharpe_ratio_mean": float("nan"),
            "sortino_ratio_mean": float("inf"),
            "calmar_ratio_mean": 1.0,
            "max_drawdown_mean": 0.15,
        }
        fitness = _extract_fitness(combined)
        assert fitness[0] == -1.0  # nan → default
        assert fitness[1] == -1.0  # inf → default
        assert fitness[2] == 1.0

    def test_negative_drawdown_clamped_to_zero(self) -> None:
        combined = {
            "sharpe_ratio_mean": 1.0,
            "sortino_ratio_mean": 1.0,
            "calmar_ratio_mean": 1.0,
            "max_drawdown_mean": -0.1,  # negative drawdown doesn't make sense
        }
        fitness = _extract_fitness(combined)
        assert fitness[3] == 0.0  # clamped


class TestApplyConstraints:
    """_apply_constraints modifies fitness based on min_trades, CAGR, PF."""

    def test_min_trades_sentinel(self) -> None:
        """Below min_trades → _EMPTY_FITNESS."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.1),
            combined={},
            total_trades=5,
            min_trades=10,
        )
        assert result == _EMPTY_FITNESS

    def test_min_trades_ok(self) -> None:
        """At or above min_trades → fitness unchanged when CAGR/PF ok."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.1),
            combined={"cagr_mean": 0.10, "profit_factor_mean": 1.5},
            total_trades=15,
            min_trades=10,
        )
        assert result == (1.0, 2.0, 3.0, 0.1)

    def test_cagr_penalty_below_threshold(self) -> None:
        """CAGR below 5% applies a linear penalty."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.1),
            combined={"cagr_mean": 0.02, "profit_factor_mean": 1.5},
            total_trades=15,
            min_trades=10,
        )
        # cagr_mult = 0.02 / 0.05 = 0.4 → sharpe/sortino/calmar scaled by 0.4
        assert result[0] == pytest.approx(1.0 * 0.4)
        assert result[1] == pytest.approx(2.0 * 0.4)
        assert result[2] == pytest.approx(3.0 * 0.4)
        assert result[3] == 0.1  # max_dd untouched

    def test_cagr_at_threshold_no_penalty(self) -> None:
        """CAGR exactly at 5% → no penalty (multiplier = 1.0)."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.1),
            combined={"cagr_mean": 0.05, "profit_factor_mean": 1.5},
            total_trades=15,
            min_trades=10,
        )
        assert result == (1.0, 2.0, 3.0, 0.1)

    def test_pf_penalty_below_one(self) -> None:
        """PF below 1.0 applies a linear penalty."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.1),
            combined={"cagr_mean": 0.10, "profit_factor_mean": 0.5},
            total_trades=15,
            min_trades=10,
        )
        # pf_mult = max(0.5, 0.01) = 0.5
        assert result[0] == pytest.approx(1.0 * 0.5)

    def test_pf_floor_at_001(self) -> None:
        """PF very close to 0 is floored at 0.01."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.1),
            combined={"cagr_mean": 0.10, "profit_factor_mean": 0.001},
            total_trades=15,
            min_trades=10,
        )
        # pf_mult = max(0.001, 0.01) = 0.01
        assert result[0] == pytest.approx(1.0 * 0.01)

    def test_most_restrictive_multiplier_wins(self) -> None:
        """Both CAGR and PF active → min(cagr_mult, pf_mult) applies."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.1),
            combined={"cagr_mean": 0.02, "profit_factor_mean": 0.8},
            total_trades=15,
            min_trades=10,
        )
        # cagr_mult = 0.02/0.05 = 0.4, pf_mult = max(0.8, 0.01) = 0.8
        # min(0.4, 0.8) = 0.4 → CAGR is more restrictive
        assert result[0] == pytest.approx(1.0 * 0.4)

    def test_cagr_key_missing_no_penalty(self) -> None:
        """Missing CAGR key → CAGR penalty skipped (backward compat)."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.1),
            combined={"profit_factor_mean": 1.5},
            total_trades=15,
            min_trades=10,
        )
        assert result == (1.0, 2.0, 3.0, 0.1)

    def test_both_keys_missing_no_penalty(self) -> None:
        """No CAGR or PF keys → no penalty."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.1),
            combined={},
            total_trades=15,
            min_trades=10,
        )
        assert result == (1.0, 2.0, 3.0, 0.1)

    def test_pf_exactly_one_no_penalty(self) -> None:
        """PF exactly 1.0 → no penalty."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.1),
            combined={"profit_factor_mean": 1.0},
            total_trades=15,
            min_trades=10,
        )
        assert result == (1.0, 2.0, 3.0, 0.1)


class TestMaxDDConstraint:
    """MaxDD > 25 % → _EMPTY_FITNESS (hard cap)."""

    def test_maxdd_above_cap_rejected(self) -> None:
        """MaxDD 42 % → rejected."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.42),
            combined={"cagr_mean": 0.10, "profit_factor_mean": 1.5},
            total_trades=15,
            min_trades=10,
        )
        assert result == _EMPTY_FITNESS

    def test_maxdd_at_cap_accepted(self) -> None:
        """MaxDD exactly 25 % → accepted (boundary)."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.25),
            combined={"cagr_mean": 0.10, "profit_factor_mean": 1.5},
            total_trades=15,
            min_trades=10,
        )
        assert result == (1.0, 2.0, 3.0, 0.25)

    def test_maxdd_below_cap_accepted(self) -> None:
        """MaxDD 10 % → accepted (normal case)."""
        result = _apply_constraints(
            fitness=(1.0, 2.0, 3.0, 0.10),
            combined={"cagr_mean": 0.10, "profit_factor_mean": 1.5},
            total_trades=15,
            min_trades=10,
        )
        assert result == (1.0, 2.0, 3.0, 0.10)

    def test_negative_cagr_rejected(self) -> None:
        """Negative CAGR → rejected regardless of Sharpe."""
        result = _apply_constraints(
            fitness=(5.0, 5.0, 5.0, 0.10),
            combined={"cagr_mean": -0.02, "profit_factor_mean": 1.5},
            total_trades=15,
            min_trades=10,
        )
        assert result == _EMPTY_FITNESS

    def test_zero_cagr_rejected(self) -> None:
        """CAGR exactly 0 % → rejected."""
        result = _apply_constraints(
            fitness=(5.0, 5.0, 5.0, 0.10),
            combined={"cagr_mean": 0.0, "profit_factor_mean": 1.5},
            total_trades=15,
            min_trades=10,
        )
        assert result == _EMPTY_FITNESS

"""Tests for BL-505h Dystopian Stress (Step 5 Opzione C 2026-08-16).

Type 2 (synthetic dystopian) + Type 3 (adversarial regime search) stress
tests that go beyond historical CrisisPeriod gauntlet. Pure-Python
synthetic price paths via GBM, jump-diffusion, crash-with-recovery.

Coverage:
- Path generators: shapes, monotonicity, distribution sanity
- Dystopian scenarios: deterministic, reproducible, extremes
- Synthetic metrics: Sharpe / DD / n_trades on known paths
- Dystopian runner: survival rate, failure attribution
- Adversarial regime search: worst-case found, fragility score
- Signal function contracts: must return same-length array
"""

from __future__ import annotations

import numpy as np
import pytest

from analytics.strategy.dystopian_stress import (
    DYSTOPIAN_SCENARIOS,
    AdversarialRegimeGrid,
    compute_synthetic_metrics,
    generate_crash_path,
    generate_gbm_path,
    generate_jump_diffusion_path,
    run_adversarial_regime_search,
    run_dystopian,
)

# ---------------------------------------------------------------------------
# Path generators
# ---------------------------------------------------------------------------


class TestGbmPath:
    def test_returns_correct_length(self) -> None:
        p = generate_gbm_path(n_days=252, start_price=100.0, seed=42)
        assert len(p) == 252

    def test_starts_at_start_price(self) -> None:
        # First price is exp(mu * dt + sigma * sqrt(dt) * z_0) * start_price,
        # so it's *near* start_price but not exactly equal.
        p = generate_gbm_path(n_days=100, start_price=42.0, seed=1)
        assert p[0] == pytest.approx(42.0, rel=0.05)  # within 5% of start

    def test_positive_prices(self) -> None:
        p = generate_gbm_path(n_days=500, start_price=100.0, annual_vol=0.30, seed=7)
        assert (p > 0).all()

    def test_deterministic_with_seed(self) -> None:
        p1 = generate_gbm_path(n_days=100, start_price=100.0, seed=42)
        p2 = generate_gbm_path(n_days=100, start_price=100.0, seed=42)
        np.testing.assert_array_equal(p1, p2)

    def test_different_seeds_produce_different_paths(self) -> None:
        p1 = generate_gbm_path(n_days=100, start_price=100.0, seed=1)
        p2 = generate_gbm_path(n_days=100, start_price=100.0, seed=2)
        assert not np.allclose(p1, p2)

    def test_higher_vol_higher_dispersion(self) -> None:
        # Run many paths and check std of final price scales with vol
        finals_low = [
            generate_gbm_path(n_days=252, start_price=100.0, annual_vol=0.10, seed=s)[-1]
            for s in range(50)
        ]
        finals_high = [
            generate_gbm_path(n_days=252, start_price=100.0, annual_vol=0.50, seed=s)[-1]
            for s in range(50)
        ]
        assert np.std(finals_high) > np.std(finals_low)


class TestJumpDiffusionPath:
    def test_returns_correct_length(self) -> None:
        p = generate_jump_diffusion_path(
            n_days=252, start_price=100.0, jump_intensity_per_year=10.0, seed=42
        )
        assert len(p) == 252

    def test_positive_prices(self) -> None:
        # Even with large negative jumps, prices stay positive
        p = generate_jump_diffusion_path(
            n_days=500,
            start_price=100.0,
            jump_intensity_per_year=20.0,
            jump_mean=-0.20,
            jump_std=0.30,
            seed=5,
        )
        assert (p > 0).all()

    def test_deterministic_with_seed(self) -> None:
        p1 = generate_jump_diffusion_path(n_days=100, start_price=100.0, seed=42)
        p2 = generate_jump_diffusion_path(n_days=100, start_price=100.0, seed=42)
        np.testing.assert_array_equal(p1, p2)


class TestCrashPath:
    def test_returns_correct_length(self) -> None:
        p = generate_crash_path(
            n_days=252,
            start_price=100.0,
            crash_day=10,
            crash_pct=-0.20,
            recovery_days=30,
            recovery_pct=0.5,
        )
        assert len(p) == 252

    def test_crash_actually_drops_price(self) -> None:
        p = generate_crash_path(
            n_days=252,
            start_price=100.0,
            crash_day=10,
            crash_pct=-0.20,
            recovery_days=30,
            recovery_pct=0.5,
        )
        # Day 10 should be 80% of day 9
        assert p[10] < p[9]
        assert p[10] == pytest.approx(p[9] * 0.80, rel=1e-3)

    def test_recovery_lifts_price(self) -> None:
        p = generate_crash_path(
            n_days=252,
            start_price=100.0,
            crash_day=10,
            crash_pct=-0.20,
            recovery_days=30,
            recovery_pct=1.0,
        )
        # Full recovery by day 10+30: should be back near pre-crash
        # (recovery_pct=1.0 means we recover 100% of the crash)
        assert p[40] > p[10]
        assert p[40] >= p[9] * 0.95  # within 5% of pre-crash


# ---------------------------------------------------------------------------
# Synthetic metrics
# ---------------------------------------------------------------------------


def _buy_and_hold(prices: np.ndarray) -> np.ndarray:
    """Position 1.0 long for the entire path."""
    return np.ones_like(prices)


def _short_and_hold(prices: np.ndarray) -> np.ndarray:
    """Position -1.0 short for the entire path."""
    return -np.ones_like(prices)


def _flat(prices: np.ndarray) -> np.ndarray:
    return np.zeros_like(prices)


class TestComputeSyntheticMetrics:
    def test_buy_hold_on_flat_path_returns_zero(self) -> None:
        # Constant price → no returns → Sharpe 0
        prices = np.full(100, 100.0)
        m = compute_synthetic_metrics(prices, _buy_and_hold)
        assert m["sharpe"] == 0.0
        assert m["total_return"] == 0.0
        assert m["max_drawdown"] == 0.0

    def test_buy_hold_on_uptrend_positive_return(self) -> None:
        prices = np.linspace(100.0, 120.0, 100)  # +20% over 100 days
        m = compute_synthetic_metrics(prices, _buy_and_hold)
        assert m["total_return"] > 0.15
        assert m["max_drawdown"] == 0.0  # monotonic up

    def test_short_hold_on_uptrend_negative_return(self) -> None:
        prices = np.linspace(100.0, 120.0, 100)
        m = compute_synthetic_metrics(prices, _short_and_hold)
        assert m["total_return"] < 0

    def test_flat_signal_zero_returns(self) -> None:
        prices = generate_gbm_path(n_days=100, start_price=100.0, seed=42)
        m = compute_synthetic_metrics(prices, _flat)
        assert m["total_return"] == 0.0
        assert m["sharpe"] == 0.0
        assert m["n_trades"] == 0

    def test_signal_length_mismatch_raises(self) -> None:
        prices = np.full(100, 100.0)

        def bad_signal(p: np.ndarray) -> np.ndarray:
            return np.ones(50)  # wrong length

        with pytest.raises(ValueError, match="same length"):
            compute_synthetic_metrics(prices, bad_signal)

    def test_n_trades_counts_position_changes(self) -> None:
        prices = np.full(100, 100.0)

        def switching_signal(p: np.ndarray) -> np.ndarray:
            sig = np.zeros(100)
            sig[20:50] = 1.0  # one position change at 20 and 50 → 2 trades
            return sig

        m = compute_synthetic_metrics(prices, switching_signal)
        assert m["n_trades"] == 2

    def test_short_input_returns_zeros(self) -> None:
        prices = np.array([100.0])
        m = compute_synthetic_metrics(prices, _buy_and_hold)
        assert m["sharpe"] == 0.0
        assert m["n_trades"] == 0


# ---------------------------------------------------------------------------
# Dystopian scenarios (Type 2)
# ---------------------------------------------------------------------------


class TestDystopianScenarios:
    def test_all_scenarios_have_unique_names(self) -> None:
        names = [s.name for s in DYSTOPIAN_SCENARIOS]
        assert len(names) == len(set(names))

    def test_all_scenarios_have_note(self) -> None:
        for s in DYSTOPIAN_SCENARIOS:
            assert s.note, f"{s.name} has no note"

    def test_scenario_generates_path(self) -> None:
        for s in DYSTOPIAN_SCENARIOS:
            p = s.generate(start_price=100.0)
            assert len(p) == s.n_days
            assert (p > 0).all()

    def test_scenario_deterministic_across_calls(self) -> None:
        s = DYSTOPIAN_SCENARIOS[0]
        p1 = s.generate(start_price=100.0)
        p2 = s.generate(start_price=100.0)
        np.testing.assert_array_equal(p1, p2)

    def test_vix_spike_100_has_high_vol(self) -> None:
        s = next(s for s in DYSTOPIAN_SCENARIOS if s.name == "vix_spike_100")
        assert s.annual_vol == 1.00  # 100% annualised vol

    def test_covid_extreme_has_crash(self) -> None:
        s = next(s for s in DYSTOPIAN_SCENARIOS if s.name == "covid_extreme_2020_plus")
        assert s.crash_day is not None
        assert s.crash_pct == -0.40


class TestRunDystopian:
    def test_buy_hold_on_all_scenarios_returns_results(self) -> None:
        report = run_dystopian(_buy_and_hold)
        assert len(report.scenario_results) == len(DYSTOPIAN_SCENARIOS)
        assert report.survival_rate >= 0.0
        # Buy&hold in dystopian regimes: should fail (high drawdowns expected)
        assert not report.passed  # buy&hold dies in crash scenarios

    def test_flat_signal_survives_all(self) -> None:
        # Flat signal: no risk, no reward — should survive (no failures)
        report = run_dystopian(_flat)
        assert report.passed
        assert report.failures == []

    def test_worst_scenario_set(self) -> None:
        report = run_dystopian(_buy_and_hold)
        assert report.worst_scenario in [s.name for s in DYSTOPIAN_SCENARIOS]

    def test_failure_attribution(self) -> None:
        # Short-and-hold will fail badly in rising regimes but the scenarios
        # are mostly adversarial → short may "pass" because everything is dropping
        report = run_dystopian(_short_and_hold)
        # Either way, failures are attributed to specific scenario names
        for f in report.failures:
            assert ":" in f  # "scenario_name: reason"

    def test_custom_thresholds(self) -> None:
        # Very strict thresholds → even flat signal fails on drawdown
        report = run_dystopian(_flat, max_drawdown_threshold=0.01)
        # Flat signal has 0 drawdown so passes both thresholds
        assert report.passed


# ---------------------------------------------------------------------------
# Adversarial regime search (Type 3)
# ---------------------------------------------------------------------------


class TestAdversarialRegimeSearch:
    def test_runs_on_default_grid(self) -> None:
        report = run_adversarial_regime_search(_buy_and_hold)
        # Default grid: 5 drifts × 5 vols × 3 j_int × 3 j_mean = 225 scenarios
        assert report.n_scenarios > 0
        assert report.worst_regime is not None
        assert report.best_regime is not None

    def test_worst_sharpe_le_best_sharpe(self) -> None:
        report = run_adversarial_regime_search(_buy_and_hold)
        assert report.worst_regime is not None
        assert report.best_regime is not None
        assert report.worst_regime.sharpe <= report.best_regime.sharpe

    def test_buy_hold_worst_in_negative_drift(self) -> None:
        # Buy&hold: worst regime should have negative drift
        report = run_adversarial_regime_search(_buy_and_hold)
        assert report.worst_regime is not None
        assert report.worst_regime.drift <= 0.0

    def test_flat_signal_has_zero_sharpe_everywhere(self) -> None:
        report = run_adversarial_regime_search(_flat)
        # All sharpes should be 0
        sharpes = [r.sharpe for r in report.all_results]
        assert all(abs(s) < 1e-9 for s in sharpes)
        assert report.fragility_score == 0.0

    def test_fragility_score_in_zero_to_one(self) -> None:
        report = run_adversarial_regime_search(_buy_and_hold)
        assert 0.0 <= report.fragility_score <= 1.0

    def test_small_grid_faster(self) -> None:
        grid = AdversarialRegimeGrid(
            drifts=(0.0, 0.10), vols=(0.15, 0.30), jump_intensities=(0.0,), jump_means=(0.0,)
        )
        report = run_adversarial_regime_search(_buy_and_hold, grid=grid)
        assert report.n_scenarios == 4

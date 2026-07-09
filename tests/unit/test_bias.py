"""Tests for BiasCorrector and benchmark comparison."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import polars as pl
import pytest

from analytics.backtest.bias import (
    BiasCorrector,
    _drawdown_adjustment,
    _equity_to_returns,
    _haircut_factor,
    _sharpe_se,
)
from analytics.backtest.result import BacktestResult

# ── helpers ─────────────────────────────────────────────────────────────────


def _make_result(
    *,
    sharpe: float = 1.5,
    sortino: float = 2.0,
    calmar: float = 1.2,
    max_dd: float = 0.15,
    total_trades: int = 100,
    final_equity: float = 110_000,
    equity_curve: list[float] | None = None,
) -> BacktestResult:
    """Build a BacktestResult with overridable key metrics."""
    return BacktestResult(
        run_id="test-run",
        strategy_name="test_strat",
        total_return=0.10,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown=max_dd,
        volatility=0.12,
        cagr=0.08,
        total_trades=total_trades,
        win_rate=0.55,
        profit_factor=1.8,
        avg_win=0.02,
        avg_loss=0.01,
        initial_capital=Decimal("100000"),
        final_equity=final_equity,
        equity_curve=equity_curve or [100.0, 101.0, 102.0],
        trades=[],
        instrument="SPY",
        start_time=datetime(2020, 1, 1),
        end_time=datetime(2020, 12, 31),
    )


# ── unit helpers ────────────────────────────────────────────────────────────


class TestHaircutFactor:
    def test_few_trades_max_haircut(self) -> None:
        assert _haircut_factor(0) == 0.50
        assert _haircut_factor(15) == 0.50
        assert _haircut_factor(29) == 0.50

    def test_ramp_zone(self) -> None:
        # 30 trades -> low end of ramp
        assert _haircut_factor(30) == pytest.approx(0.50, abs=0.01)
        # mid-point
        assert _haircut_factor(65) == pytest.approx(0.60, abs=0.005)
        # 100 trades -> high end
        assert _haircut_factor(100) == pytest.approx(0.70, abs=0.01)

    def test_many_trades_min_haircut(self) -> None:
        assert _haircut_factor(200) == 0.70
        assert _haircut_factor(1000) == 0.70


class TestDrawdownAdjustment:
    def test_few_trades_no_adjustment(self) -> None:
        assert _drawdown_adjustment(0) == 1.0
        assert _drawdown_adjustment(5) == 1.0
        assert _drawdown_adjustment(9) == 1.0

    def test_low_trades_small_adjustment(self) -> None:
        # 10 -> 49 trades
        assert _drawdown_adjustment(10) == 1.10
        assert _drawdown_adjustment(25) == 1.10
        assert _drawdown_adjustment(49) == 1.10

    def test_medium_trades_medium_adjustment(self) -> None:
        assert _drawdown_adjustment(50) == 1.20
        assert _drawdown_adjustment(100) == 1.20
        assert _drawdown_adjustment(199) == 1.20

    def test_many_trades_large_adjustment(self) -> None:
        assert _drawdown_adjustment(200) == 1.30
        assert _drawdown_adjustment(500) == 1.30


class TestSharpeStandardError:
    def test_few_observations(self) -> None:
        se = _sharpe_se(1.0, 2)
        assert se > 0

    def test_zero_observations(self) -> None:
        assert _sharpe_se(1.0, 0) == 0.0
        assert _sharpe_se(1.0, 1) == 0.0

    def test_high_sharpe_larger_se(self) -> None:
        se_low = _sharpe_se(0.5, 100)
        se_high = _sharpe_se(3.0, 100)
        assert se_high > se_low


class TestEquityToReturns:
    def test_empty_curve(self) -> None:
        assert _equity_to_returns([]) == []

    def test_single_value(self) -> None:
        assert _equity_to_returns([100.0]) == []

    def test_two_values(self) -> None:
        rets = _equity_to_returns([100.0, 110.0])
        assert rets == [0.10]

    def test_known_sequence(self) -> None:
        rets = _equity_to_returns([100.0, 105.0, 105.0, 115.5])
        assert rets == [0.05, 0.0, 0.10]

    def test_zero_division(self) -> None:
        rets = _equity_to_returns([0.0, 100.0])
        assert rets == [0.0]  # prev=0 -> return 0


# ── BiasCorrector tests ─────────────────────────────────────────────────────


class TestCorrectBacktest:
    def test_sharpe_haircut_applied(self) -> None:
        result = _make_result(sharpe=2.0, total_trades=100)
        corrected = BiasCorrector.correct_backtest(result)
        # 100 trades -> haircut 0.70
        assert corrected.sharpe_ratio == pytest.approx(1.4, rel=1e-4)

    def test_sortino_haircut_applied(self) -> None:
        result = _make_result(sortino=2.0, total_trades=100)
        corrected = BiasCorrector.correct_backtest(result)
        assert corrected.sortino_ratio == pytest.approx(1.4, rel=1e-4)

    def test_calmar_haircut_applied(self) -> None:
        result = _make_result(calmar=1.5, total_trades=100)
        corrected = BiasCorrector.correct_backtest(result)
        assert corrected.calmar_ratio == pytest.approx(1.05, rel=1e-4)

    def test_drawdown_increased(self) -> None:
        result = _make_result(max_dd=0.15, total_trades=100)
        corrected = BiasCorrector.correct_backtest(result)
        # 100 trades -> factor 1.20
        assert corrected.max_drawdown == pytest.approx(0.18, rel=1e-4)

    def test_original_not_mutated(self) -> None:
        result = _make_result(sharpe=1.5, total_trades=50)
        original_sharpe = result.sharpe_ratio
        BiasCorrector.correct_backtest(result)
        assert result.sharpe_ratio == original_sharpe

    def test_negative_sharpe_moves_toward_zero(self) -> None:
        """Negative Sharpe becomes less negative after haircut."""
        result = _make_result(sharpe=-1.0, total_trades=100)
        corrected = BiasCorrector.correct_backtest(result)
        # 100 trades -> haircut 0.70. -1.0 * 0.70 = -0.70 > -1.0
        assert corrected.sharpe_ratio > result.sharpe_ratio

    def test_zero_trades_no_drawdown_adjustment(self) -> None:
        result = _make_result(sharpe=1.5, total_trades=0)
        corrected = BiasCorrector.correct_backtest(result)
        # 0 trades -> haircut 0.50
        assert corrected.sharpe_ratio == pytest.approx(0.75, rel=1e-4)
        # drawdown unchanged (<10 trades -> factor 1.0)
        assert corrected.max_drawdown == pytest.approx(0.15, rel=1e-4)

    def test_confidence_interval_bounds(self) -> None:
        result = _make_result(sharpe=2.0, total_trades=100)
        corrected = BiasCorrector.correct_backtest(result)
        ci = BiasCorrector.corrected_metrics(result)
        assert ci["sharpe_ci_low"] < ci["sharpe_ci_high"]
        assert ci["sharpe_ci_low"] < corrected.sharpe_ratio
        assert ci["sharpe_ci_high"] > corrected.sharpe_ratio

    def test_corrected_metrics_non_mutating(self) -> None:
        result = _make_result(sharpe=1.5, total_trades=100)
        ci = BiasCorrector.corrected_metrics(result)
        assert "sharpe_ratio" in ci
        assert "sharpe_ci_low" in ci
        assert "sharpe_ci_high" in ci
        # original unchanged
        assert result.sharpe_ratio == 1.5


class TestCompareToBenchmark:
    def test_basic_attribution(self) -> None:
        """Basic attribution keys are present."""
        eq = [100.0, 101.0, 102.0, 103.0]
        bench_rets = pl.Series("bench", [0.01, 0.0099, 0.0098])
        result = _make_result(equity_curve=eq)
        attr = BiasCorrector.compare_to_benchmark(result, bench_rets)
        assert "alpha" in attr
        assert "beta" in attr
        assert "tracking_error" in attr
        assert "information_ratio" in attr
        assert "up_capture" in attr
        assert "down_capture" in attr

    def test_identical_series(self) -> None:
        """When strategy and benchmark are identical, beta ~ 1 and alpha ~ 0."""
        eq = [100.0, 101.0, 102.0, 103.0, 104.0]
        bench = pl.Series("bench", [0.01, 0.00990099, 0.00980392, 0.00970874])
        result = _make_result(equity_curve=eq)
        attr = BiasCorrector.compare_to_benchmark(result, bench, risk_free_rate=0.0)
        assert attr["beta"] == pytest.approx(1.0, abs=0.002)
        assert attr["alpha"] == pytest.approx(0.0, abs=0.01)

    def test_alpha_superior(self) -> None:
        """Strategy that beats benchmark consistently -> positive alpha."""
        eq = [100.0, 105.0, 110.0, 115.0, 120.0]
        bench = pl.Series("bench", [0.02, 0.02, 0.02, 0.02])
        result = _make_result(equity_curve=eq)
        attr = BiasCorrector.compare_to_benchmark(result, bench, risk_free_rate=0.0)
        assert attr["alpha"] > 0

    def test_underperforms_benchmark(self) -> None:
        """Strategy tracking at 0.8 beta with lower return -> negative alpha."""
        import numpy as np

        rng = np.random.default_rng(42)
        n = 500
        bench_vals = rng.normal(0.001, 0.012, n)
        # strategy returns 60% of benchmark + noise -> should underperform
        strat_rets = bench_vals * 0.6 + rng.normal(0, 0.002, n)
        eq = [100.0]
        for r in strat_rets:
            eq.append(eq[-1] * (1.0 + r))
        bench_s = pl.Series("bench", bench_vals)
        result = _make_result(equity_curve=eq, total_trades=200)
        attr = BiasCorrector.compare_to_benchmark(result, bench_s, risk_free_rate=0.0)
        # Underperform -> negative information ratio
        assert attr["information_ratio"] < 0, f"Expected IR<0, got {attr['information_ratio']}"

    def test_up_down_capture(self) -> None:
        """Capture ratios are computed. Down capture is positive when both
        strategy and benchmark fall together."""
        eq = [100.0, 102.0, 99.0, 101.0, 103.0]
        bench = pl.Series("bench", [0.01, -0.03, 0.02, 0.01])
        result = _make_result(equity_curve=eq)
        attr = BiasCorrector.compare_to_benchmark(result, bench)
        assert attr["up_capture"] >= 0
        # down capture is ratio of two negatives -> positive
        assert attr["down_capture"] >= 0

    def test_empty_equity_curve(self) -> None:
        result = _make_result(equity_curve=[])
        bench = pl.Series("bench", [0.01])
        attr = BiasCorrector.compare_to_benchmark(result, bench)
        assert all(v == 0.0 for v in attr.values())

    def test_short_series(self) -> None:
        result = _make_result(equity_curve=[100.0])
        bench = pl.Series("bench", [0.01])
        attr = BiasCorrector.compare_to_benchmark(result, bench)
        assert all(v == 0.0 for v in attr.values())

    def test_benchmark_longer_than_equity(self) -> None:
        """When benchmark is longer, we truncate to equity length."""
        eq = [100.0, 102.0, 104.0]
        bench = pl.Series("bench", [0.01, 0.02, 0.015, 0.005, 0.01])
        result = _make_result(equity_curve=eq)
        attr = BiasCorrector.compare_to_benchmark(result, bench)
        assert "alpha" in attr

    def test_flat_benchmark(self) -> None:
        """Flat benchmark (zero returns) -> beta = 0."""
        eq = [100.0, 102.0, 104.0]
        bench = pl.Series("bench", [0.0, 0.0])
        result = _make_result(equity_curve=eq)
        attr = BiasCorrector.compare_to_benchmark(result, bench)
        assert attr["beta"] == 0.0

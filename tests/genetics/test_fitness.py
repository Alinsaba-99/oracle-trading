"""Tests for the FitnessEvaluator.

Uses simple mock objects (not ``unittest.mock``) and synthetic price data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import polars as pl
import pytest

# Re-usable import for monkeypatching
import genetics.fitness.evaluator as _evaluator_mod
from analytics.backtest.config import BacktestConfig
from analytics.backtest.result import BacktestResult
from genetics.fitness.cache import FitnessCache
from genetics.fitness.evaluator import FitnessEvaluator, WalkForwardConfig
from genetics.genome.parameters import ContinuousParameter
from genetics.genome.signal import Genome

# ---------------------------------------------------------------------------
# Shared synthetic data
# ---------------------------------------------------------------------------


@pytest.fixture
def ohlcv() -> pl.DataFrame:
    """200 trading days of synthetic OHLCV trending upward."""
    n = 200
    return pl.DataFrame(
        {
            "timestamp": pl.date_range(
                datetime(2020, 1, 1), datetime(2020, 10, 17), interval="1d", eager=True
            )[:n],
            "open": [100.0 + i * 0.1 for i in range(n)],
            "high": [100.0 + i * 0.1 + 0.5 for i in range(n)],
            "low": [100.0 + i * 0.1 - 0.5 for i in range(n)],
            "close": [100.0 + i * 0.1 for i in range(n)],
            "volume": [1_000_000 for _ in range(n)],
        }
    )


# ---------------------------------------------------------------------------
# Test genome
# ---------------------------------------------------------------------------


@pytest.fixture
def test_genome() -> Genome:
    """A simple genome with four continuous parameters."""
    params = [
        ContinuousParameter(name="p1", low=0.01, high=1.0),
        ContinuousParameter(name="p2", low=0.01, high=1.0),
        ContinuousParameter(name="p3", low=0.01, high=1.0),
        ContinuousParameter(name="p4", low=0.01, high=1.0),
    ]
    return Genome(
        normalized_params=np.array([0.5, 0.3, 0.7, 0.2], dtype=np.float64), param_defs=params
    )


# ---------------------------------------------------------------------------
# Backtest config
# ---------------------------------------------------------------------------


@pytest.fixture
def backtest_cfg() -> BacktestConfig:
    return BacktestConfig(engine="vectorized", slippage_bps=5, commission_pct=0.001)


# ---------------------------------------------------------------------------
# Mock WalkForwardEngine helpers
# ---------------------------------------------------------------------------


class _MockWFEngine:
    """Mock WalkForwardEngine that returns configurable fold results."""

    def __init__(self, registry: Any = None, parent_experiment_id: str | None = None) -> None:
        self._fold_results: list[BacktestResult] = []
        self.captured_n_splits: int | None = None
        self.captured_purge_window: int | None = None
        self._raise_on_run: Exception | None = None
        self._combined: dict[str, Any] | None = None

    def run(
        self,
        data: pl.DataFrame,
        signal: Any,
        settings: BacktestConfig | None = None,
        n_splits: int = 5,
        n_test_splits: int = 1,
        purge_window: int = 5,
        split_method: str = "time",
    ) -> list[BacktestResult]:
        self.captured_n_splits = n_splits
        self.captured_purge_window = purge_window
        if self._raise_on_run is not None:
            raise self._raise_on_run
        return list(self._fold_results)

    def combined_metrics(self) -> dict[str, Any]:
        if self._combined is not None:
            return dict(self._combined)
        return {}

    def fold_results(self) -> list[BacktestResult]:
        return list(self._fold_results)


class _MockWFFactory:
    """Callable that returns the same mock instance regardless of constructor args."""

    def __init__(self, mock_instance: _MockWFEngine) -> None:
        self._mock = mock_instance

    def __call__(
        self, registry: Any = None, parent_experiment_id: str | None = None
    ) -> _MockWFEngine:
        return self._mock


def _make_results(
    n_folds: int,
    sharpe: float = 1.5,
    sortino: float = 2.0,
    calmar: float = 0.8,
    drawdown: float = 0.15,
    total_trades: int = 50,
) -> list[BacktestResult]:
    results: list[BacktestResult] = []
    for _ in range(n_folds):
        results.append(
            BacktestResult(
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                calmar_ratio=calmar,
                max_drawdown=drawdown,
                total_trades=total_trades,
                equity_curve=list(range(100)),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEvaluateReturns:
    """Basic output contract."""

    def test_returns_4_tuple(
        self,
        ohlcv: pl.DataFrame,
        test_genome: Genome,
        backtest_cfg: BacktestConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """evaluate returns a 4-element tuple of floats."""
        mock = _MockWFEngine()
        mock._fold_results = _make_results(3)
        mock._combined = {
            "sharpe_ratio_mean": 1.5,
            "sortino_ratio_mean": 2.0,
            "calmar_ratio_mean": 0.8,
            "max_drawdown_mean": 0.15,
            "n_folds": 3,
        }

        with monkeypatch.context() as ctx:
            ctx.setattr(_evaluator_mod, "WalkForwardEngine", _MockWFFactory(mock))
            evaluator = FitnessEvaluator(backtest_cfg)
            fitness = evaluator.evaluate(test_genome, ohlcv)

        assert isinstance(fitness, tuple)
        assert len(fitness) == 4
        assert all(isinstance(v, float) for v in fitness)
        assert fitness == (1.5, 2.0, 0.8, 0.15)


class TestFoldCount:
    """Walk-forward fold count verification."""

    def test_fold_count_is_exact(
        self,
        ohlcv: pl.DataFrame,
        test_genome: Genome,
        backtest_cfg: BacktestConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The evaluator should pass the configured n_splits to WalkForwardEngine."""
        mock = _MockWFEngine()
        mock._fold_results = _make_results(5)
        mock._combined = {
            "sharpe_ratio_mean": 1.0,
            "sortino_ratio_mean": 1.0,
            "calmar_ratio_mean": 0.5,
            "max_drawdown_mean": 0.2,
            "n_folds": 5,
        }

        wf_cfg = WalkForwardConfig(n_splits=5, purge_window=3)

        with monkeypatch.context() as ctx:
            ctx.setattr(_evaluator_mod, "WalkForwardEngine", _MockWFFactory(mock))
            evaluator = FitnessEvaluator(backtest_cfg, walk_forward_config=wf_cfg)
            evaluator.evaluate(test_genome, ohlcv)

        assert mock.captured_n_splits == 5
        assert mock.captured_purge_window == 3


class TestCaching:
    """Cache integration."""

    def test_cache_hit_returns_cached(
        self,
        ohlcv: pl.DataFrame,
        test_genome: Genome,
        backtest_cfg: BacktestConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A cache hit should return the stored value without re-running the backtest."""
        call_count = [0]

        class _CountingMock(_MockWFEngine):
            def run(
                self,
                data: pl.DataFrame,
                signal: Any,
                settings: BacktestConfig | None = None,
                n_splits: int = 5,
                n_test_splits: int = 1,
                purge_window: int = 5,
                split_method: str = "time",
            ) -> list[BacktestResult]:
                call_count[0] += 1
                return super().run(
                    data, signal, settings, n_splits, n_test_splits, purge_window, split_method
                )

        mock = _CountingMock()
        mock._fold_results = _make_results(3)
        mock._combined = {
            "sharpe_ratio_mean": 1.5,
            "sortino_ratio_mean": 2.0,
            "calmar_ratio_mean": 0.8,
            "max_drawdown_mean": 0.15,
            "n_folds": 3,
        }

        cache = FitnessCache(max_size=100)

        with monkeypatch.context() as ctx:
            ctx.setattr(_evaluator_mod, "WalkForwardEngine", _MockWFFactory(mock))
            evaluator = FitnessEvaluator(backtest_cfg, cache=cache)

            # First call — cache miss, runs walk-forward
            f1 = evaluator.evaluate(test_genome, ohlcv)
            assert call_count[0] == 1

            # Second call — cache hit, no engine run
            f2 = evaluator.evaluate(test_genome, ohlcv)
            assert call_count[0] == 1  # not incremented

            assert f1 == f2

    def test_cache_miss_triggers_evaluation(
        self,
        ohlcv: pl.DataFrame,
        test_genome: Genome,
        backtest_cfg: BacktestConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Two different genomes should each trigger a fresh evaluation."""
        call_count = [0]

        class _CountingMock(_MockWFEngine):
            def run(
                self,
                data: pl.DataFrame,
                signal: Any,
                settings: BacktestConfig | None = None,
                n_splits: int = 5,
                n_test_splits: int = 1,
                purge_window: int = 5,
                split_method: str = "time",
            ) -> list[BacktestResult]:
                call_count[0] += 1
                return super().run(
                    data, signal, settings, n_splits, n_test_splits, purge_window, split_method
                )

        mock = _CountingMock()
        mock._fold_results = _make_results(3)
        mock._combined = {
            "sharpe_ratio_mean": 1.5,
            "sortino_ratio_mean": 2.0,
            "calmar_ratio_mean": 0.8,
            "max_drawdown_mean": 0.15,
            "n_folds": 3,
        }

        cache = FitnessCache(max_size=100)

        genome_b = Genome(
            normalized_params=np.array([0.1, 0.9, 0.2, 0.8], dtype=np.float64),
            param_defs=test_genome.param_defs,
        )

        with monkeypatch.context() as ctx:
            ctx.setattr(_evaluator_mod, "WalkForwardEngine", _MockWFFactory(mock))
            evaluator = FitnessEvaluator(backtest_cfg, cache=cache)

            evaluator.evaluate(test_genome, ohlcv)
            assert call_count[0] == 1

            evaluator.evaluate(genome_b, ohlcv)
            assert call_count[0] == 2


class TestEdgeCases:
    """Degenerate inputs and failure modes."""

    def test_empty_returns(
        self,
        ohlcv: pl.DataFrame,
        test_genome: Genome,
        backtest_cfg: BacktestConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Zero trades across all folds → sentinel fitness (-1, -1, -1, 1)."""
        mock = _MockWFEngine()
        mock._fold_results = _make_results(3, total_trades=0)
        mock._combined = {
            "sharpe_ratio_mean": 0.0,
            "sortino_ratio_mean": 0.0,
            "calmar_ratio_mean": 0.0,
            "max_drawdown_mean": 0.0,
            "n_folds": 3,
        }

        with monkeypatch.context() as ctx:
            ctx.setattr(_evaluator_mod, "WalkForwardEngine", _MockWFFactory(mock))
            evaluator = FitnessEvaluator(backtest_cfg)
            fitness = evaluator.evaluate(test_genome, ohlcv)

        assert fitness == (-1.0, -1.0, -1.0, 1.0)

    def test_failed_backtest(
        self,
        ohlcv: pl.DataFrame,
        test_genome: Genome,
        backtest_cfg: BacktestConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An exception during backtest → sentinel fitness (-1e6, -1e6, -1e6, 1e6)."""
        mock = _MockWFEngine()
        mock._raise_on_run = RuntimeError("engine crashed")

        with monkeypatch.context() as ctx:
            ctx.setattr(_evaluator_mod, "WalkForwardEngine", _MockWFFactory(mock))
            evaluator = FitnessEvaluator(backtest_cfg)
            fitness = evaluator.evaluate(test_genome, ohlcv)

        assert fitness == (-1e6, -1e6, -1e6, 1e6)

    def test_nan_in_returns(
        self,
        ohlcv: pl.DataFrame,
        test_genome: Genome,
        backtest_cfg: BacktestConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NaN metrics should be replaced with sentinel defaults."""
        mock = _MockWFEngine()
        mock._fold_results = _make_results(3, total_trades=50)
        mock._combined = {
            "sharpe_ratio_mean": float("nan"),
            "sortino_ratio_mean": float("nan"),
            "calmar_ratio_mean": float("nan"),
            "max_drawdown_mean": float("nan"),
            "n_folds": 3,
        }

        with monkeypatch.context() as ctx:
            ctx.setattr(_evaluator_mod, "WalkForwardEngine", _MockWFFactory(mock))
            evaluator = FitnessEvaluator(backtest_cfg)
            fitness = evaluator.evaluate(test_genome, ohlcv)
        # NaN → sentinel -1.0, -1.0, -1.0, 1.0 (default drawdown)
        assert fitness == (-1.0, -1.0, -1.0, 1.0)

    def test_single_fold_degenerate_config(
        self,
        ohlcv: pl.DataFrame,
        test_genome: Genome,
        backtest_cfg: BacktestConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A degenerate config (n_splits=1) should not crash — empty results → sentinel."""
        mock = _MockWFEngine()
        # The mock returns empty results (simulating a cpcv_split failure)
        mock._fold_results = []
        mock._combined = {
            "sharpe_ratio_mean": 0.0,
            "sortino_ratio_mean": 0.0,
            "calmar_ratio_mean": 0.0,
            "max_drawdown_mean": 0.0,
            "n_folds": 0,
        }

        wf_cfg = WalkForwardConfig(n_splits=1, purge_window=0)

        with monkeypatch.context() as ctx:
            ctx.setattr(_evaluator_mod, "WalkForwardEngine", _MockWFFactory(mock))
            evaluator = FitnessEvaluator(backtest_cfg, walk_forward_config=wf_cfg)
            fitness = evaluator.evaluate(test_genome, ohlcv)

        assert fitness == (-1.0, -1.0, -1.0, 1.0)


class TestNoCachePath:
    """Behavior when no cache is provided."""

    def test_no_cache_runs_evaluation(
        self,
        ohlcv: pl.DataFrame,
        test_genome: Genome,
        backtest_cfg: BacktestConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without a cache, the evaluator should still produce results."""
        mock = _MockWFEngine()
        mock._fold_results = _make_results(3)
        mock._combined = {
            "sharpe_ratio_mean": 2.0,
            "sortino_ratio_mean": 2.5,
            "calmar_ratio_mean": 1.2,
            "max_drawdown_mean": 0.1,
            "n_folds": 3,
        }

        with monkeypatch.context() as ctx:
            ctx.setattr(_evaluator_mod, "WalkForwardEngine", _MockWFFactory(mock))
            evaluator = FitnessEvaluator(backtest_cfg)
            fitness = evaluator.evaluate(test_genome, ohlcv)

        assert fitness == (2.0, 2.5, 1.2, 0.1)

    def test_no_cache_multiple_calls_independent(
        self,
        ohlcv: pl.DataFrame,
        test_genome: Genome,
        backtest_cfg: BacktestConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without cache, each evaluate call triggers a walk-forward run."""
        call_count = [0]

        class _CountingMock(_MockWFEngine):
            def run(
                self,
                data: pl.DataFrame,
                signal: Any,
                settings: BacktestConfig | None = None,
                n_splits: int = 5,
                n_test_splits: int = 1,
                purge_window: int = 5,
                split_method: str = "time",
            ) -> list[BacktestResult]:
                call_count[0] += 1
                return super().run(
                    data, signal, settings, n_splits, n_test_splits, purge_window, split_method
                )

        mock = _CountingMock()
        mock._fold_results = _make_results(3)
        mock._combined = {
            "sharpe_ratio_mean": 1.0,
            "sortino_ratio_mean": 1.0,
            "calmar_ratio_mean": 0.5,
            "max_drawdown_mean": 0.2,
            "n_folds": 3,
        }

        with monkeypatch.context() as ctx:
            ctx.setattr(_evaluator_mod, "WalkForwardEngine", _MockWFFactory(mock))
            evaluator = FitnessEvaluator(backtest_cfg)
            evaluator.evaluate(test_genome, ohlcv)
            evaluator.evaluate(test_genome, ohlcv)

        assert call_count[0] == 2

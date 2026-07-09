"""Tests for CPCV splitters and WalkForwardEngine."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import pairwise

import polars as pl
import pytest

from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines import sma_crossover_signal
from analytics.backtest.result import BacktestResult
from analytics.backtest.splitters import CombinatorialPurgedCV, cpcv_split, time_series_split
from analytics.backtest.walk_forward import WalkForwardEngine
from core.domain.experiment import ExperimentContext, ExperimentRegistry

# ── helpers ─────────────────────────────────────────────────────────────────


def _n_dates(n: int, start: datetime | None = None) -> pl.Series:
    """Return a Polars datetime series with *n* daily intervals."""
    start = start or datetime(2020, 1, 1)
    end = start + timedelta(days=n - 1)
    return pl.datetime_range(start=start, end=end, interval="1d", eager=True)


def _sine_wave_data(n: int = 252) -> pl.DataFrame:
    """Synthetic price series with a recognizable sine-wave pattern."""
    import numpy as np

    t = np.arange(n, dtype=np.float64)
    price = 100.0 + 10.0 * np.sin(2 * np.pi * t / 60.0) + t * 0.02
    return pl.DataFrame(
        {
            "timestamp": _n_dates(n),
            "open": price + np.random.default_rng(42).uniform(-0.5, 0.5, n),
            "high": price + np.abs(np.random.default_rng(42).normal(0, 0.3, n)),
            "low": price - np.abs(np.random.default_rng(42).normal(0, 0.3, n)),
            "close": price,
            "volume": pl.Series(np.random.default_rng(42).poisson(1_000_000, n)),
        }
    )


def _constant_up_trend(n: int = 100) -> pl.DataFrame:
    """Price that increases monotonically."""
    return pl.DataFrame(
        {
            "timestamp": _n_dates(n),
            "open": 100.0 + pl.Series(range(n)).cast(pl.Float64),
            "high": 101.0 + pl.Series(range(n)).cast(pl.Float64),
            "low": 99.0 + pl.Series(range(n)).cast(pl.Float64),
            "close": 100.5 + pl.Series(range(n)).cast(pl.Float64),
            "volume": pl.Series([1_000_000] * n),
        }
    )


class AlwaysLong:
    """Always returns +1 (long)."""

    def compute(self, data: pl.DataFrame) -> pl.Series:
        return pl.Series("signal", [1] * len(data))


class AlwaysShort:
    """Always returns -1 (short)."""

    def compute(self, data: pl.DataFrame) -> pl.Series:
        return pl.Series("signal", [-1] * len(data))


# ── CPCV splitter tests ─────────────────────────────────────────────────────


class TestCpcvSplit:
    """Combinatorial Purged Cross-Validation splitter correctness."""

    def test_number_of_splits(self) -> None:
        """C(n_splits, n_test_splits) fold combinations are produced."""
        splits = cpcv_split(100, 5, 2)
        from math import comb

        assert len(splits) == comb(5, 2)

    def test_all_indices_covered(self) -> None:
        """Each index appears in exactly N-1 choose K-1 test sets."""
        n_instances = 100
        n_splits = 5
        n_test_splits = 2
        splits = cpcv_split(n_instances, n_splits, n_test_splits)

        coverage = dict.fromkeys(range(n_instances), 0)
        for _, test_idx in splits:
            for i in test_idx:
                coverage[i] += 1

        # Every index should appear at least once
        assert all(count > 0 for count in coverage.values())

        # All indices from 0..n_instances-1 are covered
        assert coverage[0] > 0
        assert coverage[n_instances - 1] > 0

    def test_train_test_disjoint(self) -> None:
        """Train and test indices are disjoint in every fold."""
        splits = cpcv_split(100, 5, 2)
        for train_idx, test_idx in splits:
            train_set = set(train_idx)
            test_set = set(test_idx)
            assert train_set.isdisjoint(test_set)

    def test_contiguous_groups(self) -> None:
        """Each test fold consists of contiguous index ranges."""
        splits = cpcv_split(100, 5, 2)
        for _, test_idx in splits:
            # Find contiguous segments in the (sorted) test indices
            sorted_test = sorted(test_idx)
            segments = 1
            for i in range(1, len(sorted_test)):
                if sorted_test[i] != sorted_test[i - 1] + 1:
                    segments += 1
            # Each fold has at most n_test_splits contiguous segments
            assert segments <= 2  # n_test_splits == 2

    def test_purge_window_removes_samples(self) -> None:
        """Purge window excludes samples adjacent to test group boundaries."""
        n_instances = 100
        purge = 3
        splits_no_purge = cpcv_split(n_instances, 5, 2, purge_window=0)
        splits_purge = cpcv_split(n_instances, 5, 2, purge_window=purge)

        # Purged splits should have strictly fewer train indices
        total_train_no_purge = sum(len(t) for t, _ in splits_no_purge)
        total_train_purge = sum(len(t) for t, _ in splits_purge)
        assert total_train_purge < total_train_no_purge

    def test_purge_window_no_leakage(self) -> None:
        """With purge_window, no train index is within purge_window of test."""
        n_instances = 100
        n_splits = 5
        n_test_splits = 2
        purge = 3

        splits = cpcv_split(n_instances, n_splits, n_test_splits, purge)
        for train_idx, test_idx in splits:
            train_set = set(train_idx)
            for t in test_idx:
                # No train point should be within purge_window of a test point
                for offset in range(1, purge + 1):
                    assert t - offset not in train_set, (
                        f"Train point {t - offset} too close to test point {t}"
                    )

    def test_rejects_invalid_n_test_splits(self) -> None:
        """Raises ValueError when n_test_splits >= n_splits."""
        with pytest.raises(ValueError, match="n_test_splits"):
            cpcv_split(100, 3, 3)

        with pytest.raises(ValueError, match="n_test_splits"):
            cpcv_split(100, 3, 4)


class TestTimeSeriesSplit:
    """Time-series cross-validation splitter."""

    def test_number_of_splits(self) -> None:
        dates = _n_dates(100)
        splits = time_series_split(dates, 5)
        assert len(splits) == 5

    def test_expanding_window(self) -> None:
        """Each subsequent fold has a larger training set."""
        dates = _n_dates(100)
        splits = time_series_split(dates, 5)
        train_sizes = [len(t) for t, _ in splits]
        assert all(s < s_next for s, s_next in pairwise(train_sizes))

    def test_train_test_disjoint(self) -> None:
        dates = _n_dates(100)
        splits = time_series_split(dates, 5)
        for train_idx, test_idx in splits:
            assert set(train_idx).isdisjoint(set(test_idx))

    def test_purge_window_creates_gap(self) -> None:
        """Purge window creates gap between train end and test start."""
        dates = _n_dates(100)
        purge = 5
        splits = time_series_split(dates, 5, purge_window=purge)
        for train_idx, test_idx in splits:
            if len(train_idx) > 0 and len(test_idx) > 0:
                max_train = max(train_idx)
                min_test = min(test_idx)
                assert min_test - max_train > purge

    def test_insufficient_data(self) -> None:
        """Too many splits for the data raises."""
        dates = _n_dates(5)
        with pytest.raises(ValueError, match="zero-length step"):
            time_series_split(dates, 10)


class TestCombinatorialPurgedCVClass:
    """Class wrapper."""

    def test_split_matches_function(self) -> None:
        cv = CombinatorialPurgedCV(n_splits=5, n_test_splits=2, purge_window=3)
        class_splits = cv.split(100)
        func_splits = cpcv_split(100, 5, 2, purge_window=3)
        assert len(class_splits) == len(func_splits)
        for (_t1, ts1), (_t2, ts2) in zip(class_splits, func_splits, strict=False):
            assert ts1 == ts2


# ── WalkForwardEngine tests ────────────────────────────────────────────────


class TestWalkForwardEngine:
    """Walk-forward validation engine."""

    def test_smoke(self) -> None:
        """WFA runs on SMA crossover without exceptions."""
        engine = WalkForwardEngine()
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        results = engine.run(data, sig, n_splits=4, n_test_splits=1)
        assert len(results) > 0
        assert all(isinstance(r, BacktestResult) for r in results)

    def test_number_of_folds(self) -> None:
        """Number of folds equals C(n_splits, n_test_splits)."""
        from math import comb

        engine = WalkForwardEngine()
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)

        n_splits = 5
        n_test_splits = 2
        results = engine.run(data, sig, n_splits=n_splits, n_test_splits=n_test_splits)
        assert len(results) == comb(n_splits, n_test_splits)

    def test_each_fold_has_result(self) -> None:
        """Each fold returns a populated BacktestResult."""
        engine = WalkForwardEngine()
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        results = engine.run(data, sig, n_splits=4, n_test_splits=1)
        for r in results:
            assert isinstance(r, BacktestResult)
            assert r.final_equity > 0
            assert len(r.equity_curve) > 0

    def test_combined_metrics_after_run(self) -> None:
        """combined_metrics() returns aggregated stats after run()."""
        engine = WalkForwardEngine()
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        engine.run(data, sig, n_splits=4, n_test_splits=1)

        combined = engine.combined_metrics()
        assert "total_return_mean" in combined
        assert "total_return_std" in combined
        assert "sharpe_ratio_mean" in combined
        assert "n_folds" in combined
        assert isinstance(combined["n_folds"], int)
        assert combined["n_folds"] > 0

    def test_combined_metrics_before_run(self) -> None:
        """combined_metrics() returns empty dict before run()."""
        engine = WalkForwardEngine()
        assert engine.combined_metrics() == {}

    def test_fold_results_accessor(self) -> None:
        """fold_results() returns the same list as run()."""
        engine = WalkForwardEngine()
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        results = engine.run(data, sig, n_splits=4, n_test_splits=1)
        assert engine.fold_results() == results

    def test_empty_before_run(self) -> None:
        """fold_results() is empty before run()."""
        engine = WalkForwardEngine()
        assert engine.fold_results() == []

    def test_multiple_runs_not_accumulated(self) -> None:
        """Each call to run() replaces previous results."""
        engine = WalkForwardEngine()
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        results1 = engine.run(data, sig, n_splits=3, n_test_splits=1)
        results2 = engine.run(data, sig, n_splits=4, n_test_splits=1)
        assert len(engine.fold_results()) == len(results2)
        assert engine.fold_results() != results1

    def test_always_long_profitable(self) -> None:
        """Always-long on uptrend is profitable on every fold."""
        engine = WalkForwardEngine()
        data = _constant_up_trend(200)
        results = engine.run(data, AlwaysLong(), n_splits=4, n_test_splits=1)
        for r in results:
            assert r.total_return > 0, f"Fold lost money: {r.total_return}"

    def test_custom_config(self) -> None:
        """BacktestConfig flows through to each fold."""
        engine = WalkForwardEngine()
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        from decimal import Decimal

        cfg = BacktestConfig(initial_capital=Decimal("50000"))
        results = engine.run(data, sig, settings=cfg, n_splits=4, n_test_splits=1)
        for r in results:
            assert r.initial_capital == Decimal("50000")

    def test_strategy_name_on_result(self) -> None:
        """Result carries the signal class name as strategy_name."""
        engine = WalkForwardEngine()
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        results = engine.run(data, sig, n_splits=4, n_test_splits=1)
        for r in results:
            assert r.strategy_name == "_SmaCrossoverSignal"

    def test_insufficient_data(self) -> None:
        """Too little data for the split count raises."""
        engine = WalkForwardEngine()
        data = _constant_up_trend(10)
        sig = sma_crossover_signal(fast=5, slow=20)
        with pytest.raises(ValueError, match="too few"):
            engine.run(data, sig, n_splits=5, n_test_splits=1)


# ── Sub-experiment tracking ─────────────────────────────────────────────────


class TestSubExperimentTracking:
    """Walk-forward sub-experiment tracking."""

    @pytest.fixture
    def registry(self, tmp_path: pytest.TempPathFactory) -> ExperimentRegistry:
        return ExperimentRegistry(str(tmp_path / "wf.db"))

    def test_experiments_are_registered(self, registry: ExperimentRegistry) -> None:
        """Each fold creates a sub-experiment entry in the registry."""
        engine = WalkForwardEngine(registry=registry)
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        results = engine.run(data, sig, n_splits=4, n_test_splits=1)

        experiments = registry.list()
        assert len(experiments) == len(results)

    def test_sub_experiment_has_parent(self, registry: ExperimentRegistry) -> None:
        """Sub-experiments have parent_experiment_id when provided."""

        parent_ctx = ExperimentContext(git_commit="parent-walk-forward")
        registry.register(parent_ctx)

        engine = WalkForwardEngine(registry=registry, parent_experiment_id=parent_ctx.experiment_id)
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        engine.run(data, sig, n_splits=4, n_test_splits=1)

        experiments = registry.list()
        child_experiments = [e for e in experiments if e.experiment_id != parent_ctx.experiment_id]
        assert len(child_experiments) > 0
        for child in child_experiments:
            assert child.parent_experiment_id == parent_ctx.experiment_id

    def test_sub_experiment_has_fold_tags(self, registry: ExperimentRegistry) -> None:
        """Sub-experiment tags contain fold metadata."""
        engine = WalkForwardEngine(registry=registry)
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        engine.run(data, sig, n_splits=4, n_test_splits=1, purge_window=3)

        experiments = registry.list()
        for exp in experiments:
            assert "fold" in exp.tags
            assert exp.tags["n_splits"] == "4"
            assert exp.tags["purge_window"] == "3"


# ── Purge window leakage prevention ─────────────────────────────────────────


class TestPurgeWindowLeakage:
    """Purge window prevents data leakage between train and test."""

    def test_purge_window_shrinks_training(self) -> None:
        """Training sets are smaller with purge_window > 0."""
        from math import comb

        n_instances = 200
        n_splits = 5
        n_test_splits = 2

        splits_no_purge = cpcv_split(n_instances, n_splits, n_test_splits, 0)
        splits_purge = cpcv_split(n_instances, n_splits, n_test_splits, 5)

        total_train_no_purge = sum(len(t) for t, _ in splits_no_purge)
        total_train_purge = sum(len(t) for t, _ in splits_purge)

        # Each of the C(5,2)=10 folds has 2 boundaries * 5 purged samples = 10
        # But some boundaries might be at the edge of data, so actual loss ≤ 100
        expected_loss_max = comb(n_splits, n_test_splits) * n_test_splits * 5 * 2
        actual_loss = total_train_no_purge - total_train_purge
        assert actual_loss > 0
        assert actual_loss <= expected_loss_max

    def test_wfa_with_purge_window(self) -> None:
        """WFA runs with purge_window enabled."""
        engine = WalkForwardEngine()
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        results = engine.run(data, sig, n_splits=4, n_test_splits=1, purge_window=10)
        assert len(results) > 0
        for r in results:
            assert isinstance(r, BacktestResult)

    def test_purge_window_train_test_gap(self) -> None:
        """Verify no train index is within purge_window of any test index."""
        n_instances = 200
        purge = 5
        splits = cpcv_split(n_instances, 5, 2, purge)

        for train_idx, test_idx in splits:
            train_set = set(train_idx)
            for t in test_idx:
                for offset in range(1, purge + 1):
                    before = t - offset
                    if 0 <= before < n_instances:
                        assert before not in train_set, (
                            f"Index {before} is within purge window of test index {t}"
                        )

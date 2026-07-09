"""Walk-Forward Validation Engine.

Executes Combinatorial Purged Cross-Validation (CPCV) across multiple
train/test folds, logs each fold as a sub-experiment in the Experiment
Registry, and returns per-fold :class:`BacktestResult` objects plus
combined summary metrics.
"""

from __future__ import annotations

import statistics
from typing import Any
from uuid import uuid4

import polars as pl

from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines.vectorized import VectorizedEngine
from analytics.backtest.protocol import BacktestSignal
from analytics.backtest.result import BacktestResult
from analytics.backtest.splitters import cpcv_split
from core.domain.experiment import ExperimentContext, ExperimentRegistry

# Metrics fields that are aggregated across folds.
_AGGREGATED_METRICS = [
    "total_return",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "max_drawdown",
    "volatility",
    "cagr",
    "win_rate",
    "profit_factor",
]


class WalkForwardEngine:
    """Walk-forward validation engine using Combinatorial Purged CV.

    Splits market data into train/test folds via CPCV, runs a vectorized
    backtest on each fold's test set, registers each fold as a sub-experiment
    in the Experiment Registry, and exposes per-fold results plus combined
    metrics.
    """

    def __init__(
        self, registry: ExperimentRegistry | None = None, parent_experiment_id: str | None = None
    ) -> None:
        self._registry = registry or ExperimentRegistry()
        self._parent_experiment_id = parent_experiment_id
        self._engine = VectorizedEngine()
        self._fold_results: list[BacktestResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        data: pl.DataFrame,
        signal: BacktestSignal,
        settings: BacktestConfig | None = None,
        n_splits: int = 5,
        n_test_splits: int = 1,
        purge_window: int = 5,
    ) -> list[BacktestResult]:
        """Run walk-forward validation.

        Parameters
        ----------
        data:
            OHLCV data as a Polars DataFrame.
        signal:
            A :class:`BacktestSignal` implementation.
        settings:
            Backtest configuration.  Defaults to ``BacktestConfig()``.
        n_splits:
            Number of chronological groups to divide data into (default 5).
        n_test_splits:
            Number of groups per test fold (default 1).
        purge_window:
            Samples to exclude from training on each side of test-group
            boundaries (default 5).

        Returns
        -------
        list[BacktestResult]
            One :class:`BacktestResult` per fold, representing the
            out-of-sample performance on that fold's test set.
        """
        cfg = settings or BacktestConfig()
        n = len(data)

        if n < n_splits * 3:
            raise ValueError(
                f"Data has {n} rows, which is too few for {n_splits} splits "
                f"with {n_test_splits} test groups each."
            )

        splits = cpcv_split(n, n_splits, n_test_splits, purge_window)

        self._fold_results = []
        strategy_name: str = getattr(signal, "__class__", signal.__class__).__name__

        for fold_idx, (train_idx, test_idx) in enumerate(splits):
            # Compute signal on the full data, then extract test portion.
            # This gives us the "in-sample signal" evaluated on test data,
            # consistent with walk-forward methodology where the signal
            # function is pre-trained / pre-defined on available history.
            full_signal = signal.compute(data)
            test_signal = full_signal[test_idx]
            test_data = data[test_idx]

            # Build a signal wrapper that returns only the test portion.
            fold_signal = _SubsetSignal(test_signal)

            # Run backtest on the fold's test set
            fold_result = self._engine.run(test_data, fold_signal, cfg)

            # Tag result
            fold_result.run_id = str(uuid4())
            fold_result.strategy_name = strategy_name
            fold_result.engine = "walk_forward"

            # Register sub-experiment
            ctx = ExperimentContext(
                parent_experiment_id=self._parent_experiment_id,
                tags={
                    "fold": str(fold_idx),
                    "n_splits": str(n_splits),
                    "n_test_splits": str(n_test_splits),
                    "purge_window": str(purge_window),
                    "engine": "walk_forward",
                    "total_return": str(fold_result.total_return),
                    "sharpe_ratio": str(fold_result.sharpe_ratio),
                    "n_train": str(len(train_idx)),
                    "n_test": str(len(test_idx)),
                },
            )
            self._registry.register(ctx)

            self._fold_results.append(fold_result)

        return self._fold_results

    def combined_metrics(self) -> dict[str, Any]:
        """Aggregate metrics across folds (mean and standard deviation).

        Returns
        -------
        dict
            Keys like ``total_return_mean``, ``total_return_std``,
            ``sharpe_ratio_mean``, ``sharpe_ratio_std``, etc.
        """
        if not self._fold_results:
            return {}

        combined: dict[str, Any] = {}
        for metric in _AGGREGATED_METRICS:
            values = [getattr(r, metric, 0.0) for r in self._fold_results]
            combined[f"{metric}_mean"] = statistics.mean(values)
            combined[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0

        combined["n_folds"] = len(self._fold_results)
        return combined

    def fold_results(self) -> list[BacktestResult]:
        """Return the list of per-fold results from the most recent run."""
        return list(self._fold_results)


class _SubsetSignal:
    """Wraps a pre-computed signal Series so it satisfies BacktestSignal.

    This is used internally by :class:`WalkForwardEngine` to present a
    pre-computed test-set signal to :class:`VectorizedEngine`.
    """

    def __init__(self, signal_series: pl.Series) -> None:
        self._signal = signal_series

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Return the wrapped signal, ignoring *data*."""
        del data  # signal is already computed; data shape is irrelevant
        return self._signal

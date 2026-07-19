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
        split_method: str = "time",
    ) -> list[BacktestResult]:
        """Run walk-forward validation.

        ``split_method="time"`` uses expanding window (preserves temporal
        order — recommended for KNN/ML strategies).

        ``split_method="cpcv"`` uses Combinatorial Purged CV (interleaved
        folds — original behaviour, kept for backward compatibility).

        Args:
            data: OHLCV data.
            signal: BacktestSignal instance.
            settings: Backtest configuration.
            n_splits: Number of folds.
            n_test_splits: Test groups per fold (CPCV only).
            purge_window: Gap between train and test.
            split_method: ``"time"`` (default) or ``"cpcv"``.

        Returns:
            List of BacktestResult, one per fold.
        """
        from analytics.backtest.splitters import time_series_split

        cfg = settings or BacktestConfig()
        n = len(data)
        self._fold_results = []

        if split_method == "time":
            splits = time_series_split(data["timestamp"], n_splits, purge_window)
        elif split_method == "cpcv":
            if n < n_splits * 3:
                raise ValueError(f"Data has {n} rows, too few for {n_splits} CPCV splits.")
            splits = cpcv_split(n, n_splits, n_test_splits, purge_window)
        else:
            msg = f"Unknown split_method={split_method!r}"
            raise ValueError(msg)

        strategy_name = getattr(signal, "__class__", signal.__class__).__name__

        for fold_idx, (_train_idx, test_idx) in enumerate(splits):
            # Compute signal causally on data up to the end of THIS test
            # fold.  Using the full dataset would let later folds influence
            # the training features / normalisation of this fold.
            fold_end = test_idx[-1] if len(test_idx) > 0 else len(data)
            fold_data = data[: fold_end + 1]
            full_signal = signal.compute(fold_data)
            test_signal = full_signal[test_idx]
            test_data = data[test_idx]

            fold_result = self._engine.run(test_data, _SubsetSignal(test_signal), cfg)
            fold_result.run_id = str(uuid4())
            fold_result.strategy_name = strategy_name
            fold_result.engine = "walk_forward"

            ctx = ExperimentContext(
                parent_experiment_id=self._parent_experiment_id,
                tags={
                    "fold": str(fold_idx),
                    "n_splits": str(n_splits),
                    "n_test_splits": str(n_test_splits),
                    "purge_window": str(purge_window),
                    "split_method": split_method,
                    "engine": "walk_forward",
                    "total_return": str(fold_result.total_return),
                    "sharpe_ratio": str(fold_result.sharpe_ratio),
                },
            )
            self._registry.register(ctx)
            self._fold_results.append(fold_result)

        return self._fold_results

    def combined_metrics(self) -> dict[str, Any]:
        """Aggregate metrics across folds (mean and std) + OOS concatenated equity.

        Returns
        -------
        dict
            Per-metric ``*_mean`` and ``*_std`` keys (backward compat),
            plus ``oos_*`` keys computed from the concatenated out-of-sample
            equity curve — the gold standard for walkforward validation.
        """
        if not self._fold_results:
            return {}

        import math

        from analytics.backtest.metrics import MetricsCalculator

        _mc = MetricsCalculator()

        # ── fix: compute missing ratio metrics from equity curve ─────
        for r in self._fold_results:
            if not r.equity_curve or len(r.equity_curve) < 10:
                continue
            equity = pl.Series(r.equity_curve, dtype=pl.Float64)
            returns = equity.pct_change().drop_nulls()
            if len(returns) < 2:
                continue
            if r.sharpe_ratio == 0.0:
                r.sharpe_ratio = _mc.sharpe_ratio(returns)
            if r.sortino_ratio == 0.0:
                r.sortino_ratio = _mc.sortino_ratio(returns)
            if r.max_drawdown == 0.0:
                r.max_drawdown = _mc.max_drawdown(equity)
            if r.calmar_ratio == 0.0 and r.max_drawdown > 0:
                r.calmar_ratio = _mc.calmar_ratio(returns, r.max_drawdown)

        # ── per-fold aggregation (backward compat) ───────────────────
        combined: dict[str, Any] = {}
        for metric in _AGGREGATED_METRICS:
            raw = [getattr(r, metric, 0.0) for r in self._fold_results]
            values = [v for v in raw if isinstance(v, (int, float)) and math.isfinite(v)]
            if not values:
                values = [0.0]
            combined[f"{metric}_mean"] = statistics.mean(values)
            combined[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else 0.0

        combined["n_folds"] = len(self._fold_results)

        # ── OOS concatenated equity ──────────────────────────────────
        # Build a single equity curve by concatenating each fold's
        # out-of-sample period.  Metrics on the combined series are
        # more robust than averaging per-fold ratios.
        try:
            oos_equity_parts: list[float] = []
            for r in self._fold_results:
                if r.equity_curve and len(r.equity_curve) > 1:
                    if oos_equity_parts and r.equity_curve:
                        scale = oos_equity_parts[-1] / r.equity_curve[0]
                        oos_equity_parts.extend([v * scale for v in r.equity_curve])
                    else:
                        oos_equity_parts.extend(r.equity_curve)
            if len(oos_equity_parts) > 10:
                oos_eq = pl.Series(oos_equity_parts, dtype=pl.Float64)
                oos_rets = oos_eq.pct_change().drop_nulls()
                if len(oos_rets) >= 2:
                    combined["oos_sharpe_ratio"] = _mc.sharpe_ratio(oos_rets)
                    combined["oos_sortino_ratio"] = _mc.sortino_ratio(oos_rets)
                    oos_dd = _mc.max_drawdown(oos_eq)
                    combined["oos_max_drawdown"] = oos_dd
                    combined["oos_calmar_ratio"] = _mc.calmar_ratio(oos_rets, oos_dd)
                    combined["oos_total_return"] = float(
                        (oos_eq[-1] / oos_eq[0] - 1) if oos_eq[0] > 0 else 0.0
                    )
        except Exception:
            pass  # OOS metrics are best-effort

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

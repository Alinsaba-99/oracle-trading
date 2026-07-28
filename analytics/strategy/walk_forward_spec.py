"""Walk-forward validation for StrategySpec (R4.x).

Higher-level wrapper over :class:`WalkForwardEngine` that takes a
:class:`StrategySpec`, fetches data from :class:`DataRegistry`, builds the
signal (single-TF or multi-TF), runs walk-forward cross-validation, and
computes per-fold :class:`FitnessReport` objects plus combined OOS metrics.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field

from analytics.backtest.providers import DataRegistry
from analytics.backtest.walk_forward import WalkForwardEngine
from analytics.strategy.composite_signal import CompositeMTFSignal
from analytics.strategy.fitness import EvalMode, FitnessReport, fitness
from analytics.strategy.multi_tf import MultiTFComposer, fetch_pair
from analytics.strategy.spec import StrategySpec

_log = logging.getLogger("oracle.strategy.walk_forward")


@dataclass
class WalkForwardReport:
    """Walk-forward analysis result for one spec."""

    spec_name: str
    instrument: str
    mode: EvalMode
    # Per-fold
    fold_reports: list[FitnessReport] = field(default_factory=list)
    # Combined OOS metrics (from WalkForwardEngine.combined_metrics)
    oos_sharpe: float = 0.0
    oos_sortino: float = 0.0
    oos_max_drawdown: float = 0.0
    oos_total_return: float = 0.0
    # Summary
    median_fitness: float = 0.0
    min_fitness: float = 0.0
    fold_std: float = 0.0
    # Stability indicators
    sharpe_stability: float = 0.0  # min_fold_sharpe / max_fold_sharpe (1.0 = perfectly stable)
    pass_rate_consistency: float = 0.0  # fraction of folds with pass_rate > 0 (FIRM only)


def walk_forward_spec(
    spec: StrategySpec,
    registry: DataRegistry,
    mode: EvalMode | str,
    *,
    n_splits: int = 5,
    purge_window: int = 5,
    split_method: str = "time",
    mc_window: int = 130,
    mc_stride: int = 5,
) -> WalkForwardReport:
    """Run walk-forward validation on a StrategySpec using the data lake.

    Args:
        spec: the strategy spec to evaluate.
        registry: source of OHLCV data.
        mode: ``EvalMode.FIRM`` or ``EvalMode.FREE``.
        n_splits: number of walk-forward folds.
        purge_window: gap bars between train and test.
        split_method: ``"time"`` (expanding window) or ``"cpcv"``.
        mc_window: Monte Carlo rolling window size (FIRM mode).
        mc_stride: Monte Carlo stride (FIRM mode).

    Returns:
        :class:`WalkForwardReport` with per-fold and combined OOS metrics.
    """
    mode = EvalMode(mode)
    signal = spec.build_signal()

    _log.info(
        "walk_forward_spec start",
        extra={
            "spec": spec.name,
            "instrument": spec.instrument,
            "mode": mode,
            "n_splits": n_splits,
            "split_method": split_method,
        },
    )

    if isinstance(signal, CompositeMTFSignal):
        primary_df, filter_df = fetch_pair(
            registry,
            spec.lake_instrument_id(),
            spec.timeframe,
            spec.filter_tf,  # type: ignore[arg-type]
        )
        if primary_df.is_empty():
            _log.warning("Empty primary data for %s; returning zero report", spec.name)
            return _empty_report(spec, mode)
        # Pre-attach the filter signal to the primary frame so that
        # WalkForwardEngine fold slices carry the signal_{filter_tf} column.
        composer = MultiTFComposer(spec.timeframe, spec.filter_tf)  # type: ignore[arg-type]
        filter_sig_series = signal.filter_signal.compute(filter_df)
        data = composer.attach_filter_signal(
            primary_df, filter_df, filter_sig_series, signal_col=signal.filter_signal_col
        )
    else:
        data = registry.get_ohlcv(spec.lake_instrument_id(), spec.timeframe)
        if data.is_empty():
            _log.warning("Empty data for %s; returning zero report", spec.name)
            return _empty_report(spec, mode)

    engine = WalkForwardEngine()
    fold_results = engine.run(
        data, signal, n_splits=n_splits, purge_window=purge_window, split_method=split_method
    )
    oos_metrics = engine.combined_metrics()

    # NOTE: per-fold intraday MC is skipped — WalkForwardEngine does not expose
    # the test-set row timestamps needed to align an intraday MC window.
    fold_reports: list[FitnessReport] = []
    for fold_idx, fold_result in enumerate(fold_results):
        fr = fitness(fold_result, mode, mc_window=mc_window, mc_stride=mc_stride)
        fold_reports.append(fr)
        _log.debug("fold %d fitness=%.4f", fold_idx, fr.fitness)

    return _build_report(spec, mode, fold_reports, oos_metrics)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_report(
    spec: StrategySpec,
    mode: EvalMode,
    fold_reports: list[FitnessReport],
    oos_metrics: dict[str, float],
) -> WalkForwardReport:
    """Assemble WalkForwardReport from per-fold data and OOS metrics."""
    fitness_vals = [fr.fitness for fr in fold_reports]
    median_fitness = statistics.median(fitness_vals) if fitness_vals else 0.0
    min_fitness = min(fitness_vals) if fitness_vals else 0.0
    fold_std = statistics.stdev(fitness_vals) if len(fitness_vals) > 1 else 0.0

    # Sharpe stability: min / max across folds (1.0 = all folds equal).
    sharpe_vals = [fr.sharpe for fr in fold_reports if math.isfinite(fr.sharpe)]
    sharpe_stability = _ratio_stability(sharpe_vals)

    # Pass-rate consistency: fraction of folds with mc_pass_rate > 0 (FIRM).
    if mode == EvalMode.FIRM and fold_reports:
        passing = sum(1 for fr in fold_reports if fr.mc_pass_rate > 0)
        pass_rate_consistency = passing / len(fold_reports)
    else:
        pass_rate_consistency = 0.0

    return WalkForwardReport(
        spec_name=spec.name,
        instrument=spec.instrument,
        mode=mode,
        fold_reports=fold_reports,
        oos_sharpe=oos_metrics.get("oos_sharpe_ratio", 0.0),
        oos_sortino=oos_metrics.get("oos_sortino_ratio", 0.0),
        oos_max_drawdown=oos_metrics.get("oos_max_drawdown", 0.0),
        oos_total_return=oos_metrics.get("oos_total_return", 0.0),
        median_fitness=median_fitness,
        min_fitness=min_fitness,
        fold_std=fold_std,
        sharpe_stability=sharpe_stability,
        pass_rate_consistency=pass_rate_consistency,
    )


def _empty_report(spec: StrategySpec, mode: EvalMode) -> WalkForwardReport:
    return WalkForwardReport(spec_name=spec.name, instrument=spec.instrument, mode=mode)


def _ratio_stability(values: list[float]) -> float:
    """Return min/max ratio for a list of values.

    Measures how stable a metric is across folds. Returns 0.0 when there are
    fewer than 2 values, the range straddles zero, or max is zero.
    """
    if len(values) < 2:
        return 0.0
    lo, hi = min(values), max(values)
    if hi == 0.0 or lo <= 0.0:
        return 0.0
    return lo / hi

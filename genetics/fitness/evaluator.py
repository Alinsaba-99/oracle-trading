"""FitnessEvaluator — walk-forward backtest evaluator with 4-objective fitness.

The evaluator bridges the genetic optimisation layer with the analytics
backtest stack: given a :class:`Genome` and market data, it runs
walk-forward validation, aggregates per-fold metrics, and returns a
4-tuple fitness vector suitable for multi-objective optimisation.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import polars as pl

from analytics.backtest.config import BacktestConfig
from analytics.backtest.walk_forward import WalkForwardEngine
from core.domain.experiment import ExperimentContext, ExperimentRegistry
from genetics.fitness.cache import FitnessCache, FitnessValue, fold_config_hash, genome_hash
from genetics.genome.signal import Genome, GenomeToSignal


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward validation in the fitness evaluator.

    Attributes
    ----------
from genetics.fitness.cache import FitnessCache, FitnessValue, fold_config_hash, genome_hash
    purge_window:
        Samples to exclude on each side of train/test boundaries.
    embargo:
        Number of samples to exclude after each test fold (reserved for
        future use; included in the cache key for forward compatibility).
    """

    n_splits: int = 5
    purge_window: int = 5
    embargo: int = 10


# Sentinel values for degenerate / failed evaluations.
_EMPTY_FITNESS: FitnessValue = (-1.0, -1.0, -1.0, 1.0)
_FAILED_FITNESS: FitnessValue = (-1e6, -1e6, -1e6, 1e6)


class FitnessEvaluator:
    """GA fitness evaluator using walk-forward backtest validation.

    The evaluator integrates with the :class:`ExperimentRegistry` for
    experiment tracking and uses an optional :class:`FitnessCache` to
    avoid redundant evaluations.
    """

    def __init__(
        self,
        backtest_config: BacktestConfig,
        walk_forward_config: WalkForwardConfig | None = None,
        registry: ExperimentRegistry | None = None,
        cache: FitnessCache | None = None,
        signal_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._backtest_cfg = backtest_config
        self._wf_cfg = walk_forward_config or WalkForwardConfig()
        self._registry = registry
        self._cache = cache
        self._signal_factory = signal_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        genome: Genome,
        data: pl.DataFrame,
    ) -> FitnessValue:
        """Evaluate a genome on the given market data.

        Parameters
        ----------
        genome:
            A decoded genome with normalised parameters and their
            definitions.
        data:
            OHLCV market data as a Polars DataFrame.

        Returns
        -------
        tuple[float, float, float, float]
            ``(sharpe_ratio, sortino_ratio, calmar_ratio, max_drawdown)``.
            Higher values are better for the first three; lower drawdown
            is better.
        """
        # ── cache lookup ─────────────────────────────────────────
        if self._cache is not None:
            g_hash = genome_hash(genome)
            fc_hash = fold_config_hash(
                self._wf_cfg.n_splits,
                self._wf_cfg.purge_window,
                self._wf_cfg.embargo,
            )
            d_hash = _data_fingerprint(data)
            cached = self._cache.get(g_hash, fc_hash, d_hash)
            if cached is not None:
                return cached

        # ── experiment context ───────────────────────────────────
        experiment_id = str(uuid4())
        if self._registry is not None:
            ctx = ExperimentContext(
                experiment_id=experiment_id,
                random_seed=42,
                tags={"type": "fitness_eval"},
            )
            self._registry.register(ctx)

        # ── build signal and run walk-forward ────────────────────
        try:
            if self._signal_factory is not None:
                signal = self._signal_factory(genome, genome.param_defs)
            else:
                signal = GenomeToSignal(genome, genome.param_defs)
            wf = WalkForwardEngine(
                registry=self._registry,
                parent_experiment_id=experiment_id,
            )
            fold_results = wf.run(
                data,
                signal,
                settings=self._backtest_cfg,
                n_splits=self._wf_cfg.n_splits,
                purge_window=self._wf_cfg.purge_window,
            )

            if not fold_results:
                return _EMPTY_FITNESS

            # Detect empty returns (no trades across any fold).
            if all(r.total_trades == 0 for r in fold_results):
                return _EMPTY_FITNESS

            combined = wf.combined_metrics()
            fitness = _extract_fitness(combined)

        except Exception:
            return _FAILED_FITNESS

        # ── cache the result ─────────────────────────────────────
        if self._cache is not None:
            self._cache.put(g_hash, fc_hash, d_hash, fitness)

        # ── register outcome ─────────────────────────────────────
        if self._registry is not None:
            outcome = ExperimentContext(
                experiment_id=str(uuid4()),
                parent_experiment_id=experiment_id,
                random_seed=42,
                tags={
                    "type": "fitness_result",
                    "sharpe": str(fitness[0]),
                    "sortino": str(fitness[1]),
                    "calmar": str(fitness[2]),
                    "drawdown": str(fitness[3]),
                    "n_folds": str(
                        combined.get("n_folds", 0) if fold_results else 0
                    ),
                },
            )
            self._registry.register(outcome)

        return fitness


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _data_fingerprint(data: pl.DataFrame, n_head: int = 10) -> str:
    """Lightweight data fingerprint for cache keying.

    Avoids hashing the entire DataFrame by sampling the leading rows
    of the ``close`` column and combining shape + column names.
    """
    raw: list[Any] = [data.shape]
    if "close" in data:
        sample = data["close"].head(n_head).to_list()
        raw.append(sample)
    raw.append(list(data.columns))
    return hashlib.sha256(repr(raw).encode()).hexdigest()


def _extract_fitness(combined: dict[str, Any]) -> FitnessValue:
    """Extract the 4-objective fitness vector from combined walk-forward metrics.

    Replaces any NaN or infinite values with sentinel defaults.
    """
    # Combined dict has keys like ``sharpe_ratio_mean``,
    # ``sharpe_ratio_std``, etc.  We only need the means.

    def _safe(key: str, default: float = -1.0) -> float:
        raw = combined.get(f"{key}_mean", default)
        if raw is None:
            return default
        if isinstance(raw, float) and (math.isnan(raw) or math.isinf(raw)):
            return default
        return float(raw)

    sharpe = _safe("sharpe_ratio")
    sortino = _safe("sortino_ratio")
    calmar = _safe("calmar_ratio")
    drawdown = _safe("max_drawdown", default=1.0)

    # Drawdown is penalising — higher is worse, but we invert the sign
    # in the cache / fitness record.  The raw drawdown is stored as-is.
    # Clamp negative drawdown to 0.0 (no drawdown) for consistency.
    drawdown = max(drawdown, 0.0)

    return (sharpe, sortino, calmar, drawdown)

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
    n_splits:
        Number of walk-forward folds.
    purge_window:
        Samples to exclude on each side of train/test boundaries.
    embargo:
        Number of samples to exclude after each test fold.
    split_method:
        ``"time"`` (expanding window) or ``"cpcv"`` (combinatorial purged).
    """

    n_splits: int = 5
    purge_window: int = 5
    embargo: int = 10
    split_method: str = "time"

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
        min_trades: int = 0,
        use_pybroker: bool = False,
    ) -> None:
        self._backtest_cfg = backtest_config
        self._wf_cfg = walk_forward_config or WalkForwardConfig()
        self._registry = registry
        self._cache = cache
        self._signal_factory = signal_factory
        self._min_trades = min_trades
        self._use_pybroker = use_pybroker

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
                self._min_trades,
                self._use_pybroker,
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

        try:
            if self._use_pybroker:
                return self._eval_pybroker(genome, data)
            
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
                split_method=self._wf_cfg.split_method,
            )

            if not fold_results:
                return _EMPTY_FITNESS
            if all(r.total_trades == 0 for r in fold_results):
                return _EMPTY_FITNESS

            combined = wf.combined_metrics()
            fitness = _extract_fitness(combined)

            # ── apply constraints (min_trades, CAGR, PF) ─────────
            total_trades = sum(r.total_trades for r in fold_results)
            constrained = _apply_constraints(
                fitness, combined, total_trades, self._min_trades
            )
            if constrained != fitness:
                fitness = constrained

        except Exception:
            return _FAILED_FITNESS

        # ── cache the result ─────────────────────────────────────
        if self._cache is not None:
            self._cache.put(g_hash, fc_hash, d_hash, fitness)

        return fitness


    def _eval_pybroker(self, genome: Genome, data: pl.DataFrame) -> FitnessValue:
        """Evaluate using PyBroker time-based walkforward.

        Returns 4-objective fitness tuple.
        """
        from analytics.backtest.pybroker_integration import PyBrokerBacktest

        if self._signal_factory is not None:
            sig_obj = self._signal_factory(genome, genome.param_defs)
        else:
            from genetics.genome.signal import GenomeToSignal
            sig_obj = GenomeToSignal(genome, genome.param_defs)

        pb = PyBrokerBacktest()
        sig_callable = lambda d: sig_obj.compute(d) if hasattr(sig_obj, 'compute') else sig_obj
        btc = self._backtest_cfg
        metrics = pb.run(
            data, sig_callable,
            n_windows=self._wf_cfg.n_splits,
            train_size=0.6,
            slippage_bps=btc.slippage_bps,
            commission_pct=btc.commission_pct,
        )

        sharpe = metrics.get("sharpe", 0.0)
        sortino = metrics.get("sortino", 0.0)
        calmar = metrics.get("calmar", 0.0)
        max_dd = abs(metrics.get("max_drawdown_pct", 100.0)) / 100.0

        fitness = (sharpe, sortino, calmar, max_dd)

        # Apply constraints (include MaxDD from PyBroker for hard cap)
        total_trades = metrics.get("trade_count", 0)
        pf = metrics.get("profit_factor", 0.0)
        cagr = metrics.get("cagr")  # None se non fornito da PyBroker
        max_dd_pct = abs(metrics.get("max_drawdown_pct", 100.0))
        constrained = _apply_constraints(
            fitness,
            {
                "profit_factor_mean": pf,
                "cagr_mean": cagr / 100.0 if cagr is not None else None,
                "max_drawdown_mean": max_dd_pct / 100.0,
            },
            total_trades,
            self._min_trades,
        )
        return constrained if constrained != fitness else fitness



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


def _apply_constraints(
    fitness: FitnessValue,
    combined: dict[str, Any],
    total_trades: int,
    min_trades: int,
) -> FitnessValue:
    """Apply constraints to a fitness tuple: min trades, CAGR, PF, MaxDD.

    Returns modified fitness if soft constraints are violated, or
    ``_EMPTY_FITNESS`` for hard constraint violations.
    """
    # ── Hard: min trades sentinel ──────────────────────────────────
    if total_trades < min_trades:
        return _EMPTY_FITNESS

    sharpe, sortino, calmar, maxdd = fitness

    # ── Hard: MaxDD cap ────────────────────────────────────────────
    # Drawdown > 25 % → degenerate strategy; reject outright.
    # This prevents GA from finding high-risk strategies that
    # achieve extreme Sharpe on short walkforward folds.
    if maxdd > 0.25:
        return _EMPTY_FITNESS

    # ── Hard: negative CAGR → degenerate ───────────────────────────
    cagr = combined.get("cagr_mean")
    if cagr is not None and cagr <= 0.0:
        return _EMPTY_FITNESS

    # ── Soft: CAGR multiplier (linear penalty below 5 %) ───────────
    cagr_mult = 1.0
    if cagr is not None and cagr < 0.05:
        cagr_mult = cagr / 0.05

    # ── Soft: PF multiplier (linear penalty below 1.0) ─────────────
    pf = combined.get("profit_factor_mean")
    pf_mult = 1.0
    if pf is not None and pf < 1.0:
        pf_mult = max(pf, 0.01)

    mult = min(cagr_mult, pf_mult)
    if mult < 1.0:
        return (sharpe * mult, sortino * mult, calmar * mult, maxdd)

    return fitness

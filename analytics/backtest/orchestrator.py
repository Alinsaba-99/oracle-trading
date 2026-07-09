"""BacktestOrchestrator — coordinates backtesting workflows.

Wraps :class:`BacktestDataProvider` and :class:`ExperimentRegistry` to
provide a unified entry point for single runs, walk-forward validation,
and parameter optimisation.
"""

from __future__ import annotations

from datetime import datetime
from itertools import product
from typing import Any, cast
from uuid import uuid4

import polars as pl

from analytics.backtest.config import BacktestConfig
from analytics.backtest.data import BacktestDataProvider
from analytics.backtest.engines.vectorized import VectorizedEngine
from analytics.backtest.protocol import BacktestSignal
from analytics.backtest.result import BacktestResult
from analytics.backtest.walk_forward import WalkForwardEngine
from core.domain.experiment import ExperimentContext, ExperimentRegistry
from core.logging import get_logger

logger = get_logger("oracle.backtest.orchestrator")


class BacktestOrchestrator:
    """Coordinates backtesting workflows.

    Usage
    -----
        orchestrator = BacktestOrchestrator(data_provider=provider)
        result = orchestrator.run(signal, engine="vectorized", instrument_id="SPY")
    """

    def __init__(
        self,
        data_provider: BacktestDataProvider | None = None,
        registry: ExperimentRegistry | None = None,
    ) -> None:
        self._data_provider = data_provider
        self._registry = registry or ExperimentRegistry()
        self._run_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        signal: BacktestSignal,
        engine: str = "vectorized",
        instrument_id: str = "SPY",
        start: datetime | None = None,
        end: datetime | None = None,
        config: BacktestConfig | None = None,
        data: pl.DataFrame | None = None,
    ) -> BacktestResult:
        """Run a single backtest and log to ExperimentRegistry.

        Parameters
        ----------
        signal:
            A :class:`BacktestSignal` implementation.
        engine:
            Engine backend — ``"vectorized"`` (default) or ``"nautilus"``.
        instrument_id:
            Instrument symbol (e.g. ``"SPY"``).
        start:
            Inclusive start timestamp; ``None`` for earliest available.
        end:
            Inclusive end timestamp; ``None`` for latest available.
        config:
            Backtest configuration.  Defaults to ``BacktestConfig()``.
        data:
            Pre-resolved OHLCV data.  When provided, *start* and *end*
            are ignored and *data_provider* is bypassed.

        Returns
        -------
        BacktestResult
            Fully populated result with all metrics.
        """
        cfg = config or BacktestConfig()
        resolved = data if data is not None else self._resolve_data(instrument_id, start, end)
        eng = self._build_engine(engine)

        result = cast(BacktestResult, eng.run(resolved, signal, cfg))
        result.run_id = str(uuid4())
        result.instrument = instrument_id
        result.strategy_name = self._signal_name(signal)
        result.engine = engine

        self._log_experiment(result)
        self._run_count += 1
        logger.info(
            "backtest.orchestrator.run.completed",
            instrument=instrument_id,
            engine=engine,
            sharpe=round(result.sharpe_ratio, 4),
            total_return=round(result.total_return, 4),
        )
        return result

    def run_walk_forward(
        self,
        signal: BacktestSignal,
        n_splits: int = 5,
        purge_window: int = 5,
        instrument_id: str = "SPY",
        start: datetime | None = None,
        end: datetime | None = None,
        config: BacktestConfig | None = None,
        data: pl.DataFrame | None = None,
    ) -> list[BacktestResult]:
        """Run walk-forward validation across multiple train/test folds.

        Parameters
        ----------
        signal:
            A :class:`BacktestSignal` implementation.
        n_splits:
            Number of CPCV splits.
        purge_window:
            Purge window (in periods) to prevent data leakage.
        instrument_id:
            Instrument symbol (e.g. ``"SPY"``).
        start:
            Inclusive start timestamp.
        config:
            Backtest configuration.  Defaults to ``BacktestConfig()``.
        data:
            Pre-resolved OHLCV data.  When provided, *start* and *end*
            are ignored and *data_provider* is bypassed.

        Returns
        -------
        list[BacktestResult]
            One result per fold.
        """
        cfg = config or BacktestConfig()
        resolved = data if data is not None else self._resolve_data(instrument_id, start, end)
        wf = WalkForwardEngine(registry=self._registry)
        results = wf.run(
            data=resolved,
            signal=signal,
            settings=cfg,
            n_splits=n_splits,
            n_test_splits=1,
            purge_window=purge_window,
        )
        self._run_count += len(results)
        logger.info(
            "backtest.orchestrator.walk_forward.completed",
            instrument=instrument_id,
            n_splits=n_splits,
            n_results=len(results),
        )
        return results

    def optimize(
        self,
        signal_factory: type,
        param_grid: dict[str, list[Any]],
        instrument_id: str = "SPY",
        start: datetime | None = None,
        end: datetime | None = None,
        metric: str = "sharpe_ratio",
        config: BacktestConfig | None = None,
    ) -> dict[str, Any]:
        """Grid search signal parameters to maximise *metric*.

        Parameters
        ----------
        signal_factory:
            A callable (class or function) that accepts keyword arguments
            from *param_grid* and returns a :class:`BacktestSignal`.
        param_grid:
            Mapping of parameter name to list of values to try, e.g.
            ``{"fast": [20, 50], "slow": [100, 200]}``.
        instrument_id:
            Instrument symbol.
        start:
            Inclusive start timestamp.
        end:
            Inclusive end timestamp.
        metric:
            Which ``BacktestResult`` attribute to maximise.
        config:
            Backtest configuration.

        Returns
        -------
        dict
            ``{"best_params": {...}, "best_score": float, "metric": str}``.
        """
        cfg = config or BacktestConfig()
        data = self._resolve_data(instrument_id, start, end)
        eng = self._build_engine("vectorized")

        best_score: float = -float("inf")
        best_params: dict[str, Any] = {}
        keys = list(param_grid.keys())

        for values in product(*param_grid.values()):
            params = dict(zip(keys, values, strict=True))
            try:
                signal_instance = signal_factory(**params)
                result = eng.run(data.clone(), signal_instance, cfg)
                score = float(getattr(result, metric, 0.0))
                if score > best_score:
                    best_score = score
                    best_params = params
            except Exception as exc:
                logger.warning("backtest.orchestrator.optimize.skip", params=params, error=str(exc))
                continue

        logger.info(
            "backtest.orchestrator.optimize.completed",
            instrument=instrument_id,
            best_params=best_params,
            best_score=round(best_score, 4),
        )
        return {"best_params": best_params, "best_score": best_score, "metric": metric}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_data(
        self, instrument_id: str, start: datetime | None = None, end: datetime | None = None
    ) -> pl.DataFrame:
        """Return OHLCV data for *instrument_id*.

        Delegates to the configured :class:`BacktestDataProvider` when
        available; raises :class:`ValueError` otherwise.
        """
        if self._data_provider is not None:
            # data_provider.get_ohlcv is async — run in a fresh event loop
            import asyncio

            return asyncio.run(self._data_provider.get_ohlcv(instrument_id, start, end))

        msg = (
            "No BacktestDataProvider configured. "
            "Pass a data_provider to BacktestOrchestrator, "
            "or construct one via BacktestDataProvider(feature_store, ...)."
        )
        raise ValueError(msg)

    @staticmethod
    def _build_engine(engine: str) -> Any:
        """Construct the appropriate engine for *engine*."""
        if engine == "vectorized":
            return VectorizedEngine()
        if engine == "nautilus":
            from analytics.backtest.engines.nautilus import NautilusEngine

            return NautilusEngine()
        msg = f"Unknown engine {engine!r}; choose from 'vectorized' or 'nautilus'"
        raise ValueError(msg)

    @staticmethod
    def _signal_name(signal: BacktestSignal) -> str:
        """Best-effort human-readable name for a signal."""
        name = type(signal).__name__
        if name and name != "_":
            return name
        return "unknown"

    def _log_experiment(self, result: BacktestResult) -> None:
        """Register a completed backtest as an experiment."""
        ctx = ExperimentContext(
            tags={
                "instrument": result.instrument or "",
                "engine": result.engine,
                "strategy": result.strategy_name,
                "total_return": f"{result.total_return:.6f}",
                "sharpe_ratio": f"{result.sharpe_ratio:.6f}",
                "total_trades": str(result.total_trades),
            }
        )
        self._registry.register(ctx)

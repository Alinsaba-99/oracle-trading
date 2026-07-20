"""Unified spec evaluator (R3.4).

One entry point — :func:`evaluate_spec` — that takes a :class:`StrategySpec`
(single-TF or multi-TF), a :class:`DataRegistry`, and a mode; fetches the
required data (pair or single frame); builds the signal; backtests; and
returns a :class:`FitnessReport`.

This is the callable that R4 (GA + LLM researcher) uses to score specs.
"""

from __future__ import annotations

from datetime import datetime

from analytics.backtest.orchestrator import BacktestOrchestrator
from analytics.backtest.providers import DataRegistry
from analytics.backtest.result import BacktestResult
from analytics.strategy.composite_signal import CompositeMTFSignal
from analytics.strategy.fitness import EvalMode, FitnessReport, fitness
from analytics.strategy.mtf_backtest import run_backtest_any
from analytics.strategy.multi_tf import fetch_pair
from analytics.strategy.spec import StrategySpec
from policy.prop_firm.profile import PropFirmProfile


def evaluate_spec(
    spec: StrategySpec,
    data_registry: DataRegistry,
    mode: EvalMode | str,
    *,
    profile: PropFirmProfile | None = None,
    initial_balance: float = 100_000.0,
    orchestrator: BacktestOrchestrator | None = None,
    engine: str = "vectorized",
    period: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    force: bool = False,
    mc_window: int = 130,
    mc_stride: int = 5,
    rollover_hour_utc: int = 0,
    include_timestamps: bool = True,
) -> FitnessReport:
    """Evaluate a strategy spec under the given mode.

    Single-TF spec → fetch primary frame, backtest.
    Multi-TF spec → fetch (primary, filter) pair, backtest via composite.

    Args:
        spec: the strategy spec to evaluate.
        data_registry: source of OHLCV (cached or live).
        mode: ``EvalMode.FIRM`` or ``EvalMode.FREE``.
        profile: prop-firm profile (FIRM only; default THE5ERS).
        initial_balance: MC normalization base.
        orchestrator: optional injected orchestrator.
        engine: engine backend (``vectorized`` default).
        period, start, end, force: forwarded to ``DataRegistry.get_ohlcv``.
        mc_window, mc_stride, rollover_hour_utc: Monte Carlo parameters.
        include_timestamps: when True (and primary TF < 1d), pass the
            frame timestamps to fitness for intraday MC.

    Returns:
        :class:`FitnessReport` with the fitness scalar and details.
    """
    signal = spec.build_signal()
    orch = orchestrator or BacktestOrchestrator()

    if isinstance(signal, CompositeMTFSignal):
        assert spec.filter_tf is not None
        primary_df, filter_df = fetch_pair(
            data_registry,
            spec.instrument,
            spec.timeframe,
            spec.filter_tf,
            period=period,
            start=start,
            end=end,
            force=force,
        )
    else:
        primary_df = data_registry.get_ohlcv(
            spec.instrument, spec.timeframe, period=period, start=start, end=end, force=force
        )
        filter_df = None

    if primary_df.is_empty():
        # Empty data → fitness 0, no MC.
        return FitnessReport(mode=EvalMode(mode), fitness=0.0)

    result: BacktestResult = run_backtest_any(
        signal,
        primary_df,
        filter_df,
        instrument_id=spec.instrument,
        orchestrator=orch,
        engine=engine,
    )

    # For intraday MC, pass timestamps when the primary TF is sub-daily.
    timestamps: list[datetime] | None = None
    if include_timestamps and spec.timeframe != "1d" and "timestamp" in primary_df.columns:
        ts_series = primary_df["timestamp"]
        # Polars datetime → python datetime list (tz-aware UTC expected).
        timestamps = list(ts_series.to_list())

    return fitness(
        result,
        mode,
        profile=profile,
        initial_balance=initial_balance,
        timestamps=timestamps,
        mc_window=mc_window,
        mc_stride=mc_stride,
        rollover_hour_utc=rollover_hour_utc,
    )

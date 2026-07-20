"""Multi-TF backtest runner (R3.1).

Thin layer over :class:`BacktestOrchestrator` that handles the two-frame
dance required by :class:`CompositeMTFSignal`:

1. Compute the filter signal on the filter-TF frame.
2. Broadcast it onto the primary-TF frame via :class:`MultiTFComposer`.
3. Run the standard vectorized backtest on the pre-attached primary frame.

This keeps the orchestrator itself single-frame (no invasive change) while
giving multi-TF specs a first-class evaluation path.
"""

from __future__ import annotations

import polars as pl

from analytics.backtest.config import BacktestConfig
from analytics.backtest.orchestrator import BacktestOrchestrator
from analytics.backtest.result import BacktestResult
from analytics.strategy.composite_signal import CompositeMTFSignal
from analytics.strategy.multi_tf import MultiTFComposer


def run_multi_tf_backtest(
    composite: CompositeMTFSignal,
    primary_df: pl.DataFrame,
    filter_df: pl.DataFrame,
    *,
    instrument_id: str,
    orchestrator: BacktestOrchestrator | None = None,
    engine: str = "vectorized",
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Backtest a multi-TF composite signal.

    Args:
        composite: the :class:`CompositeMTFSignal` built from a spec.
        primary_df: OHLCV on the primary TF (``composite.primary_tf``).
        filter_df: OHLCV on the filter TF (``composite.filter_tf``).
        instrument_id: instrument name for the result.
        orchestrator: optional injected orchestrator (default constructed).
        engine: engine backend (``vectorized`` default).
        config: optional :class:`BacktestConfig`.

    Returns:
        :class:`BacktestResult` from the underlying single-frame engine.
    """
    composer = MultiTFComposer(composite.primary_tf, composite.filter_tf)
    filter_sig = composite.filter_signal.compute(filter_df)
    attached = composer.attach_filter_signal(
        primary_df, filter_df, filter_sig, signal_col=composite.filter_signal_col
    )
    orch = orchestrator or BacktestOrchestrator()
    return orch.run(
        composite, engine=engine, instrument_id=instrument_id, config=config, data=attached
    )


def run_backtest_any(
    signal: object,
    primary_df: pl.DataFrame,
    filter_df: pl.DataFrame | None = None,
    *,
    instrument_id: str,
    orchestrator: BacktestOrchestrator | None = None,
    engine: str = "vectorized",
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Single entry point for single-TF and multi-TF signals.

    - If ``signal`` is a :class:`CompositeMTFSignal`, ``filter_df`` is
      required and the multi-TF path runs.
    - Otherwise, a single-frame backtest on ``primary_df``.
    """
    orch = orchestrator or BacktestOrchestrator()
    if isinstance(signal, CompositeMTFSignal):
        if filter_df is None:
            raise ValueError("CompositeMTFSignal requires filter_df; got None")
        return run_multi_tf_backtest(
            signal,
            primary_df,
            filter_df,
            instrument_id=instrument_id,
            orchestrator=orch,
            engine=engine,
            config=config,
        )
    return orch.run(
        signal,  # type: ignore[arg-type]
        engine=engine,
        instrument_id=instrument_id,
        config=config,
        data=primary_df,
    )

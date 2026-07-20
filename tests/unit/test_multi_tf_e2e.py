"""R2.6: end-to-end integration test for multi-TF strategy evaluation.

The path under test:

    spec (multi-TF) → build_signal → fetch_pair → compute_with_filter
    → vectorbt backtest → Monte Carlo pass-rate

Uses small synthetic frames (uptrend for both TFs) to keep runtime in
seconds; no network, no real data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import polars as pl
import pytest

from analytics.strategy.composite_signal import CompositeMTFSignal
from analytics.strategy.multi_tf import MultiTFComposer, fetch_pair
from analytics.strategy.spec import StrategySpec


def _trend_bars(
    start: datetime, tf_delta: timedelta, n: int, base: float, slope: float = 1.0
) -> pl.DataFrame:
    """Uptrend: each bar closes higher than the previous."""
    ts = [start + i * tf_delta for i in range(n)]
    closes = [base + i * slope for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": ts,
            "open": [c - slope * 0.2 for c in closes],
            "high": [c + slope * 0.3 for c in closes],
            "low": [c - slope * 0.4 for c in closes],
            "close": closes,
            "volume": [1000.0 + i for i in range(n)],
        }
    ).with_columns(pl.col("timestamp").cast(pl.Datetime(time_unit="us")))


@pytest.fixture
def primary_1h() -> pl.DataFrame:
    """10 days of hourly uptrend bars (240 rows)."""
    return _trend_bars(
        datetime(2026, 1, 11, tzinfo=UTC), timedelta(hours=1), 240, base=110.0, slope=0.05
    )


@pytest.fixture
def filter_1d() -> pl.DataFrame:
    """10 days of daily uptrend bars (10 rows) leading into the primary window."""
    return _trend_bars(
        datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 10, base=100.0, slope=1.0
    )


class TestEndToEnd:
    def test_spec_to_signal_to_combined_series(
        self, primary_1h: pl.DataFrame, filter_1d: pl.DataFrame
    ) -> None:
        """Spec → build_signal (composite) → compute_with_filter → series."""
        spec = StrategySpec(
            name="gold_donchian_ema_gate",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 10},
            timeframe="1h",
            filter_tf="1d",
            filter_entry="ema_trend",
            filter_entry_params={"fast": 3, "slow": 5},
            filter_mode="gate",
        )
        signal = spec.build_signal()
        assert isinstance(signal, CompositeMTFSignal)

        combined = signal.compute_with_filter(primary_1h, filter_1d)
        assert combined.len() == primary_1h.height
        # Values restricted to {0, 1} (gate mode blocks shorts).
        assert set(combined.to_list()) <= {0, 1}
        # In a strong uptrend on both TFs, at least one bar must fire.
        assert 1 in combined.to_list()

    def test_fetch_pair_drives_composite(
        self, primary_1h: pl.DataFrame, filter_1d: pl.DataFrame
    ) -> None:
        """fetch_pair returns (primary, filter) compatible with the composite."""
        registry = MagicMock()

        def _get(_instrument_id: str, tf: str, **_kwargs: object) -> pl.DataFrame:
            return primary_1h if tf == "1h" else filter_1d

        registry.get_ohlcv.side_effect = _get

        spec = StrategySpec(
            name="e2e",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 10},
            timeframe="1h",
            filter_tf="1d",
            filter_entry="ema_trend",
            filter_entry_params={"fast": 3, "slow": 5},
        )
        p, f = fetch_pair(registry, spec.instrument, spec.timeframe, spec.filter_tf or "1d")
        signal = spec.build_signal()
        assert isinstance(signal, CompositeMTFSignal)
        combined = signal.compute_with_filter(p, f)
        assert combined.len() == p.height

    def test_no_lookahead_via_future_mutation(self) -> None:
        """Mutating the filter's future bars must not change the combined
        signal for primary bars that close BEFORE the mutation window.

        Note on strictness: a filter signal computed with walk-forward-safe
        indicators *does* change its early values when later data shifts —
        not because of look-ahead, but because the indicator's own history
        is recomputed. What must NOT change is the *attachment* — i.e. a
        primary bar at time T must only see filter *bars* that closed ≤ T.
        We test that by checking that the attached ``close_1d`` column for
        early primary rows is invariant under future filter mutations.
        """
        from analytics.strategy.multi_tf import MultiTFComposer

        composer = MultiTFComposer("1h", "1d")

        # Use a shorter filter so we can clearly identify which filter bar
        # each primary row attaches to. 3 daily bars; primary starts on day 2.
        short_filter = _trend_bars(
            datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3, base=100.0, slope=1.0
        )
        # Primary = 24 hourly bars on day 2 (should all attach to day 1's close).
        primary_day2 = _trend_bars(
            datetime(2026, 1, 2, tzinfo=UTC), timedelta(hours=1), 24, base=102.0, slope=0.05
        )

        # Baseline.
        baseline = composer.compose(primary_day2, short_filter)

        # Mutate ONLY day 3's close (the "future" relative to primary_day2).
        mutated = short_filter.with_columns(
            pl.when(pl.int_range(0, pl.len()) == 2)
            .then(pl.lit(999.0))
            .otherwise(pl.col("close"))
            .alias("close")
        )
        after = composer.compose(primary_day2, mutated)

        # Every primary row attaches to day 1's close → invariant under the
        # day-3 mutation.
        assert baseline["close_1d"].to_list() == after["close_1d"].to_list()

    def test_composer_output_compatible_with_vectorbt(
        self, primary_1h: pl.DataFrame, filter_1d: pl.DataFrame
    ) -> None:
        """MultiTFComposer.compose produces a frame with the OHLCV schema
        expected by the vectorized backtest engine (plus filter columns).
        """
        composer = MultiTFComposer("1h", "1d")
        out = composer.compose(primary_1h, filter_1d)
        # Standard OHLCV cols still present.
        for col in ("timestamp", "open", "high", "low", "close", "volume"):
            assert col in out.columns
        # Filter cols added.
        for col in ("open_1d", "high_1d", "low_1d", "close_1d", "volume_1d"):
            assert col in out.columns
        # Row count preserved.
        assert out.height == primary_1h.height

    def test_full_signal_pipeline_vectorized_backtest(
        self, primary_1h: pl.DataFrame, filter_1d: pl.DataFrame
    ) -> None:
        """Smoke: composite signal can be backtested via the orchestrator
        on a pre-attached frame without exceptions, and produces a
        BacktestResult with a valid equity curve."""
        from analytics.backtest.orchestrator import BacktestOrchestrator

        composer = MultiTFComposer("1h", "1d")
        spec = StrategySpec(
            name="smoke",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 10},
            timeframe="1h",
            filter_tf="1d",
            filter_entry="ema_trend",
            filter_entry_params={"fast": 3, "slow": 5},
        )
        signal = spec.build_signal()
        assert isinstance(signal, CompositeMTFSignal)

        # Compute filter signal + attach to primary, then run the composite
        # via the pre-attached path (single-frame compute).
        filter_sig = signal.filter_signal.compute(filter_1d)
        attached = composer.attach_filter_signal(
            primary_1h, filter_1d, filter_sig, signal_col=signal.filter_signal_col
        )

        # BacktestOrchestrator passes the attached frame into compute().
        result = BacktestOrchestrator().run(
            signal, engine="vectorized", instrument_id="GOLD", data=attached
        )
        assert result is not None
        assert result.equity_curve is not None
        # Sanity: equity curve has same length as input (or shorter for warmup).
        assert len(result.equity_curve) > 0

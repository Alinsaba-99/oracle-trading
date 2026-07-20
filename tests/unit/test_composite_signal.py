"""Tests for analytics.strategy.composite_signal (R2.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from analytics.strategy.composite_signal import CompositeMode, CompositeMTFSignal
from analytics.strategy.multi_tf import MultiTFComposer


def _bars(start: datetime, tf_delta: timedelta, n: int, base: float = 100.0) -> pl.DataFrame:
    ts = [start + i * tf_delta for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": ts,
            "open": [base + i for i in range(n)],
            "high": [base + i + 0.5 for i in range(n)],
            "low": [base + i - 0.5 for i in range(n)],
            "close": [base + i + 0.25 for i in range(n)],
            "volume": [1000.0 + i for i in range(n)],
        }
    ).with_columns(pl.col("timestamp").cast(pl.Datetime(time_unit="us")))


class _ConstSignal:
    """A stub BacktestSignal that always returns a constant value."""

    def __init__(self, value: int) -> None:
        self.value = value

    def compute(self, data: pl.DataFrame) -> pl.Series:
        return pl.Series([self.value] * data.height)


class _CloseGtSignal:
    """Signal that is 1 when close > threshold, else 0."""

    def __init__(self, threshold: float) -> None:
        self.threshold = threshold

    def compute(self, data: pl.DataFrame) -> pl.Series:
        return pl.Series([1 if c > self.threshold else 0 for c in data["close"].to_list()])


class TestCompositeValidation:
    def test_rejects_same_tf(self) -> None:
        with pytest.raises(ValueError, match="strictly higher"):
            CompositeMTFSignal(_ConstSignal(1), _ConstSignal(1), primary_tf="1h", filter_tf="1h")

    def test_rejects_bad_mode(self) -> None:
        with pytest.raises(ValueError, match="not a valid"):
            CompositeMTFSignal(
                _ConstSignal(1), _ConstSignal(1), primary_tf="1h", filter_tf="1d", mode="invalid"
            )

    def test_rejects_bad_filter_sign(self) -> None:
        with pytest.raises(ValueError, match="filter_sign"):
            CompositeMTFSignal(
                _ConstSignal(1), _ConstSignal(1), primary_tf="1h", filter_tf="1d", filter_sign=0
            )

    def test_valid_modes(self) -> None:
        for mode in ("gate", "confirm", "size"):
            sig = CompositeMTFSignal(
                _ConstSignal(1), _ConstSignal(1), primary_tf="1h", filter_tf="1d", mode=mode
            )
            assert sig.mode == CompositeMode(mode)


class TestGateMode:
    def test_gate_passes_when_filter_long(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1),
            _ConstSignal(1),  # filter says long
            primary_tf="1h",
            filter_tf="1d",
            mode="gate",
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 1)
        out = comp.compute_with_filter(primary, filter_df)
        assert out.to_list() == [1]

    def test_gate_blocks_when_filter_short(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1),
            _ConstSignal(-1),  # filter says short → blocks long entry
            primary_tf="1h",
            filter_tf="1d",
            mode="gate",
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 1)
        out = comp.compute_with_filter(primary, filter_df)
        assert out.to_list() == [0]

    def test_gate_blocks_when_filter_flat(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1), _ConstSignal(0), primary_tf="1h", filter_tf="1d", mode="gate"
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 1)
        out = comp.compute_with_filter(primary, filter_df)
        assert out.to_list() == [0]

    def test_gate_filter_sign_minus_allows_short(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(-1),  # primary wants short
            _ConstSignal(-1),  # filter agrees short
            primary_tf="1h",
            filter_tf="1d",
            mode="gate",
            filter_sign=-1,
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 1)
        out = comp.compute_with_filter(primary, filter_df)
        assert out.to_list() == [-1]


class TestConfirmMode:
    def test_confirm_same_sign(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1), _ConstSignal(1), primary_tf="1h", filter_tf="1d", mode="confirm"
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 1)
        out = comp.compute_with_filter(primary, filter_df)
        assert out.to_list() == [1]

    def test_confirm_blocks_divergence(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1), _ConstSignal(-1), primary_tf="1h", filter_tf="1d", mode="confirm"
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 1)
        out = comp.compute_with_filter(primary, filter_df)
        assert out.to_list() == [0]

    def test_confirm_blocks_zero(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1), _ConstSignal(0), primary_tf="1h", filter_tf="1d", mode="confirm"
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 1)
        out = comp.compute_with_filter(primary, filter_df)
        assert out.to_list() == [0]


class TestSizeMode:
    def test_size_scales_primary(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1),
            _ConstSignal(2),  # filter magnitude 2
            primary_tf="1h",
            filter_tf="1d",
            mode="size",
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 1)
        out = comp.compute_with_filter(primary, filter_df)
        assert out.to_list() == [2.0]

    def test_size_zero_kills(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1), _ConstSignal(0), primary_tf="1h", filter_tf="1d", mode="size"
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 1)
        out = comp.compute_with_filter(primary, filter_df)
        assert out.to_list() == [0.0]

    def test_size_negative_flips(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1), _ConstSignal(-1), primary_tf="1h", filter_tf="1d", mode="size"
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 1)
        out = comp.compute_with_filter(primary, filter_df)
        assert out.to_list() == [-1.0]


class TestComputeWithPreAttached:
    """The single-frame compute() path expects signal_{filter_tf} present."""

    def test_compute_with_preattached(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1), _ConstSignal(1), primary_tf="1h", filter_tf="1d", mode="gate"
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 2)
        # Manually attach the broadcast filter column.
        preattached = primary.with_columns(pl.lit(1).alias("signal_1d"))
        out = comp.compute(preattached)
        assert out.to_list() == [1, 1]

    def test_compute_missing_filter_col_raises(self) -> None:
        comp = CompositeMTFSignal(
            _ConstSignal(1), _ConstSignal(1), primary_tf="1h", filter_tf="1d", mode="gate"
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        with pytest.raises(ValueError, match="signal_1d"):
            comp.compute(primary)

    def test_null_filter_defaults_to_zero(self) -> None:
        """Null filter signal = no confirmation (safe default)."""
        comp = CompositeMTFSignal(
            _ConstSignal(1), _ConstSignal(1), primary_tf="1h", filter_tf="1d", mode="gate"
        )
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 2)
        preattached = primary.with_columns(pl.Series("signal_1d", [None, 1]))
        out = comp.compute(preattached)
        assert out.to_list() == [0, 1]  # null → 0 → blocked


class TestWithRealSignals:
    """Integration with the actual signal library (R1 + base)."""

    def test_donchian_primary_ema_filter(self) -> None:
        """DonchianBreakout(5) on 1h gated by EmaTrend(5,10) on 1d."""
        from analytics.strategy.signals import DonchianBreakout, EmaTrend

        # Filter: 20 days of uptrend → EmaTrend should be 1 by the end.
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 20, base=100.0)
        # Primary: 10 hours continuing the uptrend.
        primary = _bars(datetime(2026, 1, 21, tzinfo=UTC), timedelta(hours=1), 10, base=119.0)

        comp = CompositeMTFSignal(
            DonchianBreakout(period=5),
            EmaTrend(fast=5, slow=10),
            primary_tf="1h",
            filter_tf="1d",
            mode="gate",
        )
        out = comp.compute_with_filter(primary, filter_df)
        # Some 1s expected (filter allows long in uptrend + donchian fires on new highs).
        assert set(out.to_list()) <= {0, 1}
        # At least one bar should fire (strong uptrend in both frames).
        assert 1 in out.to_list()


class TestComposerIntegration:
    """End-to-end: compose OHLCV, attach filter signal, compute composite."""

    def test_full_pipeline(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3, base=1.0)
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 3)

        # Step 1: filter signal.
        filter_sig = pl.Series([1, 1, 1])
        # Step 2: attach to primary.
        attached = composer.attach_filter_signal(primary, filter_df, filter_sig)
        # Step 3: composite compute on pre-attached frame.
        comp = CompositeMTFSignal(
            _ConstSignal(1), _ConstSignal(1), primary_tf="1h", filter_tf="1d", mode="gate"
        )
        out = comp.compute(attached)
        assert out.to_list() == [1, 1, 1]

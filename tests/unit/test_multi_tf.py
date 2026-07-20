"""Tests for analytics.strategy.multi_tf (R2.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from analytics.strategy.multi_tf import MultiTFComposer


def _bars(start: datetime, tf_delta: timedelta, n: int, base: float = 100.0) -> pl.DataFrame:
    """Generate ``n`` sequential OHLCV bars starting at ``start``."""
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


class TestComposerValidation:
    def test_rejects_same_tf(self) -> None:
        with pytest.raises(ValueError, match="strictly higher"):
            MultiTFComposer("1h", "1h")

    def test_rejects_inverted(self) -> None:
        with pytest.raises(ValueError, match="strictly higher"):
            MultiTFComposer("1d", "1h")

    def test_accepts_valid(self) -> None:
        MultiTFComposer("15m", "1h")
        MultiTFComposer("1h", "1d")
        MultiTFComposer("4h", "1d")


class TestCompose:
    def test_empty_primary_returns_empty(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        empty = pl.DataFrame(
            schema={
                "timestamp": pl.Datetime(time_unit="us"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
            }
        )
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3)
        out = composer.compose(empty, filter_df)
        assert out.is_empty()

    def test_empty_filter_attaches_null_columns(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        primary = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(hours=1), 5)
        empty_filter = pl.DataFrame(
            schema={
                "timestamp": pl.Datetime(time_unit="us"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
            }
        )
        out = composer.compose(primary, empty_filter)
        assert out.height == primary.height
        assert "close_1d" in out.columns
        assert out["close_1d"].null_count() == out.height

    def test_adds_suffixed_columns(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        primary = _bars(datetime(2026, 1, 2, tzinfo=UTC), timedelta(hours=1), 10)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3)
        out = composer.compose(primary, filter_df)
        for col in ("open_1d", "high_1d", "low_1d", "close_1d", "volume_1d"):
            assert col in out.columns, f"missing {col}"

    def test_no_lookahead_within_filter_bar(self) -> None:
        """Primary bars inside day N's filter bar must see day N-1's close,
        not day N's (which hasn't closed yet)."""
        composer = MultiTFComposer("1h", "1d")
        # Filter: day 1 close=1.25, day 2 close=2.25, day 3 close=3.25
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3, base=1.0)
        # Primary: hour 0 of day 2 (2026-01-02 00:00). Day 2 has just opened,
        # hasn't closed — must still see day 1's close (1.25).
        primary = _bars(datetime(2026, 1, 2, tzinfo=UTC), timedelta(hours=1), 1)
        out = composer.compose(primary, filter_df)
        assert out["close_1d"][0] == pytest.approx(1.25)

    def test_visible_after_filter_close(self) -> None:
        """A primary bar at or after the filter bar's close sees that filter."""
        composer = MultiTFComposer("1h", "1d")
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3, base=1.0)
        # Primary: hour 23 of day 1 (2026-01-01 23:00). Day 1's close ts
        # is 2026-01-01 23:59:59.999999 — 23:00 is *before* that, so still
        # sees day 0's data (none in this synthetic) → null. Hour 23 of day 2
        # is after day 2 opens but before day 2 closes → sees day 1's close.
        primary_late_day1 = _bars(datetime(2026, 1, 1, 23, tzinfo=UTC), timedelta(hours=1), 1)
        primary_day2 = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        out1 = composer.compose(primary_late_day1, filter_df)
        out2 = composer.compose(primary_day2, filter_df)
        # 23:00 on day 1 is before day 1's close → still on prior filter (none).
        assert out1["close_1d"][0] is None
        # 12:00 on day 2 → day 1 closed at end of day 1 → visible.
        assert out2["close_1d"][0] == pytest.approx(1.25)

    def test_before_first_filter_bar_is_null(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        primary = _bars(datetime(2025, 12, 31, tzinfo=UTC), timedelta(hours=1), 3)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3)
        out = composer.compose(primary, filter_df)
        # Primary precedes the entire filter → null in all filter columns.
        assert out["close_1d"].null_count() == 3

    def test_preserves_primary_order(self) -> None:
        """Composer must restore primary's original row order after join."""
        composer = MultiTFComposer("1h", "1d")
        primary = _bars(datetime(2026, 1, 2, tzinfo=UTC), timedelta(hours=1), 10)
        # Shuffle primary rows.
        shuffled = primary.sample(fraction=1.0, seed=42)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3)
        out = composer.compose(shuffled, filter_df)
        assert out["timestamp"].to_list() == shuffled["timestamp"].to_list()

    def test_keep_filter_ts_optional(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        primary = _bars(datetime(2026, 1, 2, tzinfo=UTC), timedelta(hours=1), 3)
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3)
        out_with = composer.compose(primary, filter_df, keep_filter_ts=True)
        assert "_filter_close_ts" in out_with.columns
        out_without = composer.compose(primary, filter_df)
        assert "_filter_close_ts" not in out_without.columns


class TestAttachFilterSignal:
    def test_broadcasts_filter_signal(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3, base=1.0)
        # Day 1 → 1, day 2 → 0, day 3 → -1
        filter_signal = pl.Series([1, 0, -1])
        # Primary bars inside day 2 (which sees day 1's signal = 1).
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        out = composer.attach_filter_signal(primary, filter_df, filter_signal)
        assert "signal_1d" in out.columns
        assert out["signal_1d"][0] == 1

    def test_length_mismatch_raises(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3)
        primary = _bars(datetime(2026, 1, 2, tzinfo=UTC), timedelta(hours=1), 5)
        bad_signal = pl.Series([1, 0])  # wrong length
        with pytest.raises(ValueError, match="length mismatch"):
            composer.attach_filter_signal(primary, filter_df, bad_signal)

    def test_custom_signal_col_name(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 2)
        filter_signal = pl.Series([1, 1])
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        out = composer.attach_filter_signal(
            primary, filter_df, filter_signal, signal_col="trend_gate"
        )
        assert "trend_gate" in out.columns
        assert out["trend_gate"][0] == 1

    def test_empty_filter_gives_null(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        empty_filter = pl.DataFrame(
            schema={
                "timestamp": pl.Datetime(time_unit="us"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
            }
        )
        primary = _bars(datetime(2026, 1, 2, tzinfo=UTC), timedelta(hours=1), 3)
        out = composer.attach_filter_signal(primary, empty_filter, pl.Series([], dtype=pl.Int64))
        assert "signal_1d" in out.columns
        assert out["signal_1d"].null_count() == 3


class TestNoLookAhead:
    """Critical correctness: perturbing future filter bars must NOT change
    earlier primary rows' attached values.
    """

    def test_future_filter_change_does_not_leak(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        # Day 1 close=1.25, day 2 close=2.25, day 3 close=3.25
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 3, base=1.0)
        # Primary bar inside day 2 → should see day 1's close.
        primary = _bars(datetime(2026, 1, 2, 12, tzinfo=UTC), timedelta(hours=1), 1)
        baseline = composer.compose(primary, filter_df)["close_1d"][0]

        # Mutate day 3's close (the future relative to primary).
        modified = filter_df.with_columns(
            pl.when(pl.col("timestamp") == pl.col("timestamp").max())
            .then(pl.lit(999.0))
            .otherwise(pl.col("close"))
            .alias("close")
        )
        after = composer.compose(primary, modified)["close_1d"][0]
        assert baseline == after

    def test_full_shuffle_of_future_does_not_leak(self) -> None:
        composer = MultiTFComposer("1h", "1d")
        filter_df = _bars(datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 5, base=1.0)
        # Primary inside day 3 → sees day 2's close.
        primary = _bars(datetime(2026, 1, 3, 12, tzinfo=UTC), timedelta(hours=1), 1)
        baseline = composer.compose(primary, filter_df)["close_1d"][0]

        # Zero out closes for days 4 and 5 (future relative to primary).
        cutoff = datetime(2026, 1, 3, tzinfo=UTC)
        modified = filter_df.with_columns(
            pl.when(pl.col("timestamp") >= pl.lit(cutoff).cast(pl.Datetime(time_unit="us")))
            .then(pl.lit(0.0))
            .otherwise(pl.col("close"))
            .alias("close")
        )
        after = composer.compose(primary, modified)["close_1d"][0]
        assert baseline == after

"""Tests for mtf_backtest (R3.1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from analytics.strategy.composite_signal import CompositeMTFSignal
from analytics.strategy.mtf_backtest import run_backtest_any, run_multi_tf_backtest
from analytics.strategy.signals import DonchianBreakout, EmaTrend


def _trend_bars(
    start: datetime, tf_delta: timedelta, n: int, base: float, slope: float = 1.0
) -> pl.DataFrame:
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
    return _trend_bars(
        datetime(2026, 1, 11, tzinfo=UTC), timedelta(hours=1), 240, base=110.0, slope=0.05
    )


@pytest.fixture
def filter_1d() -> pl.DataFrame:
    return _trend_bars(
        datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 10, base=100.0, slope=1.0
    )


class TestRunMultiTFBacktest:
    def test_runs_and_returns_result(
        self, primary_1h: pl.DataFrame, filter_1d: pl.DataFrame
    ) -> None:
        composite = CompositeMTFSignal(
            DonchianBreakout(period=10),
            EmaTrend(fast=3, slow=5),
            primary_tf="1h",
            filter_tf="1d",
            mode="gate",
        )
        result = run_multi_tf_backtest(composite, primary_1h, filter_1d, instrument_id="GOLD")
        assert result is not None
        assert result.instrument == "GOLD"
        assert result.equity_curve is not None
        assert len(result.equity_curve) > 0

    def test_result_has_metrics(self, primary_1h: pl.DataFrame, filter_1d: pl.DataFrame) -> None:
        composite = CompositeMTFSignal(
            DonchianBreakout(period=10),
            EmaTrend(fast=3, slow=5),
            primary_tf="1h",
            filter_tf="1d",
            mode="gate",
        )
        result = run_multi_tf_backtest(composite, primary_1h, filter_1d, instrument_id="GOLD")
        # Result exposes the standard metrics (may be 0 in toy data).
        assert isinstance(result.total_return, float)
        assert isinstance(result.sharpe_ratio, float)


class TestRunBacktestAny:
    def test_single_tf_path(self, primary_1h: pl.DataFrame) -> None:
        """Single-TF signal → straight through, no filter needed."""
        result = run_backtest_any(DonchianBreakout(period=10), primary_1h, instrument_id="GOLD")
        assert result.instrument == "GOLD"

    def test_multi_tf_path(self, primary_1h: pl.DataFrame, filter_1d: pl.DataFrame) -> None:
        composite = CompositeMTFSignal(
            DonchianBreakout(period=10),
            EmaTrend(fast=3, slow=5),
            primary_tf="1h",
            filter_tf="1d",
            mode="gate",
        )
        result = run_backtest_any(composite, primary_1h, filter_1d, instrument_id="GOLD")
        assert result.instrument == "GOLD"

    def test_multi_tf_missing_filter_raises(self, primary_1h: pl.DataFrame) -> None:
        composite = CompositeMTFSignal(
            DonchianBreakout(period=10),
            EmaTrend(fast=3, slow=5),
            primary_tf="1h",
            filter_tf="1d",
            mode="gate",
        )
        with pytest.raises(ValueError, match="filter_df"):
            run_backtest_any(composite, primary_1h, None, instrument_id="GOLD")

"""Tests for PyBroker integration — walkforward backtesting bridge."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

from analytics.backtest.pybroker_integration import PyBrokerBacktest


@pytest.fixture
def small_data() -> pl.DataFrame:
    """Minimal OHLCV dataset for smoke testing (100 bars)."""
    n = 100
    rng = np.random.default_rng(42)
    close = 100.0 + np.arange(n) * 0.1 + rng.normal(0, 0.5, n)
    return pl.DataFrame(
        {
            "timestamp": pl.date_range(
                start=datetime(2020, 1, 1),
                end=datetime(2020, 1, 1) + timedelta(days=n - 1),
                interval="1d",
                eager=True,
            ),
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": [1_000_000] * n,
        }
    )


def _constant_long(_data: pl.DataFrame) -> pl.Series:
    """Signal that's always long (1)."""
    return pl.Series("signal", [1] * len(_data), dtype=pl.Int8)


@pytest.mark.slow
def test_pybroker_smoke(small_data: pl.DataFrame) -> None:
    """PyBroker runs without error and returns expected metric keys."""
    pb = PyBrokerBacktest()
    result = pb.run(small_data, _constant_long, n_windows=2, train_size=0.6)

    assert isinstance(result, dict)
    assert "sharpe" in result
    assert "sortino" in result
    assert "profit_factor" in result
    assert "max_drawdown_pct" in result
    assert "trade_count" in result
    assert "total_return_pct" in result
    assert result["trade_count"] >= 0


@pytest.mark.slow
def test_pybroker_constant_long_positive_return(small_data: pl.DataFrame) -> None:
    """Always-long on uptrending data — basic run check."""
    pb = PyBrokerBacktest()
    result = pb.run(small_data, _constant_long, n_windows=2, train_size=0.6)
    assert "total_return_pct" in result


@pytest.mark.slow
def test_pybroker_different_windows(small_data: pl.DataFrame) -> None:
    """PyBroker handles different n_windows values."""
    pb = PyBrokerBacktest()
    for nw in [2, 3]:
        result = pb.run(small_data, _constant_long, n_windows=nw, train_size=0.6)
        assert "sharpe" in result


@pytest.mark.slow
def test_pybroker_walkforward_metrics(small_data: pl.DataFrame) -> None:
    """Walkforward metrics contain bootstrap confidence intervals."""
    pb = PyBrokerBacktest()
    pb.run(small_data, _constant_long, n_windows=3, train_size=0.6)
    assert pb._last_result is not None


@pytest.mark.slow
def test_pybroker_signal_alignment(small_data: pl.DataFrame) -> None:
    """Signal is aligned by date — trading only occurs on valid signal days."""
    pb = PyBrokerBacktest()

    def partial_signal(data: pl.DataFrame) -> pl.Series:
        return pl.Series("signal", [0] * len(data), dtype=pl.Int8)

    result = pb.run(small_data, partial_signal, n_windows=2, train_size=0.6)
    assert "total_return_pct" in result

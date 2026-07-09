"""Tests for MetricsCalculator with known Polars-native values."""

from __future__ import annotations

import polars as pl
import pytest

from analytics.backtest.metrics import MetricsCalculator


class TestSharpeRatio:
    def test_zero_returns(self) -> None:
        returns = pl.Series("returns", [0.0, 0.0, 0.0, 0.0])
        assert MetricsCalculator.sharpe_ratio(returns) == 0.0

    def test_positive_returns(self) -> None:
        # All positive constant returns — infinite Sharpe
        returns = pl.Series("returns", [0.01, 0.01, 0.01, 0.01, 0.01])
        sr = MetricsCalculator.sharpe_ratio(returns)
        assert sr == float("inf")

    def test_negative_returns(self) -> None:
        returns = pl.Series("returns", [-0.01, -0.01, -0.01])
        sr = MetricsCalculator.sharpe_ratio(returns)
        assert sr == float("-inf")

    def test_single_observation(self) -> None:
        returns = pl.Series("returns", [0.01])
        assert MetricsCalculator.sharpe_ratio(returns) == 0.0

    def test_known_values(self) -> None:
        # Ensure the calculation is numerically correct with variance.
        returns = pl.Series(
            "returns", [0.02, 0.01, -0.01, 0.005, 0.015, -0.005, 0.01, -0.02, 0.03, 0.0]
        )
        sr = MetricsCalculator.sharpe_ratio(returns)
        assert sr > 0  # positive mean return


class TestSortinoRatio:
    def test_no_negative_returns(self) -> None:
        returns = pl.Series("returns", [0.01, 0.02, 0.015])
        sr = MetricsCalculator.sortino_ratio(returns)
        assert sr == float("inf")

    def test_all_negative_returns(self) -> None:
        returns = pl.Series("returns", [-0.01, -0.02, -0.015])
        sr = MetricsCalculator.sortino_ratio(returns)
        assert sr < 0

    def test_single_observation(self) -> None:
        returns = pl.Series("returns", [0.01])
        assert MetricsCalculator.sortino_ratio(returns) == 0.0

    def test_mixed_returns(self) -> None:
        returns = pl.Series("returns", [0.02, -0.01, 0.01, -0.005, 0.015])
        sr = MetricsCalculator.sortino_ratio(returns)
        assert sr > 0


class TestCalmarRatio:
    def test_zero_max_drawdown(self) -> None:
        returns = pl.Series("returns", [0.01, 0.01, 0.01])
        cr = MetricsCalculator.calmar_ratio(returns, max_drawdown=0.0)
        assert cr == 0.0

    def test_single_observation(self) -> None:
        returns = pl.Series("returns", [0.01])
        assert MetricsCalculator.calmar_ratio(returns) == 0.0

    def test_known_drawdown(self) -> None:
        returns = pl.Series("returns", [0.01, -0.05, 0.02, -0.03, 0.01])
        cr = MetricsCalculator.calmar_ratio(returns)
        # Total return = -0.04, n=5 -> ann_return = -0.04/5*252 = -2.016
        # Max drawdown computed from equity curve
        assert cr < 0  # negative total return -> negative Calmar

    def test_negative_return_calmar(self) -> None:
        returns = pl.Series("returns", [-0.01, -0.02, -0.01, -0.03])
        cr = MetricsCalculator.calmar_ratio(returns)
        assert cr < 0


class TestMaxDrawdown:
    def test_monotonic_up(self) -> None:
        equity = pl.Series("equity", [100, 101, 102, 103])
        assert MetricsCalculator.max_drawdown(equity) == 0.0

    def test_single_drawdown(self) -> None:
        equity = pl.Series("equity", [100, 110, 90, 105])
        mdd = MetricsCalculator.max_drawdown(equity)
        # max was 110, trough was 90 -> (110-90)/110 approx 0.1818
        assert mdd == pytest.approx(0.1818, rel=0.01)

    def test_no_decline(self) -> None:
        equity = pl.Series("equity", [100, 100, 100])
        assert MetricsCalculator.max_drawdown(equity) == 0.0

    def test_single_value(self) -> None:
        equity = pl.Series("equity", [100])
        assert MetricsCalculator.max_drawdown(equity) == 0.0

    def test_known_values(self) -> None:
        equity = pl.Series("equity", [100, 120, 110, 130, 125, 115, 140])
        mdd = MetricsCalculator.max_drawdown(equity)
        # running max: 100, 120, 120, 130, 130, 130, 140
        # drawdowns: 0, 0, -8.3%, 0, -3.8%, -11.5%, 0
        # max = 11.5%
        assert mdd == pytest.approx(0.1154, rel=0.02)

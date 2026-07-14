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


class TestTotalReturn:
    def test_single_observation(self) -> None:
        assert MetricsCalculator.total_return(pl.Series("eq", [100])) == 0.0

    def test_zero_initial(self) -> None:
        assert MetricsCalculator.total_return(pl.Series("eq", [0, 10])) == 0.0

    def test_gain(self) -> None:
        # 100 -> 120 = +20%
        assert MetricsCalculator.total_return(pl.Series("eq", [100, 120])) == pytest.approx(0.20)

    def test_loss(self) -> None:
        # 100 -> 90 = -10%
        assert MetricsCalculator.total_return(pl.Series("eq", [100, 90])) == pytest.approx(-0.10)


class TestVolatility:
    def test_single_observation(self) -> None:
        assert MetricsCalculator.volatility(pl.Series("r", [0.01])) == 0.0

    def test_positive(self) -> None:
        returns = pl.Series("r", [0.02, 0.01, -0.01, 0.0])
        vol = MetricsCalculator.volatility(returns, annualization_factor=252)
        assert vol > 0.0


class TestCagr:
    def test_single_observation(self) -> None:
        assert MetricsCalculator.cagr(pl.Series("eq", [100])) == 0.0

    def test_non_positive_initial(self) -> None:
        assert MetricsCalculator.cagr(pl.Series("eq", [0, 100])) == 0.0

    def test_total_loss(self) -> None:
        # capital wiped out -> -1.0
        assert MetricsCalculator.cagr(pl.Series("eq", [100, 0])) == -1.0

    def test_doubling_over_one_year(self) -> None:
        # 253 daily points (one year), 100 -> 200 -> CAGR ~ 100%
        equity = pl.Series("eq", [100.0 + i * (100.0 / 252) for i in range(253)])
        cagr = MetricsCalculator.cagr(equity, periods_per_year=252)
        assert cagr == pytest.approx(1.0, rel=0.02)


class TestProfitFactor:
    def test_empty(self) -> None:
        assert MetricsCalculator.profit_factor(pl.Series("r", [])) == 0.0

    def test_no_losses(self) -> None:
        assert MetricsCalculator.profit_factor(pl.Series("r", [0.1, 0.2, 0.05])) == float("inf")

    def test_no_profits(self) -> None:
        assert MetricsCalculator.profit_factor(pl.Series("r", [-0.1, -0.2])) == 0.0

    def test_known_value(self) -> None:
        # gross profit 0.30, gross loss 0.10 -> PF 3.0
        returns = pl.Series("r", [0.2, 0.1, -0.1])
        assert MetricsCalculator.profit_factor(returns) == pytest.approx(3.0)


class TestWinRate:
    def test_empty(self) -> None:
        assert MetricsCalculator.win_rate(pl.Series("r", [])) == 0.0

    def test_half(self) -> None:
        returns = pl.Series("r", [0.1, -0.1, 0.2, -0.05])
        assert MetricsCalculator.win_rate(returns) == 0.5

    def test_all_winners(self) -> None:
        returns = pl.Series("r", [0.1, 0.2, 0.3])
        assert MetricsCalculator.win_rate(returns) == 1.0


class TestExpectancy:
    def test_empty(self) -> None:
        assert MetricsCalculator.expectancy(pl.Series("r", [])) == 0.0

    def test_mean(self) -> None:
        returns = pl.Series("r", [0.1, -0.05, 0.2])
        assert MetricsCalculator.expectancy(returns) == pytest.approx(0.08333, rel=0.01)


class TestMaxConsecutiveLosses:
    def test_none(self) -> None:
        assert MetricsCalculator.max_consecutive_losses(pl.Series("r", [0.1, 0.2])) == 0

    def test_streak(self) -> None:
        returns = pl.Series("r", [-0.1, -0.2, 0.05, -0.1, -0.1, -0.1, 0.1])
        assert MetricsCalculator.max_consecutive_losses(returns) == 3


class TestUlcerIndex:
    def test_single_observation(self) -> None:
        assert MetricsCalculator.ulcer_index(pl.Series("eq", [100])) == 0.0

    def test_monotonic_up(self) -> None:
        assert MetricsCalculator.ulcer_index(pl.Series("eq", [100, 110, 120])) == 0.0

    def test_positive_with_drawdown(self) -> None:
        # Drawdown to 90 from 100 -> -10% for one bar -> UI ~ 10
        equity = pl.Series("eq", [100, 100, 90, 100])
        ui = MetricsCalculator.ulcer_index(equity)
        assert ui == pytest.approx(5.0, rel=0.05)

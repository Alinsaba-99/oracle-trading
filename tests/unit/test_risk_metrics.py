"""Tests for equity-curve risk metrics and bar-size annualisation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.backtest.engines.vectorized import _periods_per_year, _risk_metrics_from_equity


def _index(periods: int, freq: str, unit: str = "us") -> pd.DatetimeIndex:
    idx = pd.date_range("2020-01-01", periods=periods, freq=freq)
    # Polars hands the engine microsecond datetimes, so tests use that unit.
    return idx.as_unit(unit)


class TestPeriodsPerYear:
    def test_daily(self) -> None:
        assert _periods_per_year(_index(500, "1D")) == pytest.approx(252.0, rel=0.01)

    def test_hourly(self) -> None:
        assert _periods_per_year(_index(500, "1h")) == pytest.approx(252.0 * 24, rel=0.01)

    def test_four_hourly(self) -> None:
        assert _periods_per_year(_index(500, "4h")) == pytest.approx(252.0 * 6, rel=0.01)

    def test_microsecond_unit_matches_nanosecond_unit(self) -> None:
        """Bar spacing must not depend on the index's storage unit.

        Reading raw int64 values assumes nanoseconds; a microsecond index then
        looks 1000x faster and inflates annualised metrics ~31x.
        """
        us = _periods_per_year(_index(400, "1D", unit="us"))
        ns = _periods_per_year(_index(400, "1D", unit="ns"))
        assert us == pytest.approx(ns, rel=1e-9)

    def test_weekend_gaps_do_not_skew(self) -> None:
        # Median spacing ignores the 2-day weekend jump that a mean would absorb.
        idx = pd.date_range("2020-01-01", periods=300, freq="1B").as_unit("us")
        assert _periods_per_year(idx) == pytest.approx(252.0, rel=0.05)

    def test_non_datetime_index_falls_back(self) -> None:
        assert _periods_per_year(pd.RangeIndex(100)) == 252.0

    def test_too_short_falls_back(self) -> None:
        assert _periods_per_year(_index(2, "1D")) == 252.0


class TestRiskMetrics:
    def test_flat_equity_is_all_zero(self) -> None:
        equity = np.full(300, 100_000.0)
        sharpe, sortino, calmar, vol = _risk_metrics_from_equity(equity, 0.0)
        assert (sharpe, sortino, calmar, vol) == (0.0, 0.0, 0.0, 0.0)

    def test_steady_growth_has_positive_sharpe(self) -> None:
        equity = 100_000.0 * np.exp(np.arange(500) * 0.0004)
        sharpe, _sortino, _calmar, _vol = _risk_metrics_from_equity(equity, 5.0)
        assert sharpe > 0

    def test_decline_has_negative_sharpe(self) -> None:
        equity = 100_000.0 * np.exp(-np.arange(500) * 0.0004)
        sharpe, _sortino, _calmar, _vol = _risk_metrics_from_equity(equity, 20.0)
        assert sharpe < 0

    def test_known_sharpe_is_recovered(self) -> None:
        # Compare against the *realised* sample moments, not the population
        # parameters — sampling error in the mean is large relative to itself.
        rng = np.random.default_rng(11)
        returns = rng.normal(0.0005, 0.01, 4000)
        equity = 100_000.0 * np.exp(np.cumsum(returns))
        sharpe, _sortino, _calmar, _vol = _risk_metrics_from_equity(
            equity, 10.0, periods_per_year=252.0
        )
        realised = returns.mean() / returns.std(ddof=1) * np.sqrt(252.0)
        assert sharpe == pytest.approx(realised, rel=0.02)

    def test_annualisation_scales_with_bar_size(self) -> None:
        equity = 100_000.0 * np.exp(np.arange(1000) * 0.0002)
        daily, *_ = _risk_metrics_from_equity(equity, 5.0, periods_per_year=252.0)
        hourly, *_ = _risk_metrics_from_equity(equity, 5.0, periods_per_year=252.0 * 24)
        assert hourly == pytest.approx(daily * np.sqrt(24.0), rel=0.01)

    def test_realistic_sharpe_magnitude(self) -> None:
        """A low-CAGR equity curve must not produce a double-digit Sharpe.

        Guards the annualisation bug directly: the buggy version reported
        Sharpe above 5 for a 2%/yr strategy.
        """
        n = 252 * 20
        rng = np.random.default_rng(5)
        returns = rng.normal(0.00008, 0.006, n)
        equity = 100_000.0 * np.exp(np.cumsum(returns))
        sharpe, *_ = _risk_metrics_from_equity(equity, 30.0, periods_per_year=252.0)
        assert abs(sharpe) < 3.0, f"implausible Sharpe {sharpe}"

    def test_no_losing_bars_falls_back_to_sharpe(self) -> None:
        equity = 100_000.0 * np.exp(np.arange(300) * 0.001)
        sharpe, sortino, _calmar, _vol = _risk_metrics_from_equity(equity, 1.0)
        assert sortino == pytest.approx(sharpe)

    def test_zero_drawdown_gives_zero_calmar(self) -> None:
        equity = 100_000.0 * np.exp(np.arange(300) * 0.001)
        _sharpe, _sortino, calmar, _vol = _risk_metrics_from_equity(equity, 0.0)
        assert calmar == 0.0

    def test_short_series_returns_zeros(self) -> None:
        assert _risk_metrics_from_equity(np.array([1.0, 2.0]), 5.0) == (0.0, 0.0, 0.0, 0.0)

    def test_nan_and_nonpositive_are_filtered(self) -> None:
        equity = 100_000.0 * np.exp(np.arange(300) * 0.0003)
        equity[10] = np.nan
        equity[20] = -5.0
        metrics = _risk_metrics_from_equity(equity, 5.0)
        assert all(np.isfinite(m) for m in metrics)

    def test_all_outputs_always_finite(self) -> None:
        for equity in (
            np.full(50, 1e-12),
            np.concatenate([np.full(50, 100.0), np.full(50, 1e6)]),
            100_000.0 * np.exp(np.arange(400) * 0.05),
        ):
            metrics = _risk_metrics_from_equity(equity, 15.0)
            assert all(np.isfinite(m) for m in metrics), equity[:3]

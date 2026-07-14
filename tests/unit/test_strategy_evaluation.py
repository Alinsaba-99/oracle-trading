"""Tests for the Monte Carlo challenge evaluation harness."""

from __future__ import annotations

import polars as pl

from analytics.backtest.result import BacktestResult
from analytics.strategy.evaluation import (
    MonteCarloReport,
    evaluate_strategies,
    monte_carlo_pass_rate,
)
from analytics.strategy.signals import BbandReversion, EmaTrend
from policy.prop_firm import THE5ERS


def _result(equity: list[float]) -> BacktestResult:
    return BacktestResult(
        run_id="t",
        total_return=(equity[-1] - equity[0]) / equity[0],
        equity_curve=equity,
    )


UP = [100_000 * (1.005**i) for i in range(200)]  # +0.5%/day -> passes everywhere
DOWN = [100_000 * (0.99**i) for i in range(200)]  # -1%/day -> fails overall


class TestMonteCarloPassRate:
    def test_monotonic_up_passes_all_windows(self) -> None:
        report = monte_carlo_pass_rate(_result(UP), THE5ERS)
        assert report.total > 0
        assert report.pass_rate == 1.0
        assert report.failed_daily == 0 and report.failed_overall == 0

    def test_monotonic_down_fails_all_windows(self) -> None:
        report = monte_carlo_pass_rate(_result(DOWN), THE5ERS)
        assert report.total > 0
        assert report.pass_rate == 0.0
        assert report.failed_overall == report.total

    def test_too_short_curve_is_empty(self) -> None:
        report = monte_carlo_pass_rate(_result([100_000]), THE5ERS)
        assert report.total == 0
        assert report.pass_rate == 0.0

    def test_aggregate_properties(self) -> None:
        report = monte_carlo_pass_rate(_result(UP), THE5ERS)
        assert report.mean_max_drawdown >= 0.0
        assert report.median_days >= 0


class TestEvaluateStrategies:
    def test_ranked_by_pass_rate(self) -> None:
        up, down = _result(UP), _result(DOWN)

        def fake_bt(_data: pl.DataFrame, signal: object, _inst: str) -> BacktestResult:
            return up if isinstance(signal, EmaTrend) else down

        report = evaluate_strategies(
            data_by_inst={"EURUSD": pl.DataFrame({"close": [100.0]})},
            strategies={"ema": EmaTrend, "bband": BbandReversion},
            backtest_fn=fake_bt,
        )
        assert len(report.rows) == 2
        # EmaTrend (up curve) ranks first with ~100% pass.
        assert report.rows[0].strategy == "ema"
        assert report.rows[0].mc_pass_rate == 1.0
        assert report.rows[1].mc_pass_rate == 0.0

    def test_report_text(self) -> None:
        def fake_bt(_data: pl.DataFrame, _signal: object, _inst: str) -> BacktestResult:
            return _result(UP)

        report = evaluate_strategies(
            data_by_inst={"EURUSD": pl.DataFrame({"close": [100.0]})},
            strategies={"ema": EmaTrend},
            backtest_fn=fake_bt,
        )
        text = report.as_text()
        assert "Monte Carlo" in text
        assert "ema" in text
        assert "pass=" in text


class TestMonteCarloReport:
    def test_empty_report_rates(self) -> None:
        r = MonteCarloReport()
        assert r.pass_rate == 0.0
        assert r.mean_max_drawdown == 0.0
        assert r.median_days == 0

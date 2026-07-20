"""Tests for analytics.strategy.mc_intraday (R3.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from analytics.backtest.result import BacktestResult
from analytics.strategy.mc_intraday import IntradayMCReport, monte_carlo_intraday_pass_rate
from policy.prop_firm import THE5ERS


def _result(equity: list[float]) -> BacktestResult:
    return BacktestResult(
        run_id="t",
        strategy_name="t",
        instrument="GOLD",
        initial_capital=Decimal("100000"),
        final_equity=equity[-1] if equity else 100000.0,
        equity_curve=equity,
    )


def _hourly_ts(n: int, start: datetime | None = None) -> list[datetime]:
    base = start or datetime(2026, 1, 1, tzinfo=UTC)
    return [base + timedelta(hours=i) for i in range(n)]


class TestValidation:
    def test_length_mismatch_raises(self) -> None:
        result = _result([100000.0, 100100.0, 100200.0])
        ts = _hourly_ts(2)  # wrong length
        with pytest.raises(ValueError, match="length mismatch"):
            monte_carlo_intraday_pass_rate(result, ts, THE5ERS)

    def test_short_curve_returns_empty_report(self) -> None:
        """Window larger than the curve → no windows → empty report."""
        result = _result([100000.0 + i * 10 for i in range(50)])
        ts = _hourly_ts(50)
        report = monte_carlo_intraday_pass_rate(result, ts, THE5ERS, window=130, stride=5)
        assert report.total == 0
        assert report.pass_rate == 0.0


class TestFlatCurve:
    def test_flat_curve_never_passes_nor_fails(self) -> None:
        """A perfectly flat equity curve = IN_PROGRESS in every window."""
        n = 200
        result = _result([100000.0] * n)
        ts = _hourly_ts(n)
        report = monte_carlo_intraday_pass_rate(result, ts, THE5ERS, window=130, stride=10)
        assert report.total > 0
        assert report.passed == 0
        assert report.failed_daily == 0
        assert report.failed_overall == 0
        assert report.in_progress == report.total


class TestIntradayBreach:
    def test_intraday_dip_detected_close_to_close_would_miss(self) -> None:
        """A curve that dips >3% intraday but recovers by close must fail.

        With close-to-close accounting, the day ends flat → no breach.
        With intraday accounting, the dip is caught.
        """
        # Build hourly equity: day 1 flat at 100k, day 2 dips to 96.5k at
        # hour 8 then recovers to 100k by hour 23.
        equity = [100000.0] * 24 + [100000.0] * 4 + [96500.0] + [100000.0] * 19
        # Pad to reach the 130-bar window.
        equity = equity + [100000.0] * (200 - len(equity))
        ts = _hourly_ts(len(equity))
        result = _result(equity)
        report = monte_carlo_intraday_pass_rate(result, ts, THE5ERS, window=130, stride=50)
        assert report.total > 0
        # At least one window saw the intraday dip → daily-loss failure.
        assert report.failed_daily >= 1


class TestPassingCurve:
    def test_strong_uptrend_passes(self) -> None:
        """A curve that gains >10% within the window hits the profit target
        and passes (with monotonic up moves, every day is profitable, so
        min_profitable_days is satisfied quickly).
        """
        n = 200
        # Strong ramp: +30% over the window → every window crosses 10%.
        equity = [100000.0 + i * (30000.0 / n) for i in range(n)]
        ts = _hourly_ts(n)
        result = _result(equity)
        report = monte_carlo_intraday_pass_rate(result, ts, THE5ERS, window=130, stride=50)
        assert report.total > 0
        # Never a daily/overall breach in a monotonic uptrend.
        assert report.failed_daily == 0
        assert report.failed_overall == 0
        # Strong ramp: every window passes.
        assert report.pass_rate == pytest.approx(1.0)


class TestReportAggregation:
    def test_rates_sum_to_one(self) -> None:
        n = 200
        equity = [100000.0] * n
        ts = _hourly_ts(n)
        result = _result(equity)
        report = monte_carlo_intraday_pass_rate(result, ts, THE5ERS, window=130, stride=10)
        total_rate = (
            report.pass_rate
            + report.failed_daily_rate
            + report.failed_overall_rate
            + (report.in_progress / report.total)
        )
        assert total_rate == pytest.approx(1.0)

    def test_report_fields(self) -> None:
        report = IntradayMCReport(
            total=10,
            passed=6,
            failed_daily=2,
            failed_overall=1,
            in_progress=1,
            max_drawdowns=[0.05] * 10,
            days_elapsed=[30] * 10,
        )
        assert report.pass_rate == pytest.approx(0.6)
        assert report.failed_daily_rate == pytest.approx(0.2)
        assert report.failed_overall_rate == pytest.approx(0.1)
        assert report.mean_max_drawdown == pytest.approx(0.05)
        assert report.median_days == 30

"""Tests for analytics.strategy.fitness (R3.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from analytics.backtest.result import BacktestResult
from analytics.strategy.fitness import EvalMode, fitness


def _result(
    equity: list[float],
    *,
    sharpe: float = 1.0,
    sortino: float = 1.2,
    cagr: float = 0.10,
    max_dd: float = 0.05,
    total_trades: int = 10,
    total_return: float = 0.10,
) -> BacktestResult:
    return BacktestResult(
        run_id="t",
        strategy_name="t",
        instrument="GOLD",
        initial_capital=Decimal("100000"),
        final_equity=equity[-1] if equity else 100000.0,
        equity_curve=equity,
        total_return=total_return,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        cagr=cagr,
        max_drawdown=max_dd,
        total_trades=total_trades,
    )


def _hourly_ts(n: int) -> list[datetime]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [base + timedelta(hours=i) for i in range(n)]


class TestFreeMode:
    def test_free_fitness_uses_composite(self) -> None:
        result = _result(
            [100000.0, 105000.0, 110000.0], sharpe=1.5, sortino=1.8, cagr=0.12, max_dd=0.05
        )
        report = fitness(result, EvalMode.FREE)
        assert report.mode == EvalMode.FREE
        # Composite combines sharpe+sortino+cagr with dd penalty.
        assert report.fitness > 0
        assert report.free_composite == report.fitness

    def test_free_higher_sharpe_higher_fitness(self) -> None:
        low = _result([100000.0, 101000.0], sharpe=0.5, sortino=0.6, cagr=0.05)
        high = _result([100000.0, 101000.0], sharpe=2.0, sortino=2.4, cagr=0.05)
        assert fitness(high, "free").fitness > fitness(low, "free").fitness

    def test_free_dd_penalty(self) -> None:
        """Higher drawdown lowers fitness for same Sharpe."""
        smooth = _result([100000.0, 101000.0], sharpe=1.0, max_dd=0.01)
        choppy = _result([100000.0, 101000.0], sharpe=1.0, max_dd=0.20)
        assert fitness(smooth, "free").fitness > fitness(choppy, "free").fitness

    def test_free_no_trades_returns_zeroish(self) -> None:
        """A no-trade backtest has zero metrics; fitness should be near 0."""
        result = _result([100000.0] * 10, sharpe=0.0, sortino=0.0, cagr=0.0, total_trades=0)
        report = fitness(result, "free")
        assert abs(report.fitness) < 0.01


class TestFirmMode:
    def test_firm_uses_mc_pass_rate(self) -> None:
        # Strong uptrend → high pass rate.
        n = 200
        equity = [100000.0 + i * 150.0 for i in range(n)]
        result = _result(equity, sharpe=1.0)
        report = fitness(result, EvalMode.FIRM)
        assert report.mode == EvalMode.FIRM
        assert report.mc_total > 0
        assert 0.0 <= report.mc_pass_rate <= 1.0
        # fitness = pass_rate + small sharpe tiebreak.
        assert report.fitness == pytest.approx(report.mc_pass_rate + 1.0 * 0.01, abs=1e-6)

    def test_firm_intraday_mc_with_timestamps(self) -> None:
        n = 200
        equity = [100000.0 + i * 150.0 for i in range(n)]
        ts = _hourly_ts(n)
        result = _result(equity, sharpe=1.0)
        report = fitness(result, "firm", timestamps=ts)
        assert report.mc_total > 0

    def test_firm_daily_mc_without_timestamps(self) -> None:
        n = 200
        equity = [100000.0 + i * 150.0 for i in range(n)]
        result = _result(equity, sharpe=1.0)
        report = fitness(result, "firm")
        assert report.mc_total > 0

    def test_firm_sharpe_tiebreak(self) -> None:
        """Same MC pass-rate, different Sharpe → higher Sharpe wins."""
        n = 200
        equity = [100000.0 + i * 150.0 for i in range(n)]
        low_s = _result(equity, sharpe=0.5)
        high_s = _result(equity, sharpe=2.0)
        low_r = fitness(low_s, "firm")
        high_r = fitness(high_s, "firm")
        assert high_r.fitness > low_r.fitness

    def test_firm_populates_mc_fields(self) -> None:
        n = 200
        equity = [100000.0 + i * 150.0 for i in range(n)]
        result = _result(equity, sharpe=1.0)
        report = fitness(result, "firm")
        assert report.mc_total > 0
        assert report.mc_median_days >= 0
        assert 0.0 <= report.mc_failed_daily_rate <= 1.0
        assert 0.0 <= report.mc_failed_overall_rate <= 1.0
        assert report.mc_mean_maxdd >= 0.0


class TestModeValidation:
    def test_invalid_mode_raises(self) -> None:
        result = _result([100000.0, 101000.0])
        with pytest.raises(ValueError, match="not a valid"):
            fitness(result, "invalid")

    def test_accepts_str_and_enum(self) -> None:
        result = _result([100000.0, 101000.0])
        r1 = fitness(result, "firm")
        r2 = fitness(result, EvalMode.FIRM)
        assert r1.mode == r2.mode == EvalMode.FIRM


class TestReportFields:
    def test_common_metrics_propagated(self) -> None:
        result = _result(
            [100000.0, 105000.0],
            sharpe=1.5,
            sortino=1.7,
            cagr=0.12,
            max_dd=0.05,
            total_trades=42,
            total_return=0.05,
        )
        report = fitness(result, "free")
        assert report.sharpe == 1.5
        assert report.sortino == 1.7
        assert report.cagr == 0.12
        assert report.max_drawdown == 0.05
        assert report.total_trades == 42
        assert report.total_return == 0.05

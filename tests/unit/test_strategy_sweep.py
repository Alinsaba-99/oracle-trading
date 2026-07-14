"""Tests for the strategy sweep ranking logic (offline, stubbed backtest)."""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from analytics.backtest.result import BacktestResult
from analytics.strategy.signals import BbandReversion, EmaTrend
from analytics.strategy.sweep import run_sweep
from policy.prop_firm import THE5ERS


def _df(prices: list[float]) -> pl.DataFrame:
    today = date.today()
    return pl.DataFrame(
        {
            "timestamp": [today + timedelta(days=i) for i in range(len(prices))],
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": [0.0] * len(prices),
        }
    )


def _result(equity: list[float], sharpe: float = 1.0, dd: float = 0.05) -> BacktestResult:
    return BacktestResult(
        run_id="t",
        instrument="",
        total_return=(equity[-1] - equity[0]) / equity[0],
        sharpe_ratio=sharpe,
        max_drawdown=dd,
        profit_factor=1.5,
        total_trades=10,
        equity_curve=equity,
    )


def test_ranking_pass_first_then_return() -> None:
    passing = _result([100_000 * (1.005**i) for i in range(25)], sharpe=2.0, dd=0.02)  # -> PASS
    failing = _result([100_000, 95_000], sharpe=0.5, dd=0.07)  # -> FAILED_OVERALL

    def fake_bt(_data: pl.DataFrame, signal: object, _inst: str) -> BacktestResult:
        return passing if isinstance(signal, EmaTrend) else failing

    report = run_sweep(
        data_by_inst={"EURUSD": _df([100.0] * 30)},
        strategies={"ema": EmaTrend, "bband": BbandReversion},
        profile=THE5ERS,
        backtest_fn=fake_bt,
    )

    assert len(report.rows) == 2
    assert report.rows[0].passed is True  # EmaTrend (passing) ranked first
    assert report.rows[0].strategy == "ema"
    assert report.rows[1].passed is False
    assert report.pass_count == 1


def test_empty_instrument_skipped() -> None:
    report = run_sweep(
        data_by_inst={"EURUSD": pl.DataFrame()},
        strategies={"ema": EmaTrend},
        backtest_fn=lambda *_: _result([100_000, 101_000]),
    )
    assert report.rows == []


def test_report_text_contains_pass_banner() -> None:
    report = run_sweep(
        data_by_inst={"EURUSD": _df([100.0] * 30)},
        strategies={"ema": EmaTrend},
        backtest_fn=lambda *_: _result([100_000, 101_000]),
    )
    text = report.as_text()
    assert "Strategy sweep" in text
    assert "ema" in text

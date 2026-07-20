"""R3.5: end-to-end integration test for the unified evaluator.

Validates the full pipeline:

    spec → fetch_pair → build_signal → backtest (multi-TF) → fitness (FIRM/FREE)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import polars as pl
import pytest

from analytics.strategy.evaluator import evaluate_spec
from analytics.strategy.fitness import EvalMode, FitnessReport
from analytics.strategy.spec import StrategySpec


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
def registry() -> MagicMock:
    """Mock registry returning realistic-looking data for both TFs."""
    reg = MagicMock()

    def _get(_inst: str, tf: str, **_kwargs: object) -> pl.DataFrame:
        if tf == "1h":
            # 30 days of hourly uptrend (720 bars).
            return _trend_bars(
                datetime(2026, 1, 11, tzinfo=UTC), timedelta(hours=1), 720, base=110.0, slope=0.05
            )
        if tf == "1d":
            # 60 days of daily uptrend leading into the hourly window.
            return _trend_bars(
                datetime(2025, 11, 12, tzinfo=UTC), timedelta(days=1), 60, base=100.0, slope=0.3
            )
        raise ValueError(f"unexpected tf {tf}")

    reg.get_ohlcv.side_effect = _get
    return reg


class TestEndToEnd:
    def test_multi_tf_spec_firm_mode(self, registry: MagicMock) -> None:
        spec = StrategySpec(
            name="e2e_firm",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 15},
            timeframe="1h",
            filter_tf="1d",
            filter_entry="ema_trend",
            filter_entry_params={"fast": 5, "slow": 10},
            filter_mode="gate",
        )
        report = evaluate_spec(spec, registry, EvalMode.FIRM, mc_window=100, mc_stride=50)
        assert isinstance(report, FitnessReport)
        assert report.mode == EvalMode.FIRM
        assert 0.0 <= report.mc_pass_rate <= 1.0
        # Sanity on common fields.
        assert isinstance(report.total_return, float)
        assert isinstance(report.sharpe, float)

    def test_multi_tf_spec_free_mode(self, registry: MagicMock) -> None:
        spec = StrategySpec(
            name="e2e_free",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 15},
            timeframe="1h",
            filter_tf="1d",
            filter_entry="ema_trend",
            filter_entry_params={"fast": 5, "slow": 10},
            filter_mode="gate",
        )
        report = evaluate_spec(spec, registry, EvalMode.FREE)
        assert report.mode == EvalMode.FREE
        # FREE composite is finite (Sharpe/Sortino/CAGR blend).
        assert report.fitness == report.free_composite

    def test_single_tf_spec_both_modes(self, registry: MagicMock) -> None:
        spec = StrategySpec(
            name="e2e_single",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 15},
            timeframe="1h",
        )
        firm = evaluate_spec(spec, registry, EvalMode.FIRM, mc_window=100, mc_stride=50)
        free = evaluate_spec(spec, registry, EvalMode.FREE)
        assert firm.mode == EvalMode.FIRM
        assert free.mode == EvalMode.FREE

    def test_report_serializable(self, registry: MagicMock) -> None:
        """FitnessReport must be safely loggable (dataclass with plain fields)."""
        spec = StrategySpec(
            name="e2e_ser",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 15},
            timeframe="1h",
        )
        report = evaluate_spec(spec, registry, EvalMode.FIRM, mc_window=100, mc_stride=50)
        # Access every numeric field; all must be plain Python types.
        for f in (
            report.fitness,
            report.total_return,
            report.sharpe,
            report.sortino,
            report.cagr,
            report.max_drawdown,
            report.mc_pass_rate,
            report.mc_failed_daily_rate,
            report.mc_failed_overall_rate,
            report.mc_mean_maxdd,
        ):
            assert isinstance(f, float)
        assert isinstance(report.total_trades, int)
        assert isinstance(report.mc_total, int)
        assert isinstance(report.mc_median_days, int)

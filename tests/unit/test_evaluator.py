"""Tests for analytics.strategy.evaluator (R3.4)."""

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
    reg = MagicMock()

    def _get(_inst: str, tf: str, **_kwargs: object) -> pl.DataFrame:
        if tf == "1h":
            return _trend_bars(
                datetime(2026, 1, 11, tzinfo=UTC), timedelta(hours=1), 240, base=110.0, slope=0.05
            )
        if tf == "1d":
            return _trend_bars(
                datetime(2026, 1, 1, tzinfo=UTC), timedelta(days=1), 60, base=100.0, slope=0.5
            )
        raise ValueError(f"unexpected tf {tf}")

    reg.get_ohlcv.side_effect = _get
    return reg


class TestSingleTFSpec:
    def test_single_tf_firm(self, registry: MagicMock) -> None:
        spec = StrategySpec(
            name="gold_donchian",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 10},
            timeframe="1h",
        )
        report = evaluate_spec(spec, registry, EvalMode.FIRM)
        assert isinstance(report, FitnessReport)
        assert report.mode == EvalMode.FIRM
        assert report.mc_total >= 0  # MC may be 0 if curve too short

    def test_single_tf_free(self, registry: MagicMock) -> None:
        spec = StrategySpec(
            name="gold_donchian",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 10},
            timeframe="1h",
        )
        report = evaluate_spec(spec, registry, EvalMode.FREE)
        assert report.mode == EvalMode.FREE
        # FREE composite uses Sharpe/Sortino/CAGR (finite or 0).
        assert report.fitness is not None


class TestMultiTFSpec:
    def test_multi_tf_fetches_pair(self, registry: MagicMock) -> None:
        spec = StrategySpec(
            name="gold_donchian_ema_gate",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 10},
            timeframe="1h",
            filter_tf="1d",
            filter_entry="ema_trend",
            filter_entry_params={"fast": 3, "slow": 5},
        )
        report = evaluate_spec(spec, registry, EvalMode.FIRM)
        # Two get_ohlcv calls (1h + 1d).
        assert registry.get_ohlcv.call_count == 2
        tfs = {c.args[1] for c in registry.get_ohlcv.call_args_list}
        assert tfs == {"1h", "1d"}
        assert report.mode == EvalMode.FIRM

    def test_multi_tf_free_mode(self, registry: MagicMock) -> None:
        spec = StrategySpec(
            name="gold_donchian_ema_gate",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 10},
            timeframe="1h",
            filter_tf="1d",
            filter_entry="ema_trend",
            filter_entry_params={"fast": 3, "slow": 5},
        )
        report = evaluate_spec(spec, registry, EvalMode.FREE)
        assert report.mode == EvalMode.FREE


class TestEdgeCases:
    def test_empty_data_returns_zero_fitness(self) -> None:
        registry = MagicMock()
        registry.get_ohlcv.return_value = pl.DataFrame(
            schema={
                "timestamp": pl.Datetime(time_unit="us"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
            }
        )
        spec = StrategySpec(
            name="empty", instrument="GOLD", entry="donchian_breakout", timeframe="1h"
        )
        report = evaluate_spec(spec, registry, EvalMode.FIRM)
        assert report.fitness == 0.0

    def test_intraday_timestamps_included_for_sub_daily(self, registry: MagicMock) -> None:
        """1h TF should trigger the intraday MC path."""
        spec = StrategySpec(
            name="gold_intraday",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 10},
            timeframe="1h",
        )
        # Just verify no exception + valid report shape.
        report = evaluate_spec(spec, registry, EvalMode.FIRM, mc_window=50, mc_stride=25)
        assert report.mode == EvalMode.FIRM

    def test_daily_spec_uses_daily_mc(self, registry: MagicMock) -> None:
        """1d TF → no timestamps → daily-bar MC."""
        spec = StrategySpec(
            name="gold_daily",
            instrument="GOLD",
            entry="donchian_breakout",
            entry_params={"period": 10},
            timeframe="1d",
        )
        report = evaluate_spec(spec, registry, EvalMode.FIRM, mc_window=30, mc_stride=10)
        assert report.mode == EvalMode.FIRM

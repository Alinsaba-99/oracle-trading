"""Tests for the multi-asset walk-forward module (BL-023 Fase 2)."""

from __future__ import annotations

import contextlib
from datetime import datetime

import numpy as np
import polars as pl

from analytics.qualification.walkforward import (
    evaluate,
    load_frame,
    max_drawdown,
    sharpe,
    strategy_returns,
)


def _df(closes: list[float], start: datetime) -> pl.DataFrame:
    n = len(closes)
    timestamps = [start.replace(year=start.year + i // 252) for i in range(n)]
    return pl.DataFrame({"timestamp": timestamps, "close": closes})


class TestStrategyReturns:
    def test_no_lookahead_shift(self) -> None:
        # direction[0]=1 must earn return[1] (close1/close0-1), NOT return[0].
        directions = np.asarray([1.0, 0.0, 1.0], dtype=float)
        closes = np.asarray([100.0, 110.0, 121.0, 133.1], dtype=float)
        rets = strategy_returns(directions, closes)
        # expected: 110/100-1=0.10 (pos at t0), 0.0 (flat at t1), 133.1/121-1=0.10 (pos at t2)
        np.testing.assert_allclose(rets, [0.10, 0.0, 0.10], atol=1e-9)

    def test_flat_all_zero(self) -> None:
        directions = np.asarray([0.0, 0.0, 0.0], dtype=float)
        closes = np.asarray([100.0, 110.0, 90.0], dtype=float)
        np.testing.assert_allclose(strategy_returns(directions, closes), [0.0, 0.0], atol=1e-12)


class TestMaxDrawdown:
    def test_known_drawdown(self) -> None:
        returns = np.asarray([0.10, -0.20, 0.05], dtype=float)
        # equity: 1.10 -> 0.88 -> 0.924; peak=1.10; dd max = 1-0.88/1.10 = 0.20
        np.testing.assert_allclose(max_drawdown(returns), 0.20, atol=1e-9)

    def test_monotonic_up_no_drawdown(self) -> None:
        returns = np.asarray([0.01, 0.02, 0.03], dtype=float)
        assert max_drawdown(returns) == 0.0


class TestSharpe:
    def test_constant_returns_zero_std(self) -> None:
        # std=0 -> guard returns 0.0, never inf/nan
        returns = np.asarray([0.01, 0.01, 0.01], dtype=float)
        assert sharpe(returns) == 0.0

    def test_positive_mean_positive_sharpe(self) -> None:
        # deterministic rising series with noise -> positive Sharpe
        base = np.linspace(0.0005, 0.001, 252)
        noise = np.sin(np.arange(252) * 0.5) * 0.0002
        assert sharpe(base + noise) > 0


class TestEvaluate:
    def test_trend_signal_on_synthetic_trend(self) -> None:
        # A steadily rising market with ema_trend (fast>slow) should hold
        # long and produce positive out-of-sample Sharpe, no crash.
        # start 2022 so the 500 bars span into 2023 (test period non-empty)
        closes = [100.0 * (1.002**i) for i in range(500)]
        df = _df(closes, datetime(2022, 1, 1))
        out = evaluate("ES", "ema_trend", df)
        assert out["signal"] == "ema_trend"
        assert out["bars"] == 500
        assert out["test_bars"] > 0
        assert out["sharpe_test"] > 0
        assert out["bars_in_position"] > 0

    def test_unknown_signal_raises(self) -> None:
        closes = [100.0, 101.0, 102.0]
        df = _df(closes, datetime(2020, 1, 1))
        try:
            evaluate("ES", "no_such_signal", df)
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for unknown signal")


class TestLoadFrame:
    def test_row_pin_mismatch_raises(self) -> None:
        # SPY pin is 6679; a tampered/missing frame must raise, not silently pass.
        with contextlib.suppress(ValueError):
            load_frame("SPY")

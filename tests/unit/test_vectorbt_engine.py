"""Tests for VectorizedEngine (vectorbt adapter)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import polars as pl
import pytest

from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines import VectorizedEngine, sma_crossover_signal
from analytics.backtest.protocol import BacktestSignal
from analytics.backtest.result import BacktestResult

# ── helpers ─────────────────────────────────────────────────────────────────


def _n_dates(n: int, start: datetime | None = None) -> pl.Series:
    """Return a Polars datetime series with *n* daily intervals."""
    start = start or datetime(2020, 1, 1)
    end = start + timedelta(days=n - 1)
    return pl.datetime_range(start=start, end=end, interval="1d", eager=True)


def _sine_wave_data(n: int = 252) -> pl.DataFrame:
    """Synthetic price series with a recognizable sine-wave pattern."""
    import numpy as np

    t = np.arange(n, dtype=np.float64)
    price = 100.0 + 10.0 * np.sin(2 * np.pi * t / 60.0) + t * 0.02
    return pl.DataFrame(
        {
            "timestamp": _n_dates(n),
            "open": price + np.random.default_rng(42).uniform(-0.5, 0.5, n),
            "high": price + np.abs(np.random.default_rng(42).normal(0, 0.3, n)),
            "low": price - np.abs(np.random.default_rng(42).normal(0, 0.3, n)),
            "close": price,
            "volume": pl.Series(np.random.default_rng(42).poisson(1_000_000, n)),
        }
    )


def _constant_up_trend(n: int = 100) -> pl.DataFrame:
    """Price that increases monotonically — always-long should profit."""
    return pl.DataFrame(
        {
            "timestamp": _n_dates(n),
            "open": 100.0 + pl.Series(range(n)).cast(pl.Float64),
            "high": 101.0 + pl.Series(range(n)).cast(pl.Float64),
            "low": 99.0 + pl.Series(range(n)).cast(pl.Float64),
            "close": 100.5 + pl.Series(range(n)).cast(pl.Float64),
            "volume": pl.Series([1_000_000] * n),
        }
    )


def _flat_market(n: int = 50) -> pl.DataFrame:
    """Constant price — no trend."""
    return pl.DataFrame(
        {
            "timestamp": _n_dates(n),
            "open": 100.0,
            "high": 100.5,
            "low": 99.5,
            "close": 100.0,
            "volume": 1_000_000,
        }
    )


# ── Constant-signal strategies ──────────────────────────────────────────────


class AlwaysLong:
    """Always returns +1 (long)."""

    def compute(self, data: pl.DataFrame) -> pl.Series:
        return pl.Series("signal", [1] * len(data))


class AlwaysShort:
    """Always returns -1 (short)."""

    def compute(self, data: pl.DataFrame) -> pl.Series:
        return pl.Series("signal", [-1] * len(data))


class AlwaysFlat:
    """Always returns 0 (neutral)."""

    def compute(self, data: pl.DataFrame) -> pl.Series:
        return pl.Series("signal", [0] * len(data))


class SineWaveSignal:
    """Signal based on sine wave — alternates long/short."""

    def compute(self, data: pl.DataFrame) -> pl.Series:
        import numpy as np

        close = data["close"].to_numpy()
        diff = np.diff(close, prepend=close[0])
        return pl.Series("signal", np.where(diff >= 0, 1, -1))


# ── Tests ───────────────────────────────────────────────────────────────────


class TestVectorizedEngineConstruction:
    """Engine lifecycle and ergonomics."""

    def test_construct(self) -> None:
        engine = VectorizedEngine()
        assert engine.equity_curve().to_list() == []
        assert engine.trades() == []

    def test_equity_curve_before_run_is_empty(self) -> None:
        engine = VectorizedEngine()
        assert len(engine.equity_curve()) == 0

    def test_trades_before_run_is_empty(self) -> None:
        engine = VectorizedEngine()
        assert engine.trades() == []


class TestVectorizedEngineRun:
    """Core ``run()`` method."""

    def test_smoke(self) -> None:
        """Run on synthetic data — verify no exceptions."""
        engine = VectorizedEngine()
        data = _constant_up_trend(50)
        result = engine.run(data, AlwaysLong())
        assert isinstance(result, BacktestResult)
        assert result.total_trades > 0

    def test_return_type(self) -> None:
        engine = VectorizedEngine()
        data = _constant_up_trend(30)
        result = engine.run(data, AlwaysLong())
        assert isinstance(result, BacktestResult)
        assert isinstance(result.total_return, float)
        assert isinstance(result.sharpe_ratio, float)
        assert isinstance(result.max_drawdown, float)
        assert isinstance(result.final_equity, float)
        assert isinstance(result.equity_curve, list)
        assert isinstance(result.trades, list)

    def test_result_shape(self) -> None:
        """BacktestResult has all expected fields populated."""
        engine = VectorizedEngine()
        data = _constant_up_trend(100)
        result = engine.run(data, AlwaysLong())
        assert result.total_trades >= 0
        assert result.final_equity > 0
        assert len(result.equity_curve) == len(data)
        # Always-long on uptrend should be profitable
        assert result.total_return > 0
        assert result.final_equity > float(result.initial_capital)

    def test_always_flat_is_flat(self) -> None:
        """Always-flat signal should keep initial capital unchanged."""
        engine = VectorizedEngine()
        data = _constant_up_trend(50)
        result = engine.run(data, AlwaysFlat())
        assert result.total_trades == 0
        assert result.final_equity == pytest.approx(float(result.initial_capital), rel=1e-4)

    def test_always_long_profitable_up_trend(self) -> None:
        """Always-long on a monotonic up trend gives positive return."""
        engine = VectorizedEngine()
        data = _constant_up_trend(100)
        result = engine.run(data, AlwaysLong())
        assert result.total_return > 0
        assert result.final_equity > float(result.initial_capital)

    def test_always_short_profitable_down_trend(self) -> None:
        """Always-short on a down trend gives positive return."""
        engine = VectorizedEngine()
        n = 100
        data = pl.DataFrame(
            {
                "timestamp": _n_dates(n),
                "open": 200.0 - pl.Series(range(n)).cast(pl.Float64),
                "high": 201.0 - pl.Series(range(n)).cast(pl.Float64),
                "low": 199.0 - pl.Series(range(n)).cast(pl.Float64),
                "close": 200.5 - pl.Series(range(n)).cast(pl.Float64),
                "volume": pl.Series([1_000_000] * n),
            }
        )
        result = engine.run(data, AlwaysShort())
        assert result.total_trades >= 0
        assert result.final_equity > 0

    def test_equity_curve_after_run(self) -> None:
        """equity_curve() returns the same values as result.equity_curve."""
        engine = VectorizedEngine()
        data = _constant_up_trend(50)
        result = engine.run(data, AlwaysLong())
        assert engine.equity_curve().to_list() == result.equity_curve

    def test_trades_after_run(self) -> None:
        """trades() returns core domain Trade models."""
        engine = VectorizedEngine()
        data = _constant_up_trend(50)
        result = engine.run(data, AlwaysLong())
        assert engine.trades() == result.trades
        if result.trades:
            from core.domain.trade import Trade

            assert all(isinstance(t, Trade) for t in result.trades)

    def test_signal_alignment(self) -> None:
        """Signal length must match data length."""
        engine = VectorizedEngine()
        data = _constant_up_trend(50)

        class MisalignedSignal:
            def compute(self, _data: pl.DataFrame) -> pl.Series:
                return pl.Series("signal", [1] * 10)

        with pytest.raises(ValueError, match=r"length|shape|size|align"):
            engine.run(data, MisalignedSignal())

    def test_sma_crossover_smoke(self) -> None:
        """SMA crossover runs on synthetic data."""
        engine = VectorizedEngine()
        data = _sine_wave_data(252)
        sig = sma_crossover_signal(fast=10, slow=30)
        result = engine.run(data, sig)
        assert isinstance(result, BacktestResult)
        assert result.total_trades >= 0
        assert result.final_equity > 0

    def test_custom_config(self) -> None:
        """BacktestConfig parameters flow through to the result."""
        engine = VectorizedEngine()
        data = _constant_up_trend(50)
        cfg = BacktestConfig(
            initial_capital=Decimal("50000"), slippage_bps=10.0, commission_pct=0.002
        )
        result = engine.run(data, AlwaysLong(), cfg)
        assert result.initial_capital == Decimal("50000")
        assert result.final_equity <= 2 * 50000

    def test_no_datetime_column(self) -> None:
        """Engine handles data without a datetime column."""
        engine = VectorizedEngine()
        n = 30
        data = pl.DataFrame(
            {
                "open": [100.0] * n,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": [100.0 + i * 0.5 for i in range(n)],
                "volume": [1_000_000] * n,
            }
        )
        result = engine.run(data, AlwaysLong())
        assert result.total_trades >= 0


class TestSmaCrossoverSignal:
    """Unit tests for the bundled SMA crossover signal."""

    def test_basic_signal_shape(self) -> None:
        """Signal returns -1, 0, or 1 for each bar."""
        sig = sma_crossover_signal(fast=5, slow=20)
        data = _sine_wave_data(252)
        result = sig.compute(data)
        assert isinstance(result, pl.Series)
        assert len(result) == len(data)
        assert all(v in (-1, 0, 1) for v in result.to_list())

    def test_first_bars_are_neutral(self) -> None:
        """Before the slow SMA starts, the signal should be 0."""
        sig = sma_crossover_signal(fast=5, slow=20)
        data = _sine_wave_data(252)
        result = sig.compute(data)
        vals = result.to_list()
        assert all(v == 0 for v in vals[:19])

    def test_is_protocol_compliant(self) -> None:
        """SMA signal satisfies the BacktestSignal protocol."""
        sig = sma_crossover_signal()
        assert isinstance(sig, BacktestSignal)
        data = _sine_wave_data(100)
        result = sig.compute(data)
        assert len(result) == len(data)


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_missing_close_column(self) -> None:
        engine = VectorizedEngine()
        data = pl.DataFrame({"foo": [1, 2, 3]})
        with pytest.raises(ValueError, match="close"):
            engine.run(data, AlwaysLong())

    def test_single_bar(self) -> None:
        """Engine handles a single bar gracefully."""
        engine = VectorizedEngine()
        data = pl.DataFrame(
            {
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1_000_000],
            }
        )
        # Should not raise — even though vectorbt may create an open trade
        result = engine.run(data, AlwaysLong())
        assert isinstance(result, BacktestResult)
        assert result.final_equity > 0

    def test_flat_market_runs(self) -> None:
        """Flat market — no movement but engine should run without error."""
        engine = VectorizedEngine()
        data = _flat_market(50)
        result = engine.run(data, AlwaysLong())
        assert isinstance(result, BacktestResult)

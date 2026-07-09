"""Tests for BacktestSignal protocol."""

from __future__ import annotations

import polars as pl
import pytest

from analytics.backtest.protocol import BacktestSignal


class TestBacktestSignalProtocol:
    """Verify that a concrete implementation satisfies the protocol."""

    def test_protocol_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            BacktestSignal()  # type: ignore[abstract]

    def test_concrete_implementation(self) -> None:
        class MovingAverageCross(BacktestSignal):
            def compute(self, data: pl.DataFrame) -> pl.Series:
                _ = data  # signal is static for this test
                return pl.Series("signal", [1, 0, -1, 1, 0])

        sig = MovingAverageCross()
        df = pl.DataFrame({"close": [100, 101, 102, 99, 98]})
        result = sig.compute(df)
        assert isinstance(result, pl.Series)
        assert result.dtype == pl.Int64
        assert result.to_list() == [1, 0, -1, 1, 0]
        assert all(v in (-1, 0, 1) for v in result.to_list())

    def test_signal_values_are_valid(self) -> None:
        class ConstantLong(BacktestSignal):
            def compute(self, data: pl.DataFrame) -> pl.Series:
                return pl.Series("signal", [1] * len(data))

        sig = ConstantLong()
        df = pl.DataFrame({"close": [100, 101, 102]})
        result = sig.compute(df)
        assert all(v == 1 for v in result.to_list())

    def test_signal_aligned_with_input(self) -> None:
        class ThresholdSignal(BacktestSignal):
            def compute(self, data: pl.DataFrame) -> pl.Series:
                close = data["close"]
                mean = close.mean()
                return pl.Series(
                    "signal", [1 if c > mean else -1 if c < mean else 0 for c in close]
                )

        sig = ThresholdSignal()
        df = pl.DataFrame({"close": [100, 102, 98, 101, 99]})
        result = sig.compute(df)
        assert len(result) == len(df)

    def test_protocol_type_checking(self) -> None:
        """Verify that isinstance checks work with Protocol."""

        class DummySignal:
            def compute(self, data: pl.DataFrame) -> pl.Series:
                return pl.Series("signal", [0] * len(data))

        assert isinstance(DummySignal(), BacktestSignal)

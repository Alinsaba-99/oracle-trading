"""Tests for technical indicators — TA-Lib vs Polars-native."""

from collections.abc import Sequence

import polars as pl

from analytics.technical.polars_indicators import atr, bbands, ema, macd, rsi, sma
from analytics.technical.ta_lib_wrapper import sma as ta_sma


def _series(name: str, values: Sequence[float]) -> pl.Series:
    return pl.Series(name, [float(v) for v in values])


def _allclose(a: Sequence[float | None], b: Sequence[float | None]) -> bool:
    for x, y in zip(a, b, strict=False):
        if (x is None) != (y is None):
            return False
        if x is not None and y is not None and abs(x - y) > 0.001:
            return False
    return True


class TestSMA:
    def test_known_values(self) -> None:
        close = _series("close", [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
        result = sma(close, period=3)
        assert result[0:2].to_list() == [None, None]
        assert abs(result[3] - 12.0) < 0.001

    def test_ta_lib_match(self) -> None:
        close = _series("close", range(1, 31))
        pl_result = sma(close, period=5)
        ta_result = ta_sma(close, period=5)
        assert _allclose(pl_result.to_list(), ta_result.to_list())


class TestRSI:
    def test_known_values(self) -> None:
        close = _series("close", [45, 46, 47, 48, 49, 50, 49, 48, 47, 46, 45, 44, 43, 42, 41])
        result = rsi(close, period=14)
        assert result is not None


class TestBBands:
    def test_basic(self) -> None:
        close = _series("close", range(10, 31))
        upper, mid, lower = bbands(close, period=5, std=2.0)
        assert mid is not None
        assert upper is not None
        assert lower is not None
        valid = [
            (u, m)
            for u, m in zip(upper.to_list(), mid.to_list(), strict=False)
            if u is not None and m is not None
        ]
        if valid:
            assert valid[0][0] >= valid[0][1]


class TestATR:
    def test_basic(self) -> None:
        high = _series("high", [105, 106, 107, 108, 109, 110])
        low = _series("low", [95, 96, 97, 98, 99, 100])
        close = _series("close", [100, 102, 104, 106, 108, 110])
        result = atr(high, low, close, period=3)
        assert result is not None
        assert len(result) == 6


class TestMACD:
    def test_basic(self) -> None:
        close = _series("close", range(20, 51))
        m_line, s_line, hist = macd(close, fast=12, slow=26, signal=9)
        assert m_line is not None
        assert s_line is not None
        assert hist is not None


class TestShortInputRobustness:
    def test_indicators_fail_soft_on_short_input(self) -> None:
        # BL-023 Fase 5: replay calls signal.compute(prefix) bar-by-bar, so
        # indicators must never IndexError on prefixes shorter than their
        # warmup — they fail soft with aligned NaN (None in to_list()).
        close = _series("close", [100.0, 101.0, 102.0])
        for indicator, args in ((ema, (close, 14)), (rsi, (close, 14))):
            result = indicator(*args)
            assert result is not None
            assert len(result) == 3
            # Polars keeps NaN as float nan (not null) in to_list().
            assert all(value != value for value in result.to_list())
        high = _series("high", [101.0, 102.0, 103.0])
        low = _series("low", [99.0, 100.0, 101.0])
        result = atr(high, low, close, 14)
        assert result is not None
        assert len(result) == 3
        assert all(value != value for value in result.to_list())

    def test_rsi_reversion_compute_stays_flat_on_short_prefix(self) -> None:
        # Regression: RsiReversion.compute crashed with IndexError on the
        # first replay prefixes (< period+1 bars); it must stay flat.
        from analytics.strategy.signals import RsiReversion

        data = pl.DataFrame({"close": [100.0, 101.0, 102.0]})
        signal = RsiReversion(period=14).compute(data)
        assert signal.to_list() == [0, 0, 0]


class TestCandlestickPatterns:
    def test_doji(self) -> None:
        from analytics.technical.patterns import detect

        open_p = _series("open", [100.0, 100.0, 100.0])
        high_p = _series("high", [102.0, 102.0, 102.0])
        low_p = _series("low", [98.0, 99.0, 99.0])
        close_p = _series("close", [100.0, 101.0, 99.5])
        patterns = detect(open_p, high_p, low_p, close_p)
        assert isinstance(patterns, list)

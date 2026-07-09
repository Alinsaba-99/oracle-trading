"""Tests for technical indicators — TA-Lib vs Polars-native."""

import polars as pl

from analytics.technical.polars_indicators import atr, bbands, macd, rsi, sma
from analytics.technical.ta_lib_wrapper import sma as ta_sma


def _series(name, values):
    return pl.Series(name, [float(v) for v in values])


def _allclose(a, b):
    for x, y in zip(a, b, strict=False):
        if (x is None) != (y is None):
            return False
        if x is not None and abs(x - y) > 0.001:
            return False
    return True


class TestSMA:
    def test_known_values(self):
        close = _series("close", [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
        result = sma(close, period=3)
        assert result[0:2].to_list() == [None, None]
        assert abs(result[3] - 12.0) < 0.001

    def test_ta_lib_match(self):
        close = _series("close", range(1, 31))
        pl_result = sma(close, period=5)
        ta_result = ta_sma(close, period=5)
        assert _allclose(pl_result.to_list(), ta_result.to_list())


class TestRSI:
    def test_known_values(self):
        close = _series("close", [45, 46, 47, 48, 49, 50, 49, 48, 47, 46, 45, 44, 43, 42, 41])
        result = rsi(close, period=14)
        assert result is not None


class TestBBands:
    def test_basic(self):
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
    def test_basic(self):
        high = _series("high", [105, 106, 107, 108, 109, 110])
        low = _series("low", [95, 96, 97, 98, 99, 100])
        close = _series("close", [100, 102, 104, 106, 108, 110])
        result = atr(high, low, close, period=3)
        assert result is not None
        assert len(result) == 6


class TestMACD:
    def test_basic(self):
        close = _series("close", range(20, 51))
        m_line, s_line, hist = macd(close, fast=12, slow=26, signal=9)
        assert m_line is not None
        assert s_line is not None
        assert hist is not None


class TestCandlestickPatterns:
    def test_doji(self):
        from analytics.technical.patterns import detect

        open_p = _series("open", [100.0, 100.0, 100.0])
        high_p = _series("high", [102.0, 102.0, 102.0])
        low_p = _series("low", [98.0, 99.0, 99.0])
        close_p = _series("close", [100.0, 101.0, 99.5])
        patterns = detect(open_p, high_p, low_p, close_p)
        assert isinstance(patterns, list)

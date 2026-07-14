"""Tests for the prop-firm strategy signal library (offline, synthetic data)."""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from analytics.strategy.signals import (
    DEFAULT_STRATEGIES,
    BbandReversion,
    DonchianBreakout,
    EmaTrend,
    RsiReversion,
)


def _df(prices: list[float]) -> pl.DataFrame:
    today = date.today()
    return pl.DataFrame(
        {
            "timestamp": [today + timedelta(days=i) for i in range(len(prices))],
            "open": prices,
            "high": [p * 1.001 for p in prices],
            "low": [p * 0.999 for p in prices],
            "close": prices,
            "volume": [0.0] * len(prices),
        }
    )


def _assert_long_flat(sig: pl.Series, n: int) -> None:
    assert len(sig) == n
    assert set(sig.to_list()) <= {0, 1}


class TestEmaTrend:
    def test_long_in_uptrend(self) -> None:
        prices = [100 + i * 0.5 for i in range(120)]  # steady uptrend
        sig = EmaTrend(10, 30).compute(_df(prices))
        _assert_long_flat(sig, 120)
        assert sig[-1] == 1  # fast above slow in an uptrend

    def test_flat_when_data_too_short(self) -> None:
        sig = EmaTrend(10, 30).compute(_df([100, 101, 102]))
        _assert_long_flat(sig, 3)


class TestRsiReversion:
    def test_goes_long_on_oversold(self) -> None:
        prices = [100 - i * 1.0 for i in range(50)]  # sharp drop -> RSI plunges
        sig = RsiReversion(14, oversold=40.0).compute(_df(prices))
        _assert_long_flat(sig, 50)
        assert 1 in sig.to_list()  # at least one oversold long


class TestBbandReversion:
    def test_goes_long_below_lower_band(self) -> None:
        prices = [100.0] * 25 + [90.0, 88.0]  # sudden drop below band
        sig = BbandReversion(20, 2.0).compute(_df(prices))
        _assert_long_flat(sig, 27)
        assert 1 in sig.to_list()


class TestDonchianBreakout:
    def test_goes_long_on_breakout(self) -> None:
        prices = [100.0] * 25 + [105.0, 106.0]  # breakout above prior high
        sig = DonchianBreakout(20).compute(_df(prices))
        _assert_long_flat(sig, 27)
        assert 1 in sig.to_list()


class TestRegistry:
    def test_default_strategies_present(self) -> None:
        names = set(DEFAULT_STRATEGIES)
        expected = {
            "ema_trend_20_50",
            "rsi_reversion_14",
            "bband_reversion_20",
            "donchian_breakout_20",
        }
        assert expected <= names
        # Each entry constructs a working signal.
        for cls in DEFAULT_STRATEGIES.values():
            instance = cls()
            sig = instance.compute(_df([100 + i for i in range(60)]))
            assert isinstance(sig, pl.Series)

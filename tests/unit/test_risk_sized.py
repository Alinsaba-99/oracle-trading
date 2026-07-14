"""Tests for the volatility-scaled sizing helper (offline, synthetic)."""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from analytics.strategy.risk_sized import atr_percent_sizes


def _df(prices: list[float], amp: float = 0.01) -> pl.DataFrame:
    today = date.today()
    return pl.DataFrame(
        {
            "timestamp": [today + timedelta(days=i) for i in range(len(prices))],
            "open": prices,
            "high": [p * (1 + amp) for p in prices],
            "low": [p * (1 - amp) for p in prices],
            "close": prices,
            "volume": [0.0] * len(prices),
        }
    )


class TestAtrPercentSizes:
    def test_bounded_in_zero_to_max(self) -> None:
        sizes = atr_percent_sizes(_df([100 + i for i in range(40)]), max_pct=0.5)
        vals = sizes.to_list()
        assert all(0.0 <= v <= 0.5 for v in vals)

    def test_higher_volatility_smaller_size(self) -> None:
        calm = atr_percent_sizes(_df([100.0] * 40, amp=0.002), atr_period=14)[-1]
        wild = atr_percent_sizes(_df([100.0] * 40, amp=0.02), atr_period=14)[-1]
        # More volatile instrument -> smaller deployed fraction.
        assert wild < calm

    def test_zero_before_warmup(self) -> None:
        sizes = atr_percent_sizes(_df([100.0] * 40), atr_period=14)
        # ATR needs `period` bars; first values should be 0 (filled NaN).
        assert sizes.to_list()[0] == 0.0

    def test_respects_max_pct_cap(self) -> None:
        # Tiny volatility would imply a huge fraction -> capped at max_pct.
        sizes = atr_percent_sizes(_df([100.0] * 40, amp=0.0001), max_pct=0.25)
        assert max(sizes.to_list()) <= 0.25

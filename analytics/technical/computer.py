"""IndicatorComputer — computes indicators from market.bar events."""

from __future__ import annotations

import polars as pl

from analytics.common.errors import IndicatorError
from analytics.technical import atr, bbands, ema, macd, rsi, sma


def compute_all(
    close: pl.Series, high: pl.Series | None = None, low: pl.Series | None = None
) -> dict[str, list[float | None]]:
    results = {}
    try:
        results["sma_20"] = sma(close, period=20).to_list()
        results["ema_20"] = ema(close, period=20).to_list()
        results["rsi_14"] = rsi(close, period=14).to_list()

        if high is not None and low is not None:
            results["atr_14"] = atr(high, low, close, period=14).to_list()

        upper, mid, lower = bbands(close, period=20, std=2.0)
        results["bb_upper"] = upper.to_list()
        results["bb_middle"] = mid.to_list()
        results["bb_lower"] = lower.to_list()

        m_line, s_line, hist = macd(close, fast=12, slow=26, signal=9)
        results["macd_line"] = m_line.to_list()
        results["macd_signal"] = s_line.to_list()
        results["macd_hist"] = hist.to_list()

    except Exception as e:
        raise IndicatorError(f"Indicator computation failed: {e}") from e

    return results

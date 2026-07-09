"""Polars-native technical indicators.

Each indicator is implemented using native Polars expressions and
numpy operations behind a Polars Series interface. These serve as
a zero-dependency alternative to TA-Lib for the common hot indicators.
"""

from __future__ import annotations

import numpy as np
import polars as pl


def sma(close: pl.Series, period: int = 20) -> pl.Series:
    """Simple Moving Average via rolling mean."""
    return close.rolling_mean(window_size=period)


def ema(close: pl.Series, period: int = 20) -> pl.Series:
    """Exponential Moving Average (Wilder / TA-Lib compatible)."""
    arr = close.to_numpy().astype(np.float64, copy=True)
    out = np.full_like(arr, np.nan)
    alpha = 2.0 / (period + 1.0)

    # Seed with SMA of the first `period` elements
    out[period - 1] = np.nanmean(arr[:period])
    for i in range(period, len(arr)):
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]

    return pl.Series("ema", out)


def rsi(close: pl.Series, period: int = 14) -> pl.Series:
    """Relative Strength Index (Wilder smoothing, TA-Lib compatible).

    Uses Wilder's smoothed averaging: first average is SMA of the
    first ``period`` gains/losses, then:
        avg_i = (avg_{i-1} * (period - 1) + value_i) / period
    """
    arr = close.to_numpy().astype(np.float64, copy=False)
    deltas = np.diff(arr, prepend=np.nan)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.full_like(arr, np.nan)
    avg_loss = np.full_like(arr, np.nan)

    # First smoothed values: SMA of first `period` entries
    avg_gain[period] = np.mean(gains[1 : period + 1])
    avg_loss[period] = np.mean(losses[1 : period + 1])

    for i in range(period + 1, len(arr)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period

    rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.nan), where=avg_loss != 0)
    rsi_values = 100.0 - (100.0 / (1.0 + rs))
    return pl.Series("rsi", rsi_values)


def atr(high: pl.Series, low: pl.Series, close: pl.Series, period: int = 14) -> pl.Series:
    """Average True Range (Wilder smoothing, TA-Lib compatible).

    True Range = max(high - low, |high - prev_close|, |low - prev_close|).
    First ATR is SMA of first ``period`` TR values, then Wilder smoothing.
    """
    h = high.to_numpy().astype(np.float64, copy=False)
    low_arr = low.to_numpy().astype(np.float64, copy=False)
    c = close.to_numpy().astype(np.float64, copy=False)

    prev_c = np.roll(c, 1)
    prev_c[0] = np.nan

    tr = np.maximum(h - low_arr, np.maximum(np.abs(h - prev_c), np.abs(low_arr - prev_c)))
    out = np.full_like(tr, np.nan)

    # First ATR = SMA of first `period` TR values
    out[period - 1] = np.nanmean(tr[:period])
    for i in range(period, len(tr)):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period

    return pl.Series("atr", out)


def bbands(
    close: pl.Series, period: int = 20, std: float = 2.0
) -> tuple[pl.Series, pl.Series, pl.Series]:
    """Bollinger Bands — returns (upper, middle, lower).

    Uses population standard deviation (ddof=0) to match TA-Lib.
    """
    middle = close.rolling_mean(window_size=period)
    # Polars rolling_std defaults to ddof=1; use ddof=0 for population std
    rolling_std = close.rolling_std(window_size=period, ddof=0)
    upper = middle + (rolling_std * std)
    lower = middle - (rolling_std * std)
    return upper, middle, lower


def macd(
    close: pl.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pl.Series, pl.Series, pl.Series]:
    """MACD — returns (macd_line, signal_line, histogram).

    macd_line = EMA(fast) - EMA(slow)
    signal_line = EMA(macd_line, signal)
    histogram = macd_line - signal_line
    """
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

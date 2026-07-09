"""TA-Lib wrapper — technical indicators with Polars I/O.

Each function accepts Polars Series, delegates to the corresponding TA-Lib
function via 1-D numpy arrays, and returns Polars Series.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl

from analytics.common.converters import from_numpy


def _to_numpy_1d(series: pl.Series) -> np.ndarray:
    """Convert a Polars Series to a 1-D float64 numpy array for TA-Lib."""
    return series.to_numpy().astype(np.float64, copy=False)


def _talib_call(func: Any, *series: pl.Series, **kwargs: Any) -> pl.Series | tuple[pl.Series, ...]:
    """Convert Polars Series → numpy 1-D → call TA-Lib → Polars Series(es)."""
    np_args = [_to_numpy_1d(s) for s in series]
    result = func(*np_args, **kwargs)

    if isinstance(result, np.ndarray):
        return from_numpy(result)
    return tuple(from_numpy(r) for r in result)


def sma(close: pl.Series, period: int = 20) -> pl.Series:
    """Simple Moving Average."""
    import talib

    return _talib_call(talib.SMA, close, timeperiod=period)  # type: ignore[return-value]


def ema(close: pl.Series, period: int = 20) -> pl.Series:
    """Exponential Moving Average."""
    import talib

    return _talib_call(talib.EMA, close, timeperiod=period)  # type: ignore[return-value]


def rsi(close: pl.Series, period: int = 14) -> pl.Series:
    """Relative Strength Index."""
    import talib

    return _talib_call(talib.RSI, close, timeperiod=period)  # type: ignore[return-value]


def atr(high: pl.Series, low: pl.Series, close: pl.Series, period: int = 14) -> pl.Series:
    """Average True Range."""
    import talib

    return _talib_call(talib.ATR, high, low, close, timeperiod=period)  # type: ignore[return-value]


def bbands(
    close: pl.Series, period: int = 20, std: float = 2.0
) -> tuple[pl.Series, pl.Series, pl.Series]:
    """Bollinger Bands — returns (upper, middle, lower)."""
    import talib

    upper, middle, lower = _talib_call(
        talib.BBANDS, close, timeperiod=period, nbdevup=std, nbdevdn=std, matype=0
    )
    return upper, middle, lower


def macd(
    close: pl.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pl.Series, pl.Series, pl.Series]:
    """MACD — returns (macd_line, signal_line, histogram)."""
    import talib

    macd_line, signal_line, hist = _talib_call(
        talib.MACD, close, fastperiod=fast, slowperiod=slow, signalperiod=signal
    )
    return macd_line, signal_line, hist

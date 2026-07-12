"""Heikin Ashi candle conversion — smooths OHLCV for noise reduction.

Heikin Ashi ('average bar' in Japanese) modifies OHLCV to create smoother
candles that make trends and reversals more visible:

    HA_Close = (open + high + low + close) / 4
    HA_Open  = (prev_HA_Open + prev_HA_Close) / 2
    HA_High  = max(high, HA_Open, HA_Close)
    HA_Low   = min(low, HA_Open, HA_Close)

Reference: https://www.tradingview.com/support/solutions/43000501980-heikin-ashi/
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl


def to_heikin_ashi(data: pl.DataFrame) -> pl.DataFrame:
    """Convert OHLCV DataFrame to Heikin Ashi format.

    Expects columns: open, high, low, close, volume (plus any others).
    Returns a copy with open/high/low/close modified; volume stays unchanged.

    Args:
        data: OHLCV DataFrame.

    Returns:
        DataFrame with Heikin Ashi open, high, low, close.
    """
    import polars as pl

    n = len(data)
    if n == 0:
        return data

    close_arr = data["close"].to_numpy()
    open_arr = data["open"].to_numpy()
    high_arr = data["high"].to_numpy()
    low_arr = data["low"].to_numpy()

    # HA_Close = (O + H + L + C) / 4
    ha_close = (open_arr + high_arr + low_arr + close_arr) / 4.0

    # HA_Open[i] = (HA_Open[i-1] + HA_Close[i-1]) / 2
    # First HA_Open = (O + C) / 2
    ha_open = open_arr.copy()
    for i in range(n):
        if i == 0:
            ha_open[i] = (open_arr[i] + close_arr[i]) / 2.0
        else:
            ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0

    # HA_High = max(high, HA_Open, HA_Close)
    ha_high = np_maximum(high_arr, ha_open)
    ha_high = np_maximum(ha_high, ha_close)

    # HA_Low = min(low, HA_Open, HA_Close)
    ha_low = np_minimum(low_arr, ha_open)
    ha_low = np_minimum(ha_low, ha_close)

    return data.with_columns(
        [
            pl.Series("open", ha_open),
            pl.Series("high", ha_high),
            pl.Series("low", ha_low),
            pl.Series("close", ha_close),
        ]
    )


def np_maximum(a: np.ndarray, b: np.ndarray) -> np.ndarray:  # type: ignore[no-any-unimported]
    """Element-wise maximum, handling numpy import lazily."""
    import numpy as np

    return np.maximum(a, b)


def np_minimum(a: np.ndarray, b: np.ndarray) -> np.ndarray:  # type: ignore[no-any-unimported]
    """Element-wise minimum, handling numpy import lazily."""
    import numpy as np

    return np.minimum(a, b)

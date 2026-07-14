"""Extra technical indicators (R1) complementing polars_indicators.py.

ADX/DMI, rate-of-change, Donchian channels, stochastic oscillator. Inputs are
polars Series or 1-d array-likes; outputs are ``pl.Series`` aligned to input,
matching the convention in :mod:`analytics.technical.polars_indicators`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl


def _to_pd(s: pl.Series | np.ndarray | pd.Series) -> pd.Series:
    if isinstance(s, pl.Series):
        return pd.Series(s.to_numpy().astype(np.float64))
    return pd.Series(np.asarray(s, dtype=np.float64))


def roc(close: pl.Series, period: int = 12) -> pl.Series:
    """Rate of change as a fraction (pct_change over ``period``)."""
    return pl.Series("roc", _to_pd(close).pct_change(period).to_numpy())


def donchian_channels(close: pl.Series, period: int = 20) -> tuple[pl.Series, pl.Series]:
    """Prior-N high/low (shifted to avoid look-ahead). Returns (upper, lower)."""
    s = _to_pd(close)
    upper = s.rolling(period).max().shift(1)
    lower = s.rolling(period).min().shift(1)
    return pl.Series("don_up", upper.to_numpy()), pl.Series("don_lo", lower.to_numpy())


def stochastic(
    high: pl.Series, low: pl.Series, close: pl.Series, period: int = 14
) -> pl.Series:
    """Stochastic %K over ``period``."""
    h = _to_pd(high).rolling(period).max()
    l = _to_pd(low).rolling(period).min()
    c = _to_pd(close)
    k = 100.0 * (c - l) / (h - l).replace(0.0, np.nan)
    return pl.Series("stoch_k", k.to_numpy())


def _wilder_smooth(s: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing (seed = sum of first period; recurse)."""
    out = pd.Series(np.nan, index=s.index, dtype=float)
    filled = s.fillna(0.0).to_numpy()
    if len(filled) < period:
        return out
    out.iloc[period - 1] = filled[:period].sum()
    for i in range(period, len(filled)):
        out.iloc[i] = out.iloc[i - 1] - out.iloc[i - 1] / period + filled[i]
    return out


def adx(
    high: pl.Series, low: pl.Series, close: pl.Series, period: int = 14
) -> pl.Series:
    """Average Directional Index (Wilder). Higher = stronger trend."""
    h = _to_pd(high)
    l = _to_pd(low)
    c = _to_pd(close)
    up = h.diff()
    down = -l.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=h.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=h.index)
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_s = _wilder_smooth(tr, period)
    plus_di = 100.0 * _wilder_smooth(plus_dm, period) / atr_s.replace(0.0, np.nan)
    minus_di = 100.0 * _wilder_smooth(minus_dm, period) / atr_s.replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx_val = _wilder_smooth(dx.fillna(0.0), period)
    return pl.Series("adx", adx_val.to_numpy())

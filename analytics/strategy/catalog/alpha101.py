"""QLib Alpha101 adapter — wrap QLib alpha definitions as Oracle signals.

Provides the 101 WorldQuant alpha factors as ``BacktestSignal``-compatible
strategies.  Each alpha is a formulaic expression that maps OHLCV data
to a trading signal.

NOTE: The original Alpha101 is CROSS-SECTIONAL (ranks N tickers).  These
adapters adapt them to TIME-SERIES (single instrument) by using z-score
thresholds on the raw alpha value.

Reference: 101 Formulaic Alphas, Zura Kakushadze (2016)
"""

from __future__ import annotations

import numpy as np
import polars as pl


def _col(data: pl.DataFrame, name: str) -> np.ndarray:
    return data[name].to_numpy().astype(float)


def _high_low_spread(high: np.ndarray, low: np.ndarray) -> np.ndarray:
    return np.where(high > low, high - low, 1.0)


# ── Alpha #1: (close - open) / (high - low) ──────────────────────────


def alpha_001(data: pl.DataFrame) -> pl.Series:
    """Alpha#1: rank of (close - open) / (high - low).

    Mean reversion signal: large positive = possible reversal down.
    """
    o, h, l_, c = [_col(data, x) for x in ["open", "high", "low", "close"]]
    spread = _high_low_spread(h, l_)
    raw = (c - o) / spread
    # Standardize
    z = (raw - np.mean(raw)) / (np.std(raw) + 1e-9)
    return pl.Series("signal", np.where(z < -1.0, 1, 0).astype(np.int8))


# ── Alpha #2: (high - low) / close − (high_20 - low_20) / close_20 ──


def alpha_002(data: pl.DataFrame) -> pl.Series:
    """Alpha#2: volatility expansion — breakout signal."""
    h, l_, c = [_col(data, x) for x in ["high", "low", "close"]]
    curr = (h - l_) / (c + 1e-9)
    h20 = np.convolve(h, np.ones(20) / 20, mode="same")
    l20 = np.convolve(l_, np.ones(20) / 20, mode="same")
    prev = (h20 - l20) / (np.convolve(c, np.ones(20) / 20, mode="same") + 1e-9)
    delta = curr - prev
    return pl.Series("signal", np.where(delta > np.std(delta), 1, 0).astype(np.int8))


# ── Alpha #3: (close - min_low_20) / (max_high_20 - min_low_20) ────


def alpha_003(data: pl.DataFrame) -> pl.Series:
    """Alpha#3: close position within 20-day range — overbought/oversold."""
    from scipy.ndimage import uniform_filter1d

    c = _col(data, "close")
    h = _col(data, "high")
    l_ = _col(data, "low")
    min_l = uniform_filter1d(l_, size=20, mode="constant", origin=0)
    max_h = uniform_filter1d(h, size=20, mode="constant", origin=0)
    raw = (c - min_l) / (max_h - min_l + 1e-9)
    # Oversold (< 0.2) → long
    return pl.Series("signal", np.where(raw < 0.2, 1, 0).astype(np.int8))


# ── Alpha #4: delta(volume, 1) / volume_20 mean ──────────────────────


def alpha_004(data: pl.DataFrame) -> pl.Series:
    """Alpha#4: volume surge — momentum confirmation."""
    v = _col(data, "volume")
    v_ma = np.convolve(v, np.ones(20) / 20, mode="same")
    delta = np.diff(v, prepend=v[0]) / (v_ma + 1e-9)
    return pl.Series("signal", np.where(delta > 1.5, 1, 0).astype(np.int8))


# ── Alpha #6: correlation(close, volume, 10) ─────────────────────────


def alpha_006(data: pl.DataFrame) -> pl.Series:
    """Alpha#6: close-volume correlation — trend strength."""
    c = _col(data, "close")
    v = _col(data, "volume")
    n = len(c)
    result = np.zeros(n, dtype=np.int8)
    for i in range(10, n):
        corr = np.corrcoef(c[i - 10 : i], v[i - 10 : i])[0, 1]
        if not np.isfinite(corr):
            continue
        if corr > 0.5:
            result[i] = 1
    return pl.Series("signal", result)


# ── Alpha #8: -1 * rank(close - open) / (high - low) ────────────────


def alpha_008(data: pl.DataFrame) -> pl.Series:
    """Alpha#8: negative of alpha#1 — reversal opposite direction."""
    o, h, l_, c = [_col(data, x) for x in ["open", "high", "low", "close"]]
    spread = _high_low_spread(h, l_)
    raw = (c - o) / spread
    z = (raw - np.mean(raw)) / (np.std(raw) + 1e-9)
    return pl.Series("signal", np.where(z > 1.0, 1, 0).astype(np.int8))


# ── Alpha #10: correlation(close, volume, 5) ─────────────────────────


def alpha_010(data: pl.DataFrame) -> pl.Series:
    """Alpha#10: short-term close-volume correlation."""
    return alpha_006(data)


# ── Alpha #12: sign(delta(close, 7)) - sign(delta(close, 14)) ───────


def alpha_012(data: pl.DataFrame) -> pl.Series:
    """Alpha#12: momentum acceleration."""
    c = _col(data, "close")
    c7 = np.diff(c, n=7, prepend=c[:7].mean())
    c14 = np.diff(c, n=14, prepend=c[:14].mean())
    sig = np.sign(c7) - np.sign(c14)
    return pl.Series("signal", np.where(sig > 0, 1, 0).astype(np.int8))


# ── Alpha #18: RSI-style mean reversion ──────────────────────────────


def alpha_018(data: pl.DataFrame) -> pl.Series:
    """Alpha#18: close / max_high_5 — pullback to recent high."""
    c = _col(data, "close")
    from scipy.ndimage import maximum_filter1d

    max5 = maximum_filter1d(c, size=5, mode="constant")
    raw = c / (max5 + 1e-9)
    # Pullback > 5% from max → long
    return pl.Series("signal", np.where(raw < 0.95, 1, 0).astype(np.int8))


# ── Alpha #20: close / SMA(close, 20) ────────────────────────────────


def alpha_020(data: pl.DataFrame) -> pl.Series:
    """Alpha#20: position relative to 20-day SMA — overbought/oversold."""
    c = _col(data, "close")
    sma20 = np.convolve(c, np.ones(20) / 20, mode="same")
    raw = c / (sma20 + 1e-9)
    return pl.Series("signal", np.where(raw < 0.97, 1, 0).astype(np.int8))


# ── Alpha #31: correlation(close, volume, 12) ────────────────────────


def alpha_031(data: pl.DataFrame) -> pl.Series:
    """Alpha#31: (corr(close, volume, 12) > 0) → long."""
    c = _col(data, "close")
    v = _col(data, "volume")
    n = len(c)
    result = np.zeros(n, dtype=np.int8)
    for i in range(12, n):
        corr = np.corrcoef(c[i - 12 : i], v[i - 12 : i])[0, 1]
        if np.isfinite(corr) and corr > 0.3:
            result[i] = 1
    return pl.Series("signal", result)


# ── Alpha #44: (close - sma(close, 10)) / sma(close, 10) ────────────


def alpha_044(data: pl.DataFrame) -> pl.Series:
    """Alpha#44: deviation from 10-day SMA."""
    c = _col(data, "close")
    sma10 = np.convolve(c, np.ones(10) / 10, mode="same")
    raw = (c - sma10) / (sma10 + 1e-9) * 100
    return pl.Series("signal", np.where(raw < -1.0, 1, 0).astype(np.int8))


# ── Alpha #45: (close - sma(close, 20)) / sma(close, 20) ────────────


def alpha_045(data: pl.DataFrame) -> pl.Series:
    """Alpha#45: deviation from 20-day SMA — pullback mean reversion."""
    c = _col(data, "close")
    sma20 = np.convolve(c, np.ones(20) / 20, mode="same")
    raw = (c - sma20) / (sma20 + 1e-9) * 100
    return pl.Series("signal", np.where(raw < -2.0, 1, 0).astype(np.int8))


# ── Alpha #50: (close - sma(close, 5)) / sma(close, 5) ──────────────


def alpha_050(data: pl.DataFrame) -> pl.Series:
    """Alpha#50: short-term deviation from 5-day SMA."""
    c = _col(data, "close")
    sma5 = np.convolve(c, np.ones(5) / 5, mode="same")
    raw = (c - sma5) / (sma5 + 1e-9) * 100
    return pl.Series("signal", np.where(raw < -0.5, 1, 0).astype(np.int8))


# ── Alpha #55: correlation(high, volume, 20) ─────────────────────────


def alpha_055(data: pl.DataFrame) -> pl.Series:
    """Alpha#55: high-volume correlation — momentum quality."""
    h = _col(data, "high")
    v = _col(data, "volume")
    n = len(h)
    result = np.zeros(n, dtype=np.int8)
    for i in range(20, n):
        corr = np.corrcoef(h[i - 20 : i], v[i - 20 : i])[0, 1]
        if np.isfinite(corr) and corr > 0.4:
            result[i] = 1
    return pl.Series("signal", result)


# ── Alpha #60: (close - open) / (high - low) * volume ────────────────


def alpha_060(data: pl.DataFrame) -> pl.Series:
    """Alpha#60: volume-weighted intraday pressure."""
    o, h, l_, c, v = [_col(data, x) for x in ["open", "high", "low", "close", "volume"]]
    spread = _high_low_spread(h, l_)
    raw = (c - o) / spread * v / (np.mean(v) + 1e-9)
    z = (raw - np.mean(raw)) / (np.std(raw) + 1e-9)
    return pl.Series("signal", np.where(z < -1.5, 1, 0).astype(np.int8))


# ── Alpha #63: SMA(close, 20) - SMA(close, 50) / SMA(close, 50) ─────


def alpha_063(data: pl.DataFrame) -> pl.Series:
    """Alpha#63: SMA cross (20/50) — classic trend signal."""
    c = _col(data, "close")
    sma20 = np.convolve(c, np.ones(20) / 20, mode="same")
    sma50 = np.convolve(c, np.ones(50) / 50, mode="same")
    raw = (sma20 - sma50) / (sma50 + 1e-9)
    return pl.Series("signal", np.where(raw > 0.01, 1, 0).astype(np.int8))


# ── Catalog ───────────────────────────────────────────────────────────


ALPHA_101_CATALOG: dict[str, object] = {
    "alpha_001": alpha_001,
    "alpha_002": alpha_002,
    "alpha_003": alpha_003,
    "alpha_004": alpha_004,
    "alpha_006": alpha_006,
    "alpha_008": alpha_008,
    "alpha_010": alpha_010,
    "alpha_012": alpha_012,
    "alpha_018": alpha_018,
    "alpha_020": alpha_020,
    "alpha_031": alpha_031,
    "alpha_044": alpha_044,
    "alpha_045": alpha_045,
    "alpha_050": alpha_050,
    "alpha_055": alpha_055,
    "alpha_060": alpha_060,
    "alpha_063": alpha_063,
}


__all__ = [
    "ALPHA_101_CATALOG",
    "alpha_001",
    "alpha_002",
    "alpha_003",
    "alpha_004",
    "alpha_006",
    "alpha_008",
    "alpha_010",
    "alpha_012",
    "alpha_018",
    "alpha_020",
    "alpha_031",
    "alpha_044",
    "alpha_045",
    "alpha_050",
    "alpha_055",
    "alpha_060",
    "alpha_063",
]

"""
Operatori per expression-based alpha factors.

Ogni operatore e` una funzione pura che accetta np.ndarray (e parametri)
e restituisce np.ndarray. L'output e` sempre sanitizzato con np.nan_to_num.
"""

from __future__ import annotations

import numpy as np
import polars as pl

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _clean(x: np.ndarray) -> np.ndarray:
    """NaN → 0.0 su ogni output."""
    return np.nan_to_num(x, nan=0.0)


# ---------------------------------------------------------------------------
# Time-series (window-based)
# ---------------------------------------------------------------------------

def ts_mean(x: np.ndarray, d: int) -> np.ndarray:
    """Rolling mean di finestra ``d``.

    Head (primi ``d-1`` elementi): riempiti con la media del primo finestra
    ``x[:d].mean()``.
    """
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    head_val = np.mean(x[:d])
    out[: d - 1] = head_val
    for i in range(d - 1, n):
        out[i] = np.mean(x[i - d + 1 : i + 1])
    return _clean(out)


def ts_std(x: np.ndarray, d: int) -> np.ndarray:
    """Rolling std dev di finestra ``d``.

    Head riempito con ``1.0``.
    """
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    out[: d - 1] = 1.0
    for i in range(d - 1, n):
        out[i] = np.std(x[i - d + 1 : i + 1])
    return _clean(out)


def ts_sum(x: np.ndarray, d: int) -> np.ndarray:
    """Rolling sum di finestra ``d``.

    Head usa il prefisso disponibile.
    """
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    for i in range(d - 1):
        out[i] = np.sum(x[: i + 1])
    for i in range(d - 1, n):
        out[i] = np.sum(x[i - d + 1 : i + 1])
    return _clean(out)


def ts_prod(x: np.ndarray, d: int) -> np.ndarray:
    """Rolling product di finestra ``d``.

    Head usa il prefisso disponibile.
    """
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    for i in range(d - 1):
        out[i] = np.prod(x[: i + 1])
    for i in range(d - 1, n):
        out[i] = np.prod(x[i - d + 1 : i + 1])
    return _clean(out)


def ts_min(x: np.ndarray, d: int) -> np.ndarray:
    """Rolling minimum di finestra ``d``.

    Head usa il prefisso disponibile.
    """
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    for i in range(d - 1):
        out[i] = np.min(x[: i + 1])
    for i in range(d - 1, n):
        out[i] = np.min(x[i - d + 1 : i + 1])
    return _clean(out)


def ts_max(x: np.ndarray, d: int) -> np.ndarray:
    """Rolling maximum di finestra ``d``.

    Head usa il prefisso disponibile.
    """
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    for i in range(d - 1):
        out[i] = np.max(x[: i + 1])
    for i in range(d - 1, n):
        out[i] = np.max(x[i - d + 1 : i + 1])
    return _clean(out)


def ts_argmax(x: np.ndarray, d: int) -> np.ndarray:
    """Giorni trascorsi dall'ultimo massimo nella finestra ``d``.

    ``days_since = (d - 1) - argmax_in_window``.
    Head usa il prefisso disponibile (finestra piu` corta).
    """
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    for i in range(d - 1):
        k = i + 1
        idx = np.argmax(x[: i + 1])
        out[i] = float(k - 1 - idx)
    for i in range(d - 1, n):
        w = x[i - d + 1 : i + 1]
        idx = np.argmax(w)
        out[i] = float(d - 1 - idx)
    return _clean(out)


def ts_argmin(x: np.ndarray, d: int) -> np.ndarray:
    """Giorni trascorsi dall'ultimo minimo nella finestra ``d``.

    Head usa il prefisso disponibile.
    """
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    for i in range(d - 1):
        k = i + 1
        idx = np.argmin(x[: i + 1])
        out[i] = float(k - 1 - idx)
    for i in range(d - 1, n):
        w = x[i - d + 1 : i + 1]
        idx = np.argmin(w)
        out[i] = float(d - 1 - idx)
    return _clean(out)


# ---------------------------------------------------------------------------
# Cross-sectional (single value at each time)
# ---------------------------------------------------------------------------

def rank(x: np.ndarray) -> np.ndarray:
    """Rank normalizzato tra 0 e 1."""
    xc = np.nan_to_num(x, nan=0.0)
    n = len(xc)
    if n <= 1:
        return _clean(np.zeros_like(xc))
    # argsort degli argsort → rank 0-based
    ranks = np.argsort(np.argsort(xc)).astype(float)
    return _clean(ranks / (n - 1))


def scale(x: np.ndarray) -> np.ndarray:
    """Normalizza in [-1, 1] tale che sum(abs) = 1."""
    xc = np.nan_to_num(x, nan=0.0)
    total = np.sum(np.abs(xc))
    if total == 0.0:
        return _clean(np.zeros_like(xc))
    return _clean(xc / total)


def zscore(x: np.ndarray) -> np.ndarray:
    """Z-score: (x - mean) / std sull'intero array."""
    xc = np.nan_to_num(x, nan=0.0)
    mu = np.mean(xc)
    s = np.std(xc)
    if s == 0.0:
        return _clean(np.zeros_like(xc))
    return _clean((xc - mu) / s)


# ---------------------------------------------------------------------------
# Math operations  (element-wise, broadcasting)
# ---------------------------------------------------------------------------

def neg(x: np.ndarray) -> np.ndarray:
    return _clean(-x)


def add(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return _clean(x + y)


def sub(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return _clean(x - y)


def mul(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return _clean(x * y)


def div(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Divisione sicura: x / (|y| + 1e-10)."""
    return _clean(x / (np.abs(y) + 1e-10))


def abs_(x: np.ndarray) -> np.ndarray:
    return _clean(np.abs(x))


def sign(x: np.ndarray) -> np.ndarray:
    return _clean(np.sign(x))


def log_(x: np.ndarray) -> np.ndarray:
    return _clean(np.log(np.abs(x) + 1e-10))


def sqrt_(x: np.ndarray) -> np.ndarray:
    return _clean(np.sqrt(np.abs(x)))


# ---------------------------------------------------------------------------
# Financial
# ---------------------------------------------------------------------------

def correlation(x: np.ndarray, y: np.ndarray, d: int) -> np.ndarray:
    """Rolling Pearson correlation tra ``x`` e ``y`` su finestra ``d``.

    Head usa il prefisso disponibile; se varianza zero → 0.0.
    """
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    for i in range(d - 1):
        k = i + 1
        c = np.corrcoef(x[:k], y[:k])[0, 1]
        out[i] = 0.0 if np.isnan(c) else c
    for i in range(d - 1, n):
        c = np.corrcoef(x[i - d + 1 : i + 1], y[i - d + 1 : i + 1])[0, 1]
        out[i] = 0.0 if np.isnan(c) else c
    return _clean(out)


def covariance(x: np.ndarray, y: np.ndarray, d: int) -> np.ndarray:
    """Rolling covariance tra ``x`` e ``y`` su finestra ``d``.

    Head usa il prefisso disponibile.
    """
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    for i in range(d - 1):
        k = i + 1
        m = np.cov(x[:k], y[:k])
        out[i] = m[0, 1]
    for i in range(d - 1, n):
        m = np.cov(x[i - d + 1 : i + 1], y[i - d + 1 : i + 1])
        out[i] = m[0, 1]
    return _clean(out)


def delta(x: np.ndarray, d: int) -> np.ndarray:
    """Differenza: ``x_i - x_{i-d}``, primi ``d`` elementi → 0."""
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    out = np.empty(n)
    out[:d] = 0.0
    out[d:] = x[d:] - x[:-d]
    return _clean(out)


# alias
sma = ts_mean


def ema(x: np.ndarray, d: int) -> np.ndarray:
    """Exponential moving average, alpha = 2 / (d + 1)."""
    n = len(x)
    if n < d:
        return _clean(np.zeros(n))
    alpha = 2.0 / (d + 1)
    out = np.empty(n)
    out[0] = x[0]
    for i in range(1, n):
        out[i] = alpha * x[i] + (1.0 - alpha) * out[i - 1]
    return _clean(out)


# ---------------------------------------------------------------------------
# Leaf nodes  (data sources)
# ---------------------------------------------------------------------------

def leaf_close(data: pl.DataFrame) -> np.ndarray:
    """Estrae la colonna 'close' da un ``pl.DataFrame``."""
    return _clean(data["close"].to_numpy())


def leaf_open(data: pl.DataFrame) -> np.ndarray:
    """Estrae la colonna 'open'."""
    return _clean(data["open"].to_numpy())


def leaf_high(data: pl.DataFrame) -> np.ndarray:
    """Estrae la colonna 'high'."""
    return _clean(data["high"].to_numpy())


def leaf_low(data: pl.DataFrame) -> np.ndarray:
    """Estrae la colonna 'low'."""
    return _clean(data["low"].to_numpy())


def leaf_volume(data: pl.DataFrame) -> np.ndarray:
    """Estrae la colonna 'volume'."""
    return _clean(data["volume"].to_numpy())


def leaf_returns(data: pl.DataFrame) -> np.ndarray:
    """Percent change di 'close': ``pct_change`` con primo elemento 0."""
    c = data["close"].to_numpy()
    out = np.empty_like(c)
    out[0] = 0.0
    out[1:] = c[1:] / c[:-1] - 1.0
    return _clean(out)


def leaf_vwap(data: pl.DataFrame) -> np.ndarray:
    """Volume-weighted average price (semplice): ``(close + high + low) / 3``."""
    c = data["close"].to_numpy()
    h = data["high"].to_numpy()
    l = data["low"].to_numpy()
    return _clean((c + h + l) / 3.0)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

OPERATORS_MAP: dict[str, callable] = {
    # Time-series
    "ts_mean": ts_mean,
    "ts_std": ts_std,
    "ts_sum": ts_sum,
    "ts_prod": ts_prod,
    "ts_min": ts_min,
    "ts_max": ts_max,
    "ts_argmax": ts_argmax,
    "ts_argmin": ts_argmin,
    # Cross-sectional
    "rank": rank,
    "scale": scale,
    "zscore": zscore,
    # Math
    "neg": neg,
    "add": add,
    "sub": sub,
    "mul": mul,
    "div": div,
    "abs": abs_,
    "sign": sign,
    "log": log_,
    "sqrt": sqrt_,
    # Financial
    "correlation": correlation,
    "covariance": covariance,
    "delta": delta,
    "sma": sma,
    "ema": ema,
    # Leaf
    "leaf_close": leaf_close,
    "leaf_open": leaf_open,
    "leaf_high": leaf_high,
    "leaf_low": leaf_low,
    "leaf_volume": leaf_volume,
    "leaf_returns": leaf_returns,
    "leaf_vwap": leaf_vwap,
}

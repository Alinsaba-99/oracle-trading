"""BL-718 / D1 — Bollinger Squeeze factor (MoonDev ``bb_squeeze_adx.py``).

Distilled from the MoonDev *bb_squeeze_adx* script (canonical formula in
``trading-os/DISTILL-BOM.md`` §D1).  The BB Squeeze is a *compression*
detector: Bollinger Bands collapse inside Keltner Channels when realised
volatility drops below the average true range.  When the bands break
back out ("release"), a directional move is statistically more likely.

The factor is **NOT** directional by itself — IC ≈ 0 expected in
isolation (deep-research 2026-08-15, §D1.2).  The signal value comes
from the interaction ``release × ADX``, which is why the factory
pre-registers the hypothesis as a triple conjunction (release & ADX>25 &
close outside BB) and not as a single feature.

Spec verbatim from the BOM:

    squeeze: (upper_bb < upper_kc) & (lower_bb > lower_kc)
    release: squeeze.shift(1) & ~squeeze
    entry_long:  released & adx.shift(1) > 25 & close > upper_bb
    entry_short: released & adx.shift(1) > 25 & close < lower_bb
    exit:  {tp_pct: 5, sl_pct: 3}
    params: bb_window=20, bb_std=2.0, keltner_window=20, kc_mult=1.5,
            adx_period=14, adx_threshold=25
    dati:  OHLCV (nessun dato esterno)

The module is self-contained: it does not import from
``analytics.technical.*`` so it can be lifted into a greenfield kit
without dragging the wider Oracle stack.  All indicators are computed
with the public-domain Wilder formulas (Bollinger 1980s, Keltner 1960s,
Wilder 1978).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

# ── Defaults from the pre-registration spec ─────────────────────────────────

DEFAULT_BB_WINDOW: int = 20
DEFAULT_BB_STD: float = 2.0
DEFAULT_KELTNER_WINDOW: int = 20
DEFAULT_KC_MULT: float = 1.5
DEFAULT_ADX_PERIOD: int = 14
DEFAULT_ADX_THRESHOLD: float = 25.0
DEFAULT_TP_PCT: float = 5.0
DEFAULT_SL_PCT: float = 3.0


@dataclass(frozen=True)
class BBSqueezeParams:
    """Pre-registered BB Squeeze parameters (DISTILL-BOM §D1)."""

    bb_window: int = DEFAULT_BB_WINDOW
    bb_std: float = DEFAULT_BB_STD
    keltner_window: int = DEFAULT_KELTNER_WINDOW
    kc_mult: float = DEFAULT_KC_MULT
    adx_period: int = DEFAULT_ADX_PERIOD
    adx_threshold: float = DEFAULT_ADX_THRESHOLD
    tp_pct: float = DEFAULT_TP_PCT
    sl_pct: float = DEFAULT_SL_PCT


# ── Result container ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class BBSqueezeResult:
    """All artefacts produced by :func:`compute_bb_squeeze`.

    Attributes
    ----------
    signals
        Polars DataFrame with columns ``date, close, bb_upper, bb_lower,
        kc_upper, kc_lower, adx, squeeze, release, entry_long, entry_short``.
    params
        The parameters actually used (echo of the input).
    """

    signals: pl.DataFrame
    params: BBSqueezeParams


# ── Public API ─────────────────────────────────────────────────────────────


def compute_bb_squeeze(
    data: pl.DataFrame, params: BBSqueezeParams | None = None
) -> BBSqueezeResult:
    """Compute the BB Squeeze factor and the pre-registered entry signals.

    Parameters
    ----------
    data
        Polars DataFrame with columns ``open``, ``high``, ``low``, ``close``
        (any order; extra columns are preserved).  Must be sorted ascending
        by date.
    params
        Optional override for the pre-registered defaults.  All fields
        default to the BOM §D1 values.

    Returns
    -------
    BBSqueezeResult
        The signals DataFrame plus the params echo.  No look-ahead: every
        derived indicator uses ``shift(1)`` where the spec calls for it.
    """
    p = params or BBSqueezeParams()
    if not {"open", "high", "low", "close"}.issubset(data.columns):
        raise ValueError("data must contain open, high, low, close columns")

    close = data["close"].to_numpy().astype(np.float64)
    high = data["high"].to_numpy().astype(np.float64)
    low = data["low"].to_numpy().astype(np.float64)

    bb_upper, _, bb_lower = _bollinger_bands(close, p.bb_window, p.bb_std)
    kc_upper, kc_lower = _keltner_channels(high, low, close, p.keltner_window, p.kc_mult)
    adx_vals = _adx(high, low, close, p.adx_period)

    squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)
    release = np.zeros_like(squeeze, dtype=bool)
    release[1:] = squeeze[:-1] & ~squeeze[1:]
    adx_prev = np.roll(adx_vals, 1)
    adx_prev[0] = np.nan
    close_prev = np.roll(close, 1)
    close_prev[0] = np.nan
    bb_upper_prev = np.roll(bb_upper, 1)
    bb_upper_prev[0] = np.nan
    bb_lower_prev = np.roll(bb_lower, 1)
    bb_lower_prev[0] = np.nan
    adx_ok = adx_prev > p.adx_threshold
    entry_long = release & adx_ok & (close_prev > bb_upper_prev)
    entry_short = release & adx_ok & (close_prev < bb_lower_prev)

    signals = pl.DataFrame(
        {
            "date": data["date"] if "date" in data.columns else pl.int_range(0, len(close)),
            "close": close,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "kc_upper": kc_upper,
            "kc_lower": kc_lower,
            "adx": adx_vals,
            "squeeze": squeeze,
            "release": release,
            "entry_long": entry_long,
            "entry_short": entry_short,
        }
    )
    return BBSqueezeResult(signals=signals, params=p)


# ── Indicators (self-contained, Wilder-compatible) ────────────────────────


def _bollinger_bands(
    close: np.ndarray, window: int, std_mult: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bollinger bands (population std, ddof=0) — TA-Lib compatible."""
    if window < 1:
        raise ValueError("bb_window must be >= 1")
    n = len(close)
    upper = np.full(n, np.nan)
    middle = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    if n < window:
        return upper, middle, lower
    cum = np.cumsum(np.insert(close, 0, 0.0))
    cum_sq = np.cumsum(np.insert(close * close, 0, 0.0))
    sums = cum[window:] - cum[:-window]
    sumsq = cum_sq[window:] - cum_sq[:-window]
    means = sums / window
    # population variance = E[X^2] - E[X]^2
    var = np.maximum(sumsq / window - means * means, 0.0)
    sd = np.sqrt(var)
    middle[window - 1 :] = means
    upper[window - 1 :] = means + std_mult * sd
    lower[window - 1 :] = means - std_mult * sd
    return upper, middle, lower


def _keltner_channels(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int, mult: float
) -> tuple[np.ndarray, np.ndarray]:
    """Keltner channels: EMA(close) ± mult·ATR(window).

    Uses Wilder ATR so the values are TA-Lib compatible.
    """
    if window < 1:
        raise ValueError("keltner_window must be >= 1")
    n = len(close)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    if n < window + 1:
        return upper, lower
    atr_vals = _wilder_atr(high, low, close, window)
    # EMA seed = SMA of first ``window`` closes (standard EMA init).
    alpha = 2.0 / (window + 1.0)
    ema = np.full(n, np.nan)
    ema[window - 1] = np.mean(close[:window])
    for i in range(window, n):
        ema[i] = alpha * close[i] + (1.0 - alpha) * ema[i - 1]
    valid = ~np.isnan(atr_vals) & ~np.isnan(ema)
    upper[valid] = ema[valid] + mult * atr_vals[valid]
    lower[valid] = ema[valid] - mult * atr_vals[valid]
    return upper, lower


def _wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Wilder ATR — seed = SMA of first ``period`` TRs, then recurse."""
    n = len(close)
    prev_close = np.roll(close, 1)
    prev_close[0] = np.nan
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    out = np.full(n, np.nan)
    if n < period + 1:
        return out
    out[period] = np.nanmean(tr[1 : period + 1])
    for i in range(period + 1, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Average Directional Index — Wilder 1978."""
    n = len(close)
    out = np.full(n, np.nan)
    if n < period * 2 + 1:
        return out
    up = np.diff(high, prepend=np.nan)
    down = -np.diff(low, prepend=np.nan)
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    prev_close = np.roll(close, 1)
    prev_close[0] = np.nan
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    atr_s = _wilder_smooth(tr, period)
    plus_di = 100.0 * _wilder_smooth(plus_dm, period) / np.where(atr_s == 0, np.nan, atr_s)
    minus_di = 100.0 * _wilder_smooth(minus_dm, period) / np.where(atr_s == 0, np.nan, atr_s)
    di_sum = plus_di + minus_di
    dx = 100.0 * np.abs(plus_di - minus_di) / np.where(di_sum == 0, np.nan, di_sum)
    out = _wilder_smooth(np.where(np.isnan(dx), 0.0, dx), period)
    return out


def _wilder_smooth(series: np.ndarray, period: int) -> np.ndarray:
    """Wilder smoothing: seed = sum of first ``period``, recurse."""
    n = len(series)
    out = np.full(n, np.nan)
    if n < period:
        return out
    cleaned = np.where(np.isnan(series), 0.0, series)
    out[period - 1] = np.sum(cleaned[:period])
    for i in range(period, n):
        out[i] = out[i - 1] - out[i - 1] / period + cleaned[i]
    return out


# ── Convenience helpers ────────────────────────────────────────────────────


def exit_levels(entry_price: float, params: BBSqueezeParams, *, side: str) -> tuple[float, float]:
    """Return (take_profit, stop_loss) per the BOM exit policy.

    Long: TP above entry, SL below.  Short: mirrored.
    """
    if side not in {"long", "short"}:
        raise ValueError(f"side must be 'long' or 'short', got {side!r}")
    tp_mult = 1.0 + params.tp_pct / 100.0
    sl_mult = 1.0 - params.sl_pct / 100.0
    if side == "long":
        return entry_price * tp_mult, entry_price * sl_mult
    return entry_price * (2.0 - tp_mult), entry_price * (2.0 - sl_mult)


__all__ = [
    "DEFAULT_ADX_PERIOD",
    "DEFAULT_ADX_THRESHOLD",
    "DEFAULT_BB_STD",
    "DEFAULT_BB_WINDOW",
    "DEFAULT_KC_MULT",
    "DEFAULT_KELTNER_WINDOW",
    "DEFAULT_SL_PCT",
    "DEFAULT_TP_PCT",
    "BBSqueezeParams",
    "BBSqueezeResult",
    "compute_bb_squeeze",
    "exit_levels",
]

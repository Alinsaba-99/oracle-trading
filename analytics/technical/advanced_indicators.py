"""Indicators backing the R5 signal families.

Complements :mod:`polars_indicators` and :mod:`extra_indicators`. Same
convention throughout: inputs are ``pl.Series`` (or array-likes), outputs are
``pl.Series`` aligned to the input length and NaN-padded during warmup, so a
caller can index them against the original frame without offsetting.

Every function here is causal — no value depends on a future bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl


def _to_pd(s: pl.Series | np.ndarray | pd.Series) -> pd.Series:
    if isinstance(s, pl.Series):
        return pd.Series(s.to_numpy().astype(np.float64))
    if isinstance(s, pd.Series):
        return s.astype(np.float64)
    return pd.Series(np.asarray(s, dtype=np.float64))


def _out(name: str, arr: np.ndarray | pd.Series) -> pl.Series:
    values = arr.to_numpy() if isinstance(arr, pd.Series) else np.asarray(arr)
    return pl.Series(name, values.astype(np.float64))


def true_range(high: pl.Series, low: pl.Series, close: pl.Series) -> pd.Series:
    """Wilder true range as a pandas Series (internal building block)."""
    h, lo, c = _to_pd(high), _to_pd(low), _to_pd(close)
    prev = c.shift(1)
    return pd.concat([(h - lo), (h - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)


def atr_wilder(high: pl.Series, low: pl.Series, close: pl.Series, period: int = 14) -> pd.Series:
    """Wilder-smoothed ATR as pandas (RMA, not simple mean)."""
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


# --------------------------------------------------------------- oscillators


def williams_r(high: pl.Series, low: pl.Series, close: pl.Series, period: int = 14) -> pl.Series:
    """Williams %R — 0 at the period high, -100 at the period low."""
    h = _to_pd(high).rolling(period).max()
    lo = _to_pd(low).rolling(period).min()
    rng = (h - lo).replace(0.0, np.nan)
    return _out("williams_r", -100.0 * (h - _to_pd(close)) / rng)


def cci(high: pl.Series, low: pl.Series, close: pl.Series, period: int = 20) -> pl.Series:
    """Commodity Channel Index using mean absolute deviation (Lambert)."""
    tp = (_to_pd(high) + _to_pd(low) + _to_pd(close)) / 3.0
    ma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return _out("cci", (tp - ma) / (0.015 * mad.replace(0.0, np.nan)))


def dpo(close: pl.Series, period: int = 20) -> pl.Series:
    """Detrended Price Oscillator: price minus a lagged SMA.

    The SMA is shifted by ``period // 2 + 1`` bars *into the past*, which keeps
    the indicator causal (the classic chart version centres it and peeks ahead).
    """
    c = _to_pd(close)
    shift = period // 2 + 1
    return _out("dpo", c - c.rolling(period).mean().shift(shift))


def stochastic_full(
    high: pl.Series,
    low: pl.Series,
    close: pl.Series,
    period: int = 14,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> tuple[pl.Series, pl.Series]:
    """Slow stochastic — returns (%K, %D), both smoothed."""
    h = _to_pd(high).rolling(period).max()
    lo = _to_pd(low).rolling(period).min()
    raw_k = 100.0 * (_to_pd(close) - lo) / (h - lo).replace(0.0, np.nan)
    k = raw_k.rolling(k_smooth).mean()
    return _out("stoch_k", k), _out("stoch_d", k.rolling(d_smooth).mean())


def trix(close: pl.Series, period: int = 15) -> pl.Series:
    """TRIX — rate of change of a triple-smoothed EMA."""
    c = _to_pd(close)
    for _ in range(3):
        c = c.ewm(span=period, adjust=False, min_periods=period).mean()
    return _out("trix", c.pct_change() * 100.0)


def aroon(high: pl.Series, low: pl.Series, period: int = 25) -> tuple[pl.Series, pl.Series]:
    """Aroon Up / Down — how recently the period extreme occurred (0-100)."""
    h, lo = _to_pd(high), _to_pd(low)
    up = h.rolling(period + 1).apply(lambda x: 100.0 * float(np.argmax(x)) / period, raw=True)
    down = lo.rolling(period + 1).apply(lambda x: 100.0 * float(np.argmin(x)) / period, raw=True)
    return _out("aroon_up", up), _out("aroon_down", down)


# -------------------------------------------------------------------- volume


def obv(close: pl.Series, volume: pl.Series) -> pl.Series:
    """On-Balance Volume — cumulative signed volume."""
    c, v = _to_pd(close), _to_pd(volume)
    return _out("obv", (np.sign(c.diff().fillna(0.0)) * v.fillna(0.0)).cumsum())


def mfi(
    high: pl.Series, low: pl.Series, close: pl.Series, volume: pl.Series, period: int = 14
) -> pl.Series:
    """Money Flow Index — a volume-weighted RSI on typical price."""
    tp = (_to_pd(high) + _to_pd(low) + _to_pd(close)) / 3.0
    raw = tp * _to_pd(volume).fillna(0.0)
    up = tp.diff()
    pos = raw.where(up > 0, 0.0).rolling(period).sum()
    neg = raw.where(up < 0, 0.0).rolling(period).sum()
    return _out("mfi", 100.0 - 100.0 / (1.0 + pos / neg.replace(0.0, np.nan)))


def vwap_rolling(
    high: pl.Series, low: pl.Series, close: pl.Series, volume: pl.Series, period: int = 20
) -> pl.Series:
    """Rolling VWAP over ``period`` bars.

    A rolling window rather than a session anchor, since the lake has no
    session boundaries and FX trades nearly continuously. Falls back to the
    typical-price mean when volume is absent (many FX feeds report zero).
    """
    tp = (_to_pd(high) + _to_pd(low) + _to_pd(close)) / 3.0
    v = _to_pd(volume).fillna(0.0)
    vol_sum = v.rolling(period).sum()
    vw = (tp * v).rolling(period).sum() / vol_sum.replace(0.0, np.nan)
    return _out("vwap", vw.fillna(tp.rolling(period).mean()))


def volume_ratio(volume: pl.Series, period: int = 20) -> pl.Series:
    """Current volume over its rolling average (1.0 = average)."""
    v = _to_pd(volume).fillna(0.0)
    return _out("volume_ratio", v / v.rolling(period).mean().replace(0.0, np.nan))


# ---------------------------------------------------------------- volatility


def keltner_channels(
    high: pl.Series, low: pl.Series, close: pl.Series, period: int = 20, mult: float = 2.0
) -> tuple[pl.Series, pl.Series, pl.Series]:
    """Keltner channels around an EMA, width in ATR multiples.

    Returns (upper, middle, lower) — same ordering as ``bbands``.
    """
    c = _to_pd(close)
    mid = c.ewm(span=period, adjust=False, min_periods=period).mean()
    band = atr_wilder(high, low, close, period) * mult
    return _out("kc_upper", mid + band), _out("kc_mid", mid), _out("kc_lower", mid - band)


def bb_width(close: pl.Series, period: int = 20, std: float = 2.0) -> pl.Series:
    """Bollinger bandwidth as a fraction of the middle band."""
    c = _to_pd(close)
    mid = c.rolling(period).mean()
    sd = c.rolling(period).std(ddof=0)
    return _out("bb_width", (2.0 * std * sd) / mid.replace(0.0, np.nan))


def supertrend(
    high: pl.Series, low: pl.Series, close: pl.Series, period: int = 10, mult: float = 3.0
) -> tuple[pl.Series, pl.Series]:
    """Supertrend — returns (trend_line, direction) where direction is +1/-1.

    Bands ratchet in the direction of the trend and only flip when price
    closes through the opposing band, which is what makes it a trailing stop
    rather than a simple channel.
    """
    h, lo, c = _to_pd(high), _to_pd(low), _to_pd(close)
    hl2 = (h + lo) / 2.0
    atr_v = atr_wilder(high, low, close, period)
    upper_basic = (hl2 + mult * atr_v).to_numpy()
    lower_basic = (hl2 - mult * atr_v).to_numpy()
    close_np = c.to_numpy()
    n = len(close_np)

    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    direction = np.zeros(n, dtype=np.float64)
    trend = np.full(n, np.nan)

    start = int(np.argmax(~np.isnan(atr_v.to_numpy()))) if n else 0
    if n == 0 or np.isnan(atr_v.to_numpy()).all():
        return _out("supertrend", trend), _out("st_dir", direction)

    upper[start] = upper_basic[start]
    lower[start] = lower_basic[start]
    direction[start] = 1.0
    trend[start] = lower[start]

    for i in range(start + 1, n):
        if np.isnan(upper_basic[i]):
            upper[i], lower[i] = upper[i - 1], lower[i - 1]
            direction[i], trend[i] = direction[i - 1], trend[i - 1]
            continue
        # Tighten the band unless price already broke the previous one.
        upper[i] = (
            min(upper_basic[i], upper[i - 1]) if close_np[i - 1] <= upper[i - 1] else upper_basic[i]
        )
        lower[i] = (
            max(lower_basic[i], lower[i - 1]) if close_np[i - 1] >= lower[i - 1] else lower_basic[i]
        )
        if close_np[i] > upper[i - 1]:
            direction[i] = 1.0
        elif close_np[i] < lower[i - 1]:
            direction[i] = -1.0
        else:
            direction[i] = direction[i - 1]
        trend[i] = lower[i] if direction[i] > 0 else upper[i]

    return _out("supertrend", trend), _out("st_dir", direction)


def parabolic_sar(
    high: pl.Series, low: pl.Series, step: float = 0.02, max_step: float = 0.2
) -> tuple[pl.Series, pl.Series]:
    """Parabolic SAR — returns (sar, direction) with direction +1/-1."""
    h, lo = _to_pd(high).to_numpy(), _to_pd(low).to_numpy()
    n = len(h)
    sar = np.full(n, np.nan)
    direction = np.zeros(n, dtype=np.float64)
    if n < 2:
        return _out("sar", sar), _out("sar_dir", direction)

    trend_up = h[1] >= h[0]
    accel = step
    extreme = h[1] if trend_up else lo[1]
    sar[1] = lo[0] if trend_up else h[0]
    direction[1] = 1.0 if trend_up else -1.0

    for i in range(2, n):
        prev = sar[i - 1]
        current = prev + accel * (extreme - prev)
        if trend_up:
            # SAR may never rise above the last two lows.
            current = min(current, lo[i - 1], lo[i - 2])
            if lo[i] < current:
                trend_up = False
                current = extreme
                extreme = lo[i]
                accel = step
            elif h[i] > extreme:
                extreme = h[i]
                accel = min(accel + step, max_step)
        else:
            current = max(current, h[i - 1], h[i - 2])
            if h[i] > current:
                trend_up = True
                current = extreme
                extreme = h[i]
                accel = step
            elif lo[i] < extreme:
                extreme = lo[i]
                accel = min(accel + step, max_step)
        sar[i] = current
        direction[i] = 1.0 if trend_up else -1.0

    return _out("sar", sar), _out("sar_dir", direction)


# ------------------------------------------------------------------ structure


def ichimoku(
    high: pl.Series, low: pl.Series, conversion: int = 9, base: int = 26, span_b: int = 52
) -> tuple[pl.Series, pl.Series, pl.Series, pl.Series]:
    """Ichimoku — returns (tenkan, kijun, senkou_a, senkou_b).

    Takes only high/low: every returned line is a midpoint of rolling
    high/low extremes. Close is used only by the chikou span, not returned here.

    The cloud spans are shifted *forward* on a chart. Shifting forward would
    leak future data into a backtest, so the spans here are returned unshifted
    and lag by ``base`` bars instead — comparisons stay causal.
    """
    h, lo = _to_pd(high), _to_pd(low)

    def _mid(period: int) -> pd.Series:
        return (h.rolling(period).max() + lo.rolling(period).min()) / 2.0

    tenkan = _mid(conversion)
    kijun = _mid(base)
    senkou_a = ((tenkan + kijun) / 2.0).shift(base)
    senkou_b = _mid(span_b).shift(base)
    return (
        _out("tenkan", tenkan),
        _out("kijun", kijun),
        _out("senkou_a", senkou_a),
        _out("senkou_b", senkou_b),
    )


def heikin_ashi(
    open_: pl.Series, high: pl.Series, low: pl.Series, close: pl.Series
) -> tuple[pl.Series, pl.Series, pl.Series, pl.Series]:
    """Heikin Ashi candles — returns (ha_open, ha_high, ha_low, ha_close)."""
    o, h, lo, c = _to_pd(open_), _to_pd(high), _to_pd(low), _to_pd(close)
    ha_close = ((o + h + lo + c) / 4.0).to_numpy()
    n = len(ha_close)
    ha_open = np.full(n, np.nan)
    if n == 0:
        empty = _out("ha_open", ha_open)
        return (empty, empty, empty, empty)

    o_np, h_np, lo_np = o.to_numpy(), h.to_numpy(), lo.to_numpy()
    ha_open[0] = (o_np[0] + ha_close[0]) / 2.0
    # Recursive by definition: each HA open averages the previous HA candle.
    for i in range(1, n):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0

    return (
        _out("ha_open", ha_open),
        _out("ha_high", np.maximum.reduce([h_np, ha_open, ha_close])),
        _out("ha_low", np.minimum.reduce([lo_np, ha_open, ha_close])),
        _out("ha_close", ha_close),
    )


def linreg_channel(
    close: pl.Series, period: int = 50, std: float = 2.0
) -> tuple[pl.Series, pl.Series, pl.Series, pl.Series]:
    """Rolling linear-regression channel.

    Returns (mid, upper, lower, slope). ``mid`` is the fitted value at the end
    of each window, so nothing depends on later bars.
    """
    c = _to_pd(close).to_numpy()
    n = len(c)
    mid = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    slope = np.full(n, np.nan)
    if n < period:
        return (
            _out("lr_mid", mid),
            _out("lr_up", upper),
            _out("lr_lo", lower),
            _out("lr_slope", slope),
        )

    x = np.arange(period, dtype=np.float64)
    x_mean = x.mean()
    x_var = ((x - x_mean) ** 2).sum()
    for i in range(period - 1, n):
        window = c[i - period + 1 : i + 1]
        if np.isnan(window).any():
            continue
        y_mean = window.mean()
        beta = ((x - x_mean) * (window - y_mean)).sum() / x_var
        alpha = y_mean - beta * x_mean
        fitted = alpha + beta * x
        resid = float(np.std(window - fitted))
        end = alpha + beta * x[-1]
        mid[i] = end
        upper[i] = end + std * resid
        lower[i] = end - std * resid
        slope[i] = beta

    return (
        _out("lr_mid", mid),
        _out("lr_up", upper),
        _out("lr_lo", lower),
        _out("lr_slope", slope),
    )


def kalman_trend(
    close: pl.Series, process_var: float = 1e-5, measure_var: float = 1e-2
) -> tuple[pl.Series, pl.Series]:
    """Scalar Kalman filter over price — returns (level, velocity).

    A constant-velocity model: the filter adapts its smoothing to realised
    noise instead of using a fixed lookback, which is the point of using it
    over a moving average. Both outputs are causal by construction.
    """
    c = _to_pd(close).to_numpy()
    n = len(c)
    level = np.full(n, np.nan)
    velocity = np.full(n, np.nan)
    if n == 0:
        return _out("kf_level", level), _out("kf_velocity", velocity)

    # State = [level, velocity]; covariance starts deliberately loose.
    x = np.array([c[0], 0.0])
    p = np.eye(2)
    f = np.array([[1.0, 1.0], [0.0, 1.0]])
    q = np.array([[process_var, 0.0], [0.0, process_var]])
    h = np.array([[1.0, 0.0]])

    for i in range(n):
        if np.isnan(c[i]):
            level[i], velocity[i] = x[0], x[1]
            continue
        x = f @ x
        p = f @ p @ f.T + q
        residual = c[i] - float((h @ x).item())
        s = float((h @ p @ h.T).item()) + measure_var
        gain = (p @ h.T / s).ravel()
        x = x + gain * residual
        p = p - np.outer(gain, h @ p)
        level[i], velocity[i] = x[0], x[1]

    return _out("kf_level", level), _out("kf_velocity", velocity)


def pivot_points(
    high: pl.Series, low: pl.Series, close: pl.Series
) -> tuple[pl.Series, pl.Series, pl.Series]:
    """Classic pivot levels from the *previous* bar — returns (pivot, r1, s1)."""
    h, lo, c = _to_pd(high).shift(1), _to_pd(low).shift(1), _to_pd(close).shift(1)
    pivot = (h + lo + c) / 3.0
    return (_out("pivot", pivot), _out("r1", 2.0 * pivot - lo), _out("s1", 2.0 * pivot - h))

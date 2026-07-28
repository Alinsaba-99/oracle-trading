"""R5 signal breadth — long/short families across the strategy taxonomy.

Unlike the v1 and R1 libraries (long-flat 0/1), everything here emits the full
``{-1, 0, +1}`` domain the engine already supports: ``vectorbt.from_signals``
is wired with ``short_entries``/``short_exits``, so a -1 becomes a real short.
Doubling the tradable direction roughly doubles the opportunity set on FX,
where downtrends are as common as uptrends.

Families, grouped by the edge they try to capture:

* trend        — Supertrend, PSAR, Ichimoku, Elder Triple Screen, LinReg
                 channel, Heikin Ashi, Aroon, TRIX, SMA golden cross
* mean revert  — Williams %R, CCI, DPO, envelopes, pivot bounce, slow
                 stochastic, MFI
* breakout     — previous-day high/low, opening range, volatility squeeze,
                 range compression
* price action — pin bar, engulfing, inside bar, Fakey, star patterns,
                 three-soldiers
* volume       — VWAP reversion, OBV divergence, volume exhaustion,
                 liquidity sweep
* adaptive     — Kalman trend, regime-switching dual strategy

Conventions every class follows (enforced by tests):
  * ``compute(data) -> pl.Series`` of ``pl.Int8``, named ``"signal"``
  * length equals ``data.height``; 0 during warmup, never NaN
  * position persists between entry and exit conditions (stateful loops)
  * no value depends on a future bar
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl

from analytics.technical.advanced_indicators import (
    aroon,
    atr_wilder,
    bb_width,
    cci,
    dpo,
    heikin_ashi,
    ichimoku,
    kalman_trend,
    keltner_channels,
    linreg_channel,
    mfi,
    obv,
    parabolic_sar,
    pivot_points,
    stochastic_full,
    supertrend,
    trix,
    volume_ratio,
    vwap_rolling,
    williams_r,
)
from analytics.technical.extra_indicators import adx
from analytics.technical.polars_indicators import ema, sma

# ----------------------------------------------------------------- accessors


def _col(data: pl.DataFrame, name: str) -> pl.Series:
    """Fetch an OHLCV column tolerating both lower- and capitalised names."""
    if name in data.columns:
        return data[name]
    cap = name.capitalize()
    if cap in data.columns:
        return data[cap]
    raise KeyError(f"missing column {name!r}; have {data.columns}")


def _np(series: pl.Series) -> np.ndarray:
    return series.to_numpy().astype(np.float64)


def _ohlc(data: pl.DataFrame) -> tuple[pl.Series, pl.Series, pl.Series, pl.Series]:
    return (_col(data, "open"), _col(data, "high"), _col(data, "low"), _col(data, "close"))


def _volume(data: pl.DataFrame) -> pl.Series:
    for name in ("volume", "Volume"):
        if name in data.columns:
            return data[name]
    return pl.Series("volume", np.zeros(data.height))


def _sig(values: np.ndarray) -> pl.Series:
    return pl.Series("signal", values.astype(np.int8))


def _zeros(n: int) -> pl.Series:
    return pl.Series("signal", np.zeros(n, dtype=np.int8))


def _hold(entries_long: np.ndarray, entries_short: np.ndarray, exits: np.ndarray) -> np.ndarray:
    """Turn per-bar conditions into a persistent -1/0/+1 position series.

    An opposing entry flips the position directly; ``exits`` only forces flat.
    """
    n = len(entries_long)
    out = np.zeros(n, dtype=np.int8)
    pos = 0
    for i in range(n):
        if entries_long[i]:
            pos = 1
        elif entries_short[i]:
            pos = -1
        elif exits[i]:
            pos = 0
        out[i] = pos
    return out


def _clean(*arrays: np.ndarray) -> np.ndarray:
    """Boolean mask of rows where every input is finite."""
    mask = np.ones(len(arrays[0]), dtype=bool)
    for arr in arrays:
        mask &= np.isfinite(arr)
    return mask


# =========================================================== trend following


class SupertrendSignal:
    """Follow the Supertrend direction flag (ATR trailing stop)."""

    def __init__(self, period: int = 10, mult: float = 3.0) -> None:
        self.period = max(2, int(period))
        self.mult = float(mult)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        if data.height < self.period + 2:
            return _zeros(data.height)
        _line, direction = supertrend(h, lo, c, self.period, self.mult)
        d = _np(direction)
        return _sig(np.where(np.isfinite(d), d, 0.0))


class ParabolicSarSignal:
    """Trade in the direction of the Parabolic SAR."""

    def __init__(self, step: float = 0.02, max_step: float = 0.2) -> None:
        self.step = float(step)
        self.max_step = float(max_step)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, _c = _ohlc(data)
        if data.height < 3:
            return _zeros(data.height)
        _sar, direction = parabolic_sar(h, lo, self.step, self.max_step)
        d = _np(direction)
        return _sig(np.where(np.isfinite(d), d, 0.0))


class IchimokuBreakout:
    """Kumo breakout — long above both cloud spans, short below both."""

    def __init__(self, conversion: int = 9, base: int = 26, span_b: int = 52) -> None:
        self.conversion = max(2, int(conversion))
        self.base = max(3, int(base))
        self.span_b = max(4, int(span_b))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        need = self.span_b + self.base + 2
        if data.height < need:
            return _zeros(data.height)
        tenkan, kijun, span_a, span_b = ichimoku(h, lo, self.conversion, self.base, self.span_b)
        close = _np(c)
        tk, kj = _np(tenkan), _np(kijun)
        sa, sb = _np(span_a), _np(span_b)
        ok = _clean(close, tk, kj, sa, sb)
        cloud_top = np.maximum(sa, sb)
        cloud_bottom = np.minimum(sa, sb)
        # Cloud break plus a confirming tenkan/kijun cross.
        long_in = ok & (close > cloud_top) & (tk > kj)
        short_in = ok & (close < cloud_bottom) & (tk < kj)
        # Losing the cloud edge is the exit, before the opposite setup forms.
        flat = ok & (close <= cloud_top) & (close >= cloud_bottom)
        return _sig(_hold(long_in, short_in, flat))


class ElderTripleScreen:
    """Elder's triple screen: long-term EMA tide, oscillator wave, breakout.

    Screen 1 is the EMA slope, screen 2 requires the oscillator to have pulled
    back against the tide, screen 3 enters on the break of the prior extreme.
    """

    def __init__(self, trend_period: int = 50, osc_period: int = 13, breakout: int = 2) -> None:
        self.trend_period = max(5, int(trend_period))
        self.osc_period = max(3, int(osc_period))
        self.breakout = max(1, int(breakout))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        if data.height < self.trend_period + self.osc_period + 2:
            return _zeros(data.height)
        trend = _np(ema(c, self.trend_period))
        slope = np.concatenate([[np.nan], np.diff(trend)])
        # Force index (Elder): price change scaled by an EMA of itself.
        close = _np(c)
        force_raw = pd.Series(np.concatenate([[np.nan], np.diff(close)]))
        force = force_raw.ewm(span=self.osc_period, adjust=False).mean().to_numpy()

        high_np, low_np = _np(h), _np(lo)
        prior_high = pd.Series(high_np).rolling(self.breakout).max().shift(1).to_numpy()
        prior_low = pd.Series(low_np).rolling(self.breakout).min().shift(1).to_numpy()

        ok = _clean(slope, force, prior_high, prior_low, close)
        long_in = ok & (slope > 0) & (force < 0) & (close > prior_high)
        short_in = ok & (slope < 0) & (force > 0) & (close < prior_low)
        flat = ok & (((slope > 0) & (close < trend)) | ((slope < 0) & (close > trend)))
        return _sig(_hold(long_in, short_in, flat))


class LinRegChannelSignal:
    """Linear-regression channel: fade the bands, direction set by slope."""

    def __init__(self, period: int = 50, std: float = 2.0) -> None:
        self.period = max(10, int(period))
        self.std = float(std)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, _h, _lo, c = _ohlc(data)
        if data.height < self.period + 2:
            return _zeros(data.height)
        mid, upper, lower, slope = linreg_channel(c, self.period, self.std)
        close = _np(c)
        m, up, lw, sl = _np(mid), _np(upper), _np(lower), _np(slope)
        ok = _clean(close, m, up, lw, sl)
        # Buy the lower rail only while the channel itself points up.
        long_in = ok & (close <= lw) & (sl > 0)
        short_in = ok & (close >= up) & (sl < 0)
        flat = ok & (((close >= m) & (sl > 0)) | ((close <= m) & (sl < 0)))
        return _sig(_hold(long_in, short_in, flat))


class HeikinAshiTrend:
    """Ride persistent Heikin Ashi colour runs."""

    def __init__(self, streak: int = 3) -> None:
        self.streak = max(1, int(streak))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        o, h, lo, c = _ohlc(data)
        if data.height < self.streak + 2:
            return _zeros(data.height)
        ha_open, _ha_high, _ha_low, ha_close = heikin_ashi(o, h, lo, c)
        hc, ho = _np(ha_close), _np(ha_open)
        bull = hc > ho
        bear = hc < ho
        run_bull = pd.Series(bull.astype(float)).rolling(self.streak).sum().to_numpy()
        run_bear = pd.Series(bear.astype(float)).rolling(self.streak).sum().to_numpy()
        ok = _clean(run_bull, run_bear, hc, ho)
        long_in = ok & (run_bull >= self.streak)
        short_in = ok & (run_bear >= self.streak)
        # A single opposite candle ends the run.
        flat = ok & ~bull & ~bear
        return _sig(_hold(long_in, short_in, flat))


class AroonTrend:
    """Aroon crossover — long when Up dominates, short when Down does."""

    def __init__(self, period: int = 25, threshold: float = 70.0) -> None:
        self.period = max(5, int(period))
        self.threshold = float(threshold)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, _c = _ohlc(data)
        if data.height < self.period + 3:
            return _zeros(data.height)
        up_s, down_s = aroon(h, lo, self.period)
        up, down = _np(up_s), _np(down_s)
        ok = _clean(up, down)
        long_in = ok & (up >= self.threshold) & (up > down)
        short_in = ok & (down >= self.threshold) & (down > up)
        flat = ok & (np.abs(up - down) < 20.0)
        return _sig(_hold(long_in, short_in, flat))


class TrixSignal:
    """TRIX zero-line cross — triple-smoothed momentum."""

    def __init__(self, period: int = 15, signal_period: int = 9) -> None:
        self.period = max(3, int(period))
        self.signal_period = max(2, int(signal_period))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, _h, _lo, c = _ohlc(data)
        if data.height < self.period * 3 + self.signal_period + 2:
            return _zeros(data.height)
        tx = _np(trix(c, self.period))
        sig_line = pd.Series(tx).ewm(span=self.signal_period, adjust=False).mean().to_numpy()
        ok = _clean(tx, sig_line)
        long_in = ok & (tx > sig_line) & (tx > 0)
        short_in = ok & (tx < sig_line) & (tx < 0)
        flat = ok & (np.sign(tx) != np.sign(sig_line))
        return _sig(_hold(long_in, short_in, flat))


class GoldenCross:
    """Classic SMA 50/200 golden / death cross."""

    def __init__(self, fast: int = 50, slow: int = 200) -> None:
        self.fast = max(2, int(fast))
        self.slow = max(self.fast + 1, int(slow))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, _h, _lo, c = _ohlc(data)
        if data.height < self.slow + 2:
            return _zeros(data.height)
        f, s = _np(sma(c, self.fast)), _np(sma(c, self.slow))
        ok = _clean(f, s)
        return _sig(np.where(ok & (f > s), 1, np.where(ok & (f < s), -1, 0)))


# ============================================================ mean reversion


class WilliamsRReversal:
    """Williams %R extremes — buy oversold, sell overbought."""

    def __init__(
        self, period: int = 14, oversold: float = -80.0, overbought: float = -20.0
    ) -> None:
        self.period = max(2, int(period))
        self.oversold = float(oversold)
        self.overbought = float(overbought)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        if data.height < self.period + 2:
            return _zeros(data.height)
        w = _np(williams_r(h, lo, c, self.period))
        ok = _clean(w)
        long_in = ok & (w <= self.oversold)
        short_in = ok & (w >= self.overbought)
        # Exit back at the midpoint rather than waiting for the far extreme.
        flat = ok & (w > -60.0) & (w < -40.0)
        return _sig(_hold(long_in, short_in, flat))


class CciReversion:
    """CCI beyond +/-threshold, betting on the statistical snap-back."""

    def __init__(self, period: int = 20, threshold: float = 100.0) -> None:
        self.period = max(4, int(period))
        self.threshold = abs(float(threshold))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        if data.height < self.period + 2:
            return _zeros(data.height)
        v = _np(cci(h, lo, c, self.period))
        ok = _clean(v)
        long_in = ok & (v <= -self.threshold)
        short_in = ok & (v >= self.threshold)
        flat = ok & (np.abs(v) < self.threshold * 0.2)
        return _sig(_hold(long_in, short_in, flat))


class DpoReversion:
    """Detrended Price Oscillator cycle reversion."""

    def __init__(self, period: int = 20, threshold_pct: float = 0.01) -> None:
        self.period = max(4, int(period))
        self.threshold_pct = abs(float(threshold_pct))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, _h, _lo, c = _ohlc(data)
        if data.height < self.period * 2 + 2:
            return _zeros(data.height)
        close = _np(c)
        d = _np(dpo(c, self.period))
        # Scale the band by price so one threshold works across instruments.
        band = self.threshold_pct * np.abs(close)
        ok = _clean(d, band) & (band > 0)
        long_in = ok & (d <= -band)
        short_in = ok & (d >= band)
        flat = ok & (np.abs(d) < band * 0.25)
        return _sig(_hold(long_in, short_in, flat))


class EnvelopeReversion:
    """Percentage envelopes around a moving average."""

    def __init__(self, period: int = 20, deviation_pct: float = 0.02) -> None:
        self.period = max(2, int(period))
        self.deviation_pct = abs(float(deviation_pct))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, _h, _lo, c = _ohlc(data)
        if data.height < self.period + 2:
            return _zeros(data.height)
        close = _np(c)
        mid = _np(sma(c, self.period))
        upper = mid * (1.0 + self.deviation_pct)
        lower = mid * (1.0 - self.deviation_pct)
        ok = _clean(close, mid, upper, lower)
        long_in = ok & (close <= lower)
        short_in = ok & (close >= upper)
        flat = ok & (np.abs(close - mid) < mid * self.deviation_pct * 0.2)
        return _sig(_hold(long_in, short_in, flat))


class PivotBounce:
    """Treat the previous bar's pivot as a magnet; fade R1/S1 rejections."""

    def __init__(self, buffer_pct: float = 0.0005) -> None:
        self.buffer_pct = abs(float(buffer_pct))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        if data.height < 3:
            return _zeros(data.height)
        pivot_s, r1_s, s1_s = pivot_points(h, lo, c)
        close = _np(c)
        pivot, r1, s1 = _np(pivot_s), _np(r1_s), _np(s1_s)
        ok = _clean(close, pivot, r1, s1)
        buf = self.buffer_pct * np.abs(close)
        long_in = ok & (close <= s1 + buf)
        short_in = ok & (close >= r1 - buf)
        flat = ok & (np.abs(close - pivot) <= buf)
        return _sig(_hold(long_in, short_in, flat))


class StochasticReversal:
    """Slow stochastic %K/%D crosses inside the extreme zones."""

    def __init__(
        self,
        period: int = 14,
        k_smooth: int = 3,
        d_smooth: int = 3,
        oversold: float = 20.0,
        overbought: float = 80.0,
    ) -> None:
        self.period = max(2, int(period))
        self.k_smooth = max(1, int(k_smooth))
        self.d_smooth = max(1, int(d_smooth))
        self.oversold = float(oversold)
        self.overbought = float(overbought)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        if data.height < self.period + self.k_smooth + self.d_smooth + 2:
            return _zeros(data.height)
        k_s, d_s = stochastic_full(h, lo, c, self.period, self.k_smooth, self.d_smooth)
        k, d = _np(k_s), _np(d_s)
        prev_k = np.concatenate([[np.nan], k[:-1]])
        prev_d = np.concatenate([[np.nan], d[:-1]])
        ok = _clean(k, d, prev_k, prev_d)
        cross_up = (k > d) & (prev_k <= prev_d)
        cross_down = (k < d) & (prev_k >= prev_d)
        long_in = ok & cross_up & (k < self.oversold + 20.0)
        short_in = ok & cross_down & (k > self.overbought - 20.0)
        flat = ok & (k > 45.0) & (k < 55.0)
        return _sig(_hold(long_in, short_in, flat))


class MfiReversion:
    """Money Flow Index extremes — volume-weighted overbought/oversold."""

    def __init__(self, period: int = 14, oversold: float = 20.0, overbought: float = 80.0) -> None:
        self.period = max(2, int(period))
        self.oversold = float(oversold)
        self.overbought = float(overbought)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        vol = _volume(data)
        # Volume-based edges are meaningless on a feed that reports no volume.
        if data.height < self.period + 2 or float(np.nansum(_np(vol))) <= 0.0:
            return _zeros(data.height)
        m = _np(mfi(h, lo, c, vol, self.period))
        ok = _clean(m)
        long_in = ok & (m <= self.oversold)
        short_in = ok & (m >= self.overbought)
        flat = ok & (m > 45.0) & (m < 55.0)
        return _sig(_hold(long_in, short_in, flat))


# =================================================================== breakout


class PrevExtremeBreakout:
    """Break of the prior N-bar high/low, with an ATR buffer to cut noise."""

    def __init__(self, lookback: int = 1, atr_buffer: float = 0.1, atr_period: int = 14) -> None:
        self.lookback = max(1, int(lookback))
        self.atr_buffer = float(atr_buffer)
        self.atr_period = max(2, int(atr_period))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        if data.height < self.lookback + self.atr_period + 2:
            return _zeros(data.height)
        close = _np(c)
        prior_high = pd.Series(_np(h)).rolling(self.lookback).max().shift(1).to_numpy()
        prior_low = pd.Series(_np(lo)).rolling(self.lookback).min().shift(1).to_numpy()
        buf = atr_wilder(h, lo, c, self.atr_period).to_numpy() * self.atr_buffer
        ok = _clean(close, prior_high, prior_low, buf)
        long_in = ok & (close > prior_high + buf)
        short_in = ok & (close < prior_low - buf)
        mid = (prior_high + prior_low) / 2.0
        flat = ok & (close < prior_high) & (close > prior_low) & (np.abs(close - mid) < buf)
        return _sig(_hold(long_in, short_in, flat))


class OpeningRangeBreakout:
    """Opening-range breakout, anchored on each session's first N bars.

    Sessions are detected from the timestamp column's calendar date, so this
    only makes sense on intraday frames; daily bars have one bar per session
    and yield no range.
    """

    def __init__(self, range_bars: int = 4) -> None:
        self.range_bars = max(1, int(range_bars))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        if "timestamp" not in data.columns or data.height < self.range_bars + 2:
            return _zeros(data.height)
        _o, h, lo, c = _ohlc(data)
        close, high_np, low_np = _np(c), _np(h), _np(lo)
        days = data["timestamp"].dt.date().to_numpy()

        n = data.height
        long_in = np.zeros(n, dtype=bool)
        short_in = np.zeros(n, dtype=bool)
        session_end = np.zeros(n, dtype=bool)

        idx = 0
        while idx < n:
            end = idx
            while end < n and days[end] == days[idx]:
                end += 1
            # Need the range window plus at least one bar to trade it.
            if end - idx > self.range_bars:
                window = slice(idx, idx + self.range_bars)
                hi = float(np.nanmax(high_np[window]))
                lwo = float(np.nanmin(low_np[window]))
                if np.isfinite(hi) and np.isfinite(lwo):
                    body = slice(idx + self.range_bars, end)
                    long_in[body] = close[body] > hi
                    short_in[body] = close[body] < lwo
            session_end[end - 1] = True  # never hold a session breakout overnight
            idx = end

        return _sig(_hold(long_in, short_in, session_end))


class VolatilitySqueeze:
    """TTM-style squeeze: Bollinger inside Keltner, then trade the expansion."""

    def __init__(self, period: int = 20, bb_std: float = 2.0, kc_mult: float = 1.5) -> None:
        self.period = max(4, int(period))
        self.bb_std = float(bb_std)
        self.kc_mult = float(kc_mult)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        if data.height < self.period + 3:
            return _zeros(data.height)
        close = _np(c)
        mid = _np(sma(c, self.period))
        sd = pd.Series(close).rolling(self.period).std(ddof=0).to_numpy()
        bb_up, bb_lo = mid + self.bb_std * sd, mid - self.bb_std * sd
        kc_up_s, _kc_mid, kc_lo_s = keltner_channels(h, lo, c, self.period, self.kc_mult)
        kc_up, kc_lo = _np(kc_up_s), _np(kc_lo_s)

        ok = _clean(close, bb_up, bb_lo, kc_up, kc_lo, mid)
        squeezed = (bb_up < kc_up) & (bb_lo > kc_lo)
        was_squeezed = np.concatenate([[False], squeezed[:-1]])
        # Fire on the bar the squeeze releases, in the direction of the break.
        long_in = ok & was_squeezed & ~squeezed & (close > mid)
        short_in = ok & was_squeezed & ~squeezed & (close < mid)
        flat = ok & squeezed
        return _sig(_hold(long_in, short_in, flat))


class RangeCompressionBreakout:
    """Trade the break of a prolonged low-volatility consolidation."""

    def __init__(self, period: int = 20, compression_pct: float = 0.4) -> None:
        self.period = max(5, int(period))
        self.compression_pct = float(compression_pct)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        if data.height < self.period * 3 + 2:
            return _zeros(data.height)
        close = _np(c)
        width = _np(bb_width(c, self.period))
        # Compare current width to its own recent distribution, so the
        # threshold is scale-free across instruments and timeframes.
        baseline = pd.Series(width).rolling(self.period * 2).median().to_numpy()
        prior_high = pd.Series(_np(h)).rolling(self.period).max().shift(1).to_numpy()
        prior_low = pd.Series(_np(lo)).rolling(self.period).min().shift(1).to_numpy()

        ok = _clean(close, width, baseline, prior_high, prior_low) & (baseline > 0)
        compressed = ok & (width < baseline * self.compression_pct)
        was_compressed = np.concatenate([[False], compressed[:-1]])
        long_in = ok & was_compressed & (close > prior_high)
        short_in = ok & was_compressed & (close < prior_low)
        flat = ok & compressed
        return _sig(_hold(long_in, short_in, flat))


# =============================================================== price action


def _body_and_shadows(
    o: np.ndarray, h: np.ndarray, lo: np.ndarray, c: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (body, upper_shadow, lower_shadow, full_range)."""
    body = np.abs(c - o)
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - lo
    rng = h - lo
    return body, upper, lower, rng


class PinBarReversal:
    """Pin bar / hammer — a long rejection wick against the prevailing swing."""

    def __init__(self, shadow_ratio: float = 2.0, trend_period: int = 20) -> None:
        self.shadow_ratio = float(shadow_ratio)
        self.trend_period = max(3, int(trend_period))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        o_s, h_s, lo_s, c_s = _ohlc(data)
        if data.height < self.trend_period + 3:
            return _zeros(data.height)
        o, h, lo, c = _np(o_s), _np(h_s), _np(lo_s), _np(c_s)
        body, upper, lower, rng = _body_and_shadows(o, h, lo, c)
        trend = _np(sma(c_s, self.trend_period))

        ok = _clean(o, h, lo, c, trend) & (rng > 0) & (body > 0)
        hammer = ok & (lower > body * self.shadow_ratio) & (upper < body)
        shooting = ok & (upper > body * self.shadow_ratio) & (lower < body)
        # Only trade the wick that rejects *into* the trend direction.
        long_in = hammer & (c > trend)
        short_in = shooting & (c < trend)
        exits = np.zeros(len(o), dtype=bool)
        exits[:] = ok & (np.abs(c - trend) < rng * 0.1)
        return _sig(_hold(long_in, short_in, exits))


class EngulfingPattern:
    """Bullish / bearish engulfing — current body swallows the previous one."""

    def __init__(self, trend_period: int = 20) -> None:
        self.trend_period = max(3, int(trend_period))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        o_s, _h, _lo, c_s = _ohlc(data)
        if data.height < self.trend_period + 3:
            return _zeros(data.height)
        o, c = _np(o_s), _np(c_s)
        prev_o = np.concatenate([[np.nan], o[:-1]])
        prev_c = np.concatenate([[np.nan], c[:-1]])
        trend = _np(sma(c_s, self.trend_period))

        ok = _clean(o, c, prev_o, prev_c, trend)
        bull = ok & (c > o) & (prev_c < prev_o) & (c > prev_o) & (o < prev_c)
        bear = ok & (c < o) & (prev_c > prev_o) & (c < prev_o) & (o > prev_c)
        flat = ok & (np.abs(c - trend) < np.abs(c) * 0.0005)
        return _sig(_hold(bull, bear, flat))


class InsideBarBreakout:
    """Inside bar: enter on the break of the mother bar's range."""

    def __init__(self, lookback: int = 1) -> None:
        self.lookback = max(1, int(lookback))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h_s, lo_s, c_s = _ohlc(data)
        if data.height < self.lookback + 3:
            return _zeros(data.height)
        h, lo, c = _np(h_s), _np(lo_s), _np(c_s)
        mother_high = np.concatenate([[np.nan], h[:-1]])
        mother_low = np.concatenate([[np.nan], lo[:-1]])
        inside = (h <= mother_high) & (lo >= mother_low)

        # The setup forms on bar i; the break can only be traded from i+1.
        setup = np.concatenate([[False], inside[:-1]])
        pending_high = np.concatenate([[np.nan], mother_high[:-1]])
        pending_low = np.concatenate([[np.nan], mother_low[:-1]])

        ok = _clean(c, pending_high, pending_low)
        long_in = ok & setup & (c > pending_high)
        short_in = ok & setup & (c < pending_low)
        flat = ok & inside
        return _sig(_hold(long_in, short_in, flat))


class FakeySetup:
    """Fakey — a false break of an inside bar, traded in the opposite way."""

    def __init__(self) -> None:
        pass

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h_s, lo_s, c_s = _ohlc(data)
        if data.height < 4:
            return _zeros(data.height)
        h, lo, c = _np(h_s), _np(lo_s), _np(c_s)
        mother_high = np.concatenate([[np.nan], h[:-1]])
        mother_low = np.concatenate([[np.nan], lo[:-1]])
        inside = (h <= mother_high) & (lo >= mother_low)

        prev_inside = np.concatenate([[False], inside[:-1]])
        prev_high = np.concatenate([[np.nan], h[:-1]])
        prev_low = np.concatenate([[np.nan], lo[:-1]])
        ib_high = np.concatenate([[np.nan], mother_high[:-1]])
        ib_low = np.concatenate([[np.nan], mother_low[:-1]])

        ok = _clean(c, prev_high, prev_low, ib_high, ib_low)
        # Wick took out the level but the close came back inside: trap.
        fake_down = ok & prev_inside & (prev_low < ib_low) & (c > ib_low)
        fake_up = ok & prev_inside & (prev_high > ib_high) & (c < ib_high)
        flat = ok & inside
        return _sig(_hold(fake_down, fake_up, flat))


class StarPattern:
    """Morning / evening star — three-bar exhaustion reversal."""

    def __init__(self, body_ratio: float = 0.5) -> None:
        self.body_ratio = float(body_ratio)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        o_s, _h, _lo, c_s = _ohlc(data)
        if data.height < 5:
            return _zeros(data.height)
        o, c = _np(o_s), _np(c_s)
        body = np.abs(c - o)
        avg_body = pd.Series(body).rolling(10).mean().to_numpy()

        def lag(arr: np.ndarray, k: int) -> np.ndarray:
            return np.concatenate([np.full(k, np.nan), arr[:-k]])

        o1, c1, b1 = lag(o, 2), lag(c, 2), lag(body, 2)  # first candle
        b2 = lag(body, 1)  # small middle candle
        ok = _clean(o, c, o1, c1, b1, b2, avg_body) & (avg_body > 0)
        small_middle = b2 < b1 * self.body_ratio
        morning = ok & (c1 < o1) & small_middle & (c > o) & (c > (o1 + c1) / 2.0)
        evening = ok & (c1 > o1) & small_middle & (c < o) & (c < (o1 + c1) / 2.0)
        flat = np.zeros(len(o), dtype=bool)
        return _sig(_hold(morning, evening, flat))


class ThreeSoldiers:
    """Three white soldiers / three black crows — directional confirmation."""

    def __init__(self, count: int = 3) -> None:
        self.count = max(2, int(count))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        o_s, _h, _lo, c_s = _ohlc(data)
        if data.height < self.count + 3:
            return _zeros(data.height)
        o, c = _np(o_s), _np(c_s)
        bull = (c > o).astype(float)
        bear = (c < o).astype(float)
        run_bull = pd.Series(bull).rolling(self.count).sum().to_numpy()
        run_bear = pd.Series(bear).rolling(self.count).sum().to_numpy()
        rising = pd.Series(c).diff().rolling(self.count).min().to_numpy()
        falling = pd.Series(c).diff().rolling(self.count).max().to_numpy()

        ok = _clean(run_bull, run_bear, rising, falling)
        long_in = ok & (run_bull >= self.count) & (rising > 0)
        short_in = ok & (run_bear >= self.count) & (falling < 0)
        flat = ok & (run_bull < self.count) & (run_bear < self.count)
        return _sig(_hold(long_in, short_in, flat))


# ===================================================================== volume


class VwapReversion:
    """Fade stretches away from rolling VWAP, in the direction of the trend."""

    def __init__(
        self, period: int = 20, stretch_pct: float = 0.005, trend_period: int = 50
    ) -> None:
        self.period = max(2, int(period))
        self.stretch_pct = abs(float(stretch_pct))
        self.trend_period = max(5, int(trend_period))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        if data.height < self.trend_period + self.period + 2:
            return _zeros(data.height)
        close = _np(c)
        vw = _np(vwap_rolling(h, lo, c, _volume(data), self.period))
        trend = _np(ema(c, self.trend_period))
        ok = _clean(close, vw, trend) & (vw > 0)
        stretch = (close - vw) / vw
        # Buy dips below VWAP only while the longer trend is still up.
        long_in = ok & (stretch <= -self.stretch_pct) & (close > trend)
        short_in = ok & (stretch >= self.stretch_pct) & (close < trend)
        flat = ok & (np.abs(stretch) < self.stretch_pct * 0.2)
        return _sig(_hold(long_in, short_in, flat))


class ObvDivergence:
    """Price/OBV divergence — flow disagreeing with price."""

    def __init__(self, period: int = 20) -> None:
        self.period = max(5, int(period))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, _h, _lo, c = _ohlc(data)
        vol = _volume(data)
        if data.height < self.period * 2 + 2 or float(np.nansum(_np(vol))) <= 0.0:
            return _zeros(data.height)
        close = _np(c)
        flow = _np(obv(c, vol))
        price_chg = pd.Series(close).diff(self.period).to_numpy()
        flow_chg = pd.Series(flow).diff(self.period).to_numpy()
        ok = _clean(price_chg, flow_chg)
        # Bullish: price still falling while cumulative flow turns up.
        long_in = ok & (price_chg < 0) & (flow_chg > 0)
        short_in = ok & (price_chg > 0) & (flow_chg < 0)
        flat = ok & (np.sign(price_chg) == np.sign(flow_chg))
        return _sig(_hold(long_in, short_in, flat))


class VolumeExhaustion:
    """Trend accelerating on fading volume — a late-move exhaustion fade."""

    def __init__(self, period: int = 20, vol_threshold: float = 0.7) -> None:
        self.period = max(5, int(period))
        self.vol_threshold = float(vol_threshold)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, _h, _lo, c = _ohlc(data)
        vol = _volume(data)
        if data.height < self.period * 2 + 2 or float(np.nansum(_np(vol))) <= 0.0:
            return _zeros(data.height)
        close = _np(c)
        ratio = _np(volume_ratio(vol, self.period))
        momentum = pd.Series(close).pct_change(self.period).to_numpy()
        move = pd.Series(np.abs(momentum)).rolling(self.period).mean().to_numpy()
        ok = _clean(ratio, momentum, move) & (move > 0)
        extended = np.abs(momentum) > move * 1.5
        thin = ratio < self.vol_threshold
        # Fade the direction of the exhausted move.
        long_in = ok & extended & thin & (momentum < 0)
        short_in = ok & extended & thin & (momentum > 0)
        flat = ok & ~extended
        return _sig(_hold(long_in, short_in, flat))


class LiquiditySweep:
    """Enter after a wick clears a recent extreme and price closes back inside."""

    def __init__(self, lookback: int = 20, wick_atr: float = 0.5, atr_period: int = 14) -> None:
        self.lookback = max(3, int(lookback))
        self.wick_atr = float(wick_atr)
        self.atr_period = max(2, int(atr_period))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h_s, lo_s, c_s = _ohlc(data)
        if data.height < self.lookback + self.atr_period + 2:
            return _zeros(data.height)
        h, lo, c = _np(h_s), _np(lo_s), _np(c_s)
        prior_high = pd.Series(h).rolling(self.lookback).max().shift(1).to_numpy()
        prior_low = pd.Series(lo).rolling(self.lookback).min().shift(1).to_numpy()
        atr_v = atr_wilder(h_s, lo_s, c_s, self.atr_period).to_numpy()

        ok = _clean(h, lo, c, prior_high, prior_low, atr_v) & (atr_v > 0)
        threshold = atr_v * self.wick_atr
        # Stops above the high were taken, then price rejected: sweep long.
        swept_low = ok & (lo < prior_low - threshold) & (c > prior_low)
        swept_high = ok & (h > prior_high + threshold) & (c < prior_high)
        mid = (prior_high + prior_low) / 2.0
        flat = ok & (np.abs(c - mid) < threshold)
        return _sig(_hold(swept_low, swept_high, flat))


# =================================================================== adaptive


class KalmanTrendSignal:
    """Trade the sign of a Kalman-filtered velocity estimate.

    The filter re-weights new information by measured noise, so the effective
    smoothing adapts to the regime instead of being fixed by a lookback.
    """

    def __init__(
        self, process_var: float = 1e-5, measure_var: float = 1e-2, min_velocity: float = 0.0
    ) -> None:
        self.process_var = float(process_var)
        self.measure_var = float(measure_var)
        self.min_velocity = abs(float(min_velocity))

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, _h, _lo, c = _ohlc(data)
        if data.height < 10:
            return _zeros(data.height)
        level_s, vel_s = kalman_trend(c, self.process_var, self.measure_var)
        close = _np(c)
        level, vel = _np(level_s), _np(vel_s)
        ok = _clean(close, level, vel)
        # Scale the deadband by price so it ports across instruments.
        band = self.min_velocity * np.abs(close)
        long_in = ok & (vel > band) & (close > level)
        short_in = ok & (vel < -band) & (close < level)
        flat = ok & (np.abs(vel) <= band)
        return _sig(_hold(long_in, short_in, flat))


class RegimeSwitchSignal:
    """Run a trend rule in trending regimes and a reversion rule otherwise.

    ADX picks the regime per bar. This is the closest thing in the library to
    the "adapts itself to the market" behaviour: one genome covers both states
    instead of the search having to pick a single regime and hope.
    """

    def __init__(
        self,
        adx_period: int = 14,
        adx_threshold: float = 25.0,
        trend_fast: int = 10,
        trend_slow: int = 30,
        revert_period: int = 20,
        revert_z: float = 2.0,
    ) -> None:
        self.adx_period = max(2, int(adx_period))
        self.adx_threshold = float(adx_threshold)
        self.trend_fast = max(2, int(trend_fast))
        self.trend_slow = max(self.trend_fast + 1, int(trend_slow))
        self.revert_period = max(4, int(revert_period))
        self.revert_z = float(revert_z)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        _o, h, lo, c = _ohlc(data)
        need = max(self.trend_slow, self.revert_period, self.adx_period) + 3
        if data.height < need:
            return _zeros(data.height)
        close = _np(c)
        strength = _np(adx(h, lo, c, self.adx_period))
        fast, slow = _np(ema(c, self.trend_fast)), _np(ema(c, self.trend_slow))
        roll = pd.Series(close)
        mean = roll.rolling(self.revert_period).mean().to_numpy()
        sd = roll.rolling(self.revert_period).std(ddof=0).to_numpy()
        z = np.divide(close - mean, sd, out=np.full_like(close, np.nan), where=sd > 0)

        ok = _clean(close, strength, fast, slow, z)
        trending = strength >= self.adx_threshold
        long_in = ok & ((trending & (fast > slow)) | (~trending & (z <= -self.revert_z)))
        short_in = ok & ((trending & (fast < slow)) | (~trending & (z >= self.revert_z)))
        # In reversion mode close at the mean; in trend mode stay with the cross.
        flat = ok & ~trending & (np.abs(z) < 0.3)
        return _sig(_hold(long_in, short_in, flat))


#: Name -> class for everything defined here.
R2_SIGNALS: dict[str, type] = {
    # trend
    "supertrend": SupertrendSignal,
    "parabolic_sar": ParabolicSarSignal,
    "ichimoku_breakout": IchimokuBreakout,
    "elder_triple_screen": ElderTripleScreen,
    "linreg_channel": LinRegChannelSignal,
    "heikin_ashi_trend": HeikinAshiTrend,
    "aroon_trend": AroonTrend,
    "trix": TrixSignal,
    "golden_cross": GoldenCross,
    # mean reversion
    "williams_r": WilliamsRReversal,
    "cci_reversion": CciReversion,
    "dpo_reversion": DpoReversion,
    "envelope_reversion": EnvelopeReversion,
    "pivot_bounce": PivotBounce,
    "stochastic_reversal": StochasticReversal,
    "mfi_reversion": MfiReversion,
    # breakout
    "prev_extreme_breakout": PrevExtremeBreakout,
    "opening_range_breakout": OpeningRangeBreakout,
    "volatility_squeeze": VolatilitySqueeze,
    "range_compression": RangeCompressionBreakout,
    # price action
    "pin_bar": PinBarReversal,
    "engulfing": EngulfingPattern,
    "inside_bar": InsideBarBreakout,
    "fakey": FakeySetup,
    "star_pattern": StarPattern,
    "three_soldiers": ThreeSoldiers,
    # volume
    "vwap_reversion": VwapReversion,
    "obv_divergence": ObvDivergence,
    "volume_exhaustion": VolumeExhaustion,
    "liquidity_sweep": LiquiditySweep,
    # adaptive
    "kalman_trend": KalmanTrendSignal,
    "regime_switch": RegimeSwitchSignal,
}


def _register() -> None:
    from analytics.strategy.signals import DEFAULT_STRATEGIES

    DEFAULT_STRATEGIES.update(R2_SIGNALS)


_register()

"""R1 signal breadth — extended families spanning the day-trading taxonomy.

Adds ten factors to the v1 library, all implementing ``BacktestSignal.compute``
(``-> pl.Series`` Int8, long-flat 0/1) and self-registering into
``signals.DEFAULT_STRATEGIES`` on import (via the trailing import in
``signals.py``):

* :class:`AdxTrend`        — EMA trend gated by ADX strength
* :class:`MacdTrend`        — MACD line vs signal
* :class:`VolumeBreakout`  — Donchian breakout + volume confirmation
* :class:`Pullback`        — buy the dip in an uptrend (MA bounce)
* :class:`GapSignal`       — gap-up continuation
* :class:`ScalpingRibbon`  — bullish stacked 5/8/13 MA ribbon
* :class:`PatternSignal`   — candlestick (bullish engulfing / hammer)
* :class:`RegimeGatedSignal` — wrap a base signal with an ADX trend gate
* :class:`PairSpreadSignal`  — spread reversion via ``pair_trading.spread_zscore``
* :class:`MlSignal`          — LightGBM direction classifier, walk-forward

Design notes (kept honest in code comments):
- ``PatternSignal`` uses inline per-bar candlestick rules; ``technical.patterns``
  wraps TA-Lib aggregate detection which does not map to per-bar positions.
- ``RegimeGatedSignal`` gates by a rolling ADX trend proxy; ``analytics.regime``
  classifies a whole series and suits live regime labelling more than per-bar
  backtest gating.
- ``PairSpreadSignal`` expects ``data['close']`` to be a precomputed spread
  (built via ``pair_trading.compute_cointegration`` by the sweep layer); it
  keeps the long-spread side only (long-flat) until the engine supports shorts.
- ``MlSignal`` trains walk-forward (expanding window, features causal, label =
  next-bar direction) so there is no look-ahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl

from analytics.backtest.protocol import BacktestSignal
from analytics.technical.extra_indicators import adx, donchian_channels
from analytics.technical.polars_indicators import atr, ema, macd, rsi, sma


def _close(data: pl.DataFrame) -> pl.Series:
    col = "close" if "close" in data.columns else "Close"
    return data[col]


def _to_np(series: pl.Series) -> np.ndarray:
    return series.to_numpy().astype(np.float64)


def _col(data: pl.DataFrame, name: str, alt: str) -> pl.Series:
    return data[name] if name in data.columns else data[alt]


def _zeros(n: int) -> pl.Series:
    return pl.Series("signal", [0] * n, dtype=pl.Int8)


# ------------------------------------------------------------------ trend/momo
class AdxTrend:
    """Long while fast EMA > slow EMA AND ADX above a strength threshold."""

    def __init__(
        self, fast: int = 20, slow: int = 50, adx_period: int = 14, threshold: float = 25.0
    ) -> None:
        self.fast = fast
        self.slow = slow
        self.adx_period = adx_period
        self.threshold = threshold

    def compute(self, data: pl.DataFrame) -> pl.Series:
        close = _close(data)
        c = _to_np(close)
        if len(c) < self.slow:
            return _zeros(len(c))
        above = _to_np(ema(close, self.fast)) > _to_np(ema(close, self.slow))
        a = _to_np(
            adx(_col(data, "high", "High"), _col(data, "low", "Low"), close, self.adx_period)
        )
        out = np.where((above & (a > self.threshold)), 1, 0).astype(np.int8)
        out = np.where(np.isnan(a), 0, out)
        return pl.Series("signal", out)


class MacdTrend:
    """Long while the MACD line is above its signal line."""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9) -> None:
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def compute(self, data: pl.DataFrame) -> pl.Series:
        close = _close(data)
        c = _to_np(close)
        if len(c) < self.slow + self.signal:
            return _zeros(len(c))
        line, sig_line, _hist = macd(close, self.fast, self.slow, self.signal)
        m = _to_np(line)
        s = _to_np(sig_line)
        out = np.where(m > s, 1, 0).astype(np.int8)
        out = np.where(np.isnan(m) | np.isnan(s), 0, out)
        return pl.Series("signal", out)


class VolumeBreakout:
    """Donchian breakout confirmed by above-average volume."""

    def __init__(self, period: int = 20, vol_period: int = 20, vol_mult: float = 1.5) -> None:
        self.period = period
        self.vol_period = vol_period
        self.vol_mult = vol_mult

    def compute(self, data: pl.DataFrame) -> pl.Series:
        close = _close(data)
        c = _to_np(close)
        if "volume" not in data.columns and "Volume" not in data.columns:
            return _zeros(len(c))
        vol = _to_np(_col(data, "volume", "Volume"))
        up, lo = donchian_channels(close, self.period)
        upn = _to_np(up)
        lon = _to_np(lo)
        vol_ma = pd.Series(vol).rolling(self.vol_period).mean().to_numpy()
        pos = 0
        sig = np.zeros(len(c), dtype=np.int8)
        for i in range(len(c)):
            if np.isnan(upn[i]) or np.isnan(vol_ma[i]) or vol_ma[i] <= 0:
                continue
            if c[i] > upn[i] and vol[i] > vol_ma[i] * self.vol_mult:
                pos = 1
            elif c[i] < lon[i]:
                pos = 0
            sig[i] = pos
        return pl.Series("signal", sig)


class Pullback:
    """Buy the dip in an uptrend: long when close > long MA and close > short MA
    (price pulled back then resumed above the short MA). Exit below the long MA."""

    def __init__(self, short: int = 20, long: int = 50) -> None:
        self.short = short
        self.long = long

    def compute(self, data: pl.DataFrame) -> pl.Series:
        close = _close(data)
        c = _to_np(close)
        if len(c) < self.long:
            return _zeros(len(c))
        sh = _to_np(sma(close, self.short))
        ln = _to_np(sma(close, self.long))
        pos = 0
        sig = np.zeros(len(c), dtype=np.int8)
        for i in range(len(c)):
            if np.isnan(sh[i]) or np.isnan(ln[i]):
                continue
            if c[i] > ln[i] and c[i] > sh[i]:
                pos = 1
            elif c[i] < ln[i]:
                pos = 0
            sig[i] = pos
        return pl.Series("signal", sig)


class GapSignal:
    """Gap-up continuation: long after an overnight gap up, exit on weakness/timeout."""

    def __init__(self, min_gap_pct: float = 0.01, hold: int = 5) -> None:
        self.min_gap_pct = min_gap_pct
        self.hold = hold

    def compute(self, data: pl.DataFrame) -> pl.Series:
        close = _close(data)
        c = _to_np(close)
        if "open" not in data.columns and "Open" not in data.columns:
            return _zeros(len(c))
        o = _to_np(_col(data, "open", "Open"))
        sig = np.zeros(len(c), dtype=np.int8)
        pos = 0
        bars_in = 0
        for i in range(1, len(c)):
            gap = (o[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0.0
            if pos == 0 and gap > self.min_gap_pct:
                pos = 1
                bars_in = 1
            elif pos == 1:
                bars_in += 1
                if c[i] < c[i - 1] or bars_in > self.hold:
                    pos = 0
            sig[i] = pos
        return pl.Series("signal", sig)


class ScalpingRibbon:
    """Bullish stacked MA ribbon (fast>mid>slow) with price above the fast MA."""

    def __init__(self, fast: int = 5, mid: int = 8, slow: int = 13) -> None:
        self.fast = fast
        self.mid = mid
        self.slow = slow

    def compute(self, data: pl.DataFrame) -> pl.Series:
        close = _close(data)
        c = _to_np(close)
        if len(c) < self.slow:
            return _zeros(len(c))
        f = _to_np(ema(close, self.fast))
        m = _to_np(ema(close, self.mid))
        s = _to_np(ema(close, self.slow))
        stacked = (f > m) & (m > s) & (c > f)
        out = np.where(stacked, 1, 0).astype(np.int8)
        out = np.where(np.isnan(f) | np.isnan(s), 0, out)
        return pl.Series("signal", out)


class PatternSignal:
    """Candlestick long: bullish engulfing or hammer; exit on bearish engulfing.

    Self-contained per-bar rules (TA-Lib aggregate detection in
    ``technical.patterns`` does not map to per-bar positions).
    """

    def __init__(self) -> None:
        pass

    def compute(self, data: pl.DataFrame) -> pl.Series:
        o = pd.Series(_to_np(_col(data, "open", "Open")))
        c = pd.Series(_to_np(_close(data)))
        h = pd.Series(_to_np(_col(data, "high", "High")))
        low = pd.Series(_to_np(_col(data, "low", "Low")))
        po = o.shift(1)
        pc = c.shift(1)
        body = c - o
        oc_max = pd.concat([o, c], axis=1).max(axis=1)
        oc_min = pd.concat([o, c], axis=1).min(axis=1)
        lower_wick = oc_min - low
        upper_wick = h - oc_max
        bull_engulf = (pc < po) & (c > o) & (c >= po) & (o <= pc)
        hammer = (c > o) & (lower_wick > 2.0 * body.abs()) & (upper_wick < body.abs())
        bear_engulf = (pc > po) & (c < o) & (o >= pc) & (c <= po)
        bullish = (bull_engulf | hammer).to_numpy()
        bearish = bear_engulf.to_numpy()
        pos = 0
        sig = np.zeros(len(c), dtype=np.int8)
        for i in range(len(c)):
            if np.isnan(po.iloc[i]):
                continue
            if bullish[i]:
                pos = 1
            elif bearish[i]:
                pos = 0
            sig[i] = pos
        return pl.Series("signal", sig)


class RegimeGatedSignal:
    """Wrap a base signal; allow longs only when a rolling ADX trend regime is on.

    The ADX gate is a regime proxy. ``analytics.regime.RegimeDetector`` labels a
    whole series and is better suited to live regime classification than
    per-bar backtest gating.
    """

    def __init__(
        self, base: BacktestSignal | None = None, adx_period: int = 14, threshold: float = 25.0
    ) -> None:
        if base is None:
            from analytics.strategy.signals import EmaTrend

            base = EmaTrend()
        self.base = base
        self.adx_period = adx_period
        self.threshold = threshold

    def compute(self, data: pl.DataFrame) -> pl.Series:
        base_sig = _to_np(self.base.compute(data))
        close = _close(data)
        a = _to_np(
            adx(_col(data, "high", "High"), _col(data, "low", "Low"), close, self.adx_period)
        )
        gate = np.where(np.isnan(a), 0, (a > self.threshold).astype(np.int8))
        out = (base_sig * gate).astype(np.int8)
        return pl.Series("signal", out)


class PairSpreadSignal:
    """Long-spread reversion via ``pair_trading.spread_zscore``.

    Expects ``data['close']`` to be a precomputed spread series (built by the
    sweep layer via ``pair_trading.compute_cointegration``). Long-flat: keeps
    only the long-spread side until the backtest engine supports shorts.
    """

    def __init__(
        self, window: int = 20, entry_threshold: float = 2.0, exit_threshold: float = 0.5
    ) -> None:
        self.window = window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def compute(self, data: pl.DataFrame) -> pl.Series:
        from analytics.technical.pair_trading import spread_zscore

        spread = _close(data)
        s = spread_zscore(spread, self.window, self.entry_threshold, self.exit_threshold)
        return (s == 1).cast(pl.Int8).alias("signal")


class MlSignal:
    """LightGBM next-bar direction classifier, walk-forward (no look-ahead).

    Causal features: lagged returns, RSI, rolling vol, z-score, ATR%. Label:
    next-bar up(1)/down(0). Train on an expanding window from ``train_min``;
    retrain every ``retrain_every`` bars. Position = prediction.
    """

    def __init__(self, train_min: int = 500, retrain_every: int = 200, lags: int = 3) -> None:
        self.train_min = train_min
        self.retrain_every = retrain_every
        self.lags = lags

    def compute(self, data: pl.DataFrame) -> pl.Series:
        import lightgbm as lgb

        close = _close(data)
        c = _to_np(close)
        n = len(c)
        if n < self.train_min + 2:
            return _zeros(n)
        s = pd.Series(c)
        ret = s.pct_change()
        feats: dict[str, pd.Series] = {}
        for k in range(1, self.lags + 1):
            feats[f"ret_lag{k}"] = ret.shift(k)
        feats["rsi"] = pd.Series(_to_np(rsi(close, 14)))
        feats["vol20"] = ret.rolling(20).std()
        feats["z20"] = (s - s.rolling(20).mean()) / s.rolling(20).std().replace(0.0, np.nan)
        feats["atr_pct"] = (
            pd.Series(_to_np(atr(_col(data, "high", "High"), _col(data, "low", "Low"), close, 14)))
            / s
        )
        x = pd.DataFrame(feats).to_numpy()
        y = (ret.shift(-1) > 0).to_numpy().astype(float)  # next-bar direction
        valid = ~np.isnan(x).any(axis=1) & ~np.isnan(y)
        sig = np.zeros(n, dtype=np.int8)
        model = None
        last_train = -(10**9)
        for i in range(self.train_min, n):
            if not valid[i]:
                continue
            if model is None or (i - last_train) >= self.retrain_every:
                rows = np.where(valid[:i])[0]
                if len(rows) < self.train_min:
                    continue
                model = lgb.LGBMClassifier(n_estimators=50, verbose=-1, n_jobs=1)
                model.fit(x[rows], y[rows].astype(int))
                last_train = i
            sig[i] = int(model.predict(x[i : i + 1])[0])
        return pl.Series("signal", sig)


# ---- self-register into signals.DEFAULT_STRATEGIES on import ---------------
def _register() -> None:
    from analytics.strategy.signals import DEFAULT_STRATEGIES

    DEFAULT_STRATEGIES.update(
        {
            "adx_trend": AdxTrend,
            "macd_trend": MacdTrend,
            "volume_breakout": VolumeBreakout,
            "pullback": Pullback,
            "gap": GapSignal,
            "ribbon": ScalpingRibbon,
            "pattern": PatternSignal,
            "regime_gated": RegimeGatedSignal,
            "pair_spread": PairSpreadSignal,
            "ml": MlSignal,
        }
    )


_register()

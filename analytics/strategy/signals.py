"""Strategy signal library for prop-firm challenge backtests.

All signals implement :class:`BacktestSignal` and return a Polars Series
of position states.  Strategies are **long-flat** (0 = flat, 1 = long)
for v1 — prop-firm challenges are easier to manage without shorts, and
the single direction keeps the challenge-simulator analysis clean.

The signal value at bar *i* reflects data up to and including bar *i*;
the backtest engine shifts by one bar before execution, so there is no
look-ahead.

Four complementary styles are provided so the strategy sweep (Fase 6)
can search across regimes:

* :class:`EmaTrend` — trend following (fast/slow EMA)
* :class:`RsiReversion` — mean reversion (RSI oversold long)
* :class:`BbandReversion` — mean reversion (Bollinger lower-band long)
* :class:`DonchianBreakout` — breakout (prior-N high)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl

from analytics.backtest.protocol import BacktestSignal
from analytics.technical.polars_indicators import atr, bbands, ema, rsi


def _close(data: pl.DataFrame) -> pl.Series:
    col = "close" if "close" in data.columns else "Close"
    return data[col]


def _to_np(series: pl.Series) -> np.ndarray:
    return series.to_numpy().astype(np.float64)


class EmaTrend:
    """Long while fast EMA is above slow EMA (trend following)."""

    def __init__(self, fast: int = 20, slow: int = 50) -> None:
        self.fast = fast
        self.slow = slow

    def compute(self, data: pl.DataFrame) -> pl.Series:
        close = _close(data)
        if len(close) < self.slow:
            return pl.Series("signal", [0] * len(close), dtype=pl.Int8)
        above = ema(close, self.fast) > ema(close, self.slow)
        return above.cast(pl.Int8).alias("signal")


class RsiReversion:
    """Go long from oversold, exit when momentum normalises (mean reversion)."""

    def __init__(self, period: int = 14, oversold: float = 30.0, exit_level: float = 55.0) -> None:
        self.period = period
        self.oversold = oversold
        self.exit_level = exit_level

    def compute(self, data: pl.DataFrame) -> pl.Series:
        r = _to_np(rsi(_close(data), self.period))
        pos = 0
        sig = np.zeros(len(r), dtype=np.int8)
        for i in range(len(r)):
            if np.isnan(r[i]):
                continue
            if r[i] < self.oversold:
                pos = 1
            elif r[i] > self.exit_level:
                pos = 0
            sig[i] = pos
        return pl.Series("signal", sig)


class BbandReversion:
    """Go long when price closes below the lower Bollinger band.

    Exits when price reverts above the mid band (simple moving average).
    """

    def __init__(self, period: int = 20, std: float = 2.0) -> None:
        self.period = period
        self.std = std

    def compute(self, data: pl.DataFrame) -> pl.Series:
        close = _close(data)
        lower, mid, _upper = bbands(close, self.period, self.std)
        c = _to_np(close)
        lo = _to_np(lower)
        mi = _to_np(mid)
        pos = 0
        sig = np.zeros(len(c), dtype=np.int8)
        for i in range(len(c)):
            if np.isnan(lo[i]):
                continue
            if c[i] < lo[i]:
                pos = 1
            elif c[i] > mi[i]:
                pos = 0
            sig[i] = pos
        return pl.Series("signal", sig)


class DonchianBreakout:
    """Long on a close above the prior-N-bar high; flat below the prior-N low."""

    def __init__(self, period: int = 20) -> None:
        self.period = period

    def compute(self, data: pl.DataFrame) -> pl.Series:
        c = _to_np(_close(data))
        s = pd.Series(c)
        prior_high = s.rolling(self.period).max().shift(1).to_numpy()
        prior_low = s.rolling(self.period).min().shift(1).to_numpy()
        pos = 0
        sig = np.zeros(len(c), dtype=np.int8)
        for i in range(len(c)):
            if np.isnan(prior_high[i]):
                continue
            if c[i] > prior_high[i]:
                pos = 1
            elif c[i] < prior_low[i]:
                pos = 0
            sig[i] = pos
        return pl.Series("signal", sig)


class TrendFilteredBreakout:
    """Donchian breakout, but only long when price is above a long MA.

    Filters out counter-trend breakouts (the main whipsaw source on the
    gold donchian — see the Fase 6 Monte Carlo finding that fail_o, not
    fail_d, is the structural killer).  This is the ``market_regime``
    pattern from stratevo ([[strategy-research]]): only deploy when the
    secular trend agrees with the breakout direction.
    """

    def __init__(self, period: int = 20, ma_period: int = 200) -> None:
        self.period = period
        self.ma_period = ma_period

    def compute(self, data: pl.DataFrame) -> pl.Series:
        c = _to_np(_close(data))
        if len(c) < self.ma_period:
            return pl.Series("signal", [0] * len(c), dtype=pl.Int8)
        s = pd.Series(c)
        prior_high = s.rolling(self.period).max().shift(1).to_numpy()
        prior_low = s.rolling(self.period).min().shift(1).to_numpy()
        ma = s.rolling(self.ma_period).mean().to_numpy()
        pos = 0
        sig = np.zeros(len(c), dtype=np.int8)
        for i in range(len(c)):
            if np.isnan(prior_high[i]) or np.isnan(ma[i]):
                continue
            # Long on breakout ONLY when above the secular trend MA.
            if c[i] > prior_high[i] and c[i] > ma[i]:
                pos = 1
            elif c[i] < prior_low[i]:
                pos = 0
            sig[i] = pos
        return pl.Series("signal", sig)


#: Registry of v1 strategies for the sweep harness. New factors are appended
#: after their class definitions below.
DEFAULT_STRATEGIES: dict[str, type[BacktestSignal]] = {
    "ema_trend_20_50": EmaTrend,
    "rsi_reversion_14": RsiReversion,
    "bband_reversion_20": BbandReversion,
    "donchian_breakout_20": DonchianBreakout,
    "trend_filtered_breakout": TrendFilteredBreakout,
}


class RocMomentum:
    """Rate-of-change momentum: long while N-period ROC is positive."""

    def __init__(self, period: int = 12) -> None:
        self.period = period

    def compute(self, data: pl.DataFrame) -> pl.Series:
        c = _to_np(_close(data))
        if len(c) < self.period + 1:
            return pl.Series("signal", [0] * len(c), dtype=pl.Int8)
        s = pd.Series(c)
        roc = s.pct_change(self.period).to_numpy()
        sig = np.zeros(len(c), dtype=np.int8)
        for i in range(len(c)):
            if np.isnan(roc[i]):
                continue
            sig[i] = 1 if roc[i] > 0 else 0
        return pl.Series("signal", sig)


class ZscoreReversion:
    """Mean reversion: long when price z-score is below a negative threshold."""

    def __init__(self, period: int = 20, entry_z: float = 2.0) -> None:
        self.period = period
        self.entry_z = entry_z

    def compute(self, data: pl.DataFrame) -> pl.Series:
        c = _to_np(_close(data))
        if len(c) < self.period:
            return pl.Series("signal", [0] * len(c), dtype=pl.Int8)
        s = pd.Series(c)
        mean = s.rolling(self.period).mean().to_numpy()
        std = s.rolling(self.period).std().to_numpy()
        z = (c - mean) / np.where(std > 0, std, np.nan)
        pos = 0
        sig = np.zeros(len(c), dtype=np.int8)
        for i in range(len(c)):
            if np.isnan(z[i]):
                continue
            if z[i] < -self.entry_z:
                pos = 1
            elif z[i] > 0:
                pos = 0
            sig[i] = pos
        return pl.Series("signal", sig)


class KeltnerReversion:
    """Mean reversion: long when price closes below the lower Keltner band.

    Lower band = EMA(period) - mult * ATR(period).  Exit when price
    reverts above the EMA.
    """

    def __init__(self, period: int = 20, mult: float = 2.0) -> None:
        self.period = period
        self.mult = mult

    def compute(self, data: pl.DataFrame) -> pl.Series:
        close = _close(data)
        c = _to_np(close)
        if len(c) < self.period:
            return pl.Series("signal", [0] * len(c), dtype=pl.Int8)
        mid = _to_np(ema(close, self.period))
        high = data["high"] if "high" in data.columns else data["High"]
        low = data["low"] if "low" in data.columns else data["Low"]
        a = _to_np(atr(high, low, close, self.period))
        lower = mid - self.mult * a
        pos = 0
        sig = np.zeros(len(c), dtype=np.int8)
        for i in range(len(c)):
            if np.isnan(lower[i]):
                continue
            if c[i] < lower[i]:
                pos = 1
            elif c[i] > mid[i]:
                pos = 0
            sig[i] = pos
        return pl.Series("signal", sig)


DEFAULT_STRATEGIES["roc_momentum"] = RocMomentum
DEFAULT_STRATEGIES["zscore_reversion"] = ZscoreReversion
DEFAULT_STRATEGIES["keltner_reversion"] = KeltnerReversion


# R1 breadth - extended families (signals_r1) self-register into
# DEFAULT_STRATEGIES on import. Keep LAST so the dict is populated first.
from analytics.strategy import signals_r1 as _signals_r1  # noqa: E402,F401

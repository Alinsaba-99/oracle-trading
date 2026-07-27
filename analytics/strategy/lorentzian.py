"""Lorentzian Distance KNN Classifier — scalping strategy for prop-firm challenges.

Port of the TradingView "Machine Learning: Lorentzian Classification" (jdehorty)
to Oracle's BacktestSignal protocol.

Core idea
---------
Instead of Euclidean distance, use **Lorentzian distance** to find similar
historical market states:

    d(x, y) = Σ log(1 + |x_i - y_i|)   for i = 1 .. n_features

The log(1 + |diff|) compresses large outliers so a single extreme feature
does not dominate the distance — making it more robust for financial data.

Features (default 5)
--------------------
1. RSI(14)         – Relative Strength Index
2. WT(10, 11)      – Ehlers WaveTrend (smoother than RSI)
3. CCI(20)         – Commodity Channel Index
4. ADX(14)         – Average Directional Index
5. RSI(5)          – faster RSI for temporal resolution

For each bar, the K=8 nearest historical neighbors (by Lorentzian dist) are
found.  Their training labels (next-4-bar direction) are majority-voted to
produce the current signal.  Optional filters gate the signal by volatility,
regime trend, and ADX strength.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import polars as pl

from analytics.technical.polars_indicators import atr, ema, rsi, sma

# ── helpers ──────────────────────────────────────────────────────────────────


def _close(data: pl.DataFrame) -> pl.Series:
    return data["close"] if "close" in data.columns else data["Close"]


def _high(data: pl.DataFrame) -> pl.Series:
    return data["high"] if "high" in data.columns else data["High"]


def _low(data: pl.DataFrame) -> pl.Series:
    return data["low"] if "low" in data.columns else data["Low"]


def _hlc3(data: pl.DataFrame) -> pl.Series:
    return (_high(data) + _low(data) + _close(data)) / 3.0


def _to_np(s: pl.Series) -> np.ndarray:
    return s.to_numpy().astype(np.float64)


# ── indicator helpers ────────────────────────────────────────────────────────


def wavetrend(close: pl.Series, n: int = 10, m: int = 11) -> pl.Series:
    """Ehlers WaveTrend oscillator.

    Returns a smoothed cycle-oscillator in the range ~ -100 .. +100.
    """
    esa = ema(close, n)
    de = ema((close - esa).abs(), n)
    ci = (close - esa) / (0.015 * de)
    wt1 = ema(ci, m)
    return wt1


def cci(high: pl.Series, low: pl.Series, close: pl.Series, period: int = 20) -> pl.Series:
    """Commodity Channel Index.

    CCI = (TP - SMA(TP)) / (0.015 * mean_abs_deviation)
    where TP = typical price.
    """
    tp = (high + low + close) / 3.0
    tp_np = _to_np(tp)
    tp_sma = sma(tp, period)
    tp_sma_np = _to_np(tp_sma)

    # Mean absolute deviation
    n = len(tp_np)
    mad = np.full(n, np.nan, dtype=np.float64)
    for i in range(period - 1, n):
        window = tp_np[i - period + 1 : i + 1]
        wmean = tp_sma_np[i]
        mad[i] = np.abs(window - wmean).mean()

    result = np.where(mad > 0, (tp_np - tp_sma_np) / (0.015 * mad), 0.0)
    return pl.Series("cci", result)


def adx_line(high: pl.Series, low: pl.Series, close: pl.Series, period: int = 14) -> pl.Series:
    """Average Directional Index (just ADX line, not +/-DI)."""
    from analytics.technical.extra_indicators import adx as _adx_func

    return _adx_func(high, low, close, period)


# ── feature functions ────────────────────────────────────────────────────────

FEATURE_REGISTRY: dict[str, tuple[Callable[..., np.ndarray], int, int]] = {
    "rsi": (lambda c, _h, _l, _h3, p1, _p2: _to_np(rsi(c, p1)), 14, 1),
    "wt": (lambda c, _h, _l, _h3, p1, p2: _to_np(wavetrend(c, p1, p2)), 10, 11),
    "cci": (lambda c, h, low, _h3, p1, _p2: _to_np(cci(h, low, c, p1)), 20, 1),
    "adx": (lambda c, h, low, _h3, p1, _p2: _to_np(adx_line(h, low, c, p1)), 14, 1),
}


def compute_features(data: pl.DataFrame, feature_specs: list[tuple[str, int, int]]) -> np.ndarray:
    """Compute feature matrix: (n_bars, n_features).

    Each spec is (feature_name, param_a, param_b).
    Features are min-max normalised to [0, 1] using an EXPANDING window:
    at bar t, the normalisation bounds are ``min/max(raw[0..t])`` — never
    the full-sample min/max.  This preserves causality (no look-ahead).

    Implementation notes:
      * ``np.minimum.accumulate`` / ``np.maximum.accumulate`` ignore NaN
        only if we seed them carefully; we use pandas-style expanding
        min/max via ``np.fmin.accumulate`` / ``np.fmax.accumulate``
        after replacing NaN with +inf / -inf.
      * Bars before the first non-NaN feature remain NaN.
    """
    close = _close(data)
    high = _high(data)
    low = _low(data)
    hlc3 = _hlc3(data)
    n = len(data)
    cols: list[np.ndarray] = []

    for name, p1, p2 in feature_specs:
        fn = FEATURE_REGISTRY[name][0]
        raw = fn(close, high, low, hlc3, p1, p2)
        if len(raw) < n:
            raw = np.pad(raw, (n - len(raw), 0), constant_values=np.nan)

        # Causal expanding min/max: at bar t, bounds use only data ≤ t.
        # Replace NaN with sentinels so accumulate ignores them.  After the
        # accumulate, restore NaN wherever the input was NaN so downstream
        # KNN/filter code can detect missing values.
        finite_mask = ~np.isnan(raw)
        if not finite_mask.any():
            cols.append(np.full(n, np.nan))
            continue

        raw_for_min = np.where(finite_mask, raw, np.inf)
        raw_for_max = np.where(finite_mask, raw, -np.inf)
        exp_min = np.fmin.accumulate(raw_for_min)
        exp_max = np.fmax.accumulate(raw_for_max)
        # Before the first finite value, exp_min=+inf / exp_max=-inf → mark NaN.
        has_data = exp_max >= exp_min
        range_ = exp_max - exp_min
        with np.errstate(invalid="ignore", divide="ignore"):
            normalised = np.where(
                has_data & (range_ > 0), (raw - exp_min) / range_, np.where(has_data, 0.5, np.nan)
            )
        # Crucially: restore NaN where the original input was NaN —
        # otherwise warmup bars look like legitimate 0.0 or 0.5 values.
        normalised = np.where(finite_mask, normalised, np.nan)
        cols.append(normalised)

    return np.column_stack(cols)


# ── Lorentzian distance ──────────────────────────────────────────────────────


def lorentzian_distance(x: np.ndarray, y: np.ndarray) -> float:
    """Lorentzian distance between two feature vectors.

    d(x, y) = Σ log(1 + |x_i - y_i|)  for i = 1 .. n_features

    The log(1 + abs(diff)) compresses large differences so outliers
    don't dominate.  Equivalent to the implementation in jdehorty's
    TradingView script.
    """
    return float(np.sum(np.log(1.0 + np.abs(x - y))))


def lorentzian_distances(query: np.ndarray, history: np.ndarray) -> np.ndarray:
    """Compute Lorentzian distance from *query* to every row in *history*.

    Returns a 1D array of distances.
    """
    # Vectorised: log(1 + |query - each_row|) summed across features
    diffs = np.abs(history - query.reshape(1, -1))  # (n_history, n_features)
    result: np.ndarray = np.sum(np.log(1.0 + diffs), axis=1)
    return result


# ── training labels ──────────────────────────────────────────────────────────


def make_labels(close: np.ndarray, lookahead: int = 4) -> np.ndarray:
    """Label each bar: +1 if price increases over next *lookahead* bars, else -1.

    These are the "training labels" for the KNN: each historical bar is
    classified by what happened *after* it.
    """
    n = len(close)
    labels = np.full(n, np.nan, dtype=np.float64)
    for i in range(n - lookahead):
        labels[i] = 1.0 if close[i + lookahead] > close[i] else -1.0
    return labels


# ── KNN classifier ───────────────────────────────────────────────────────────


def knn_predict(
    query_features: np.ndarray, history_features: np.ndarray, history_labels: np.ndarray, k: int = 8
) -> float:
    """Predict direction by majority vote of K nearest Lorentzian neighbors.

    Returns +1 (long) or -1 (short).  Ties → 0 (neutral).
    """
    dists = lorentzian_distances(query_features, history_features)
    # Get K nearest (smallest distances)
    nearest = np.argpartition(dists, k)[:k]
    neighbor_labels = history_labels[nearest]
    valid = neighbor_labels[~np.isnan(neighbor_labels)]
    if len(valid) == 0:
        return 0.0
    vote = np.sign(np.sum(valid))
    return vote if vote != 0 else 0.0


# ══════════════════════════════════════════════════════════════════════════════
# BacktestSignal implementation
# ══════════════════════════════════════════════════════════════════════════════


class LorentzianKNN:
    """Lorentzian Distance KNN Classifier — BacktestSignal.

    Parameters
    ----------
    k : int
        Number of nearest neighbors (default 8).
    lookahead : int
        Bars ahead for training labels (default 4).
    feature_count : int
        Number of features (2-5, default 5).
    max_bars_back : int
        Lookback window for training history (default 2000).
    use_volatility_filter : bool
        Gate signal by recent volatility (default True).
    use_regime_filter : bool
        Gate signal by trend regime (default True).
    use_adx_filter : bool
        Gate signal by ADX strength (default False).
    regime_threshold : float
        Threshold for regime filter (default -0.1).
    adx_threshold : int
        Minimum ADX for trend filter (default 20).
    long_only : bool
        When True, return only 0/1 instead of -1/0/1 (default True).
    """

    def __init__(
        self,
        k: int = 8,
        lookahead: int = 4,
        feature_count: int = 5,
        max_bars_back: int = 2000,
        use_volatility_filter: bool = True,
        use_regime_filter: bool = True,
        use_adx_filter: bool = False,
        regime_threshold: float = -0.1,
        adx_threshold: int = 20,
        long_only: bool = True,
    ) -> None:
        self.k = k
        self.lookahead = lookahead
        self.feature_count = min(max(feature_count, 2), 5)
        self.max_bars_back = max_bars_back
        self.use_volatility_filter = use_volatility_filter
        self.use_regime_filter = use_regime_filter
        self.use_adx_filter = use_adx_filter
        self.regime_threshold = regime_threshold
        self.adx_threshold = adx_threshold
        self.long_only = long_only

        # Default feature specs (matching TradingView defaults)
        self._feature_specs = [
            ("rsi", 14, 1),
            ("wt", 10, 11),
            ("cci", 20, 1),
            ("adx", 14, 1),
            ("rsi", 5, 1),
        ][: self.feature_count]

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Compute Lorentzian KNN trading signal.

        Returns a Polars Int8 Series with values:
          - 1 (long) when KNN predicts up
          - 0 (flat) otherwise
        """
        close = _close(data)
        high = _high(data)
        low = _low(data)
        close_np = _to_np(close)
        n = len(data)

        if n < 100:
            return pl.Series("signal", [0] * n, dtype=pl.Int8)

        # 1. Compute feature matrix
        features = compute_features(data, self._feature_specs)

        # 2. Generate training labels
        labels = make_labels(close_np, self.lookahead)

        # 3. Pre-compute filters
        vol_series = _to_np(atr(high, low, close, 10)) / _to_np(close)
        reg_series = _to_np(sma(close, 50)) - _to_np(close)
        adx_series = _to_np(adx_line(high, low, close, 14))

        # 4. Compute signal bar-by-bar (expand training window)
        sig = np.zeros(n, dtype=np.int8)
        warmup = max(60, self.max_bars_back // 10)

        for i in range(warmup, n):
            # History: all bars before i, limited by max_bars_back
            hist_start = max(0, i - self.max_bars_back)
            hist_feat = features[hist_start:i]
            hist_labels = labels[hist_start:i]

            # Skip if not enough history or too many NaN features
            if hist_feat.shape[0] < self.k * 3:
                continue
            if np.any(np.isnan(features[i])):
                continue

            # Query: current bar's features
            query = features[i]

            # Filters
            low_vol = (
                self.use_volatility_filter
                and i > 10
                and vol_series[i] < np.nanpercentile(vol_series[:i], 20)
            )
            if low_vol:
                sig[i] = 0
                continue

            bearish = (
                self.use_regime_filter
                and not np.isnan(reg_series[i])
                and reg_series[i] < self.regime_threshold
            )
            if bearish:
                sig[i] = 0
                continue

            weak_trend = (
                self.use_adx_filter
                and not np.isnan(adx_series[i])
                and adx_series[i] < self.adx_threshold
            )
            if weak_trend:
                sig[i] = 0
                continue

            # KNN prediction
            pred = knn_predict(query, hist_feat, hist_labels, self.k)
            sig[i] = 1 if pred > 0 else 0

        return pl.Series("signal", sig, dtype=pl.Int8)


# ── convenience factory ──────────────────────────────────────────────────────


def lorentzian_scalp(
    k: int = 8, lookahead: int = 4, long_only: bool = True, **kwargs: object
) -> LorentzianKNN:
    """Factory for a Lorentzian scalping strategy with sensible defaults."""
    return LorentzianKNN(k=k, lookahead=lookahead, long_only=long_only, **kwargs)  # type: ignore[arg-type]


def lorentzian_swing(
    k: int = 16, lookahead: int = 12, long_only: bool = True, **kwargs: object
) -> LorentzianKNN:
    """Factory for a Lorentzian swing strategy (slower, higher confidence)."""
    return LorentzianKNN(k=k, lookahead=lookahead, long_only=long_only, **kwargs)  # type: ignore[arg-type]

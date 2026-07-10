"""KNN trading signal using Lorentzian distance — ML-powered classification.

Translates the TradingView "Lorentzian Classification" strategy by @jdehorty
into a GA-optimisable BacktestSignal for Oracle.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import polars as pl

    from genetics.genome.parameters import GenomeParameter
    from genetics.genome.signal import Genome

_FEATURE_NAMES = ["rsi", "cci", "adx", "wavetrend", "mom"]


def _compute_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder's RSI."""
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.full_like(close, np.nan)
    avg_loss = np.full_like(close, np.nan)
    avg_gain[period] = float(np.mean(gain[1 : period + 1]))
    avg_loss[period] = float(np.mean(loss[1 : period + 1]))
    for i in range(period + 1, len(close)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i]) / period
    rs = avg_gain / np.maximum(avg_loss, 1e-10)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return np.nan_to_num(rsi, nan=50.0)


def _compute_cci(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20
) -> np.ndarray:
    """Commodity Channel Index."""
    tp = (high + low + close) / 3.0
    sma = np.full_like(tp, np.nan)
    for i in range(period - 1, len(tp)):
        sma[i] = float(np.mean(tp[i - period + 1 : i + 1]))
    mad = np.full_like(tp, np.nan)
    for i in range(period - 1, len(close)):
        mad[i] = float(np.mean(np.abs(tp[i - period + 1 : i + 1] - sma[i])))
    cci = np.where(mad > 0, (tp - sma) / (0.015 * mad), 0.0)
    return np.nan_to_num(cci, nan=0.0)


def _compute_adx(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
) -> np.ndarray:
    """Average Directional Index."""
    n = len(close)
    up = np.diff(high, prepend=high[0])
    down = np.diff(low, prepend=low[0])
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = np.maximum(high - low, np.abs(high - close))
    tr = np.maximum(tr, np.abs(low - close))
    atr = np.full_like(close, np.nan)
    atr[period] = float(np.mean(tr[1 : period + 1]))
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    pdi = 100.0 * np.where(atr > 0, np.cumsum(plus_dm) / np.cumsum(atr), 0.0)
    mdi = 100.0 * np.where(atr > 0, np.cumsum(minus_dm) / np.cumsum(atr), 0.0)
    dx = 100.0 * np.abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-10)
    adx = np.full_like(close, np.nan)
    adx[2 * period] = float(np.mean(dx[period + 1 : 2 * period + 1]))
    for i in range(2 * period + 1, n):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
    return np.nan_to_num(adx, nan=25.0)


def _compute_wavetrend(
    hlc3: np.ndarray, channel_length: int = 10, avg_length: int = 11
) -> np.ndarray:
    """WaveTrend oscillator."""
    esa = np.full_like(hlc3, np.nan)
    for i in range(channel_length - 1, len(hlc3)):
        esa[i] = float(np.mean(hlc3[i - channel_length + 1 : i + 1]))
    d = np.full_like(hlc3, np.nan)
    for i in range(channel_length - 1, len(hlc3)):
        d[i] = float(np.mean(np.abs(hlc3[i - channel_length + 1 : i + 1] - esa[i])))
    ci = (hlc3 - esa) / (0.015 * np.maximum(d, 1e-10))
    wt = np.full_like(hlc3, np.nan)
    for i in range(avg_length - 1, len(hlc3)):
        wt[i] = float(np.mean(ci[i - avg_length + 1 : i + 1]))
    return np.nan_to_num(wt, nan=0.0)


def _compute_mom(close: np.ndarray, period: int = 12) -> np.ndarray:
    """Simple momentum."""
    mom = np.full_like(close, np.nan)
    mom[period:] = close[period:] / np.maximum(close[:-period], 1e-10) - 1.0
    return np.nan_to_num(mom, nan=0.0)


def _lorentzian_distance(
    a: np.ndarray, b: np.ndarray, weights: np.ndarray | None = None
) -> float:
    """Lorentzian distance: sum(wn * ln(1 + |an - bn|)).

    When *weights* is None, all features are equally weighted.
    """
    diff = np.abs(a - b)
    if weights is not None:
        diff = diff * weights
    return float(np.sum(np.log(1.0 + diff)))


def _extract_features(
    data: pl.DataFrame,
    periods: dict[str, int] | None = None,
) -> np.ndarray:
    """Compute feature matrix [RSI, CCI, ADX, WaveTrend, Momentum] z-scored."""
    p = periods or {}
    close = data["close"].to_numpy()
    high = data["high"].to_numpy()
    low = data["low"].to_numpy()
    hlc3 = (high + low + close) / 3.0
    features = np.column_stack([
        _compute_rsi(close, p.get("rsi_period", 14)),
        _compute_cci(high, low, close, p.get("cci_period", 20)),
        _compute_adx(high, low, close, p.get("adx_period", 14)),
        _compute_wavetrend(hlc3, p.get("wt_channel", 10), p.get("wt_avg", 11)),
        _compute_mom(close, p.get("mom_period", 12)),
    ])
    means = np.nanmean(features, axis=0)
    stds = np.nanstd(features, axis=0)
    stds = np.where(stds < 1e-10, 1.0, stds)
    features = (features - means) / stds
    return np.nan_to_num(features, nan=0.0)


class KNNGenomeToSignal:
    """K-Nearest Neighbours trading signal with Lorentzian distance.

    GA-optimisable parameters:
        k_neighbors, train_length, threshold, rsi_period,
        w_rsi, w_cci, w_adx, w_wt, w_mom
    """

    def __init__(
        self,
        genome: Genome,
        param_defs: Sequence[GenomeParameter],  # noqa: ARG002 — protocol compat
    ) -> None:
        from genetics.genome.signal import decode

        self._raw = decode(genome)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        import polars as pl

        n = len(data)
        if n < 50:
            return pl.Series("signal", [0] * n, dtype=pl.Int8)

        k = max(1, min(int(self._raw.get("k_neighbors", 8)), n // 4))
        train_len = max(1, min(int(self._raw.get("train_length", 4)), 20))
        threshold = max(0.1, min(float(self._raw.get("threshold", 0.5)), 0.9))

        periods = {
            "rsi_period": int(self._raw.get("rsi_period", 14)),
            "cci_period": int(self._raw.get("cci_period", 20)),
            "adx_period": int(self._raw.get("adx_period", 14)),
            "wt_channel": int(self._raw.get("wt_channel", 10)),
            "wt_avg": int(self._raw.get("wt_avg", 11)),
            "mom_period": int(self._raw.get("mom_period", 12)),
        }

        weights = np.array(
            [float(self._raw.get(w, 1.0)) for w in ["w_rsi", "w_cci", "w_adx", "w_wt", "w_mom"]],
            dtype=np.float64,
        )
        weights = np.maximum(weights, 0.0)
        ws = weights.sum()
        if ws > 0:
            weights = weights / ws
        features = _extract_features(data, periods)
        close = data["close"].to_numpy()

        future = np.roll(close, -train_len)
        labels = np.full(n, 0, dtype=np.int8)
        labels[:-train_len] = np.where(future[:-train_len] > close[:-train_len], 1, -1)

        # Class balance weight: higher = more minority-boost
        class_weight = max(0.1, float(self._raw.get("class_weight", 0.7)))

        result = np.zeros(n, dtype=np.int8)
        lookback = min(n // 2, 100)
        min_bars = max(k + 1, lookback // 10)
        weights_row = weights[np.newaxis, :]  # pre-shaped for broadcasting

        for i in range(min_bars, n):
            start = max(0, i - lookback)
            if i - start < k:
                continue

            # Vectorized Lorentzian distance over the lookback window
            fi = features[i]  # local ref to avoid repeated indexing
            hist = features[start:i]
            diff = np.abs(fi - hist)
            dists = np.sum(np.log1p(diff * weights_row), axis=1)

            # Distance-weighted voting
            nearest = np.argpartition(dists, k)[:k]
            nearest_dists = dists[nearest] + 1e-10
            inv_dist = 1.0 / nearest_dists
            vote_weights = inv_dist / inv_dist.sum()

            nl = labels[start + nearest]
            w_up = float(vote_weights[nl == 1].sum())
            w_dn = float(vote_weights[nl == -1].sum())
            n_up = int((nl == 1).sum())
            n_dn = int((nl == -1).sum())
            if n_up > n_dn:
                w_dn *= class_weight
            elif n_dn > n_up:
                w_up *= class_weight
            total_w = w_up + w_dn
            if total_w > 0:
                effective_th = max(0.5, threshold)
                if w_up / total_w >= effective_th:
                    result[i] = 1
                elif w_dn / total_w >= effective_th:
                    result[i] = -1

        return pl.Series("signal", result, dtype=pl.Int8)

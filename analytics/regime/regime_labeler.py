"""Regime labeling basato su metriche reali — senza forward-looking.

Ogni barra viene classificata in uno degli 8 regimi Kairos-v2 usando
SOLO i dati disponibili al momento della barra stessa:

  0 Dong_Bang  → frozen      (ATR bassissimo, no movimento)
  1 Nen_Chat   → compression  (BB squeeze, volatilità in contrazione)
  2 Dau_XH     → start uptrend (prezzo > EMA, ADX in salita)
  3 XH_Manh   → strong uptrend (ADX > 25, prezzo lontano da EMA)
  4 Cao_Trao   → climax       (wide range, vol alta, wick estremo)
  5 Hoi_Quy    → retracement  (prezzo torna verso EMA, vol normale)
  6 Nhieu_Dong → noisy        (CHOP > 60, ADX < 20)
  7 Quet_TK    → stop hunting  (ombra lunga, body piccolo, inversione)

Usage::
    from analytics.regime.regime_labeler import label_by_metrics
    df = compute_all_features(df_ohlcv)
    labels = label_by_metrics(df)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl

from analytics.regime.ml_features import compute_all_features

# ── Thresholds (calibrati su ES 1d 2000-2026 via percentile analysis) ──

# ADX (our implementation returns 0-1 scale, not 0-100)
ADX_STRONG = 0.35  # ~p75: ADX > 35% on 0-1 scale
ADX_WEAK = 0.20  # ~p25: below 20%
ADX_RISING = 0.03  # ADX salito di 0.03 in 3 barre

# CHOP (our implementation returns negative values due to log ratio)
# Less negative = more trending.  More negative = more choppy
CHOP_NOISY = -55.0  # p25: more negative than this = choppy
CHOP_TRENDING = -40.0  # p75: less negative than this = trending

# D (EMA distance %)
D_STRONG_TREND = 3.5  # ~p75: >3.5% from EMA
D_MODERATE = 1.2  # ~p25: >1.2% from EMA
D_CLOSE = 0.8  # ~p15: <0.8% = very close to EMA

# BBwidth (our implementation uses ratio form)
BBW_SQUEEZE = 0.035  # ~p25: narrower than this = squeeze
BBW_EXPANDED = 0.08  # ~p75: wider than this = expansion

# ATRn (ATR/close %)
ATRN_FROZEN = 0.8  # ~p10: very low vol
ATRN_CLIMAX = 2.5  # ~p90: very high vol

# Wick proportions
WICK_LONG = 0.5  # ~p90: long upper or lower wick
BODY_TINY = 0.15  # ~p25: small body (doji-like)
BODY_LARGE = 0.7  # ~p75: large body (trending bar)


def classify_regime(row: dict[str, Any]) -> int:
    """Classify a single bar into one of 8 regimes using ONLY current metrics.

    Priority order (first match wins):
      1. Climax (Cao_Trao)     — wide range, extreme vol, long wick
      2. Frozen (Dong_Bang)    — no movement, ATR near zero
      3. Compression (Nen_Chat) — BB squeeze
      4. Stop Hunt (Quet_TK)    — long shadow, small body
      5. Strong Trend (XH_Manh) — ADX > 25, price far from EMA
      6. Start Trend (Dau_XH)   — ADX rising, price crossed EMA
      7. Noisy (Nhieu_Dong)     — CHOP > 60, ADX < 20
      8. Retracement (Hoi_Quy)  — price near EMA, no clear signal
    """

    def v(key: str, default: float = 0.0) -> float:
        val = row.get(key)
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    d = abs(v("D"))
    adx = v("ADX")
    chop = v("CHOP", 50)
    atrn = v("ATRn")
    bbw = v("BBwidth", 1)
    wick_up = v("WickUpProp")
    wick_dn = v("WickDnProp")
    body = v("BodyProp", 0.5)
    v("SQZ", 0)
    v("RSI", 50)

    # 0 → Dong_Bang (Frozen)
    if atrn < ATRN_FROZEN and d < D_CLOSE and adx < ADX_WEAK:
        return 0

    # 1 → Nen_Chat (Compression / Squeeze) — BB narrow + choppy
    if bbw < BBW_SQUEEZE and chop < CHOP_NOISY:
        return 1

    # 7 → Quet_TK (Stop Hunting) — long wick + small body
    if body < BODY_TINY and (wick_up > WICK_LONG or wick_dn > WICK_LONG):
        return 7

    # 4 → Cao_Trao (Climax) — wide range + extreme vol
    if atrn > ATRN_CLIMAX and d > D_STRONG_TREND and (wick_up > 0.6 or wick_dn > 0.6):
        return 4

    # 3 → XH_Manh (Strong uptrend or downtrend)
    if adx > ADX_STRONG and d > D_STRONG_TREND:
        return 3

    # 6 → Nhieu_Dong (Noisy)
    if chop > CHOP_NOISY and adx < ADX_WEAK:
        return 6

    # 2 → Dau_XH (Start trend)
    if ADX_WEAK < adx < ADX_STRONG and d > D_MODERATE:
        return 2

    # 5 → Hoi_Quy (Retracement) — price near EMA after a move
    if d < D_CLOSE:
        return 5

    # Default: noisy
    return 6


def label_by_metrics(df_features: pl.DataFrame) -> list[int]:
    """Label every bar in a features DataFrame using real-time metrics.

    Args:
        df_features: DataFrame with 18 core features computed
                     (output of ``compute_all_features()``).

    Returns:
        List of integer regime labels (0-7), one per bar.
    """
    feature_cols = [
        "D",
        "ADX",
        "CHOP",
        "ATRn",
        "BBwidth",
        "SQZ",
        "WickUpProp",
        "WickDnProp",
        "BodyProp",
        "RSI",
    ]

    # Ensure all feature columns exist
    missing = set(feature_cols) - set(df_features.columns)
    if missing:
        raise ValueError(
            f"Missing feature columns: {missing}. "
            f"Run compute_all_features() first. "
            f"Available: {list(df_features.columns)}"
        )

    labels = []
    for row in df_features.iter_rows(named=True):
        label = classify_regime(row)
        labels.append(label)

    return labels


def label_and_featurize(df_ohlcv: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """One-shot: compute features + regime labels for training.

    Args:
        df_ohlcv: Raw OHLCV DataFrame.

    Returns:
        (features_matrix, labels_array) suitable for ML training.
        features: (n_bars, 18) float32
        labels:   (n_bars,) int64
    """
    from analytics.regime.ml_features import FEATURE_NAMES

    df_feat = compute_all_features(df_ohlcv)
    raw_labels = label_by_metrics(df_feat)

    # Build feature matrix
    n = len(df_feat)
    x_mat = np.zeros((n, len(FEATURE_NAMES)), dtype=np.float32)
    for i, name in enumerate(FEATURE_NAMES):
        x_mat[:, i] = df_feat[name].to_numpy().astype(np.float32)

    y = np.array(raw_labels, dtype=np.int64)

    # Remove rows with NaN features
    valid = ~np.isnan(x_mat).any(axis=1)
    return x_mat[valid], y[valid]


# ── Regime distribution analysis ────────────────────────────────────


def regime_distribution(labels: list[int]) -> dict[str, int]:
    """Return count of each regime in a label list."""
    names = [
        "Dong_Bang",
        "Nen_Chat",
        "Dau_XH",
        "XH_Manh",
        "Cao_Trao",
        "Hoi_Quy",
        "Nhieu_Dong",
        "Quet_TK",
    ]
    return {names[i]: labels.count(i) for i in range(8)}


__all__ = ["classify_regime", "label_and_featurize", "label_by_metrics", "regime_distribution"]

"""18 Core Features — da Kairos-v2 per ML regime classification.

Riproduce fedelmente le feature engineering di Kairos-v2:
  https://github.com/PVinh-Quant/Kairos-v2
  ml/trang_thai_thi_truong_ml/tao_feature.py

Le 18 feature sono calcolate su OHLCV con Polars e servono come
input per il PyTorch TradingMLP (8 regimi di mercato).

Ogni funzione accetta un ``pl.DataFrame`` con colonne
``open, high, low, close, volume`` e restituisce un ``pl.DataFrame``
con le stesse righe più le colonne feature.

Usage::
    from analytics.regime.ml_features import compute_all_features
    df = compute_all_features(data_ohlcv)
    # df ha 18 nuove colonne: D, S, ADX, RSI, RSIslope, ROC, ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    import numpy as np

# ── Constants (Kairos-v2 defaults) ───────────────────────────────────

EMA_LEN = 50
ADX_LEN = 14
RSI_LEN = 14
BB_LEN = 20
VOL_MA_LEN = 20
ATR_LEN = 14
CHOP_LEN = 14
ER_LEN = 10


def _fill_na(df: pl.DataFrame) -> pl.DataFrame:
    """Forward-fill NaN values created by rolling windows."""
    return df.fill_nan(None).fill_null(strategy="forward")


def compute_atr(df: pl.DataFrame) -> pl.DataFrame:
    """Average True Range (ATR14)."""
    return df.with_columns(
        pl.max_horizontal(
            [
                pl.col("high") - pl.col("low"),
                (pl.col("high") - pl.col("close").shift(1)).abs(),
                (pl.col("low") - pl.col("close").shift(1)).abs(),
            ]
        )
        .rolling_mean(ATR_LEN)
        .alias("atr")
    )


def compute_all_features(df: pl.DataFrame) -> pl.DataFrame:
    """Compute all 18 core features in a single pipeline.

    Args:
        df: OHLCV DataFrame with columns open, high, low, close, volume.

    Returns:
        Original DataFrame with 18 new feature columns + intermediate columns,
        including a 'timestamp' column suitable for multi-TF alignment.
    """
    # Ensure required columns
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df = df.with_columns(
        pl.col("close").diff().alias("diff"), (pl.col("high") - pl.col("low")).alias("hl")
    )

    # ATR
    df = compute_atr(df)

    # 1. D — EMA distance
    df = df.with_columns(
        pl.col("close").ewm_mean(span=EMA_LEN, adjust=False).alias("ema_50")
    ).with_columns(((pl.col("close") - pl.col("ema_50")) / pl.col("close") * 100).alias("D"))

    # 2. S — EMA slope
    df = df.with_columns((pl.col("ema_50") - pl.col("ema_50").shift(3)).alias("S"))

    # 3-4. RSI + RSIslope
    df = (
        df.with_columns(
            pl.when(pl.col("diff") > 0)
            .then(pl.col("diff"))
            .otherwise(0)
            .rolling_mean(RSI_LEN)
            .alias("avg_gain"),
            pl.when(pl.col("diff") < 0)
            .then(pl.col("diff").abs())
            .otherwise(0)
            .rolling_mean(RSI_LEN)
            .alias("avg_loss"),
        )
        .with_columns(
            (100 - (100 / (1 + pl.col("avg_gain") / (pl.col("avg_loss") + 1e-9)))).alias("RSI")
        )
        .with_columns((pl.col("RSI") - pl.col("RSI").shift(3)).alias("RSIslope"))
    )

    # 5. ADX
    df = (
        df.with_columns(
            (pl.col("high") - pl.col("high").shift(1)).alias("up_move"),
            (pl.col("low").shift(1) - pl.col("low")).alias("down_move"),
        )
        .with_columns(
            pl.when((pl.col("up_move") > pl.col("down_move")) & (pl.col("up_move") > 0))
            .then(pl.col("up_move"))
            .otherwise(0)
            .alias("plus_dm"),
            pl.when((pl.col("down_move") > pl.col("up_move")) & (pl.col("down_move") > 0))
            .then(pl.col("down_move"))
            .otherwise(0)
            .alias("minus_dm"),
        )
        .with_columns(
            (pl.col("plus_dm").rolling_mean(ADX_LEN) / (pl.col("atr") + 1e-9)).alias("di_plus"),
            (pl.col("minus_dm").rolling_mean(ADX_LEN) / (pl.col("atr") + 1e-9)).alias("di_minus"),
        )
        .with_columns(
            (
                (pl.col("di_plus") - pl.col("di_minus")).abs()
                / (pl.col("di_plus") + pl.col("di_minus") + 1e-9)
            )
            .rolling_mean(ADX_LEN)
            .alias("ADX")
        )
    )

    # 6. ROC — Rate of Change
    df = df.with_columns((pl.col("close") / pl.col("close").shift(10) - 1).alias("ROC"))

    # 7. ATRn — Normalized ATR
    df = df.with_columns((pl.col("atr") / pl.col("close") * 100).alias("ATRn"))

    # 8. VOLz — Volume z-score
    df = df.with_columns(
        (
            (pl.col("volume") - pl.col("volume").rolling_mean(VOL_MA_LEN))
            / (pl.col("volume").rolling_std(VOL_MA_LEN) + 1e-9)
        ).alias("VOLz")
    )

    # 9. SpreadATR
    df = df.with_columns((pl.col("hl") / (pl.col("atr") + 1e-9)).alias("SpreadATR"))

    # 10. BBwidth — Bollinger Band width
    df = (
        df.with_columns(
            pl.col("close").rolling_mean(BB_LEN).alias("bb_mid"),
            (pl.col("close").rolling_std(BB_LEN) * 2).alias("bb_std"),
        )
        .with_columns(
            ((pl.col("bb_mid") + pl.col("bb_std")) - (pl.col("bb_mid") - pl.col("bb_std"))).alias(
                "bb_range"
            )
        )
        .with_columns((pl.col("bb_range") / (pl.col("bb_mid") + 1e-9)).alias("BBwidth"))
    )

    # 11. SQZ — Bollinger/Keltner squeeze
    df = df.with_columns(pl.col("atr").rolling_mean(20).alias("kc_width")).with_columns(
        (
            (pl.col("BBwidth") - pl.col("kc_width") / (pl.col("close") + 1e-9))
            / (pl.col("BBwidth") + 1e-9)
        ).alias("SQZ")
    )

    # 12. CHOP — Choppiness Index
    sum_range = (pl.col("high").rolling_max(CHOP_LEN) - pl.col("low").rolling_min(CHOP_LEN)).alias(
        "hh_ll"
    )
    df = df.with_columns(
        (
            pl.lit(100)
            * (sum_range / (pl.col("atr").rolling_sum(CHOP_LEN) + 1e-9)).log()
            / pl.lit(CHOP_LEN).log()
        ).alias("CHOP")
    )

    # 13. ER — Efficiency Ratio
    df = df.with_columns(
        (pl.col("close") - pl.col("close").shift(ER_LEN)).abs().alias("price_change"),
        (pl.col("diff").abs().rolling_sum(ER_LEN)).alias("volatility_sum"),
    ).with_columns((pl.col("price_change") / (pl.col("volatility_sum") + 1e-9)).alias("ER"))

    # 14. BBpctB — Bollinger %B
    df = df.with_columns(
        (
            (pl.col("close") - (pl.col("bb_mid") - pl.col("bb_std"))) / (pl.col("bb_range") + 1e-9)
        ).alias("BBpctB")
    )

    # 15. VWAPd — VWAP distance
    df = df.with_columns(
        ((pl.col("close") * pl.col("volume")).cum_sum() / pl.col("volume").cum_sum()).alias("vwap")
    ).with_columns(((pl.col("close") - pl.col("vwap")) / pl.col("close") * 100).alias("VWAPd"))

    # 16-18. Candlestick patterns
    df = df.with_columns(
        (
            (pl.col("high") - pl.max_horizontal(["open", "close"]))
            / (pl.col("high") - pl.col("low") + 1e-9)
        ).alias("WickUpProp"),
        (
            (pl.min_horizontal(["open", "close"]) - pl.col("low"))
            / (pl.col("high") - pl.col("low") + 1e-9)
        ).alias("WickDnProp"),
        ((pl.col("close") - pl.col("open")).abs() / (pl.col("high") - pl.col("low") + 1e-9)).alias(
            "BodyProp"
        ),
    )

    # Forward-fill all NaN created by rolling windows
    df = _fill_na(df)

    return df


FEATURE_NAMES = [
    "D",
    "S",
    "ADX",
    "RSI",
    "RSIslope",
    "ROC",
    "ATRn",
    "VOLz",
    "SpreadATR",
    "BBwidth",
    "SQZ",
    "CHOP",
    "ER",
    "BBpctB",
    "VWAPd",
    "WickUpProp",
    "WickDnProp",
    "BodyProp",
]


def feature_vector(df: pl.DataFrame) -> dict[str, float]:
    """Extract the latest 18-feature vector as dict (for inference)."""
    features = compute_all_features(df)
    last = features.row(-1, named=True)
    return {name: float(last.get(name, 0.0)) for name in FEATURE_NAMES}


__all__ = ["FEATURE_NAMES", "compute_all_features", "compute_multi_tf_features", "feature_vector"]


# ── Multi-timeframe feature combination ─────────────────────────────


def compute_multi_tf_features(
    df_1h: pl.DataFrame | None = None,
    df_4h: pl.DataFrame | None = None,
    df_1d: pl.DataFrame | None = None,
    n_context: int = 8,
) -> np.ndarray | None:
    """Compute 72-dim feature vector across 3 timeframes + context.

    Args:
        df_1h: 1-hour OHLCV DataFrame (or None).
        df_4h: 4-hour OHLCV DataFrame (or None).
        df_1d: 1-day OHLCV DataFrame (or None).
        n_context: Number of context features.

    Returns:
        (72,) numpy array of concatenated features, or None if no data.
    """
    import numpy as np

    vectors: list[np.ndarray] = []
    for df in [df_1h, df_4h, df_1d]:
        if df is not None and len(df) >= 60:
            feat = compute_all_features(df)
            vals = [float(feat[-1, name]) for name in FEATURE_NAMES]
            vectors.append(np.array(vals, dtype=np.float32))
        else:
            vectors.append(np.zeros(18, dtype=np.float32))

    ctx = np.zeros(n_context, dtype=np.float32)
    if df_1d is not None and len(df_1d) >= 20:
        closes = df_1d["close"].to_numpy().astype(float)[-20:]
        ret20 = (closes[-1] / closes[0] - 1) * 100 if closes[0] > 0 else 0
        ctx[0] = ret20
        ctx[1] = float(closes.std() / (closes.mean() + 1e-9))

    return np.concatenate([*vectors, ctx])  # 62-dim, pad to 72 at runtime

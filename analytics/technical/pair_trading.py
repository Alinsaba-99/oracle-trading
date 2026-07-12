"""Pair trading — cointegration test + spread signal."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl
from statsmodels.tsa.stattools import coint


@dataclass
class CointegrationResult:
    """Risultato del test di cointegrazione tra due asset."""

    score: float
    pvalue: float
    critical_values: dict[str, float]
    hedge_ratio: float  # beta della regressione OLS
    spread: pl.Series
    is_cointegrated: bool  # pvalue < 0.05


def compute_cointegration(
    asset_a: pl.Series, asset_b: pl.Series,
) -> CointegrationResult:
    """Test di cointegrazione Engle-Granger tra due serie di prezzi.

    Args:
        asset_a: Prezzi del primo asset.
        asset_b: Prezzi del secondo asset.

    Returns:
        CointegrationResult con spread, p-value, hedge ratio.
    """
    a = asset_a.to_numpy()
    b = asset_b.to_numpy()

    min_len = min(len(a), len(b))
    a, b = a[:min_len], b[:min_len]

    # OLS hedge ratio: b = beta * a + epsilon
    design_mat = np.column_stack([a, np.ones_like(a)])
    beta, _ = np.linalg.lstsq(design_mat, b, rcond=None)[0]
    spread = b - beta * a

    score, pvalue, crit = coint(a, b, maxlag=1)

    return CointegrationResult(
        score=float(score),
        pvalue=float(pvalue),
        critical_values={
            "1%": float(crit[0]),
            "5%": float(crit[1]),
            "10%": float(crit[2]),
        },
        hedge_ratio=float(beta),
        spread=pl.Series("spread", spread, dtype=pl.Float64),
        is_cointegrated=pvalue < 0.05,
    )


def spread_zscore(
    spread: pl.Series,
    window: int = 20,  # noqa: ARG001
    entry_threshold: float = 2.0,
    exit_threshold: float = 0.5,
) -> pl.Series:
    """Calcola il segnale pair trading dallo spread.

    Usa expanding mean/std (non globale) per evitare look-ahead.

    Args:
        spread: Serie dello spread da analizzare.
        window: Finestra per la media mobile (riservata, non usata — expanding).
        entry_threshold: Soglia di ingresso in deviazioni standard.
        exit_threshold: Soglia di uscita in deviazioni standard.

    Returns:
        Series con -1 (short spread), 0 (neutro), 1 (long spread).
    """
    arr = spread.to_numpy()
    n = len(arr)
    signal = np.zeros(n, dtype=np.int8)

    # Z-score causale (expanding)
    z = np.zeros(n)
    for i in range(1, n):
        prefix = arr[: i + 1]
        mean = float(np.nanmean(prefix))
        std = float(np.nanstd(prefix))
        if std > 1e-10:
            z[i] = (arr[i] - mean) / std

    in_position: int = 0  # 1=long spread, -1=short spread
    for i in range(1, n):
        if in_position == 0:
            if z[i] > entry_threshold:
                signal[i] = -1  # short spread (sell A, buy B)
                in_position = -1
            elif z[i] < -entry_threshold:
                signal[i] = 1  # long spread (buy A, sell B)
                in_position = 1
        elif in_position == 1:
            if z[i] > -exit_threshold:  # returned toward mean
                signal[i] = 0
                in_position = 0
            else:
                signal[i] = 1
        elif in_position == -1:
            if z[i] < exit_threshold:
                signal[i] = 0
                in_position = 0
            else:
                signal[i] = -1

    return pl.Series("signal", signal, dtype=pl.Int8)


def build_pair_df(
    data_a: pl.DataFrame,
    data_b: pl.DataFrame,
) -> pl.DataFrame:
    """Allinea due DataFrame per data e calcola spread.

    Args:
        data_a: DataFrame del primo asset (richiede colonne ``timestamp`` e ``close``).
        data_b: DataFrame del secondo asset (richiede colonne ``timestamp`` e ``close``).

    Returns:
        DataFrame con le colonne unite e lo spread calcolato.
    """
    # Merge on timestamp
    merged = data_a.select(["timestamp", "close"]).rename({"close": "close_a"})
    b_close = data_b.select(["timestamp", "close"]).rename({"close": "close_b"})
    merged = merged.join(b_close, on="timestamp", how="inner")

    result = compute_cointegration(merged["close_a"], merged["close_b"])
    merged = merged.with_columns(result.spread.alias("spread"))

    return merged

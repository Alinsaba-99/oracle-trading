"""Frame and array converters — Polars ↔ pandas ↔ NumPy interop.

All analytics code uses Polars as the primary DataFrame. Converters
bridge to pandas (for TA-Lib) and NumPy (for scipy/statsmodels).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl


def to_polars(df: pd.DataFrame | pl.DataFrame | pl.LazyFrame) -> pl.DataFrame:
    """Convert any frame to Polars DataFrame."""
    if isinstance(df, pl.LazyFrame):
        return df.collect()
    if isinstance(df, pd.DataFrame):
        return pl.from_pandas(df)
    return df


def to_pandas(df: pl.DataFrame | pl.LazyFrame) -> pd.DataFrame:
    """Convert Polars frame to pandas (for TA-Lib interop)."""
    if isinstance(df, pl.LazyFrame):
        df = df.collect()
    return df.to_pandas()


def to_numpy_2d(series: pl.Series | pd.Series | np.ndarray) -> np.ndarray:
    """Convert to 2D numpy array for TA-Lib functions."""
    if isinstance(series, pl.Series):
        series = series.to_numpy()
    if isinstance(series, pd.Series):
        series = series.to_numpy()
    return np.asarray(series, dtype=np.float64).reshape(-1, 1)


def from_numpy(arr: np.ndarray, _index: int | None = None) -> pl.Series:
    """Convert numpy array back to Polars Series, handling NaN -> null."""
    arr = np.asarray(arr, dtype=np.float64).ravel()
    cleaned = [None if np.isnan(x) else float(x) for x in arr]
    return pl.Series(values=cleaned, dtype=pl.Float64)


def validate_frame(df: pl.DataFrame, required_columns: list[str]) -> None:
    """Validate a Polars DataFrame has required columns (no silent NaN escalation)."""
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        msg = f"Missing required columns: {missing}"
        raise ValueError(msg)

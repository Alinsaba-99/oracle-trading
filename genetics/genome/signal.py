"""Genome data model, encoding/decoding, and BacktestSignal adapter.

The genome is represented as a normalised NumPy array in [0, 1], with
parameter definitions allowing conversion to and from raw values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import polars as pl

from genetics.genome.codec import clamp, denormalize, normalize
from genetics.genome.parameters import (
    CategoricalParameter,
    ContinuousParameter,
    GenomeParameter,
    IntParameter,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

__all__ = [
    "Genome",
    "GenomeConfig",
    "GenomeToSignal",
    "decode",
    "encode",
    "validate_genome",
]


@dataclass
class Genome:
    """A decoded genome as a normalised parameter vector.

    Attributes:
        normalized_params: 1-D array of parameter values in [0, 1].
        param_defs: Ordered list of parameter definitions.
        names: Parameter names derived from definitions.
    """

    normalized_params: NDArray[np.float64]
    param_defs: Sequence[GenomeParameter]
    names: list[str] = field(init=False)

    def __post_init__(self) -> None:
        self.names = [p.name for p in self.param_defs]


@dataclass
class GenomeConfig:
    """Configuration for a genome definition.

    Attributes:
        n_params: Number of parameters.
        param_defs: Ordered list of parameter definitions.
    """

    n_params: int
    param_defs: Sequence[GenomeParameter]


def encode(
    raw_params_dict: Mapping[str, float | int | str],
    param_defs: Sequence[GenomeParameter],
) -> Genome:
    """Encode a dictionary of raw parameter values into a normalised Genome.

    Args:
        raw_params_dict: Mapping of parameter names to raw values.
        param_defs: Ordered list of parameter definitions.

    Returns:
        A Genome with normalised values in [0, 1].

    Raises:
        ValueError: If a parameter name is missing from the dict, or a
            raw value fails validation.
    """
    normalised: list[float] = []
    for p in param_defs:
        name = p.name
        if name not in raw_params_dict:
            msg = f"Missing parameter {name!r} in raw_params_dict"
            raise ValueError(msg)
        raw = raw_params_dict[name]

        if isinstance(p, CategoricalParameter):
            cat_raw = str(raw)
            if cat_raw not in p.categories:
                msg = f"Invalid category {cat_raw!r} for {name!r}"
                raise ValueError(msg)
            n = len(p.categories)
            idx = p.categories.index(cat_raw)
            cat_norm = idx / (n - 1) if n > 1 else 0.0
            normalised.append(cat_norm)
        else:
            clamped = clamp(float(raw), p)
            normalised.append(normalize(float(clamped), p))

    arr: NDArray[np.float64] = np.array(normalised, dtype=np.float64)
    return Genome(normalized_params=arr, param_defs=param_defs)


def decode(genome: Genome) -> dict[str, float | int | str]:
    """Decode a normalised Genome back into raw parameter values.

    Args:
        genome: The genome to decode.

    Returns:
        Dictionary mapping parameter names to their raw values.
    """
    result: dict[str, float | int | str] = {}
    for i, p in enumerate(genome.param_defs):
        norm_val = float(genome.normalized_params[i])
        result[p.name] = denormalize(norm_val, p)
    return result


def validate_genome(genome: Genome) -> bool:
    """Check whether a genome is structurally valid.

    A valid genome has:
    - The correct number of parameters.
    - All normalised values in [0, 1].
    - No NaN or infinite values.

    Args:
        genome: The genome to validate.

    Returns:
        True if the genome passes all checks.
    """
    expected = len(genome.param_defs)
    if len(genome.normalized_params) != expected:
        return False
    if np.any(np.isnan(genome.normalized_params)):
        return False
    if np.any(np.isinf(genome.normalized_params)):
        return False
    return bool(np.all((genome.normalized_params >= 0.0) & (genome.normalized_params <= 1.0)))


# ── feature set for signal construction ─────────────────────────────


def _compute_features(data: pl.DataFrame) -> list[pl.Series]:
    """Compute a fixed set of price-derived features.

    Returns [returns, momentum, low-vol indicator, SMA-ratio].
    """
    close = data["close"]

    # 1. Short-term returns
    returns = close.diff().fill_null(0.0) / close.shift(1).fill_null(close)
    returns = returns.fill_nan(0.0)

    # 2. Medium-term momentum (10-period)
    momentum = close / close.shift(10).fill_null(close) - 1.0
    momentum = momentum.fill_nan(0.0)

    # 3. Low-volatility indicator
    vol_series = returns.rolling_std(20).fill_nan(0.0)
    vol_max_val = vol_series.max()
    vol_max = float(vol_max_val) if vol_max_val is not None else 0.0  # type: ignore[arg-type]
    if vol_max > 0:
        vol_norm = 1.0 - (vol_series / vol_max)
    else:
        vol_norm = pl.Series("vol_norm", [0.0] * len(data), dtype=pl.Float64)

    # 4. SMA-ratio (vs 20-period)
    sma_20_arr = close.rolling_mean(20).to_numpy()
    close_arr = close.to_numpy()
    sma_20_arr = np.where(np.isnan(sma_20_arr), close_arr, sma_20_arr)
    sma_20 = pl.Series(sma_20_arr)
    sma_ratio = close / sma_20 - 1.0
    sma_ratio = sma_ratio.fill_nan(0.0)

    return [returns, momentum, vol_norm, sma_ratio]


# ── signal adapter ──────────────────────────────────────────────────


class GenomeToSignal:
    """A :class:`BacktestSignal` built from a decoded genome.

    Decodes the genome into raw parameter weights, computes price-derived
    features, combines them with a weighted sum, normalises to [-1, 1],
    and thresholds to produce -1, 0, or 1 signals.
    """

    def __init__(
        self,
        genome: Genome,
        param_defs: Sequence[GenomeParameter],
    ) -> None:
        self._param_defs = param_defs
        self._raw_params = decode(genome)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Compute trading signals from market data.

        Args:
            data: Market data with a 'close' column.

        Returns:
            A Polars Int8 Series with values -1, 0, or 1.
        """
        # Collect numeric weights from decoded parameters
        weights: list[float] = []
        for p in self._param_defs:
            if isinstance(p, (ContinuousParameter, IntParameter)):
                weights.append(float(self._raw_params[p.name]))

        if not weights:
            return pl.Series("signal", [0] * len(data), dtype=pl.Int8)

        features = _compute_features(data)
        feat_count = min(len(features), len(weights))
        w = weights[:feat_count]

        # Weighted sum of features
        n = len(data)
        raw_signal = np.zeros(n, dtype=np.float64)
        for i in range(feat_count):
            raw_signal += w[i] * features[i].to_numpy()

        w_sum = sum(abs(x) for x in w)
        if w_sum == 0:
            return pl.Series("signal", [0] * n, dtype=pl.Int8)

        raw_signal /= w_sum

        # Threshold to -1, 0, 1
        result = np.zeros(n, dtype=np.int8)
        result[raw_signal > 0.3] = 1
        result[raw_signal < -0.3] = -1

        return pl.Series("signal", result, dtype=pl.Int8)


# ── alpha-factor based signal (uses CuratedAlphaLibrary) ─────────────


_CATEGORY_FACTORS: dict[str, str] = {
    "momentum": "roc_1m",
    "mean_reversion": "rsi_14",
    "volatility": "bb_width",
    "correlation": "beta_60",
    "volume": "volume_trend",
    "seasonality": "month_effect",
    "fundamental_proxies": "earnings_yield",
    "microstructure": "amihud_illiquidity",
}
"""One representative factor per category, used by AlphaGenomeToSignal."""


class AlphaGenomeToSignal:
    """A :class:`BacktestSignal` built from genome weights over 50 alpha factors.

    Uses :class:`CuratedAlphaLibrary` to compute one representative factor
    per category (8 categories), then combines them using genome-encoded
    weights and thresholds to produce -1, 0, or 1 trading signals.

    The genome must define weights for each category plus a threshold:

        mom_weight, mr_weight, vol_weight, corr_weight, volu_weight,
        seas_weight, fund_weight, micr_weight, threshold
    """

    _CATEGORY_ORDER = [
        "momentum", "mean_reversion", "volatility", "correlation",
        "volume", "seasonality", "fundamental_proxies", "microstructure",
    ]

    def __init__(
        self,
        genome: Genome,
        param_defs: Sequence[GenomeParameter],
    ) -> None:
        self._raw_params = decode(genome)

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Compute trading signals using alpha factors.

        Args:
            data: OHLCV DataFrame with columns
                [timestamp, open, high, low, close, volume].

        Returns:
            A Polars Int8 Series with values -1, 0, or 1.
        """
        n = len(data)
        if n < 20:
            return pl.Series("signal", [0] * n, dtype=pl.Int8)

        # Compute one factor per category
        try:
            from genetics.alpha.library import CuratedAlphaLibrary

            lib = CuratedAlphaLibrary()
            factor_names = [_CATEGORY_FACTORS[c] for c in self._CATEGORY_ORDER]
            factors = lib.compute(data, names=factor_names)
        except Exception:
            return pl.Series("signal", [0] * n, dtype=pl.Int8)

        # Collect weights from genome parameters (8 category weights)
        weights: list[float] = []
        threshold: float = 0.2
        for p_name in [
            "mom_weight", "mr_weight", "vol_weight", "corr_weight",
            "volu_weight", "seas_weight", "fund_weight", "micr_weight",
        ]:
            raw = self._raw_params.get(p_name, 1.0)
            weights.append(float(raw))
        if "threshold" in self._raw_params:
            threshold = float(self._raw_params["threshold"])

        # Build weighted signal
        raw_signal = np.zeros(n, dtype=np.float64)
        w_sum = 0.0
        for i, name in enumerate(factor_names):
            series = factors.get(name)
            if series is None or len(series) != n:
                continue
            w = weights[i] if i < len(weights) else 0.0
            if w == 0.0:
                continue
            arr = series.to_numpy()
            # Normalize each factor to [0, 1] range
            f_min = np.nanmin(arr)
            f_max = np.nanmax(arr)
            if f_max > f_min:
                normalized = (arr - f_min) / (f_max - f_min)
            else:
                normalized = np.zeros_like(arr)
            normalized = np.nan_to_num(normalized, nan=0.5)
            raw_signal += w * (normalized - 0.5)  # center around 0
            w_sum += w

        if w_sum == 0:
            return pl.Series("signal", [0] * n, dtype=pl.Int8)

        raw_signal /= w_sum

        # Threshold to -1, 0, 1
        result = np.zeros(n, dtype=np.int8)
        result[raw_signal > threshold] = 1
        result[raw_signal < -threshold] = -1

        return pl.Series("signal", result, dtype=pl.Int8)

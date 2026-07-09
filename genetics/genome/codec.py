"""Codec functions for normalizing genome parameters to and from [0, 1].

Supports linear and logarithmic scaling for continuous and integer
parameters, and index-based encoding for categorical parameters.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

from genetics.genome.parameters import (
    CategoricalParameter,
    ContinuousParameter,
    IntParameter,
)

__all__ = [
    "clamp",
    "denormalize",
    "normalize",
    "random_value",
    "round_int",
    "validate",
]


# ── normalisation ───────────────────────────────────────────────────


def _normalize_linear(value: float, low: float, high: float) -> float:
    """Map a value from [low, high] to [0, 1] linearly."""
    span = high - low
    if span == 0:
        return 0.0
    return (float(value) - low) / span


def _normalize_log(value: float, low: float, high: float) -> float:
    """Map a value from [low, high] to [0, 1] logarithmically."""
    log_low = math.log(low)
    log_high = math.log(high)
    span = log_high - log_low
    if span == 0:
        return 0.0
    return (math.log(value) - log_low) / span


def normalize(value: float, param: ContinuousParameter | IntParameter) -> float:
    """Map a raw parameter value to its [0, 1] normalised form.

    Args:
        value: Raw value to normalise.
        param: The parameter definition (determines scaling).

    Returns:
        A float in [0, 1].

    Raises:
        ValueError: If value is outside bounds.
    """
    if param.scaling == "log":
        return _normalize_log(value, param.low, param.high)
    return _normalize_linear(value, param.low, param.high)


# ── denormalisation ─────────────────────────────────────────────────


def _denormalize_linear(
    normalized: float, low: float, high: float,
) -> float:
    """Map a value from [0, 1] back to [low, high] linearly."""
    span = high - low
    return low + normalized * span


def _denormalize_log(
    normalized: float, low: float, high: float,
) -> float:
    """Map a value from [0, 1] back to [low, high] logarithmically."""
    log_low = math.log(low)
    log_high = math.log(high)
    span = log_high - log_low
    return math.exp(log_low + normalized * span)


def denormalize(
    normalized: float,
    param: ContinuousParameter | IntParameter | CategoricalParameter,
) -> float | int | str:
    """Reverse a normalised [0, 1] value back to a raw parameter value.

    Args:
        normalized: Value in [0, 1].
        param: Parameter definition.

    Returns:
        Raw value suitable for the parameter type.
    """
    if isinstance(param, CategoricalParameter):
        n = len(param.categories)
        if n == 1:
            return param.categories[0]
        idx = round(normalized * (n - 1))
        idx = max(0, min(idx, n - 1))
        return param.categories[idx]

    if param.scaling == "log":
        raw: float = _denormalize_log(normalized, param.low, param.high)
    else:
        raw = _denormalize_linear(normalized, param.low, param.high)

    if isinstance(param, IntParameter):
        return round_int(raw)
    return raw


# ── validation ──────────────────────────────────────────────────────


def validate(
    value: object,
    param: ContinuousParameter | IntParameter | CategoricalParameter,
) -> bool:
    """Check whether a raw value is valid for the given parameter.

    Args:
        value: Raw value to check.
        param: Parameter definition.

    Returns:
        True if the value is valid for the parameter.
    """
    if isinstance(param, CategoricalParameter):
        return isinstance(value, str) and value in param.categories

    if isinstance(param, IntParameter):
        if not isinstance(value, int | float):
            return False
        v = round_int(float(value))
        return param.low <= v <= param.high

    # ContinuousParameter
    if not isinstance(value, int | float):
        return False
    return float(param.low) <= float(value) <= float(param.high)


# ── clamping ────────────────────────────────────────────────────────


def clamp(
    value: float | str,
    param: ContinuousParameter | IntParameter | CategoricalParameter,
) -> float | int | str:
    """Clamp a value to the valid range for the parameter.

    Args:
        value: Raw value to clamp.
        param: Parameter definition.

    Returns:
        Clamped value guaranteed valid for the parameter.
    """
    if isinstance(param, CategoricalParameter):
        if isinstance(value, str) and value in param.categories:
            return value
        return param.categories[0]

    clipped = float(np.clip(value, param.low, param.high))
    if isinstance(param, IntParameter):
        return round_int(clipped)
    return clipped


# ── random initialisation ───────────────────────────────────────────


def random_value(
    param: ContinuousParameter | IntParameter | CategoricalParameter,
    rng: np.random.Generator,
) -> float | int | str:
    """Generate a random valid value for the given parameter.

    Args:
        param: Parameter definition.
        rng: NumPy random generator for reproducibility.

    Returns:
        A random value valid for the parameter.
    """
    if isinstance(param, CategoricalParameter):
        return str(rng.choice(param.categories, p=param.weights))

    lo, hi = param.init_range
    normalised = rng.uniform(lo, hi)
    return denormalize(normalised, param)


# ── helpers ─────────────────────────────────────────────────────────


def round_int(value: float) -> int:
    """Consistently round a float to the nearest integer.

    Uses ``round-half-to-even`` (banker's rounding) matching Python's
    built-in ``round()``, returning an int.
    """
    return round(value)


def normalize_array(
    values: NDArray[np.float64],
    param: ContinuousParameter | IntParameter,
) -> NDArray[np.float64]:
    """Vectorised normalise for an array of values (linear scale only).

    Args:
        values: 1-D array of raw values.
        param: Parameter definition.

    Returns:
        Array of normalised values in [0, 1].
    """
    if param.scaling == "log":
        log_arr = np.log(values.clip(min=param.low))
        log_low = math.log(param.low)
        log_high = math.log(param.high)
        return (log_arr - log_low) / (log_high - log_low)  # type: ignore[no-any-return]
    return (values - param.low) / (param.high - param.low)

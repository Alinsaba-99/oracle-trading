"""Prefix invariance test: factor(full_data)[:t] == factor(full_data[:t]).

Ogni operatore deve produrre risultati identici quando calcolato su un
dataset completo e poi troncato, rispetto a calcolarlo direttamente sul
prefisso.  Questo garantisce assenza di look-ahead bias.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import pytest

from genetics.alpha.operators import OPERATORS_MAP

# Generate deterministic test data
np.random.seed(42)
_LONG = np.cumsum(np.random.randn(200)) + 100
_SHORT = _LONG[:50]

# Leaf operator test data (dict-like input)
_LEAF_DATA = pl.DataFrame(
    {
        "open": np.cumsum(np.random.randn(200)) + 100,
        "high": np.cumsum(np.random.randn(200)) + 102,
        "low": np.cumsum(np.random.randn(200)) + 98,
        "close": _LONG,
        "volume": np.abs(np.random.randn(200) * 1000 + 10000),
    }
)

_LEAF_DATA_SHORT = _LEAF_DATA[:50]

# Binary operators
_BINARY_OPS = {"add", "sub", "mul", "div", "gt", "lt", "eq", "and_", "or_", "max", "min"}

# Operators that need a window parameter
_WINDOW_OPS = {
    "ts_mean",
    "ts_std",
    "ts_sum",
    "ts_prod",
    "ts_min",
    "ts_max",
    "ts_argmax",
    "ts_argmin",
    "sma",
    "ema",
    "delta",
}

# Operators that need leaf data (dict/DataFrame)
_LEAF_OPS = {
    "leaf_close",
    "leaf_open",
    "leaf_high",
    "leaf_low",
    "leaf_volume",
    "leaf_returns",
    "leaf_vwap",
}

# Operators needing 2 arrays + window
_JOINT_OPS = {"correlation", "covariance"}


def _call_unary(func: Any, name: str) -> tuple[np.ndarray, np.ndarray]:
    """Call func on both long and short data with appropriate args."""
    if name in _WINDOW_OPS:
        d = 20
        return func(_LONG.copy(), d), func(_SHORT.copy(), d)
    if name in _LEAF_OPS:
        return func(_LEAF_DATA), func(_LEAF_DATA_SHORT)
    if name in _JOINT_OPS:
        d = 20
        return func(_LONG.copy(), _LONG.copy(), d), func(_SHORT.copy(), _SHORT.copy(), d)
    return func(_LONG.copy()), func(_SHORT.copy())


def _call_binary(func: Any, _name: str = "") -> tuple[np.ndarray, np.ndarray]:
    """Call binary func on both long and short data."""
    return func(_LONG.copy(), _LONG.copy()), func(_SHORT.copy(), _SHORT.copy())


@pytest.mark.parametrize("name, func", sorted(OPERATORS_MAP.items()))
def test_prefix_invariance(name: str, func) -> None:
    """Verifica che l'operatore non usi dati futuri."""
    if name in _BINARY_OPS:
        full, prefix = _call_binary(func, name)
    else:
        full, prefix = _call_unary(func, name)

    assert len(full) >= len(prefix), f"{name}: full result shorter than prefix"
    np.testing.assert_array_almost_equal(
        full[: len(prefix)], prefix, decimal=5, err_msg=f"{name}: prefix invariance violated"
    )


def test_rank_prefix_invariance():
    from genetics.alpha.operators import rank

    full = rank(_LONG)
    prefix = rank(_SHORT)
    np.testing.assert_array_almost_equal(full[:50], prefix, decimal=5)


def test_zscore_prefix_invariance():
    from genetics.alpha.operators import zscore

    full = zscore(_LONG)
    prefix = zscore(_SHORT)
    np.testing.assert_array_almost_equal(full[:50], prefix, decimal=5)


def test_scale_prefix_invariance():
    from genetics.alpha.operators import scale

    full = scale(_LONG)
    prefix = scale(_SHORT)
    np.testing.assert_array_almost_equal(full[:50], prefix, decimal=5)


def test_ts_mean_prefix_invariance():
    from genetics.alpha.operators import ts_mean

    full = ts_mean(_LONG, 20)
    prefix = ts_mean(_SHORT, 20)
    np.testing.assert_array_almost_equal(full[:50], prefix, decimal=5)

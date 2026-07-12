"""Tests for PairTradingSignal."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from genetics.genome.pair_signal import PairTradingSignal
from genetics.genome.parameters import ContinuousParameter
from genetics.genome.signal import GenomeConfig, encode


@pytest.fixture
def mean_reverting_data() -> pl.DataFrame:
    """Artificial mean-reverting spread."""
    rng = np.random.default_rng(42)
    spread = np.sin(np.linspace(0, np.pi * 6, 200)) + rng.normal(0, 0.1, 200)
    return pl.DataFrame({"spread": spread})


def test_pair_signal_returns_valid_values(mean_reverting_data):
    p = [
        ContinuousParameter("entry_threshold", low=0.5, high=3.0),
        ContinuousParameter("exit_threshold", low=0.0, high=1.5),
    ]
    _ = GenomeConfig(n_params=2, param_defs=p)
    g = encode({"entry_threshold": 1.5, "exit_threshold": 0.3}, p)
    sig = PairTradingSignal(g, p)
    result = sig.compute(mean_reverting_data)
    assert set(result.to_list()).issubset({-1, 0, 1})
    assert (result != 0).sum() > 0


def test_pair_signal_empty():
    p = [
        ContinuousParameter("entry_threshold", low=0.5, high=3.0),
        ContinuousParameter("exit_threshold", low=0.0, high=1.5),
    ]
    _ = GenomeConfig(n_params=2, param_defs=p)
    g = encode({"entry_threshold": 2.0, "exit_threshold": 0.5}, p)
    sig = PairTradingSignal(g, p)
    result = sig.compute(pl.DataFrame({"close": []}))
    assert len(result) == 0


def test_pair_signal_close_alternative():
    """When no spread column, use close as fallback."""
    data = pl.DataFrame({"close": np.sin(np.linspace(0, np.pi * 3, 100)) + 100})
    p = [
        ContinuousParameter("entry_threshold", low=0.5, high=3.0),
        ContinuousParameter("exit_threshold", low=0.0, high=1.5),
    ]
    _ = GenomeConfig(n_params=2, param_defs=p)
    g = encode({"entry_threshold": 2.0, "exit_threshold": 0.5}, p)
    sig = PairTradingSignal(g, p)
    result = sig.compute(data)
    assert len(result) == 100

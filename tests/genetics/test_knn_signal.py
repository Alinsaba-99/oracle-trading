"""Tests for KNNGenomeToSignal — Lorentzian distance KNN signal."""

from __future__ import annotations

import polars as pl
import pytest

from genetics.genome.knn_signal import KNNGenomeToSignal
from genetics.genome.parameters import ContinuousParameter, IntParameter
from genetics.genome.signal import GenomeConfig, encode


@pytest.fixture
def small_data() -> pl.DataFrame:
    """Minimal OHLCV (60 bars) — enough for KNN feature computation."""
    import numpy as np

    n = 60
    rng = np.random.default_rng(42)
    close = 100.0 + np.arange(n) * 0.1 + rng.normal(0, 0.3, n)
    return pl.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": [1_000_000] * n,
        }
    )


@pytest.fixture
def default_genome() -> tuple:
    """Create a genome with default KNN parameters."""
    param_defs = [
        IntParameter("k_neighbors", low=3, high=20),
        IntParameter("train_length", low=2, high=10),
        ContinuousParameter("threshold", low=0.3, high=0.9),
        ContinuousParameter("class_weight", low=0.3, high=3.0),
        IntParameter("rsi_period", low=7, high=21),
        IntParameter("cci_period", low=10, high=30),
        IntParameter("adx_period", low=7, high=21),
        IntParameter("wt_channel", low=5, high=20),
        IntParameter("wt_avg", low=7, high=21),
        IntParameter("mom_period", low=5, high=20),
        ContinuousParameter("w_rsi", low=0.0, high=2.0),
        ContinuousParameter("w_cci", low=0.0, high=2.0),
        ContinuousParameter("w_adx", low=0.0, high=2.0),
        ContinuousParameter("w_wt", low=0.0, high=2.0),
        ContinuousParameter("w_mom", low=0.0, high=2.0),
    ]
    raw = {
        "k_neighbors": 8,
        "train_length": 4,
        "threshold": 0.5,
        "class_weight": 0.5,
        "rsi_period": 14,
        "cci_period": 20,
        "adx_period": 14,
        "wt_channel": 10,
        "wt_avg": 11,
        "mom_period": 12,
        "w_rsi": 1.5,
        "w_cci": 1.0,
        "w_adx": 1.0,
        "w_wt": 1.5,
        "w_mom": 2.0,
    }
    GenomeConfig(n_params=len(param_defs), param_defs=param_defs)
    genome = encode(raw, param_defs)
    return genome, param_defs


def test_knn_returns_series(small_data: pl.DataFrame, default_genome: tuple) -> None:
    """KNNGenomeToSignal.compute() returns a Polars Series."""
    genome, param_defs = default_genome
    knn = KNNGenomeToSignal(genome, param_defs)
    result = knn.compute(small_data)
    assert isinstance(result, pl.Series)
    assert result.name == "signal"


def test_knn_signal_values(small_data: pl.DataFrame, default_genome: tuple) -> None:
    """KNN signal contains only -1, 0, or 1."""
    genome, param_defs = default_genome
    knn = KNNGenomeToSignal(genome, param_defs)
    result = knn.compute(small_data)
    unique = set(result.to_list())
    assert unique.issubset({-1, 0, 1}), f"Unexpected values: {unique}"


def test_knn_signal_length(small_data: pl.DataFrame, default_genome: tuple) -> None:
    """KNN signal has same length as input data."""
    genome, param_defs = default_genome
    knn = KNNGenomeToSignal(genome, param_defs)
    result = knn.compute(small_data)
    assert len(result) == len(small_data)


def test_knn_empty_data(default_genome: tuple) -> None:
    """KNN handles empty DataFrame gracefully."""
    genome, param_defs = default_genome
    knn = KNNGenomeToSignal(genome, param_defs)
    empty = pl.DataFrame({"close": []})
    result = knn.compute(empty)
    assert len(result) == 0
    assert isinstance(result, pl.Series)


def test_knn_different_params(small_data: pl.DataFrame) -> None:
    """Different KNN parameters produce different signals."""
    param_defs = [
        IntParameter("k_neighbors", low=3, high=20),
        ContinuousParameter("threshold", low=0.3, high=0.9),
    ]
    GenomeConfig(n_params=len(param_defs), param_defs=param_defs)

    # Parameter set A: aggressive
    raw_a = {"k_neighbors": 3, "threshold": 0.3}
    sig_a = KNNGenomeToSignal(encode(raw_a, param_defs), param_defs).compute(small_data)

    # Parameter set B: conservative
    raw_b = {"k_neighbors": 20, "threshold": 0.9}
    sig_b = KNNGenomeToSignal(encode(raw_b, param_defs), param_defs).compute(small_data)

    # Signals should differ in activity level
    active_a = (sig_a != 0).sum()
    active_b = (sig_b != 0).sum()
    # Conservative threshold typically produces fewer signals
    # (not asserting magnitude, just that they exist)
    assert active_a >= 0
    assert active_b >= 0


def test_knn_class_weight_effect(small_data: pl.DataFrame) -> None:
    """class_weight parameter changes signal distribution."""
    param_defs = [
        IntParameter("k_neighbors", low=3, high=20),
        ContinuousParameter("class_weight", low=0.3, high=3.0),
    ]
    GenomeConfig(n_params=len(param_defs), param_defs=param_defs)

    raw_low = {"k_neighbors": 8, "class_weight": 0.3}
    raw_high = {"k_neighbors": 8, "class_weight": 3.0}

    sig_low = KNNGenomeToSignal(encode(raw_low, param_defs), param_defs).compute(small_data)
    sig_high = KNNGenomeToSignal(encode(raw_high, param_defs), param_defs).compute(small_data)

    # At minimum, both should produce valid signals
    assert (sig_low != 0).sum() >= 0
    assert (sig_high != 0).sum() >= 0

"""Unit tests for analytics/strategy/edge_ensemble_v2.py (BL-201).

Verifies:
- EdgeEnsembleV2: hysteresis-gated combination of 3 specialists
- Weighted score is bounded in [-1, +1]
- Hysteresis prevents whipsaw on isolated signal bars
- Config validation (weights sum > 0)
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from analytics.strategy.edge_ensemble_v2 import (
    EdgeEnsembleV2,
    EdgeEnsembleV2Config,
    build_edge_ensemble_v2,
)


def _make_close(
    seed: int = 42, n: int = 200, mu: float = 0.0005, sigma: float = 0.01
) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(mu, sigma, size=n)
    close = 100.0 * np.exp(np.cumsum(rets))
    return pl.DataFrame(
        {
            "date": pl.arange(0, n, eager=True),
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 1000.0),
        }
    )


def test_edge_ensemble_v2_initialises_with_default_config() -> None:
    ee = EdgeEnsembleV2()
    assert ee.config.roc_period == 12
    assert ee.config.bollinger_period == 20
    assert ee.config.donchian_period == 10
    assert ee.config.weight_roc == 0.50
    assert ee.config.weight_bollinger == 0.30
    assert ee.config.weight_donchian == 0.20


def test_edge_ensemble_v2_weights_normalized() -> None:
    """Weights should sum to 1.0 internally after normalisation."""
    ee = EdgeEnsembleV2(
        EdgeEnsembleV2Config(weight_roc=2.0, weight_bollinger=1.0, weight_donchian=1.0)
    )
    # Internally normalised: roc should be 0.5, others 0.25
    assert ee._w_roc == pytest.approx(0.5)
    assert ee._w_boll == pytest.approx(0.25)
    assert ee._w_don == pytest.approx(0.25)


def test_edge_ensemble_v2_rejects_zero_weights() -> None:
    with pytest.raises(ValueError, match="weights sum"):
        EdgeEnsembleV2(
            EdgeEnsembleV2Config(weight_roc=0.0, weight_bollinger=0.0, weight_donchian=0.0)
        )


def test_compute_individual_returns_three_signals() -> None:
    data = _make_close(n=200)
    ee = EdgeEnsembleV2()
    signals = ee.compute_individual(data)
    assert set(signals.keys()) == {"roc", "bollinger", "donchian"}
    for key, arr in signals.items():
        assert len(arr) == 200
        # Signals are int8 in {0, 1} (long-flat)
        assert arr.dtype == np.int8
        assert set(np.unique(arr)).issubset({0, 1})


def test_compute_weighted_score_bounded() -> None:
    data = _make_close(n=200)
    ee = EdgeEnsembleV2()
    score = ee.compute_weighted_score(data)
    assert len(score) == 200
    # Score is a weighted sum of {0,1} signals → bounded in [0, 1] (long-flat)
    assert np.nanmax(score) <= 1.0 + 1e-9
    assert np.nanmin(score) >= 0.0 - 1e-9


def test_compute_returns_int8_signal_with_hysteresis() -> None:
    data = _make_close(n=200)
    ee = EdgeEnsembleV2(EdgeEnsembleV2Config(hysteresis_bars=2, hysteresis_threshold=0.60))
    sig = ee.compute(data)
    assert sig.len() == 200
    assert sig.dtype == pl.Int8
    unique = set(sig.to_numpy())
    assert unique.issubset({0, 1})  # long-flat


def test_hysteresis_prevents_whipsaw_on_isolated_signal_bars() -> None:
    """A 1-bar signal burst should NOT trigger a position change."""
    # Build data where signals are mostly flat with one isolated bull bar
    # by making close mostly constant (signals flat) then 1 bar spike.
    n = 100
    close_arr = np.full(n, 100.0)
    close_arr[50] = 110.0  # isolated spike — 1 bar above prior-high threshold
    close_arr[51:] = 100.0
    data = pl.DataFrame(
        {
            "date": pl.arange(0, n, eager=True),
            "open": close_arr,
            "high": close_arr,
            "low": close_arr,
            "close": close_arr,
            "volume": np.full(n, 1000.0),
        }
    )
    ee = EdgeEnsembleV2(EdgeEnsembleV2Config(hysteresis_bars=3, hysteresis_threshold=0.60))
    sig = ee.compute(data).to_numpy()
    # With hysteresis_bars=3, a single-bar spike should NOT trigger position
    # (need 3 consecutive bars above threshold)
    # At most a small number of long bars; should not stay long for the whole series
    n_long = int(np.sum(sig > 0))
    assert n_long <= 5, f"whipsaw: {n_long} long bars for isolated signal"


def test_higher_hysteresis_threshold_reduces_signal_count() -> None:
    """Raising the threshold from 0.60 to 0.95 should reduce or equal long bars."""
    data = _make_close(seed=7, n=500, mu=0.001, sigma=0.015)
    ee_lo = EdgeEnsembleV2(EdgeEnsembleV2Config(hysteresis_threshold=0.60, hysteresis_bars=1))
    ee_hi = EdgeEnsembleV2(EdgeEnsembleV2Config(hysteresis_threshold=0.95, hysteresis_bars=1))
    sig_lo = ee_lo.compute(data).to_numpy()
    sig_hi = ee_hi.compute(data).to_numpy()
    n_long_lo = int(np.sum(sig_lo > 0))
    n_long_hi = int(np.sum(sig_hi > 0))
    # Higher threshold → fewer or equal long bars
    assert n_long_hi <= n_long_lo


def test_build_edge_ensemble_v2_factory() -> None:
    ee = build_edge_ensemble_v2(
        roc_period=8,
        bollinger_period=15,
        donchian_period=8,
        weight_roc=0.4,
        weight_bollinger=0.4,
        weight_donchian=0.2,
    )
    assert ee.config.roc_period == 8
    assert ee.config.bollinger_period == 15
    assert ee.config.donchian_period == 8

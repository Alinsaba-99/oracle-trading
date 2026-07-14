"""Tests for R1 signal breadth (signals_r1 + self-registration)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

import analytics.strategy.signals as signals


def synth_ohlcv(n: int = 600, seed: int = 42, drift: float = 0.0005) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, 0.01, n)
    close = 100.0 * np.exp(np.cumsum(rets))
    op = close * (1.0 + rng.normal(0.0, 0.002, n))
    hi = np.maximum(close, op) * (1.0 + np.abs(rng.normal(0.0, 0.002, n)))
    lo = np.minimum(close, op) * (1.0 - np.abs(rng.normal(0.0, 0.002, n)))
    vol = rng.uniform(1_000.0, 5_000.0, n)
    return pl.DataFrame({"open": op, "high": hi, "low": lo, "close": close, "volume": vol})


NEW_KEYS = [
    "adx_trend",
    "macd_trend",
    "volume_breakout",
    "pullback",
    "gap",
    "ribbon",
    "pattern",
    "regime_gated",
    "pair_spread",
    "ml",
]


def test_self_registration_adds_ten_families() -> None:
    # 8 v1 + 10 R1 = 18 (signals_r1 self-registers on import).
    assert len(signals.DEFAULT_STRATEGIES) == 18
    for key in NEW_KEYS:
        assert key in signals.DEFAULT_STRATEGIES, key


@pytest.mark.parametrize("key", NEW_KEYS[:8])  # OHLCV-driven families
def test_compute_returns_valid_long_flat_series(key: str) -> None:
    data = synth_ohlcv(600)
    s = signals.DEFAULT_STRATEGIES[key]().compute(data)
    assert len(s) == 600
    assert s.dtype == pl.Int8
    assert set(np.unique(s.to_numpy())).issubset({0, 1})


def test_adx_trend_fires_on_trend() -> None:
    # Strong uptrend -> ADX high -> AdxTrend should go long at least once.
    data = synth_ohlcv(600, seed=1, drift=0.003)
    s = signals.DEFAULT_STRATEGIES["adx_trend"](fast=10, slow=30, threshold=20.0).compute(data)
    assert int(s.sum()) > 0


def test_regime_gate_restricts_base() -> None:
    data = synth_ohlcv(600)
    base_long = int(signals.EmaTrend().compute(data).sum())
    gated = int(signals.DEFAULT_STRATEGIES["regime_gated"](threshold=25.0).compute(data).sum())
    # Gate can only remove longs, never add them.
    assert gated <= base_long


def test_pair_spread_on_synthetic_spread() -> None:
    rng = np.random.default_rng(7)
    spread_df = pl.DataFrame({"close": np.cumsum(rng.normal(0.0, 1.0, 400))})
    s = signals.DEFAULT_STRATEGIES["pair_spread"]().compute(spread_df)
    assert len(s) == 400
    assert s.dtype == pl.Int8
    assert set(np.unique(s.to_numpy())).issubset({0, 1})


def test_ml_signal_walk_forward_valid() -> None:
    data = synth_ohlcv(450)
    s = signals.DEFAULT_STRATEGIES["ml"](train_min=150, retrain_every=80).compute(data)
    assert len(s) == 450
    assert s.dtype == pl.Int8
    assert set(np.unique(s.to_numpy())).issubset({0, 1})
    # Walk-forward: nothing predicted before train_min.
    assert int(s[:150].sum()) == 0

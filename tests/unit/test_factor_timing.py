"""Tests for analytics.strategy.factor_timing — G6-I-01."""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl
import pytest

from analytics.strategy.factor_timing import (
    FactorTimingEngine,
    bh_adjust,
    decay_state,
    ic_pvalue,
    null_ic_benchmark,
    score_factor,
)

# ── effectiveness primitives ─────────────────────────────────────────


class TestEffectiveness:
    """Core scoring functions must match Inalpha semantics."""

    def test_perfect_positive_predictor(self) -> None:
        """A factor perfectly correlated with the NEXT-period return direction
        has rank_ic ≈ 1."""
        rng = np.random.default_rng(0)
        n = 100
        close = pd.Series(100 + np.cumsum(rng.standard_normal(n)))
        # Forward return = close[t+5]/close[t] - 1.  We want a factor that
        # is perfectly rank-correlated with that.
        fwd = close.shift(-5) / close - 1.0
        factor = fwd.fillna(0)  # NaN at tail is dropped by scorer
        eff = score_factor(factor, close, horizon=5, min_samples=10)
        assert eff.rank_ic > 0.99
        assert eff.direction == 1
        assert eff.strength == 1.0

    def test_perfect_negative_predictor(self) -> None:
        """Inverse factor gives rank_ic ≈ -1, direction=-1."""
        rng = np.random.default_rng(0)
        n = 100
        close = pd.Series(100 + np.cumsum(rng.standard_normal(n)))
        fwd = close.shift(-5) / close - 1.0
        factor = -fwd.fillna(0)
        eff = score_factor(factor, close, horizon=5, min_samples=10)
        assert eff.rank_ic < -0.99
        assert eff.direction == -1

    def test_random_factor_low_ic(self) -> None:
        """Noise factor gives rank_ic ≈ 0, direction=0."""
        rng = np.random.default_rng(42)
        n = 200
        close = pd.Series(100 + np.cumsum(rng.standard_normal(n)))
        factor = pd.Series(rng.standard_normal(n))
        eff = score_factor(factor, close, horizon=5, min_samples=10)
        assert abs(eff.rank_ic) < 0.2  # generous bound for noise

    def test_low_confidence_below_min_samples(self) -> None:
        """n < min_samples forces low_confidence=True and direction=0."""
        close = pd.Series(np.linspace(100, 110, 30))
        factor = close.copy()
        eff = score_factor(factor, close, horizon=5, min_samples=60)
        assert eff.low_confidence
        assert eff.direction == 0  # cannot get direction without confidence

    def test_last_h_bars_dropped(self) -> None:
        """The forward return for the last ``horizon`` bars is NaN — no look-ahead."""
        n = 50
        close = pd.Series(np.linspace(100, 200, n))
        factor = close.copy()
        eff = score_factor(factor, close, horizon=5, min_samples=10)
        # Effective sample = n - horizon
        assert eff.sample_size == n - 5

    def test_decay_state_stable(self) -> None:
        assert decay_state(0.10, 0.08) == "stable"

    def test_decay_state_fading(self) -> None:
        assert decay_state(0.10, 0.04) == "fading"

    def test_decay_state_decaying(self) -> None:
        assert decay_state(0.10, -0.05) == "decaying"
        assert decay_state(0.10, 0.0) == "decaying"


class TestNullBenchmark:
    """Null benchmark must scale with candidate count."""

    def test_more_candidates_higher_benchmark(self) -> None:
        b1 = null_ic_benchmark(1, sample_size=200, horizon=5)
        b50 = null_ic_benchmark(50, sample_size=200, horizon=5)
        b500 = null_ic_benchmark(500, sample_size=200, horizon=5)
        assert b1 < b50 < b500

    def test_more_samples_lower_benchmark(self) -> None:
        b_small = null_ic_benchmark(50, sample_size=100, horizon=5)
        b_large = null_ic_benchmark(50, sample_size=1000, horizon=5)
        assert b_small > b_large

    def test_longer_horizon_higher_benchmark(self) -> None:
        """Longer horizon → fewer effective samples → higher noise floor."""
        b1 = null_ic_benchmark(50, sample_size=500, horizon=1)
        b20 = null_ic_benchmark(50, sample_size=500, horizon=20)
        assert b1 < b20

    def test_zero_candidates_zero_benchmark(self) -> None:
        assert null_ic_benchmark(0, 100, 5) == 0.0


class TestBHAdjust:
    """Benjamini-Hochberg FDR correction."""

    def test_empty(self) -> None:
        assert bh_adjust([]) == []

    def test_single_p_unchanged(self) -> None:
        assert bh_adjust([0.05]) == [0.05]

    def test_monotone_inflation(self) -> None:
        """Smallest p inflated least, largest inflated most."""
        p = [0.001, 0.01, 0.05, 0.5]
        adj = bh_adjust(p)
        assert adj[0] <= adj[1] <= adj[2] <= adj[3]
        # BH: adjusted[i] >= p[i]
        for orig, a in zip(p, adj, strict=True):
            assert a >= orig

    def test_order_preserved(self) -> None:
        """Output order matches input order."""
        p = [0.5, 0.001, 0.05, 0.01]
        adj = bh_adjust(p)
        # adj[1] should be the smallest (p[1]=0.001 was smallest)
        assert adj[1] == min(adj)


class TestICPValue:
    """P-value for rank IC."""

    def test_zero_ic_high_p(self) -> None:
        p = ic_pvalue(0.0, sample_size=200, horizon=5)
        assert p > 0.5

    def test_strong_ic_low_p(self) -> None:
        p = ic_pvalue(0.5, sample_size=200, horizon=1)
        assert p < 0.001

    def test_ic_clamped(self) -> None:
        """|ic|=1 would be division by zero — clamped to 0.999999."""
        p = ic_pvalue(1.0, sample_size=200)
        assert 0 <= p <= 1
        assert p < 0.001


# ── FactorTimingEngine ───────────────────────────────────────────────


@pytest.fixture
def ohlcv_df() -> pl.DataFrame:
    """Synthetic OHLCV for catalog probing."""
    rng = np.random.default_rng(7)
    n = 250
    close = 100 + np.cumsum(rng.standard_normal(n) * 0.5)
    high = close + np.abs(rng.standard_normal(n)) * 0.3
    low = close - np.abs(rng.standard_normal(n)) * 0.3
    open_ = close + rng.standard_normal(n) * 0.1
    volume = np.abs(rng.standard_normal(n)) * 1e6
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    return pl.DataFrame(
        {"Date": dates, "Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}
    )


class TestFactorTimingEngine:
    """End-to-end ranking on the genetics/alpha/factors.py catalog."""

    def test_discovers_default_catalog(self) -> None:
        engine = FactorTimingEngine()
        # genetics/alpha/factors.py has 50+ factor functions
        assert len(engine.catalog) >= 40

    def test_rank_returns_sorted_list(self, ohlcv_df: pl.DataFrame) -> None:
        engine = FactorTimingEngine()
        rankings = engine.rank(ohlcv_df, horizon=5)
        assert len(rankings) > 0
        # Sorted by |rank_ic| desc
        ics = [abs(r.effectiveness.rank_ic) for r in rankings]
        assert ics == sorted(ics, reverse=True)

    def test_rank_includes_metadata(self, ohlcv_df: pl.DataFrame) -> None:
        engine = FactorTimingEngine()
        rankings = engine.rank(ohlcv_df, horizon=5)
        r = rankings[0]
        assert r.name
        assert 0 <= r.p_value <= 1
        assert 0 <= r.p_value_bh <= 1
        assert r.effectiveness.sample_size > 0

    def test_rank_with_custom_catalog(self, ohlcv_df: pl.DataFrame) -> None:
        """Custom catalog with one known factor."""
        from genetics.alpha.factors import roc_1m

        engine = FactorTimingEngine(catalog={"roc_1m": roc_1m})
        rankings = engine.rank(ohlcv_df, horizon=5)
        assert len(rankings) == 1
        assert rankings[0].name == "roc_1m"

    def test_skip_errors_true_survives_bad_factor(self, ohlcv_df: pl.DataFrame) -> None:
        def bad_factor(data: pl.DataFrame) -> pl.Series:  # noqa: ARG001
            raise RuntimeError("intentional")

        def good_factor(data: pl.DataFrame) -> pl.Series:
            return data["close"]

        engine = FactorTimingEngine(catalog={"bad": bad_factor, "good": good_factor})
        rankings = engine.rank(ohlcv_df, horizon=5, skip_errors=True)
        # bad is skipped, good is scored
        names = [r.name for r in rankings]
        assert "good" in names
        assert "bad" not in names

    def test_skip_errors_false_raises(self, ohlcv_df: pl.DataFrame) -> None:
        def bad_factor(data: pl.DataFrame) -> pl.Series:  # noqa: ARG001
            raise RuntimeError("intentional")

        engine = FactorTimingEngine(catalog={"bad": bad_factor})
        with pytest.raises(RuntimeError, match="intentional"):
            engine.rank(ohlcv_df, horizon=5, skip_errors=False)

    def test_missing_close_col_raises(self) -> None:
        df = pl.DataFrame({"NotClose": [1.0, 2.0, 3.0]})
        engine = FactorTimingEngine(catalog={})
        with pytest.raises(ValueError, match="close_col"):
            engine.rank(df, close_col="Close")

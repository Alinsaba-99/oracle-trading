"""Tests for FactorPrecomputer — caching, fingerprints, and batch compute."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from genetics.alpha.library import CuratedAlphaLibrary
from genetics.alpha.precompute import FactorPrecomputer


def _timerange(n: int, start: str = "2020-01-01") -> pl.Series:
    """Create a range of n daily timestamps starting at start (UTC)."""
    dt_start = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=UTC)
    dt_end = dt_start + timedelta(days=n - 1)
    return pl.date_range(dt_start, dt_end, interval="1d", eager=True)


def _make_ohlcv(n: int = 150, seed: int = 42) -> pl.DataFrame:
    """Create synthetic OHLCV data."""
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    high = close * (1.0 + rng.uniform(0.002, 0.015, n))
    low = close * (1.0 - rng.uniform(0.002, 0.015, n))
    open_p = close * (1.0 + rng.normal(0, 0.005, n))
    volume = rng.integers(1_000_000, 10_000_000, n)
    high = np.maximum(high, np.maximum(open_p, close))
    low = np.minimum(low, np.minimum(open_p, close))
    return pl.DataFrame({
        "timestamp": _timerange(n),
        "open": pl.Series("open", open_p.tolist()),
        "high": pl.Series("high", high.tolist()),
        "low": pl.Series("low", low.tolist()),
        "close": pl.Series("close", close.tolist()),
        "volume": pl.Series("volume", volume.tolist()),
    })


@pytest.fixture
def library() -> CuratedAlphaLibrary:
    return CuratedAlphaLibrary()


@pytest.fixture
def precomputer(library: CuratedAlphaLibrary) -> FactorPrecomputer:
    return FactorPrecomputer(library, max_cache_size=10)


class TestFactorPrecomputer:
    def test_precompute_all_factors(self, precomputer: FactorPrecomputer) -> None:
        """Precomputation returns all 50 factors."""
        data = _make_ohlcv()
        results = precomputer.precompute(data)
        assert len(results) == 50, f"Expected 50 factors, got {len(results)}"
        for _name, series in results.items():
            assert isinstance(series, pl.Series)
            assert len(series) == len(data)

    def test_cache_hit_returns_same_keys(self, precomputer: FactorPrecomputer) -> None:
        """Identical data should produce a cache hit with same keys."""
        data = _make_ohlcv()
        results1 = precomputer.precompute(data)
        stats1 = precomputer.stats()
        assert stats1["hits"] == 0
        assert stats1["misses"] == 1

        results2 = precomputer.precompute(data)
        stats2 = precomputer.stats()
        assert stats2["hits"] == 1
        assert stats2["misses"] == 1

        # Same keys, same structure
        assert set(results1.keys()) == set(results2.keys())
        # Values should be the same (identical data -> same results)
        for key in results1:
            assert results1[key].to_list() == results2[key].to_list(), (
                f"Cached result differs for {key}"
            )

    def test_cache_hit_returns_copy(self, precomputer: FactorPrecomputer) -> None:
        """Cache hit returns a mutable copy, not the internal cache entry."""
        data = _make_ohlcv()
        results1 = precomputer.precompute(data)
        results2 = precomputer.precompute(data)
        # Modifying one should not affect the other
        if len(results1) > 0 and len(results2) > 0:
            key = next(iter(results1))
            orig = results1[key].to_list()
            results2[key] = pl.Series(key, [0.0] * len(results2[key]))
            assert results1[key].to_list() == orig, (
                "Cache hit returned a shared reference"
            )

    def test_cache_miss_on_new_data(self, precomputer: FactorPrecomputer) -> None:
        """Different data (different seed) triggers a cache miss."""
        data1 = _make_ohlcv(n=150, seed=42)
        data2 = _make_ohlcv(n=150, seed=99)

        results1 = precomputer.precompute(data1)
        stats1 = precomputer.stats()
        assert stats1["hits"] == 0
        assert stats1["misses"] == 1

        results2 = precomputer.precompute(data2)
        stats2 = precomputer.stats()
        assert stats2["hits"] == 0  # no hit — different data
        assert stats2["misses"] == 2

        assert set(results1.keys()) == set(results2.keys())

    def test_cache_miss_different_dates(self, precomputer: FactorPrecomputer) -> None:
        """Same shape/seed but different date range -> different fingerprint -> miss."""
        rng = np.random.default_rng(42)
        n = 150
        close = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
        high = close * 1.01
        low = close * 0.99
        open_p = close * 1.005
        volume = [1000000] * n

        base_data = pl.DataFrame({
            "timestamp": _timerange(n, "2020-01-01"),
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })

        later_data = pl.DataFrame({
            "timestamp": _timerange(n, "2021-01-01"),
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })

        _ = precomputer.precompute(base_data)
        assert precomputer.stats()["misses"] == 1

        _ = precomputer.precompute(later_data)
        assert precomputer.stats()["misses"] == 2, "Different dates should miss cache"

    def test_clear_cache(self, precomputer: FactorPrecomputer) -> None:
        """clear() empties the cache."""
        data = _make_ohlcv()
        _ = precomputer.precompute(data)
        assert precomputer.stats()["cache_size"] == 1
        precomputer.clear()
        assert precomputer.stats()["cache_size"] == 0

        # After clear, next call is a miss
        _ = precomputer.precompute(data)
        assert precomputer.stats()["misses"] == 2  # 1st call + after clear

    def test_cache_eviction_lru(self) -> None:
        """LRU eviction when max_cache_size exceeded."""
        library = CuratedAlphaLibrary()
        precomputer = FactorPrecomputer(library, max_cache_size=3)

        # Load 3 different datasets
        data1 = _make_ohlcv(n=150, seed=1)
        data2 = _make_ohlcv(n=150, seed=2)
        data3 = _make_ohlcv(n=150, seed=3)

        _ = precomputer.precompute(data1)
        _ = precomputer.precompute(data2)
        _ = precomputer.precompute(data3)
        assert precomputer.stats()["cache_size"] == 3

        # data4 should evict data1 (LRU)
        data4 = _make_ohlcv(n=150, seed=4)
        _ = precomputer.precompute(data4)
        assert precomputer.stats()["cache_size"] == 3

        # data1 should be a miss now (evicted)
        _ = precomputer.precompute(data1)
        stats = precomputer.stats()
        # After eviction and re-compute, data1 is a miss
        assert stats["cache_size"] == 3

    def test_stats(self, precomputer: FactorPrecomputer) -> None:
        """stats() returns expected keys and values."""
        stats = precomputer.stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "cache_size" in stats
        assert "max_cache_size" in stats
        assert stats["cache_size"] == 0
        assert stats["max_cache_size"] == 10

    def test_precompute_twice_same(self, precomputer: FactorPrecomputer) -> None:
        """Precomputing same data twice: first call miss, second call hit."""
        data = _make_ohlcv()
        _ = precomputer.precompute(data)
        assert precomputer.stats() == {"hits": 0, "misses": 1, "cache_size": 1, "max_cache_size": 10}

        _ = precomputer.precompute(data)
        assert precomputer.stats()["hits"] == 1
        assert precomputer.stats()["misses"] == 1

    def test_clear_resets_cache_not_counters(self) -> None:
        """clear() removes cache entries but hit/miss counters accumulate."""
        library = CuratedAlphaLibrary()
        pc = FactorPrecomputer(library)
        data = _make_ohlcv()
        _ = pc.precompute(data)
        pc.clear()
        stats = pc.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 1
        assert stats["cache_size"] == 0

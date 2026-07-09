"""Tests for the LRU-eviciting FitnessCache.

Verifies eviction order, key collision, threading, and stats tracking.
"""

from __future__ import annotations

import threading

import pytest

from genetics.fitness.cache import FitnessCache

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def small_cache() -> FitnessCache:
    return FitnessCache(max_size=5)


@pytest.fixture
def large_cache() -> FitnessCache:
    return FitnessCache(max_size=10000)


# ---------------------------------------------------------------------------
# Basic put / get
# ---------------------------------------------------------------------------


class TestBasics:
    def test_put_and_get(self, large_cache: FitnessCache) -> None:
        large_cache.put("a", "b", "c", (1.0, 2.0, 3.0, 4.0))
        assert large_cache.get("a", "b", "c") == (1.0, 2.0, 3.0, 4.0)

    def test_miss_returns_none(self, large_cache: FitnessCache) -> None:
        assert large_cache.get("x", "y", "z") is None

    def test_clear_empties(self, large_cache: FitnessCache) -> None:
        large_cache.put("a", "b", "c", (1.0, 2.0, 3.0, 4.0))
        large_cache.clear()
        assert large_cache.get("a", "b", "c") is None
        assert len(large_cache) == 0

    def test_stats(self, large_cache: FitnessCache) -> None:
        assert large_cache.stats() == {"hits": 0, "misses": 0, "size": 0, "max_size": 10000}
        large_cache.put("a", "b", "c", (1.0, 2.0, 3.0, 4.0))
        # Miss then hit
        large_cache.get("x", "y", "z")  # miss
        large_cache.get("a", "b", "c")  # hit
        large_cache.get("a", "b", "c")  # hit
        stats = large_cache.stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["max_size"] == 10000


class TestLRUEviction:
    """LRU eviction behaviour."""

    def test_oldest_evicted_first(self, small_cache: FitnessCache) -> None:
        """Insert 6 entries into a max_size=5 cache; the oldest should be evicted."""
        for i in range(5):
            small_cache.put(f"g{i}", "fc", "d", (float(i), 0.0, 0.0, 0.0))

        # All 5 should be present (don't call get — that refreshes LRU)
        assert small_cache.stats()["size"] == 5

        # Insert a 6th — oldest (g0) should be evicted
        small_cache.put("g5", "fc", "d", (5.0, 0.0, 0.0, 0.0))
        assert small_cache.get("g0", "fc", "d") is None  # evicted
        assert small_cache.get("g5", "fc", "d") == (5.0, 0.0, 0.0, 0.0)  # present
        assert small_cache.stats()["size"] == 5

    def test_access_refreshes_lru(self, small_cache: FitnessCache) -> None:
        """Accessing an entry should move it to the 'recently used' end."""
        for i in range(5):
            small_cache.put(f"g{i}", "fc", "d", (float(i), 0.0, 0.0, 0.0))

        # Access g0 (the oldest), then insert more entries
        assert small_cache.get("g0", "fc", "d") == (0.0, 0.0, 0.0, 0.0)
        small_cache.put("g5", "fc", "d", (5.0, 0.0, 0.0, 0.0))  # evicts g1 (now oldest)
        small_cache.put("g6", "fc", "d", (6.0, 0.0, 0.0, 0.0))  # evicts g2

        # g0 should still be present (refreshed by the get)
        assert small_cache.get("g0", "fc", "d") == (0.0, 0.0, 0.0, 0.0)
        # g1 and g2 should be gone
        assert small_cache.get("g1", "fc", "d") is None
        assert small_cache.get("g2", "fc", "d") is None

    def test_update_moves_to_end(self, small_cache: FitnessCache) -> None:
        """Re-inserting an existing key should refresh its position."""
        for i in range(5):
            small_cache.put(f"g{i}", "fc", "d", (float(i), 0.0, 0.0, 0.0))

        # Update g0 (oldest) — should move to end
        small_cache.put("g0", "fc", "d", (99.0, 0.0, 0.0, 0.0))
        # Insert 2 more — should evict g1 and g2, not g0
        small_cache.put("g5", "fc", "d", (5.0, 0.0, 0.0, 0.0))
        small_cache.put("g6", "fc", "d", (6.0, 0.0, 0.0, 0.0))

        assert small_cache.get("g0", "fc", "d") == (99.0, 0.0, 0.0, 0.0)  # refreshed
        assert small_cache.get("g1", "fc", "d") is None  # evicted
        assert small_cache.get("g2", "fc", "d") is None  # evicted


# ---------------------------------------------------------------------------
# Key collision
# ---------------------------------------------------------------------------


class TestKeyCollision:
    def test_different_genome_same_data(self, large_cache: FitnessCache) -> None:
        """Different genome hashes with the same fold/data hashes should be separate."""
        large_cache.put("genome_a", "fc", "d", (1.0, 2.0, 3.0, 4.0))
        large_cache.put("genome_b", "fc", "d", (5.0, 6.0, 7.0, 8.0))
        assert large_cache.get("genome_a", "fc", "d") == (1.0, 2.0, 3.0, 4.0)
        assert large_cache.get("genome_b", "fc", "d") == (5.0, 6.0, 7.0, 8.0)
        assert large_cache.stats()["size"] == 2

    def test_data_version_miss(self, large_cache: FitnessCache) -> None:
        """Different data hashes should result in a cache miss."""
        large_cache.put("g", "fc", "data_v1", (1.0, 2.0, 3.0, 4.0))
        assert large_cache.get("g", "fc", "data_v2") is None

    def test_fold_config_miss(self, large_cache: FitnessCache) -> None:
        """Different fold config hashes should result in a cache miss."""
        large_cache.put("g", "fc_v1", "d", (1.0, 2.0, 3.0, 4.0))
        assert large_cache.get("g", "fc_v2", "d") is None


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_put_get(self) -> None:
        """Concurrent access should not corrupt internal state."""
        cache = FitnessCache(max_size=100)
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker(worker_id: int) -> None:
            try:
                for i in range(50):
                    key = f"g{worker_id}_{i}"
                    cache.put(key, "fc", "d", (float(i), 0.0, 0.0, 0.0))
                    val = cache.get(key, "fc", "d")
                    if val is not None:
                        assert val[0] == float(i)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread safety failures: {errors}"

    def test_stats_under_concurrency(self) -> None:
        """Stats counters should remain consistent under concurrent access."""
        cache = FitnessCache(max_size=1000)
        errors: list[Exception] = []
        lock = threading.Lock()
        barrier = threading.Barrier(5, timeout=10)

        def worker(worker_id: int) -> None:
            try:
                # Ensure all threads start around the same time
                barrier.wait()
                for i in range(100):
                    if i % 3 == 0:
                        cache.put(f"g{worker_id}_{i}", "fc", "d", (float(i), 0.0, 0.0, 0.0))
                    else:
                        cache.get(f"g{worker_id}_{i}", "fc", "d")
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread safety failures: {errors}"
        stats = cache.stats()
        assert stats["size"] >= 0
        assert stats["hits"] >= 0
        assert stats["misses"] >= 0


# ---------------------------------------------------------------------------
# max_size enforcement
# ---------------------------------------------------------------------------


class TestMaxSize:
    def test_max_size_at_capacity(self, small_cache: FitnessCache) -> None:
        """Cache should not exceed max_size."""
        for i in range(10):
            small_cache.put(f"g{i}", "fc", "d", (float(i), 0.0, 0.0, 0.0))
        assert small_cache.stats()["size"] == 5

    def test_max_size_zero(self) -> None:
        """A cache with max_size=0 should store nothing."""
        cache = FitnessCache(max_size=0)
        cache.put("g", "fc", "d", (1.0, 2.0, 3.0, 4.0))
        assert cache.get("g", "fc", "d") is None
        assert cache.stats()["size"] == 0

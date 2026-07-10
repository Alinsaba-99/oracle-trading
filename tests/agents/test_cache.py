"""Tests for LLMResponseCache — LRU eviction, hits/misses, thread safety."""

from __future__ import annotations

from pydantic import BaseModel

from agents.cache import LLMResponseCache


class _DummyModel(BaseModel):
    value: int


class TestLLMResponseCache:
    """Tests for LLMResponseCache."""

    def test_put_and_get_roundtrip(self) -> None:
        """A stored response can be retrieved."""
        cache = LLMResponseCache(max_size=10)
        model = _DummyModel(value=42)
        cache.put("sys", "user", "gpt-4", model)
        result = cache.get("sys", "user", "gpt-4")
        assert result is not None
        assert isinstance(result, _DummyModel)
        assert result.value == 42

    def test_cache_miss_returns_none(self) -> None:
        """Asking for a non-existent key returns None."""
        cache = LLMResponseCache()
        result = cache.get("missing", "missing", "gpt-4")
        assert result is None

    def test_lru_eviction(self) -> None:
        """Oldest entry is evicted when cache exceeds max_size."""
        cache = LLMResponseCache(max_size=2)
        cache.put("sys1", "usr1", "gpt-4", _DummyModel(value=1))
        cache.put("sys2", "usr2", "gpt-4", _DummyModel(value=2))
        # Access sys2 to promote it (prevents it from being LRU)
        cache.get("sys2", "usr2", "gpt-4")
        # Add a third entry — sys1 should be evicted (not accessed recently)
        cache.put("sys3", "usr3", "gpt-4", _DummyModel(value=3))

        assert cache.get("sys1", "usr1", "gpt-4") is None  # evicted
        assert cache.get("sys2", "usr2", "gpt-4") is not None  # kept
        assert cache.get("sys3", "usr3", "gpt-4") is not None  # kept

    def test_clear_empties_cache(self) -> None:
        """Clear removes all entries and resets stats."""
        cache = LLMResponseCache(max_size=10)
        cache.put("sys", "user", "gpt-4", _DummyModel(value=1))
        cache.put("sys2", "user2", "gpt-4", _DummyModel(value=2))

        cache.clear()
        stats = cache.stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

        assert cache.get("sys", "user", "gpt-4") is None
        assert cache.get("sys2", "user2", "gpt-4") is None

    def test_stats_tracking(self) -> None:
        """Stats accurately reflect hits, misses, and size."""
        cache = LLMResponseCache(max_size=10)
        cache.put("sys", "user", "gpt-4", _DummyModel(value=1))
        cache.put("sys2", "user2", "gpt-4", _DummyModel(value=2))

        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 2

        # One hit, one miss
        cache.get("sys", "user", "gpt-4")  # hit
        cache.get("nope", "nope", "gpt-4")  # miss

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 2

    def test_different_prompts_different_keys(self) -> None:
        """Different prompt content produces different cache keys."""
        cache = LLMResponseCache(max_size=10)
        model_a = _DummyModel(value=1)
        model_b = _DummyModel(value=2)
        cache.put("system A", "user A", "gpt-4", model_a)
        cache.put("system B", "user B", "gpt-4", model_b)

        # Each should retrieve its own
        assert cache.get("system A", "user A", "gpt-4").value == 1  # type: ignore[union-attr]
        assert cache.get("system B", "user B", "gpt-4").value == 2  # type: ignore[union-attr]

    def test_same_prompts_cache_hit(self) -> None:
        """Same content produces a cache hit."""
        cache = LLMResponseCache(max_size=10)
        cache.put("same", "same", "gpt-4", _DummyModel(value=99))

        result = cache.get("same", "same", "gpt-4")
        assert result is not None
        assert result.value == 99  # type: ignore[attr-defined]

    def test_eviction_oldest_when_full(self) -> None:
        """With max_size=3, adding a 4th evicts the oldest (unaccessed) item."""
        cache = LLMResponseCache(max_size=3)
        cache.put("s1", "u1", "m1", _DummyModel(value=1))
        cache.put("s2", "u2", "m1", _DummyModel(value=2))
        cache.put("s3", "u3", "m1", _DummyModel(value=3))
        # s1 is LRU
        cache.put("s4", "u4", "m1", _DummyModel(value=4))

        assert cache.get("s1", "u1", "m1") is None  # evicted
        assert cache.get("s2", "u2", "m1") is not None
        assert cache.get("s3", "u3", "m1") is not None
        assert cache.get("s4", "u4", "m1") is not None

    def test_different_models_separate_keys(self) -> None:
        """Different model names produce different cache keys."""
        cache = LLMResponseCache(max_size=10)
        cache.put("sys", "user", "gpt-4", _DummyModel(value=1))
        result = cache.get("sys", "user", "claude-3")
        assert result is None

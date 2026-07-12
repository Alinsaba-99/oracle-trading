"""LRU cache for LLM responses with prompt hashing and thread safety."""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel

from core.logging import get_logger

logger = get_logger("oracle.agents")

__all__ = ["LLMResponseCache"]


class LLMResponseCache:
    """LRU cache for LLM responses keyed by prompt hashes and model name.

    Uses SHA256 for prompt content hashing. LRU eviction when max_size is
    exceeded. Thread-safe via threading.Lock.
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._max_size = max_size
        self._cache: OrderedDict[str, BaseModel] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(system_prompt: str, user_prompt: str, model: str) -> str:
        system_hash = hashlib.sha256(system_prompt.encode()).hexdigest()
        user_hash = hashlib.sha256(user_prompt.encode()).hexdigest()
        return f"{system_hash}:{user_hash}:{model}"

    def get(self, system_prompt: str, user_prompt: str, model: str) -> BaseModel | None:
        """Retrieve a cached response, or None if not cached."""
        key = self._make_key(system_prompt, user_prompt, model)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def put(self, system_prompt: str, user_prompt: str, model: str, response: BaseModel) -> None:
        """Store a response in the cache, evicting LRU entries if necessary."""
        key = self._make_key(system_prompt, user_prompt, model)
        with self._lock:
            self._cache[key] = response
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cached entries and reset statistics."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int]:
        """Return current cache statistics."""
        with self._lock:
            return {"hits": self._hits, "misses": self._misses, "size": len(self._cache)}

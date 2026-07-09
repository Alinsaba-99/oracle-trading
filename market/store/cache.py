"""Thread-safe LRU cache for hot feature DataFrames."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict

import polars as pl


class FeatureLRUCache:
    """Thread-safe LRU cache for Polars DataFrames with TTL expiry.

    Uses an ``OrderedDict`` for O(1) move-to-end on access and O(1)
    eviction of the least-recently-used entry when at capacity.

    Parameters
    ----------
    max_size:
        Maximum number of entries before eviction (oldest dropped).
    ttl_seconds:
        Default time-to-live in seconds; per-item TTL may be passed
        to :meth:`put`.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int | float = 300) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[pl.DataFrame, float, float]] = OrderedDict()
        self._lock = threading.RLock()

    def put(self, key: str, df: pl.DataFrame, ttl: int | float | None = None) -> None:
        """Store *df* under *key* with optional per-item TTL (seconds).

        If the key already exists its entry is refreshed; when the cache
        is full the least-recently-used entry is evicted.
        """
        expires_at = time.monotonic() + (ttl if ttl is not None else self._ttl_seconds)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (df, time.monotonic(), expires_at)

    def get(self, key: str) -> pl.DataFrame | None:
        """Return the cached DataFrame, or ``None`` if missing / expired.

        On a hit the entry is moved to the end (most recently used) and
        returned; expired entries are removed on access.
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            df, _stored_at, expires_at = entry
            if time.monotonic() > expires_at:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return df

    def invalidate(self, key: str) -> None:
        """Remove *key* from the cache if present."""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Evict every cached entry."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        with self._lock:
            return len(self._cache)

"""FactorPrecomputer — batch computation with LRU caching.

Computes all 50 curated alpha factors in one pass, keyed by a
data fingerprint (SHA-256 of data shape, date range, and symbol).
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import TYPE_CHECKING

import numpy as np
import polars as pl

if TYPE_CHECKING:
    from genetics.alpha.library import CuratedAlphaLibrary

FactorCache = OrderedDict[str, dict[str, pl.Series]]


def _fingerprint(data: pl.DataFrame) -> str:
    """Create a deterministic hash fingerprint for a DataFrame.

    Incorporates shape, column names, date range, null counts,
    and data content (numeric mean/std/sum) to distinguish
    data that differs in values but not structure.
    """
    hasher = hashlib.sha256()
    hasher.update(f"{data.shape[0]}:{data.shape[1]}".encode())
    for col in data.columns:
        hasher.update(col.encode())
    if "timestamp" in data.columns:
        ts = data["timestamp"]
        if len(ts) > 0:
            hasher.update(str(ts[0]).encode())
            hasher.update(str(ts[-1]).encode())
    # Include null counts
    null_counts = data.null_count()
    for v in null_counts.row(0):
        hasher.update(str(v).encode())
    # Include actual data content via summary stats
    numeric_cols = [c for c in data.columns if c != "timestamp"]
    for col in numeric_cols:
        series = data[col]
        if len(series) > 0:
            arr = series.to_numpy()
            hasher.update(f"{np.nanmean(arr):.6f}".encode())
            hasher.update(f"{np.nanstd(arr):.6f}".encode())
            hasher.update(f"{np.nansum(arr):.6f}".encode())
    return hasher.hexdigest()


class FactorPrecomputer:
    """Precomputes all alpha factors with LRU caching.

    Caches factor results keyed by a data fingerprint (SHA-256).
    Cache entries are evicted LRU-style when max_cache_size is exceeded.

    Args:
        library: CuratedAlphaLibrary instance providing factor functions.
        max_cache_size: Maximum number of cache entries (default 100).
    """

    def __init__(self, library: CuratedAlphaLibrary, max_cache_size: int = 100) -> None:
        self._library = library
        self._max_cache_size = max(1, max_cache_size)
        self._cache: FactorCache = OrderedDict()
        self._hits: int = 0
        self._misses: int = 0

    def precompute(self, data: pl.DataFrame) -> dict[str, pl.Series]:
        """Compute ALL factors in one pass, using cache if available.

        Args:
            data: OHLCV DataFrame with columns
                  [timestamp, open, high, low, close, volume].

        Returns:
            Dict mapping all 50 factor names to their Series.
        """
        key = _fingerprint(data)

        if key in self._cache:
            self._hits += 1
            self._cache.move_to_end(key)
            return dict(self._cache[key])

        self._misses += 1
        results = self._library.compute(data)

        # Store in cache
        self._cache[key] = results
        if len(self._cache) > self._max_cache_size:
            self._cache.popitem(last=False)

        return dict(results)

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

    def stats(self) -> dict[str, int]:
        """Return cache hit/miss statistics.

        Returns:
            Dict with keys: hits, misses, cache_size, max_cache_size.
        """
        return {
            "hits": self._hits,
            "misses": self._misses,
            "cache_size": len(self._cache),
            "max_cache_size": self._max_cache_size,
        }

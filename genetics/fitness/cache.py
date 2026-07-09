"""Fitness caching with LRU eviction.

Thread-safe cache keyed by ``(genome_hash, fold_config_hash, data_hash)``.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict

import numpy as np

from genetics.genome.signal import Genome

FitnessValue = tuple[float, float, float, float]


def genome_hash(genome: Genome) -> str:
    """SHA-256 of a genome's normalised parameter vector."""
    return hashlib.sha256(
        np.ascontiguousarray(genome.normalized_params).tobytes(),
    ).hexdigest()


def fold_config_hash(n_splits: int, purge_window: int, embargo: int) -> str:
    """SHA-256 of the walk-forward fold configuration."""
    raw = f"{n_splits}:{purge_window}:{embargo}"
    return hashlib.sha256(raw.encode()).hexdigest()


class FitnessCache:
    """LRU-evicting cache for (genome x fold-config x data) -> fitness tuples.

    Thread-safe via ``threading.Lock``.
    """

    def __init__(self, max_size: int = 10000) -> None:
        self._max_size = max_size
        self._lock = threading.Lock()
        self._data: OrderedDict[str, FitnessValue] = OrderedDict()
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        genome_hash: str,
        fold_config_hash: str,
        data_hash: str,
    ) -> FitnessValue | None:
        """Look up a cached fitness value.

        Returns ``None`` on cache miss.
        """
        key = self._make_key(genome_hash, fold_config_hash, data_hash)
        with self._lock:
            if key in self._data:
                self._hits += 1
                self._data.move_to_end(key)
                return self._data[key]
            self._misses += 1
            return None

    def put(
        self,
        genome_hash: str,
        fold_config_hash: str,
        data_hash: str,
        fitness: FitnessValue,
    ) -> None:
        """Insert a fitness value, evicting LRU entries if at capacity."""
        key = self._make_key(genome_hash, fold_config_hash, data_hash)
        with self._lock:
            if self._max_size <= 0:
                return
            if key in self._data:
                self._data.move_to_end(key)
            else:
                while len(self._data) >= self._max_size:
                    self._data.popitem(last=False)
            self._data[key] = fitness

    def clear(self) -> None:
        """Remove all entries and reset statistics."""
        with self._lock:
            self._data.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int]:
        """Return current cache statistics.

        Returns
        -------
        dict
            Keys: ``hits``, ``misses``, ``size``, ``max_size``.
        """
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._data),
                "max_size": self._max_size,
            }

    def __len__(self) -> int:
        return len(self._data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(
        genome_hash: str,
        fold_config_hash: str,
        data_hash: str,
    ) -> str:
        return f"{genome_hash}:{fold_config_hash}:{data_hash}"

"""FeatureStore — Parquet-backed feature store with LRU caching.

Long-format schema
------------------
All Parquet files use a uniform long-format layout with columns::

    instrument_id  |  timestamp  |  feature_name  |  value  |  version

Files are stored at ``{path}/{feature_set}/{version}/{instrument_id}.parquet``.

Thread safety
-------------
Each feature set has its own ``asyncio.Lock`` for write serialisation.
Reads are lock-free and hit the LRU cache before touching disk.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import polars as pl

from market.store.cache import FeatureLRUCache
from market.store.schema import FeatureSetVersion


class FeatureStore:
    """Parquet-backed feature store with per-feature-set write locking.

    Parameters
    ----------
    path:
        Root directory for Parquet files.  Created on init if it does
        not exist.
    cache:
        Optional pre-configured :class:`FeatureLRUCache`.  A default
        instance (1000 entries, 300 s TTL) is created when omitted.
    """

    REQUIRED_COLUMNS = frozenset({"instrument_id", "timestamp", "feature_name", "value"})

    def __init__(self, path: Path, cache: FeatureLRUCache | None = None) -> None:
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._cache = cache or FeatureLRUCache()
        self._locks: dict[str, asyncio.Lock] = {}
        self._freshness: dict[str, dict[str, datetime]] = {}
        self._schemas: dict[str, dict[str, FeatureSetVersion]] = {}

    # ------------------------------------------------------------------
    # Schema registration
    # ------------------------------------------------------------------

    def register_feature_set(
        self, feature_set: str, version: str, schema: dict[str, Any]
    ) -> FeatureSetVersion:
        """Register a versioned schema for *feature_set*.

        The *schema* dictionary **must** contain the keys ``feature_names``
        and ``instrument_ids``, each a ``list[str]``.
        """
        feature_names = list(schema.get("feature_names", []))
        instrument_ids = list(schema.get("instrument_ids", []))

        created_at = datetime.now(UTC)
        raw = f"{feature_set}:{version}:{sorted(feature_names)}:{sorted(instrument_ids)}"
        schema_hash = sha256(raw.encode()).hexdigest()[:16]

        fsv = FeatureSetVersion(
            version_id=version,
            feature_names=feature_names,
            instrument_ids=instrument_ids,
            created_at=created_at,
            schema_hash=schema_hash,
            feature_count=len(feature_names),
            row_count=len(feature_names) * len(instrument_ids),
        )

        self._schemas.setdefault(feature_set, {})[version] = fsv
        return fsv

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def write_features(
        self, feature_set: str, version: str, df: pl.DataFrame, instrument_id: str
    ) -> None:
        """Write features for a single instrument to Parquet.

        Acquires a per-*feature_set* ``asyncio.Lock`` to serialise
        concurrent writes.  The DataFrame **must** contain the columns
        ``instrument_id``, ``timestamp``, ``feature_name``, ``value``.
        """
        self._validate_df_columns(df)

        if feature_set in self._schemas and version in self._schemas[feature_set]:
            fsv = self._schemas[feature_set][version]
            if "feature_name" in df.columns:
                names_in_df = df["feature_name"].unique().to_list()
                unknown = [n for n in names_in_df if n not in fsv.feature_names]
                if unknown:
                    msg = f"Unknown features in write: {unknown}. Registered: {fsv.feature_names}"
                    raise ValueError(msg)

        version_dir = self._path / feature_set / version
        lock = self._get_lock(feature_set)
        async with lock:
            version_dir.mkdir(parents=True, exist_ok=True)
            parquet_path = version_dir / f"{instrument_id}.parquet"
            df.write_parquet(str(parquet_path))
            self._freshness.setdefault(feature_set, {})[version] = datetime.now(UTC)

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    async def read_features(
        self,
        feature_set: str,
        version: str | None = None,
        instrument_ids: list[str] | None = None,
        max_age: int | None = None,
    ) -> pl.DataFrame:
        """Read features, checking the LRU cache first.

        On a cache miss the method falls back to scanning on-disk
        Parquet files with Polars.  When *max_age* is provided stale
        entries are invalidated before returning.
        """
        cache_key = self._make_cache_key(feature_set, version)

        stale = (
            max_age is not None
            and version is not None
            and self.is_stale(feature_set, version, max_age)
        )
        if stale:
            self._cache.invalidate(cache_key)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        result = self._read_from_disk(feature_set, version, instrument_ids)
        self._cache.put(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_freshness(self, feature_set: str) -> dict[str, datetime]:
        """Return ``{version: last_write_timestamp}`` for *feature_set*."""
        return dict(self._freshness.get(feature_set, {}))

    def is_stale(self, feature_set: str, version: str, max_age_seconds: int) -> bool:
        """Return ``True`` if *version* has not been updated within *max_age_seconds*."""
        freshness = self._freshness.get(feature_set, {})
        last_write = freshness.get(version)
        if last_write is None:
            return True
        elapsed = (datetime.now(UTC) - last_write).total_seconds()
        return elapsed > max_age_seconds

    def list_versions(self, feature_set: str) -> list[FeatureSetVersion]:
        """Return all registered :class:`FeatureSetVersion` objects for *feature_set*."""
        versions = self._schemas.get(feature_set, {})
        return list(versions.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_lock(self, feature_set: str) -> asyncio.Lock:
        if feature_set not in self._locks:
            self._locks[feature_set] = asyncio.Lock()
        return self._locks[feature_set]

    @staticmethod
    def _make_cache_key(feature_set: str, version: str | None) -> str:
        return f"{feature_set}:{version or 'latest'}"

    def _validate_df_columns(self, df: pl.DataFrame) -> None:
        missing = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            msg = f"Missing required columns: {missing}"
            raise ValueError(msg)

    def _read_from_disk(
        self, feature_set: str, version: str | None, instrument_ids: list[str] | None
    ) -> pl.DataFrame:
        """Scan Parquet files from disk — fallback path."""
        version_dirs: list[Path] = []

        if version:
            vd = self._path / feature_set / version
            if vd.exists():
                version_dirs.append(vd)
        else:
            base = self._path / feature_set
            if base.exists():
                version_dirs = sorted([d for d in base.iterdir() if d.is_dir()], reverse=True)[
                    :1
                ]  # latest version only

        frames: list[pl.DataFrame] = []
        for vd in version_dirs:
            if instrument_ids:
                paths = [
                    vd / f"{iid}.parquet"
                    for iid in instrument_ids
                    if (vd / f"{iid}.parquet").exists()
                ]
            else:
                paths = list(vd.glob("*.parquet"))

            for p in paths:
                try:
                    frames.append(pl.read_parquet(str(p)))
                except Exception:
                    continue

        if not frames:
            return pl.DataFrame()
        return pl.concat(frames)

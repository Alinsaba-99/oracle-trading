"""Tests for M3 Feature Store — FeatureLRUCache, FeatureStore, DuckDBQuery."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from market.store import FeatureLRUCache, FeatureSetVersion, FeatureStore
from market.store.duckdb_query import DuckDBQuery

# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def tmp_store(tmp_path: Path) -> FeatureStore:
    return FeatureStore(path=tmp_path / "features")


@pytest.fixture
def cache() -> FeatureLRUCache:
    return FeatureLRUCache(max_size=10, ttl_seconds=60)


@pytest.fixture
def sample_df() -> pl.DataFrame:
    ts = datetime.now(UTC)
    return pl.DataFrame(
        {
            "instrument_id": ["AAPL"] * 3,
            "timestamp": [ts] * 3,
            "feature_name": ["sma_20", "ema_10", "rsi_14"],
            "value": [150.0, 151.0, 55.0],
            "version": ["1.0.0"] * 3,
        }
    )


# ======================================================================
# FeatureSetVersion
# ======================================================================


class TestFeatureSetVersion:
    def test_create_deduplicates_and_sorts(self) -> None:
        fsv = FeatureSetVersion.create(
            version_id="1.0.0",
            feature_names=["b", "a", "b"],  # duplicate + unsorted
            instrument_ids=["MSFT", "AAPL"],
        )
        assert fsv.feature_names == ["a", "b"]
        assert fsv.instrument_ids == ["AAPL", "MSFT"]
        assert fsv.feature_count == 2
        assert fsv.row_count == 4
        assert fsv.schema_hash  # non-empty hex string

    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValueError, match="Naive datetime"):
            FeatureSetVersion(
                version_id="1",
                feature_names=["x"],
                instrument_ids=["A"],
                created_at=datetime(2025, 1, 1),  # no tz
                schema_hash="abc",
                feature_count=1,
                row_count=1,
            )

    def test_accepts_utc_datetime(self) -> None:
        fsv = FeatureSetVersion(
            version_id="1",
            feature_names=["x"],
            instrument_ids=["A"],
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            schema_hash="abc",
            feature_count=1,
            row_count=1,
        )
        assert fsv.created_at.tzinfo is not None


# ======================================================================
# FeatureLRUCache
# ======================================================================


class TestFeatureLRUCache:
    def test_put_and_get(self, cache: FeatureLRUCache) -> None:
        df = pl.DataFrame({"a": [1, 2, 3]})
        cache.put("key1", df)
        result = cache.get("key1")
        assert result is not None
        assert result.shape == (3, 1)

    def test_get_missing_returns_none(self, cache: FeatureLRUCache) -> None:
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self) -> None:
        short_cache = FeatureLRUCache(max_size=10, ttl_seconds=0.1)
        short_cache.put("key", pl.DataFrame({"x": [1]}))
        time.sleep(0.15)
        assert short_cache.get("key") is None

    def test_per_item_ttl(self) -> None:
        cache = FeatureLRUCache(max_size=10, ttl_seconds=60)
        cache.put("short", pl.DataFrame({"x": [1]}), ttl=0.1)
        time.sleep(0.15)
        assert cache.get("short") is None

        # default TTL should still be alive
        cache.put("long", pl.DataFrame({"x": [2]}))
        assert cache.get("long") is not None

    def test_eviction_lru(self) -> None:
        small_cache = FeatureLRUCache(max_size=3, ttl_seconds=60)
        for i in range(4):
            small_cache.put(f"k{i}", pl.DataFrame({"x": [i]}))
        # k0 should be evicted, k1-k3 should be present
        assert small_cache.get("k0") is None
        assert small_cache.get("k1") is not None
        assert small_cache.get("k2") is not None
        assert small_cache.get("k3") is not None

    def test_invalidate(self, cache: FeatureLRUCache) -> None:
        cache.put("key", pl.DataFrame({"x": [1]}))
        assert cache.get("key") is not None
        cache.invalidate("key")
        assert cache.get("key") is None

    def test_clear(self, cache: FeatureLRUCache) -> None:
        cache.put("a", pl.DataFrame({"x": [1]}))
        cache.put("b", pl.DataFrame({"x": [2]}))
        cache.clear()
        assert cache.size == 0

    def test_refresh_on_get(self) -> None:
        """Accessing an entry moves it to MRU end."""
        cache = FeatureLRUCache(max_size=2, ttl_seconds=60)
        cache.put("a", pl.DataFrame({"x": [1]}))
        cache.put("b", pl.DataFrame({"x": [2]}))
        cache.get("a")  # refresh a
        cache.put("c", pl.DataFrame({"x": [3]}))  # evicts b (LRU)
        assert cache.get("a") is not None
        assert cache.get("b") is None
        assert cache.get("c") is not None

    def test_size_property(self, cache: FeatureLRUCache) -> None:
        assert cache.size == 0
        cache.put("a", pl.DataFrame({"x": [1]}))
        assert cache.size == 1
        cache.put("b", pl.DataFrame({"x": [2]}))
        assert cache.size == 2


# ======================================================================
# FeatureStore
# ======================================================================


class TestFeatureStoreSchemaValidation:
    async def test_rejects_missing_columns(
        self, tmp_store: FeatureStore, sample_df: pl.DataFrame
    ) -> None:
        bad_df = sample_df.drop("value")
        with pytest.raises(ValueError, match="Missing required columns"):
            await tmp_store.write_features("test_fs", "1.0.0", bad_df, "AAPL")

    async def test_rejects_unregistered_features(self, tmp_store: FeatureStore) -> None:
        tmp_store.register_feature_set(
            "fs1", "1.0", {"feature_names": ["sma_20"], "instrument_ids": ["AAPL"]}
        )
        ts = datetime.now(UTC)
        df = pl.DataFrame(
            {
                "instrument_id": ["AAPL"],
                "timestamp": [ts],
                "feature_name": ["unknown_feat"],
                "value": [1.0],
                "version": ["1.0"],
            }
        )
        with pytest.raises(ValueError, match="Unknown features"):
            await tmp_store.write_features("fs1", "1.0", df, "AAPL")

    async def test_write_unregistered_passes(
        self, tmp_store: FeatureStore, sample_df: pl.DataFrame
    ) -> None:
        """Writing to an unregistered feature set should succeed (just without schema guard)."""
        await tmp_store.write_features("unregistered", "1.0.0", sample_df, "AAPL")
        fs_dir = tmp_store._path / "unregistered" / "1.0.0"
        assert (fs_dir / "AAPL.parquet").exists()


class TestFeatureStoreRoundTrip:
    async def test_write_then_read(self, tmp_store: FeatureStore, sample_df: pl.DataFrame) -> None:
        await tmp_store.write_features("tech", "1.0.0", sample_df, "AAPL")
        result = await tmp_store.read_features("tech", "1.0.0")
        assert len(result) == 3
        assert set(result["feature_name"].to_list()) == {"sma_20", "ema_10", "rsi_14"}

    async def test_read_caches_result(
        self, tmp_store: FeatureStore, sample_df: pl.DataFrame
    ) -> None:
        await tmp_store.write_features("cached", "1.0", sample_df, "AAPL")
        cache_key = "cached:1.0"

        # First read — cache miss, populates cache
        result1 = await tmp_store.read_features("cached", "1.0")
        assert len(result1) == 3

        # Verify cache contains the result
        cached = tmp_store._cache.get(cache_key)
        assert cached is not None
        assert len(cached) == 3

    async def test_read_latest_version(self, tmp_store: FeatureStore) -> None:
        """When version is None, read from the latest version directory."""
        ts = datetime.now(UTC)
        v1 = pl.DataFrame(
            {
                "instrument_id": ["AAPL"],
                "timestamp": [ts],
                "feature_name": ["feat"],
                "value": [1.0],
                "version": ["1.0"],
            }
        )
        v2 = pl.DataFrame(
            {
                "instrument_id": ["AAPL"],
                "timestamp": [ts],
                "feature_name": ["feat"],
                "value": [2.0],
                "version": ["2.0"],
            }
        )
        await tmp_store.write_features("fs", "1.0", v1, "AAPL")
        await tmp_store.write_features("fs", "2.0", v2, "AAPL")

        result = await tmp_store.read_features("fs")  # latest
        assert len(result) > 0
        # v2 is latest alphabetically, so value is 2.0
        val = result["value"].to_list()[0]
        assert val == 2.0

    async def test_read_by_instrument(
        self, tmp_store: FeatureStore, sample_df: pl.DataFrame
    ) -> None:
        await tmp_store.write_features("fs", "1", sample_df, "AAPL")
        ts = datetime.now(UTC)
        msft_df = pl.DataFrame(
            {
                "instrument_id": ["MSFT"] * 2,
                "timestamp": [ts] * 2,
                "feature_name": ["sma_20", "ema_10"],
                "value": [250.0, 251.0],
                "version": ["1"] * 2,
            }
        )
        await tmp_store.write_features("fs", "1", msft_df, "MSFT")

        result = await tmp_store.read_features("fs", "1", instrument_ids=["AAPL"])
        assert len(result) == 3
        assert all(r == "AAPL" for r in result["instrument_id"].to_list())


class TestFeatureStoreFreshness:
    async def test_freshness_tracking(
        self, tmp_store: FeatureStore, sample_df: pl.DataFrame
    ) -> None:
        await tmp_store.write_features("fresh", "1", sample_df, "AAPL")
        freshness = tmp_store.get_freshness("fresh")
        assert "1" in freshness
        assert isinstance(freshness["1"], datetime)

    async def test_get_freshness_empty(self, tmp_store: FeatureStore) -> None:
        assert tmp_store.get_freshness("nonexistent") == {}

    async def test_is_stale_detection(
        self, tmp_store: FeatureStore, sample_df: pl.DataFrame
    ) -> None:
        await tmp_store.write_features("stale_test", "1", sample_df, "AAPL")
        # Immediately should not be stale
        assert not tmp_store.is_stale("stale_test", "1", max_age_seconds=3600)
        # Should be stale with zero max_age
        assert tmp_store.is_stale("stale_test", "1", max_age_seconds=0)

    async def test_is_stale_no_data(self, tmp_store: FeatureStore) -> None:
        assert tmp_store.is_stale("nonexistent", "1", max_age_seconds=60)


class TestFeatureStoreConcurrentWrite:
    async def test_concurrent_writes_do_not_corrupt(self, tmp_store: FeatureStore) -> None:
        """Multiple concurrent writes to the same feature set are serialised."""
        ts = datetime.now(UTC)

        async def write_instrument(iid: str, val: float) -> None:
            df = pl.DataFrame(
                {
                    "instrument_id": [iid],
                    "timestamp": [ts],
                    "feature_name": ["feat"],
                    "value": [val],
                    "version": ["1"],
                }
            )
            await tmp_store.write_features("concurrent", "1", df, iid)

        await asyncio.gather(
            write_instrument("AAPL", 100.0),
            write_instrument("MSFT", 200.0),
            write_instrument("GOOG", 300.0),
        )

        result = await tmp_store.read_features("concurrent", "1")
        assert len(result) == 3
        instruments = set(result["instrument_id"].to_list())
        assert instruments == {"AAPL", "MSFT", "GOOG"}


class TestFeatureStoreListVersions:
    async def test_list_versions(self, tmp_store: FeatureStore) -> None:
        tmp_store.register_feature_set(
            "fs", "1.0", {"feature_names": ["a"], "instrument_ids": ["AAPL"]}
        )
        tmp_store.register_feature_set(
            "fs", "2.0", {"feature_names": ["a", "b"], "instrument_ids": ["AAPL", "MSFT"]}
        )
        versions = tmp_store.list_versions("fs")
        assert len(versions) == 2
        assert {v.version_id for v in versions} == {"1.0", "2.0"}

    async def test_list_versions_empty(self, tmp_store: FeatureStore) -> None:
        assert tmp_store.list_versions("nonexistent") == []


# ======================================================================
# DuckDBQuery
# ======================================================================


class TestDuckDBQuery:
    async def test_query_correctness(self, tmp_store: FeatureStore) -> None:
        """Write via FeatureStore, read back via DuckDBQuery, verify data."""
        ts = datetime.now(UTC)
        df = pl.DataFrame(
            {
                "instrument_id": ["AAPL"] * 3,
                "timestamp": [ts] * 3,
                "feature_name": ["sma_20", "ema_10", "rsi_14"],
                "value": [150.0, 151.0, 55.0],
                "version": ["1.0.0"] * 3,
            }
        )
        await tmp_store.write_features("db_test", "1.0.0", df, "AAPL")

        dq = DuckDBQuery(store_path=tmp_store._path)
        result = dq.query_features("db_test", "1.0.0")
        assert len(result) == 3
        assert set(result["feature_name"].to_list()) == {"sma_20", "ema_10", "rsi_14"}

    async def test_query_features_filtered(self, tmp_store: FeatureStore) -> None:
        ts = datetime.now(UTC)
        df = pl.DataFrame(
            {
                "instrument_id": ["AAPL"] * 3,
                "timestamp": [ts] * 3,
                "feature_name": ["sma_20", "ema_10", "rsi_14"],
                "value": [150.0, 151.0, 55.0],
                "version": ["1.0"] * 3,
            }
        )
        await tmp_store.write_features("filter_test", "1.0", df, "AAPL")

        dq = DuckDBQuery(store_path=tmp_store._path)
        result = dq.query_features("filter_test", "1.0", features=["sma_20", "rsi_14"])
        assert len(result) == 2
        assert set(result["feature_name"].to_list()) == {"sma_20", "rsi_14"}

    def test_query_arbitrary_sql(self, tmp_store: FeatureStore) -> None:
        dq = DuckDBQuery(store_path=tmp_store._path)
        result = dq.query("SELECT 1 as x")
        assert result["x"].to_list() == [1]

    def test_query_empty_dir(self, tmp_path: Path) -> None:
        dq = DuckDBQuery(store_path=tmp_path / "empty")
        result = dq.query_features("nonexistent", "1.0")
        assert len(result) == 0

    def test_query_with_params(self, tmp_path: Path) -> None:
        dq = DuckDBQuery(store_path=tmp_path)
        result = dq.query("SELECT $val::INTEGER as x", params={"val": 42})
        assert result["x"].to_list() == [42]

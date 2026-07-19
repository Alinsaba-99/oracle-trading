"""BacktestDataProvider — unified data interface wrapping FeatureStore.

Provides OHLCV in wide-format for backtest engines (fast path: Parquet;
fallback: DuckDB PIVOT on the long-format FeatureStore) and feature
queries against the long-format FeatureStore.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import polars as pl

from market.store import FeatureStore

# Schema for wide-format OHLCV DataFrames returned by get_ohlcv.
_OHLCV_SCHEMA: dict[str, pl.DataType] = {
    "timestamp": pl.Datetime(time_unit="us"),
    "open": pl.Float64(),
    "high": pl.Float64(),
    "low": pl.Float64(),
    "close": pl.Float64(),
    "volume": pl.Float64(),
}

_OHLCV_COLUMNS = list(_OHLCV_SCHEMA.keys())


class BacktestDataProvider:
    """Unified data interface for backtesting.

    Reads OHLCV data from wide-format Parquet files (fast path) and
    falls back to DuckDB PIVOT on FeatureStore long-format data. Feature
    queries delegate to the FeatureStore directly.

    Parameters
    ----------
    feature_store:
        The :class:`FeatureStore` instance containing long-format data.
    ohlcv_path:
        Path to wide-format OHLCV Parquet files. Each file is named
        ``{instrument_id}.parquet`` with columns ``timestamp, open, high,
        low, close, volume``.
    survivorship_bias:
        When ``True``, exclude delisted instruments from results.
    delisted_instruments:
        Set of instrument IDs considered delisted.
    ohlcv_feature_set:
        Feature set name storing OHLCV data in long format (fallback).
    ohlcv_version:
        Version string for the OHLCV feature set.
    feature_set:
        Feature set name queried by :meth:`get_features`.
    feature_version:
        Version string for the feature set.
    """

    def __init__(
        self,
        feature_store: FeatureStore,
        ohlcv_path: Path = Path("data/ohlcv"),
        survivorship_bias: bool = False,
        delisted_instruments: set[str] | None = None,
        ohlcv_feature_set: str = "ohlcv",
        ohlcv_version: str = "1.0.0",
        feature_set: str = "features",
        feature_version: str = "1.0.0",
    ) -> None:
        self._feature_store = feature_store
        self._ohlcv_path = Path(ohlcv_path)
        self._survivorship_bias = survivorship_bias
        self._delisted = delisted_instruments or set()
        self._ohlcv_feature_set = ohlcv_feature_set
        self._ohlcv_version = ohlcv_version
        self._feature_set = feature_set
        self._feature_version = feature_version

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_ohlcv(
        self, instrument_id: str, start: datetime | None = None, end: datetime | None = None
    ) -> pl.DataFrame:
        """Return wide-format OHLCV for *instrument_id* in ``[start, end]``.

        Parameters
        ----------
        instrument_id:
            Instrument identifier (e.g. ``"AAPL"``).
        start:
            Inclusive start timestamp; ``None`` means unbounded.
        end:
            Inclusive end timestamp; ``None`` means unbounded.

        Returns
        -------
        pl.DataFrame
            Columns ``timestamp, open, high, low, close, volume``, sorted
            ascending by timestamp.  Empty when the instrument is delisted
            or no data exists.
        """
        if self._query_delisted(instrument_id):
            return pl.DataFrame(schema=_OHLCV_SCHEMA)

        # Fast path — wide-format Parquet
        wide_path = self._ohlcv_path / f"{instrument_id}.parquet"
        if wide_path.exists():
            df = pl.read_parquet(str(wide_path))
        else:
            # Fallback — DuckDB PIVOT on FeatureStore long-format
            df = await self._pivot_ohlcv(instrument_id)

        if df.is_empty():
            return pl.DataFrame(schema=_OHLCV_SCHEMA)

        df = self._apply_time_range(df, start, end)
        return df.sort("timestamp")

    async def get_features(
        self,
        instrument_id: str,
        feature_names: list[str],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pl.DataFrame:
        """Return long-format feature data for *instrument_id*.

        Parameters
        ----------
        instrument_id:
            Instrument identifier.
        feature_names:
            Subset of features to return.
        start:
            Inclusive start timestamp; ``None`` means unbounded.
        end:
            Inclusive end timestamp; ``None`` means unbounded.

        Returns
        -------
        pl.DataFrame
            Long-format DataFrame with columns ``instrument_id, timestamp,
            feature_name, value``, sorted ascending by timestamp.
        """
        if self._query_delisted(instrument_id):
            return pl.DataFrame()

        df = await self._feature_store.read_features(
            feature_set=self._feature_set,
            version=self._feature_version,
            instrument_ids=[instrument_id],
        )
        if df.is_empty():
            return df

        df = df.filter(pl.col("feature_name").is_in(feature_names))
        df = self._apply_time_range(df, start, end)
        return df.sort("timestamp")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query_delisted(self, instrument_id: str) -> bool:
        """Return ``True`` when *instrument_id* should be excluded."""
        return self._survivorship_bias and instrument_id in self._delisted

    @staticmethod
    def _apply_time_range(
        df: pl.DataFrame, start: datetime | None, end: datetime | None
    ) -> pl.DataFrame:
        """Filter *df* rows to the requested time window."""
        if df.is_empty():
            return df
        if start is not None:
            df = df.filter(pl.col("timestamp") >= start)
        if end is not None:
            df = df.filter(pl.col("timestamp") <= end)
        return df

    async def _pivot_ohlcv(self, instrument_id: str) -> pl.DataFrame:
        """Fallback: read long-format OHLCV from FeatureStore and PIVOT.

        Uses DuckDB to transform the FeatureStore's long-format
        ``(instrument_id, timestamp, feature_name, value)`` layout into
        wide-format ``(timestamp, open, high, low, close, volume)``.
        """
        df = await self._feature_store.read_features(
            feature_set=self._ohlcv_feature_set,
            version=self._ohlcv_version,
            instrument_ids=[instrument_id],
        )
        if df.is_empty():
            return pl.DataFrame(schema=_OHLCV_SCHEMA)

        quoted = [f"'{c}'" for c in _OHLCV_COLUMNS if c != "timestamp"]
        col_list = ", ".join(c for c in _OHLCV_COLUMNS if c != "timestamp")
        quoted_list = ", ".join(quoted)

        con = duckdb.connect()
        try:
            result = con.execute(
                f"""
                SELECT
                  timestamp::TIMESTAMPTZ AT TIME ZONE 'UTC' AS timestamp,
                  {col_list}
                FROM df
                PIVOT (
                    MAX(value)
                    FOR feature_name IN ({quoted_list})
                )
                ORDER BY timestamp
                """
            ).pl()
        finally:
            con.close()

        if result.is_empty():
            return pl.DataFrame(schema=_OHLCV_SCHEMA)

        # DuckDB returns timezone-naive timestamps; restore UTC so that
        # time-range comparisons against UTC-aware literals work.
        ts_dtype = result.schema["timestamp"]
        if isinstance(ts_dtype, pl.Datetime) and ts_dtype.time_zone is None:
            result = result.with_columns(pl.col("timestamp").dt.replace_time_zone("UTC"))
        return result

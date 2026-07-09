"""DuckDB query interface on top of the Feature Store Parquet files."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl


class DuckDBQuery:
    """Version-pinned DuckDB query wrapper for Parquet feature files.

    Provides a stable SQL interface over the on-disk feature store.
    ``duckdb`` version is pinned at project level for Arrow ABI
    stability.
    """

    def __init__(self, store_path: Path) -> None:
        self._store_path = Path(store_path)

    def query(self, sql: str, params: dict[str, object] | None = None) -> pl.DataFrame:
        """Execute arbitrary *sql* and return a Polars DataFrame.

        Parameters
        ----------
        sql:
            DuckDB SQL statement. Use ``$param_name`` for placeholders.
        params:
            Named parameters to bind into the SQL template.
        """
        con = duckdb.connect()
        try:
            if params:
                return con.execute(sql, params).pl()
            return con.execute(sql).pl()
        finally:
            con.close()

    def query_features(
        self, feature_set: str, version: str, features: list[str] | None = None
    ) -> pl.DataFrame:
        """Query feature data for a feature set version.

        Parameters
        ----------
        feature_set:
            Name of the feature set (sub-directory under store root).
        version:
            Version identifier.
        features:
            Optional subset of feature names to return; ``None`` returns
            all features.
        """
        parquet_dir = self._store_path / feature_set / version
        if not parquet_dir.exists():
            return pl.DataFrame()
        parquet_pattern = str(parquet_dir / "*.parquet")

        con = duckdb.connect()
        try:
            sql = f"SELECT * FROM read_parquet('{parquet_pattern}', union_by_name=true)"
            if features:
                quoted = [f"'{f}'" for f in features]
                sql = f"""
                    SELECT * FROM read_parquet('{parquet_pattern}', union_by_name=true)
                    WHERE feature_name IN ({",".join(quoted)})
                """
            return con.execute(sql).pl()
        finally:
            con.close()

"""Quick inspect of ES lake parquet schema."""

from __future__ import annotations

import sys

import polars as pl


def main() -> int:
    df = pl.read_parquet("data/lake/normalized/symbol=ES/tf=1d/year=2024/month=03.parquet")
    print(df.head(3))
    print("---")
    print("columns:", df.columns)
    print("rows:", df.height)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Introspect companies + verify SimFinId join to shareprices."""

from __future__ import annotations

import os
import sys

import polars as pl

from analytics.fundamental.simfin_loader import SimFinLoader


def main() -> int:
    api_key = os.environ.get("SIMFIN_API_KEY")
    if not api_key:
        print("FAIL: SIMFIN_API_KEY env var not set")
        return 1
    loader = SimFinLoader(api_key=api_key)

    print("=== Companies columns ===")
    try:
        comp = loader.companies()
        for c in comp.columns:
            print(f"  - {c}")
        print(f"\nrows: {comp.height}")
        print("\nFirst 3 companies:")
        print(comp.head(3))
        if "Sector" in comp.columns:
            print("\nSector distribution:")
            print(comp.group_by("Sector").agg(pl.len()).sort("Sector", descending=True))
    except Exception as e:
        print(f"FAIL: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

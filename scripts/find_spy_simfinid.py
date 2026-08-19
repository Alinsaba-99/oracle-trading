"""Find SPY SimFinId for benchmark comparison."""

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

    # Look for SPY ETF in companies
    comp = loader.companies()
    print(f"Companies columns: {comp.columns}")
    print(f"Total companies: {comp.height}")

    # Search by name
    for needle in ["SPDR", "SPY", "S&P 500", "SPYDER", "STATE STREET"]:
        if "Company Name" in comp.columns:
            mask = comp["Company Name"].str.to_uppercase().str.contains(needle)
            matches = comp.filter(mask).head(5)
            if matches.height > 0:
                print(f"\n{needle} matches:")
                print(matches.select(["SimFinId", "Company Name"]))

    # Also try Ticker column
    if "Ticker" in comp.columns:
        spy = comp.filter(pl.col("Ticker") == "SPY")
        if spy.height > 0:
            print("\nSPY by Ticker:")
            print(spy.select(["SimFinId", "Ticker", "Company Name"]))

    return 0


if __name__ == "__main__":
    sys.exit(main())

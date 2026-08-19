"""Quick sample of SimFin income for a known ticker."""

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

    print("=== Tickers sample (find AAPL, MSFT, INTC, AMD, NVDA, TSLA) ===")
    comp = loader.companies()
    print(comp.columns)
    # SimFin doesn't expose ticker directly — use Company Name filter
    if "Company Name" in comp.columns:
        for needle in ["APPLE", "MICROSOFT", "INTEL", "ADVANCED MICRO", "NVIDIA", "TESLA"]:
            mask = comp["Company Name"].str.to_uppercase().str.contains(needle)
            matches = comp.filter(mask).head(5)
            print(f"\n{needle}:")
            print(matches.select(["SimFinId", "Company Name"]))

    print("\n=== Income statements sample (filter to AAPL) ===")
    income = loader.income_statements()
    print(f"Income total rows: {income.height}")
    print(f"Cols: {income.columns[:6]}")
    # Find Apple SimFinId (from previous introspection: 45846 was Agilent)
    # Filter by 'APPLE' in company name
    apple_mask = comp["Company Name"].str.to_uppercase().str.contains("APPLE")
    apple_ids = comp.filter(apple_mask)["SimFinId"].to_list()
    print(f"Apple SimFinIds: {apple_ids[:5]}")
    if apple_ids:
        target_id = apple_ids[0]
        apple_inc = income.filter(pl.col("SimFinId") == target_id)
        print(f"Apple income rows: {apple_inc.height}")
        if apple_inc.height > 0:
            print(
                apple_inc.select(
                    [
                        "SimFinId",
                        "Fiscal Year",
                        "Fiscal Period",
                        "Publish Date",
                        "Revenue",
                        "Gross Profit",
                        "Net Income",
                        "Shares (Diluted)",
                    ]
                ).head(5)
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())

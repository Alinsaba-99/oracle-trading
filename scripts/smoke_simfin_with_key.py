"""Smoke test SimFin with API key.

Run: .venv/bin/python scripts/smoke_simfin_with_key.py
"""

from __future__ import annotations

import os
import sys

from analytics.fundamental.simfin_loader import SimFinLoader


def main() -> int:
    api_key = os.environ.get("SIMFIN_API_KEY")
    if not api_key:
        print("FAIL: SIMFIN_API_KEY env var not set")
        return 1
    print(f"Using SIMFIN_API_KEY: {api_key[:8]}...{api_key[-4:]}")

    try:
        loader = SimFinLoader(api_key=api_key)
    except Exception as e:
        print(f"FAIL SimFinLoader init: {e}")
        return 1

    print()
    print("=== Companies (bulk) ===")
    try:
        companies = loader.companies()
        print(f"rows: {companies.height}")
        print(f"cols: {companies.columns[:6]}")
        if companies.height > 0:
            print(companies.head(3))
    except Exception as e:
        print(f"FAIL companies: {e}")

    print()
    print("=== Income statements (quarterly) ===")
    try:
        income = loader.income_statements()
        print(f"rows: {income.height}")
        print(f"cols: {income.columns[:8]}")
        if income.height > 0:
            print(income.head(3))
    except Exception as e:
        print(f"FAIL income: {e}")

    print()
    print("=== Balance sheets (quarterly) ===")
    try:
        balance = loader.balance_sheets()
        print(f"rows: {balance.height}")
        print(f"cols: {balance.columns[:8]}")
    except Exception as e:
        print(f"FAIL balance: {e}")

    print()
    print("=== Cash flows (quarterly) ===")
    try:
        cash = loader.cash_flows()
        print(f"rows: {cash.height}")
        print(f"cols: {cash.columns[:8]}")
    except Exception as e:
        print(f"FAIL cashflow: {e}")

    print()
    print("=== Daily share prices ===")
    try:
        prices = loader.daily_prices()
        print(f"rows: {prices.height}")
        print(f"cols: {prices.columns[:8]}")
    except Exception as e:
        print(f"FAIL prices: {e}")

    print()
    print("=== Universe ===")
    try:
        u = loader.universe()
        print(f"unique companies in universe: {u.height}")
        if "Sector" in u.columns:
            print("\nSectors:")
            print(u.group_by("Sector").agg(pl.len()).sort("Sector"))
    except Exception as e:
        print(f"FAIL universe: {e}")

    return 0


if __name__ == "__main__":
    import polars as pl

    _ = pl  # used inside try blocks
    sys.exit(main())

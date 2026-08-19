"""Introspect SimFin income/balance/cashflow schema to build backtester correctly."""

from __future__ import annotations

import os
import sys

from analytics.fundamental.simfin_loader import SimFinLoader


def main() -> int:
    api_key = os.environ.get("SIMFIN_API_KEY")
    if not api_key:
        print("FAIL: SIMFIN_API_KEY env var not set")
        return 1
    loader = SimFinLoader(api_key=api_key)

    print("=== Income columns ===")
    try:
        income = loader.income_statements()
        for c in income.columns:
            print(f"  - {c}")
    except Exception as e:
        print(f"FAIL: {e}")

    print("\n=== Balance columns ===")
    try:
        bal = loader.balance_sheets()
        for c in bal.columns:
            print(f"  - {c}")
    except Exception as e:
        print(f"FAIL: {e}")

    print("\n=== Cashflow columns ===")
    try:
        cf = loader.cash_flows()
        for c in cf.columns:
            print(f"  - {c}")
    except Exception as e:
        print(f"FAIL: {e}")

    print("\n=== Prices columns ===")
    try:
        pr = loader.daily_prices()
        for c in pr.columns:
            print(f"  - {c}")
    except Exception as e:
        print(f"FAIL: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

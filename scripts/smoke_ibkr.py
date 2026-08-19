"""Smoke test IBKR TWS Gateway connection + list available data.

Run: .venv/bin/python scripts/smoke_ibkr.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ib_insync import IB, Future, Stock  # noqa: E402


def main() -> int:
    print("=" * 60)
    print("IBKR TWS Gateway smoke test")
    print("=" * 60)
    print()

    ib = IB()
    ports = [7497, 4002]
    connected = False
    for port in ports:
        try:
            print(f"Connecting to localhost:{port} clientId=1 ...")
            ib.connect("127.0.0.1", port, clientId=1, timeout=10)
            if ib.isConnected():
                print(f"✅ Connected on port {port}")
                connected = True
                break
        except Exception as e:
            print(f"FAIL connection on port {port}: {e}")
            try:
                ib.disconnect()
            except Exception:
                pass
    if not connected:
        print("FAIL: could not connect on any tested port")
        return 1

    # 1. Account summary
    print("=== Account summary ===")
    try:
        summary = ib.accountSummary()
        if summary:
            for tag in ["AccountType", "NetLiquidation", "TotalCashValue", "BuyingPower"]:
                for row in summary:
                    if row.tag == tag:
                        print(f"  {tag}: {row.value} {row.currency}")
        else:
            print("  (empty — likely paper account without funded balance)")
    except Exception as e:
        print(f"  WARN accountSummary: {e}")
    print()

    # 2. Head timestamp for ES future (to verify historical data access)
    print("=== ES future head timestamp (data access check) ===")
    try:
        es = Future("ES", "CME", "202509")
        ib.qualifyContracts(es)
        print(f"  Qualified: {es.conId} {es.localSymbol} {es.lastTradeDateOrContractMonth}")
        # Try head timestamp (earliest available bar)
        head = ib.reqHeadTimeStamp(
            contract=es,
            endDateTime="",
            durationStr="1 D",
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=False,
            formatDate=1,
        )
        if head:
            print(f"  ES 1min earliest: {head}")
        else:
            print("  ES 1min head timestamp returned None (may need data subscription)")
    except Exception as e:
        print(f"  WARN ES qualify/headTimeStamp: {e}")
    print()

    # 3. SPY equity head timestamp
    print("=== SPY equity head timestamp ===")
    try:
        spy = Stock("SPY", "SMART", "USD")
        ib.qualifyContracts(spy)
        print(f"  Qualified: {spy.conId} {spy.localSymbol}")
        head = ib.reqHeadTimeStamp(
            contract=spy,
            endDateTime="",
            durationStr="1 D",
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=False,
            formatDate=1,
        )
        if head:
            print(f"  SPY 1min earliest: {head}")
        else:
            print("  SPY 1min head timestamp returned None")
    except Exception as e:
        print(f"  WARN SPY qualify/headTimeStamp: {e}")
    print()

    # 4. Try to download 1 day of ES 1m bars (recent)
    print("=== Recent ES 1min bars (last 2 days) ===")
    try:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=2)
        bars = ib.reqHistoricalData(
            es,
            endDateTime=end_dt,
            durationStr="2 D",
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=False,
            formatDate=1,
        )
        if bars:
            print(f"  Got {len(bars)} bars")
            print(
                f"  First: {bars[0].date} O={bars[0].open} H={bars[0].high} L={bars[0].low} C={bars[0].close} V={bars[0].volume}"
            )
            print(
                f"  Last:  {bars[-1].date} O={bars[-1].open} H={bars[-1].high} L={bars[-1].low} C={bars[-1].close} V={bars[-1].volume}"
            )
        else:
            print("  No bars returned (may need CME data subscription)")
    except Exception as e:
        print(f"  WARN reqHistoricalData ES: {e}")
    print()

    # 5. Available contracts list
    print("=== Available contracts (commonly traded) ===")
    test_contracts = [
        ("ES", "CME", "Future"),
        ("MES", "CME", "Future"),
        ("NQ", "CME", "Future"),
        ("GC", "COMEX", "Future"),
        ("CL", "NYMEX", "Future"),
        ("ZN", "CBOT", "Future"),
        ("SPY", "SMART", "Stock"),
        ("QQQ", "SMART", "Stock"),
        ("AAPL", "SMART", "Stock"),
        ("INTC", "SMART", "Stock"),
        ("AMD", "SMART", "Stock"),
        ("NVDA", "SMART", "Stock"),
        ("TSLA", "SMART", "Stock"),
    ]
    for sym, exch, ctype in test_contracts:
        try:
            if ctype == "Future":
                c = Future(sym, exch, "202509")
            else:
                c = Stock(sym, "SMART", "USD")
            ib.qualifyContracts(c)
            print(f"  ✅ {sym} ({ctype}): conId={c.conId}")
        except Exception as e:
            print(f"  ❌ {sym} ({ctype}): {e}")

    print()
    print("=" * 60)
    print("IBKR smoke test complete")
    print("=" * 60)
    ib.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())

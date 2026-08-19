"""Smoke IBKR connection + futures contract fix (post-fix).

Verify: account, head timestamp, ES 1m bars, futures contract qualification
with proper lastTradeDateOrContractMonth.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ib_insync import IB, Future, Stock  # noqa: E402


def qualify_futures(ib: IB) -> None:
    """Qualify futures with proper contract spec."""
    futures_to_test = [
        ("ES", "CME", "USD"),
        ("MES", "CME", "USD"),
        ("NQ", "CME", "USD"),
        ("GC", "COMEX", "USD"),
        ("CL", "NYMEX", "USD"),
        ("ZN", "CBOT", "USD"),
        ("YM", "CBOT", "USD"),
        ("RTY", "CME", "USD"),
    ]
    print("\n=== Futures contracts ===")
    for sym, exch, curr in futures_to_test:
        # Use FutureCont constructor pattern: needs expiry month
        # Without specifying expiry, IBKR returns contract chain
        try:
            c = Future(sym, exch, curr)
            cds = ib.reqContractDetails(c)
            if cds:
                # Get nearest expiry
                nearest = cds[0]
                print(
                    f"  ✅ {sym} ({exch}): conId={nearest.contract.conId}, "
                    f"expiry={nearest.contract.lastTradeDateOrContractMonth}"
                )
            else:
                print(f"  ❌ {sym} ({exch}): no contract details")
        except Exception as e:
            print(f"  ❌ {sym} ({exch}): {e}")


def fetch_es_1m_bars(ib: IB) -> None:
    """Fetch recent ES 1m bars to verify data subscription."""
    print("\n=== ES 1m bars (recent) ===")
    try:
        cds = ib.reqContractDetails(Future("ES", "CME", "USD"))
        if not cds:
            print("  No ES contracts available")
            return
        es_contract = cds[0].contract
        ib.qualifyContracts(es_contract)
        end_dt = datetime.now()
        bars = ib.reqHistoricalData(
            es_contract,
            endDateTime=end_dt,
            durationStr="2 D",
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=False,
            formatDate=1,
        )
        if bars:
            print(f"  Got {len(bars)} ES 1m bars")
            print(f"  First: {bars[0].date} close={bars[0].close}")
            print(f"  Last:  {bars[-1].date} close={bars[-1].close}")
        else:
            print("  No bars (may need CME data subscription; check Account Management)")
    except Exception as e:
        print(f"  FAIL: {e}")


def fetch_spy_1m_bars(ib: IB) -> None:
    """Fetch SPY 1m bars — free for US equities on IB paper."""
    print("\n=== SPY 1m bars (recent) ===")
    try:
        spy = Stock("SPY", "SMART", "USD")
        ib.qualifyContracts(spy)
        end_dt = datetime.now()
        bars = ib.reqHistoricalData(
            spy,
            endDateTime=end_dt,
            durationStr="2 D",
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=False,
            formatDate=1,
        )
        if bars:
            print(f"  Got {len(bars)} SPY 1m bars")
            print(f"  First: {bars[0].date} close={bars[0].close}")
            print(f"  Last:  {bars[-1].date} close={bars[-1].close}")
        else:
            print("  No SPY bars")
    except Exception as e:
        print(f"  FAIL: {e}")


def fetch_es_head_timestamp(ib: IB) -> None:
    """Get head timestamp (earliest 1m bar available) for ES."""
    print("\n=== ES earliest 1m timestamp ===")
    try:
        cds = ib.reqContractDetails(Future("ES", "CME", "USD"))
        if cds:
            es_contract = cds[0].contract
            ib.qualifyContracts(es_contract)
            head = ib.reqHeadTimeStamp(es_contract, "1 D", "1 min", 0, 1)
            print(f"  ES earliest 1m bar: {head}")
    except Exception as e:
        print(f"  FAIL: {e}")


def main() -> int:
    print("=" * 60)
    print("IBKR post-fix smoke test")
    print("=" * 60)

    ib = IB()
    try:
        print("\nConnecting to localhost:4002 ...")
        ib.connect("127.0.0.1", 4002, clientId=2, timeout=10)
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    if not ib.isConnected():
        print("FAIL: not connected")
        return 1
    print("✅ Connected")

    print("\n=== Account ===")
    for tag in ["AccountType", "NetLiquidation", "TotalCashValue", "BuyingPower"]:
        for row in ib.accountSummary():
            if row.tag == tag:
                print(f"  {tag}: {row.value} {row.currency}")

    qualify_futures(ib)
    fetch_es_head_timestamp(ib)
    fetch_es_1m_bars(ib)
    fetch_spy_1m_bars(ib)

    print("\n" + "=" * 60)
    print("IBKR post-fix smoke complete")
    print("=" * 60)
    ib.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())

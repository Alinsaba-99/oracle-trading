#!/usr/bin/env python3
"""Paper trading session — Polygon REST data → strategy → broker → P&L.

Usage::

    uv run --frozen python -u scripts/run_paper_session.py --symbol ES --fast 2 --slow 5
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Oracle Paper Trading Session")
    p.add_argument("--symbol", default="ES")
    p.add_argument("--fast", type=int, default=2)
    p.add_argument("--slow", type=int, default=5)
    p.add_argument("--capital", type=float, default=100_000)
    p.add_argument("--polls", type=int, default=5)
    p.add_argument("--interval", type=float, default=15.0)
    return p.parse_args()


def _signal(prices: list[float], fast: int, slow: int) -> str:
    if len(prices) < slow + 1:
        return "HOLD"
    f = sum(prices[-fast:]) / fast
    s = sum(prices[-slow:]) / slow
    if len(prices) < slow + 2:
        return "HOLD"
    pf = sum(prices[-(fast + 1):-1]) / fast
    ps = sum(prices[-(slow + 1):-1]) / slow
    if pf <= ps and f > s:
        return "BUY"
    if pf >= ps and f < s:
        return "SELL"
    return "HOLD"


async def run(args: argparse.Namespace) -> dict:
    from dotenv import load_dotenv
    load_dotenv()

    from core.domain.mode import OracleMode
    from core.domain.guard import guard
    from market.realtime import PolygonWebSocketFeed
    from execution.brokers.paper import PaperBroker
    from execution.brokers.types import BrokerOrder
    from core.reconciliation import ReconciliationEngine
    from decimal import Decimal

    guard(OracleMode.PAPER)
    broker = PaperBroker()
    feed = PolygonWebSocketFeed()
    symbol = args.symbol.upper()
    prices: list[float] = []
    position = 0
    trades: list[dict] = []

    print(f"\n{'='*50}")
    print(f"  PAPER SESSION: {symbol} SMA({args.fast}/{args.slow})")
    print(f"{'='*50}\n", flush=True)

    # ── Startup reconciliation ───────────────────────────────────────
    from core.ledger import InMemoryLedger
    from core.oms import InMemoryOMS
    ledger = InMemoryLedger()
    oms = InMemoryOMS(ledger=ledger)
    reconciler = ReconciliationEngine(broker=broker, oms=oms, ledger=ledger)
    start_report = await reconciler.reconcile()
    if start_report.is_clean:
        print("  Startup reconciliation: CLEAN", flush=True)
    else:
        print(f"  Startup reconciliation: {start_report.recoverable_count} recoverable, {start_report.fatal_count} fatal", flush=True)
        if start_report.has_fatal:
            print("  ⛔ FATAL mismatch at startup — blocking orders", flush=True)
    print(flush=True)

    feed._running = True
    count = 0

    async for tick in feed.rest_poll(symbol, interval_sec=args.interval):
        count += 1
        price = tick.price

        if price <= 0:
            print(f"  [{count}] waiting for data...", flush=True)
            if args.polls and count >= args.polls:
                break
            continue

        prices.append(price)
        sig = _signal(prices, args.fast, args.slow)

        contracts = 0
        new_pos = position
        if sig == "BUY" and position <= 0:
            contracts = 1 if position == 0 else 2
            new_pos = 1
        elif sig == "SELL" and position >= 0:
            contracts = 1 if position == 0 else 2
            new_pos = -1

        print(
            f"  [{count}] ${price:.2f}  sig={sig:5s}  "
            f"pos={position}  trades={contracts}",
            flush=True,
        )

        if contracts > 0:
            side = "BUY" if new_pos > 0 else "SELL"
            order = BrokerOrder(
                broker_order_id=f"paper_{count}",
                local_order_id=str(uuid4()),
                namespaced_id=f"paper:{count}",
                instrument_id=symbol,
                side=side,
                quantity=Decimal(str(contracts)),
                price=Decimal(str(price)),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            oid = await broker.submit_order(order)
            trades.append({"time": datetime.now(timezone.utc).isoformat(), "side": side, "contracts": contracts, "price": price})
            position = new_pos
            print(f"    -> FILLED #{oid}", flush=True)

        if args.polls and count >= args.polls:
            break

    print(f"\n{'='*50}")
    print(f"  RESULT: {len(trades)} trades, final pos={position}")
    print(f"{'='*50}\n", flush=True)
    return {"trades": len(trades), "position": position}


def main() -> None:
    result = asyncio.run(run(_parse_args()))
    print(f"Done: {result}", flush=True)


if __name__ == "__main__":
    main()

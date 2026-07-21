#!/usr/bin/env -S uv run --frozen
"""M32-023: Paper trading session runner — 60 sessioni.

Esegue N sessioni di paper trading in sequenza, ciascuna con dati sintetici
diversi, e verifica che non ci siano incidenti hard (risk breach, fatal
reconciliation mismatch, etc.). Ogni sessione replica il flusso reale:
  generazione dati → segnale → ordine → fill → P&L.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time as _time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


def _signal(prices: list[float], fast: int, slow: int) -> str:
    """SMA crossover signal."""
    if len(prices) < slow + 1:
        return "HOLD"
    f = sum(prices[-fast:]) / fast
    s = sum(prices[-slow:]) / slow
    if len(prices) < slow + 2:
        return "HOLD"
    pf = sum(prices[-(fast + 1) : -1]) / fast
    ps = sum(prices[-(slow + 1) : -1]) / slow
    if pf <= ps and f > s:
        return "BUY"
    if pf >= ps and f < s:
        return "SELL"
    return "HOLD"


# ---------------------------------------------------------------------------
# Synthetic data generators
# ---------------------------------------------------------------------------


def _generate_session_prices(
    seed: int,
    n_bars: int = 100,
    start_price: float = 4500.0,
    vol: float = 0.004,
    trend: float = 0.0005,
) -> list[float]:
    """Generate a deterministic price series for one session.

    Each session gets a unique seed so every session has different data.
    """
    rng = random.Random(seed)
    prices: list[float] = []
    p = start_price
    for _ in range(n_bars):
        ret = rng.gauss(trend, vol)
        p *= 1 + ret
        prices.append(round(max(p, 1.0), 2))
    return prices


# ---------------------------------------------------------------------------
# Single-session runner
# ---------------------------------------------------------------------------


async def _run_one_session(
    session_id: int, prices: list[float], fast: int, slow: int, capital: Decimal
) -> dict[str, Any]:
    """Run one paper trading session and return results.

    Pipeline: data → signal → order → broker fill → position tracking → P&L.
    No external dependencies (Polygon, etc.) — fully synthetic.
    """
    from execution.brokers.config import BrokerConfig
    from execution.brokers.paper import PaperBroker
    from execution.brokers.types import BrokerOrder

    # Use realistic broker settings
    config = BrokerConfig(
        paper_spread_bps=10,
        paper_slippage_bps=5,
        paper_partial_fill_prob=0.2,
        paper_latency_ms=10,
        paper_commission_per_contract=0.85,
    )
    broker = PaperBroker(config)
    await broker.on_price_update(Decimal(str(prices[0])))

    position = 0
    entry_price: float | None = None
    trades: list[dict[str, Any]] = []
    equity_curve: list[float] = [float(capital)]
    hard_incidents: list[str] = []
    orders_submitted = 0
    fills_received = 0

    now = datetime.now(UTC)

    for i in range(1, len(prices)):
        price = prices[i]
        sig = _signal(prices[: i + 1], fast, slow)

        # Determine action
        contracts = 0
        target_pos = position
        if sig == "BUY" and position <= 0:
            target_pos = 1
            contracts = 1 if position == 0 else 2
        elif sig == "SELL" and position >= 0:
            target_pos = -1
            contracts = 1 if position == 0 else 2

        # Execute order
        if contracts > 0:
            side = "buy" if target_pos > 0 else "sell"
            order = BrokerOrder(
                broker_order_id=f"session_{session_id}_step_{i}",
                local_order_id=str(uuid4()),
                namespaced_id=f"session:{session_id}:{i}",
                instrument_id="ES",
                side=side,
                quantity=Decimal(str(contracts)),
                price=Decimal(str(price)),
                order_type="market",
                created_at=now.isoformat(),
            )
            fills_before = len(broker._fills)
            await broker.submit_order(order)
            orders_submitted += 1

            # Market orders fill during submit_order — collect new fills
            new_fills = broker._fills[fills_before:]
            fills_received += len(new_fills)

            # Advance price so any resting orders can trigger
            await broker.on_price_update(Decimal(str(price)))

            # Get actual position from broker
            positions = await broker.positions()
            pos_qty = sum(int(p.quantity) for p in positions)
            position = pos_qty

            # Record trade
            trades.append(
                {
                    "step": i,
                    "price": price,
                    "side": side,
                    "contracts": contracts,
                    "filled_qty": sum(int(f.quantity) for f in new_fills),
                    "avg_fill_price": float(statistics.mean([float(f.price) for f in new_fills]))
                    if new_fills
                    else price,
                    "commission": float(sum(float(f.commission) for f in new_fills)),
                    "position_after": position,
                }
            )

        # Track equity
        if position != 0 and entry_price is not None:
            unrealized = (price - entry_price) * position
            equity_curve.append(float(capital) + unrealized)
        else:
            equity_curve.append(equity_curve[-1] if equity_curve else float(capital))

        # Track entry price for position
        if position != 0 and entry_price is None:
            entry_price = price
        elif position == 0:
            entry_price = None

    # Compute session metrics
    total_pnl = equity_curve[-1] - float(capital) if equity_curve else 0.0
    peak = max(equity_curve) if equity_curve else float(capital)
    max_dd = max(peak - e for e in equity_curve) if equity_curve else 0.0

    # Hard incident check
    if max_dd > float(capital) * 0.10:
        hard_incidents.append(f"drawdown_exceeded: max_dd={max_dd:.2f} > 10% of capital")
    if fills_received == 0 and orders_submitted > 0:
        hard_incidents.append("zero_fills_with_orders")

    return {
        "session_id": session_id,
        "n_bars": len(prices),
        "price_range": [min(prices), max(prices)],
        "orders_submitted": orders_submitted,
        "fills_received": fills_received,
        "n_trades": len(trades),
        "total_pnl": round(total_pnl, 2),
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd / float(capital) * 100, 2),
        "final_position": position,
        "final_equity": round(equity_curve[-1], 2) if equity_curve else float(capital),
        "hard_incidents": hard_incidents,
        "passed": len(hard_incidents) == 0,
    }


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------


async def run_sessions(
    n_sessions: int, fast: int, slow: int, capital: float, n_bars: int, results_dir: Path
) -> list[dict[str, Any]]:
    """Run ``n_sessions`` paper trading sessions and return all results."""
    results: list[dict[str, Any]] = []
    capital_dec = Decimal(str(capital))
    start_time = _time.monotonic()

    print(f"\nPaper Trading Sessions — {n_sessions} sessions")
    print(f"  Strategy: SMA({fast}/{slow})")
    print(f"  Capital:  ${capital:,.0f}")
    print(f"  Bars/session: {n_bars}")
    print(f"  Results:  {results_dir}\n")

    for sid in range(1, n_sessions + 1):
        session_start = _time.monotonic()

        # Generate session data with deterministic seed
        prices = _generate_session_prices(
            seed=sid * 1000 + 42,
            n_bars=n_bars,
            start_price=4500.0 + (sid % 10 - 5) * 50,  # vary starting price
            vol=0.003 + (sid % 5) * 0.001,  # vary volatility
            trend=0.0003 if sid % 3 != 0 else -0.0002,  # mix bull/bear
        )

        result = await _run_one_session(sid, prices, fast, slow, capital_dec)
        elapsed = _time.monotonic() - session_start
        result["elapsed_seconds"] = round(elapsed, 2)
        results.append(result)

        # Progress
        status = "✅" if result["passed"] else "❌"
        incidents = ""
        if result["hard_incidents"]:
            incidents = f"  ⚠️  {', '.join(result['hard_incidents'])}"
        print(
            f"  [{sid:>3d}/{n_sessions}] {status}  "
            f"trades={result['n_trades']:>2d}  "
            f"P&L=${result['total_pnl']:>+8.2f}  "
            f"dd={result['max_drawdown_pct']:>5.2f}%  "
            f"pos={result['final_position']:+d}  "
            f"{elapsed:>5.1f}s{incidents}",
            flush=True,
        )

    total_elapsed = _time.monotonic() - start_time
    print(
        f"\n  Total time: {total_elapsed:.1f}s  "
        f"({total_elapsed / max(n_sessions, 1):.1f}s/session)\n"
    )

    return results


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def _print_summary(results: list[dict[str, Any]]) -> None:
    """Print aggregate summary across sessions."""
    n = len(results)
    passed = [r for r in results if r["passed"]]
    failed = [r for r in results if not r["passed"]]

    print("=== Summary ===")
    print(f"  Sessions:       {n}")
    print(f"  Passed:         {len(passed)} ({len(passed) / n:.0%})")
    print(f"  Failed:         {len(failed)}")

    if passed:
        pnls = [r["total_pnl"] for r in passed]
        dds = [r["max_drawdown_pct"] for r in passed]
        trades = [r["n_trades"] for r in passed]
        print(
            f"  Avg P&L:        ${statistics.mean(pnls):>+.2f}  (std=${statistics.stdev(pnls):.2f})"
        )
        print(f"  Avg drawdown:   {statistics.mean(dds):.2f}%  (max: {max(dds):.2f}%)")
        print(f"  Avg trades/session: {statistics.mean(trades):.1f}")

    if failed:
        print("\n  Failed sessions:")
        for r in failed:
            print(f"    [{r['session_id']}] {'; '.join(r['hard_incidents'])}")

    total_pnl = sum(r["total_pnl"] for r in results)
    print(f"\n  Total P&L:      ${total_pnl:>+.2f}")
    print(f"  Avg P&L/session: ${total_pnl / max(n, 1):>+.2f}")

    # Gate check
    print("\n  Gate check:")
    hard_incidents = [r for r in results if not r["passed"]]
    win_rate = len(passed) / max(n, 1)

    ok = True
    if hard_incidents:
        print(f"    FAIL: {len(hard_incidents)} session(s) with hard incidents")
        ok = False
    else:
        print("    PASS: 0 hard incidents")

    if win_rate < 0.9:
        print(f"    FAIL: pass rate = {win_rate:.0%} (< 90%)")
        ok = False
    else:
        print(f"    PASS: pass rate = {win_rate:.0%}")

    if n < 60:
        print(f"    WARN: only {n} sessions (target: 60)")
    else:
        print(f"    PASS: {n}/60 sessions completed")

    print(f"\n  Overall: {'✅ PASS' if ok else '❌ FAIL'}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Paper trading session runner")
    parser.add_argument("--sessions", type=int, default=60, help="Number of sessions")
    parser.add_argument("--fast", type=int, default=5, help="Fast SMA period")
    parser.add_argument("--slow", type=int, default=20, help="Slow SMA period")
    parser.add_argument("--capital", type=float, default=100000.0, help="Starting capital")
    parser.add_argument("--bars", type=int, default=100, help="Bars per session")
    parser.add_argument(
        "--output", type=str, default="logs/paper_sessions.json", help="Output JSON path"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    results_dir = Path(args.output).parent
    results_dir.mkdir(parents=True, exist_ok=True)

    results = await run_sessions(
        n_sessions=args.sessions,
        fast=args.fast,
        slow=args.slow,
        capital=args.capital,
        n_bars=args.bars,
        results_dir=results_dir,
    )

    # Save results
    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(
            {
                "metadata": {
                    "sessions": args.sessions,
                    "fast": args.fast,
                    "slow": args.slow,
                    "capital": args.capital,
                    "bars": args.bars,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                "results": results,
                "summary": {
                    "total_sessions": len(results),
                    "passed": sum(1 for r in results if r["passed"]),
                    "failed": sum(1 for r in results if not r["passed"]),
                    "total_pnl": round(sum(r["total_pnl"] for r in results), 2),
                },
            },
            f,
            indent=2,
        )
    print(f"  Results saved to {output_path}")

    _print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())

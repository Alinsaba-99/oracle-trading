#!/usr/bin/env -S uv run --frozen
"""M32-021: Decision stability measurement.

Runs the same market data through the decision pipeline multiple times and
compares the resulting trading decisions. High stability means the same
market conditions produce the same signals and orders regardless of broker
randomness or timing.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Simple SMA crossover signal (same as run_paper_session.py)
# ---------------------------------------------------------------------------


def _signal(prices: list[float], fast: int, slow: int) -> str:
    """SMA crossover signal: BUY, SELL, or HOLD."""
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


def _position_from_signal(sig: str, current_pos: int) -> int:
    """Derive target position from signal and current position."""
    if sig == "BUY" and current_pos <= 0:
        return 1
    if sig == "SELL" and current_pos >= 0:
        return -1
    return current_pos


def _contracts_needed(current_pos: int, target_pos: int) -> int:
    """Number of contracts to trade to reach target position."""
    if target_pos == current_pos:
        return 0
    if current_pos == 0:
        return 1
    return 2  # flip from +1 to -1 or vice versa


# ---------------------------------------------------------------------------
# Decision runner (pure — no broker, no randomness)
# ---------------------------------------------------------------------------


def _run_pure(prices: list[float], fast: int, slow: int) -> list[dict[str, Any]]:
    """Run the decision pipeline on price data without broker interaction.

    Returns a list of decision records at each step.
    """
    decisions: list[dict[str, Any]] = []
    position = 0

    for i, price in enumerate(prices):
        sig = _signal(prices[: i + 1], fast, slow)
        target = _position_from_signal(sig, position)
        contracts = _contracts_needed(position, target)

        decisions.append(
            {
                "step": i,
                "price": price,
                "signal": sig,
                "position_before": position,
                "target_position": target,
                "contracts": contracts,
            }
        )
        if contracts > 0:
            position = target

    return decisions


# ---------------------------------------------------------------------------
# Decision runner (with broker — includes fill noise)
# ---------------------------------------------------------------------------


async def _run_with_broker(
    prices: list[float], fast: int, slow: int, realistic: bool = False
) -> list[dict[str, Any]]:
    """Run the decision pipeline through PaperBroker.

    When ``realistic=True``, enables spread/slippage/partial fills/latency.
    """
    from execution.brokers.config import BrokerConfig
    from execution.brokers.paper import PaperBroker
    from execution.brokers.types import BrokerOrder

    if realistic:
        config = BrokerConfig(
            paper_spread_bps=20,
            paper_slippage_bps=10,
            paper_partial_fill_prob=0.3,
            paper_latency_ms=25,
        )
    else:
        config = BrokerConfig()

    broker = PaperBroker(config)
    decisions: list[dict[str, Any]] = []
    position = 0

    for i, price in enumerate(prices):
        sig = _signal(prices[: i + 1], fast, slow)
        target = _position_from_signal(sig, position)
        contracts = _contracts_needed(position, target)

        if contracts > 0:
            side = "buy" if target > 0 else "sell"
            order = BrokerOrder(
                broker_order_id=f"step_{i}",
                local_order_id=str(uuid4()),
                namespaced_id=f"step:{i}",
                instrument_id="ES",
                side=side,
                quantity=Decimal(str(contracts)),
                price=Decimal(str(price)),
                order_type="market",
                created_at=datetime.now(UTC).isoformat(),
            )
            oid = await broker.submit_order(order)
            # Advance price so broker processes fill
            await broker.on_price_update(Decimal(str(price)))

            # Get actual position from broker
            positions = await broker.positions()
            pos_qty = sum(int(p.quantity) for p in positions)
            fill_records = [
                {"fill_id": f.broker_order_id, "qty": int(f.quantity), "price": float(f.price)}
                for f in broker._fills
                if f.broker_order_id == oid
            ]
        else:
            oid = None
            pos_qty = position
            fill_records = []

        decisions.append(
            {
                "step": i,
                "price": price,
                "signal": sig,
                "position_before": position,
                "target_position": target,
                "contracts": contracts,
                "order_id": oid,
                "position_after": pos_qty,
                "fills": fill_records,
            }
        )
        if contracts > 0:
            position = pos_qty

    return decisions


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _compare_decisions(runs: list[list[dict[str, Any]]], labels: list[str]) -> dict[str, Any]:
    """Compare multiple decision runs and compute agreement metrics."""
    n_runs = len(runs)
    n_steps = len(runs[0])
    results: dict[str, Any] = {}

    # Signal agreement across runs
    signal_agreement: list[float] = []
    for step in range(n_steps):
        signals = [r[step]["signal"] for r in runs]
        most_common = max(set(signals), key=signals.count)
        agreement = signals.count(most_common) / n_runs
        signal_agreement.append(agreement)

    results["signal_agreement_rate"] = round(statistics.mean(signal_agreement), 4)
    results["signal_agreement_min"] = round(min(signal_agreement), 4)
    results["signal_total_steps"] = n_steps

    # Trade decision agreement
    trade_steps = [s for s in range(n_steps) if runs[0][s]["contracts"] > 0]
    trade_agreement: list[float] = []
    for step in trade_steps:
        actions = [
            (r[step]["contracts"], r[step].get("position_after", r[step]["target_position"]))
            for r in runs
        ]
        most_common_action = max(set(actions), key=actions.count)
        agreement = actions.count(most_common_action) / n_runs
        trade_agreement.append(agreement)

    results["trade_agreement_rate"] = (
        round(statistics.mean(trade_agreement), 4) if trade_agreement else 1.0
    )
    results["trade_total"] = len(trade_steps)

    # Position divergence: max difference in position across runs per step
    max_pos_div = 0
    for step in range(n_steps):
        positions = [r[step].get("position_after", r[step]["target_position"]) for r in runs]
        spread = max(positions) - min(positions)
        max_pos_div = max(max_pos_div, spread)
    results["max_position_divergence"] = int(max_pos_div)

    # Per-run summary
    per_run: list[dict[str, Any]] = []
    for idx, (run, label) in enumerate(zip(runs, labels, strict=True)):
        trades = sum(1 for d in run if d["contracts"] > 0)
        buys = sum(1 for d in run if d.get("position_after", d["target_position"]) > 0)
        sells = sum(1 for d in run if d.get("position_after", d["target_position"]) < 0)
        final_pos = run[-1].get("position_after", run[-1]["target_position"])
        per_run.append(
            {
                "run": idx,
                "label": label,
                "trades": trades,
                "buys": buys,
                "sells": sells,
                "final_position": final_pos,
            }
        )
    results["per_run"] = per_run

    return results


# ---------------------------------------------------------------------------
# Price sequence generators
# ---------------------------------------------------------------------------


def _random_walk(n: int, start: float = 4500.0, vol: float = 0.005) -> list[float]:
    """Generate a deterministic random-walk price sequence (fixed seed)."""
    import random as _random

    rng = _random.Random(42)
    prices: list[float] = [start]
    for _ in range(n - 1):
        step = start * vol * rng.uniform(-1, 1)
        prices.append(round(prices[-1] + step, 2))
    return prices


def _sawtooth(n: int, start: float = 4500.0) -> list[float]:
    """A deterministic sawtooth pattern with clear trend reversals."""
    prices: list[float] = []
    for i in range(n):
        cycle = (i % 20) / 20.0
        if (i // 20) % 2 == 0:
            prices.append(round(start * (1 + cycle * 0.02), 2))
        else:
            prices.append(round(start * (1 + (1 - cycle) * 0.02), 2))
    return prices


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _print_prices(prices: list[float]) -> None:
    """Print a compact price summary."""
    n = len(prices)
    lo, hi = min(prices), max(prices)
    print(f"  Prices:  {n} bars  [{lo:.2f} - {hi:.2f}]  avg={statistics.mean(prices):.2f}")
    # Show first 5 and last 5
    prefix = " ".join(f"{p:.1f}" for p in prices[:5])
    suffix = " ".join(f"{p:.1f}" for p in prices[-5:])
    print(f"  Head:    {prefix}  ...")
    print(f"  Tail:    ...  {suffix}")


def _print_report(results: dict[str, Any], label: str) -> None:
    """Print a formatted stability report."""
    print(f"\n--- Decision Stability: {label} ---")
    print(
        f"  Signal agreement:   {results['signal_agreement_rate']:.2%} "
        f"(min step: {results['signal_agreement_min']:.2%})"
    )
    print(
        f"  Trade agreement:    {results['trade_agreement_rate']:.2%} "
        f"(over {results['trade_total']} trade steps)"
    )
    print(f"  Max pos divergence: {results['max_position_divergence']} contracts")
    print(f"  Total steps:        {results['signal_total_steps']}")
    print("  Runs:")
    for run in results["per_run"]:
        print(
            f"    [{run['run']}] {run['label']}: "
            f"{run['trades']} trades ({run['buys']}B/{run['sells']}S), "
            f"final pos={run['final_position']:+d}"
        )


def _check_thresholds(results: dict[str, Any]) -> bool:
    """Check against M32 paper-gate thresholds."""
    ok = True
    if results["signal_agreement_rate"] < 0.95:
        print(f"  FAIL signal_agreement_rate = {results['signal_agreement_rate']:.2%} (< 95%)")
        ok = False
    if results["trade_agreement_rate"] < 0.90:
        print(f"  FAIL trade_agreement_rate = {results['trade_agreement_rate']:.2%} (< 90%)")
        ok = False
    if results["max_position_divergence"] > 1:
        print(f"  FAIL max_position_divergence = {results['max_position_divergence']} (> 1)")
        ok = False
    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Measure decision stability")
    parser.add_argument("--fast", type=int, default=5)
    parser.add_argument("--slow", type=int, default=20)
    parser.add_argument("--bars", type=int, default=200)
    parser.add_argument("--pattern", choices=["random", "sawtooth"], default="sawtooth")
    args = parser.parse_args()

    print(f"Decision Stability - SMA({args.fast}/{args.slow})")
    print(f"Pattern: {args.pattern}, Bars: {args.bars}")

    # Generate price sequence
    prices = _random_walk(args.bars) if args.pattern == "random" else _sawtooth(args.bars)

    _print_prices(prices)

    # --- Test A: Pure signal determinism (no broker) ---
    runs_pure: list[list[dict[str, Any]]] = []
    for _i in range(5):
        runs_pure.append(_run_pure(prices, args.fast, args.slow))
    r_pure = _compare_decisions(runs_pure, [f"pure-{i}" for i in range(5)])
    _print_report(r_pure, "Pure (no broker)")
    pure_ok = _check_thresholds(r_pure)
    print(f"  Pure stability: {'PASS' if pure_ok else 'FAIL'}")

    # --- Test B: With broker, realism OFF ---
    runs_clean: list[list[dict[str, Any]]] = []
    for _i in range(5):
        run = await _run_with_broker(prices, args.fast, args.slow, realistic=False)
        runs_clean.append(run)
    r_clean = _compare_decisions(runs_clean, [f"broker-clean-{i}" for i in range(5)])
    _print_report(r_clean, "Broker realism=OFF")
    clean_ok = _check_thresholds(r_clean)
    print(f"  Broker (clean) stability: {'PASS' if clean_ok else 'FAIL'}")

    # --- Test C: With broker, realism ON ---
    runs_real: list[list[dict[str, Any]]] = []
    for _i in range(5):
        run = await _run_with_broker(prices, args.fast, args.slow, realistic=True)
        runs_real.append(run)
    r_real = _compare_decisions(runs_real, [f"broker-real-{i}" for i in range(5)])
    _print_report(r_real, "Broker realism=ON")
    real_ok = _check_thresholds(r_real)
    print(f"  Broker (real) stability: {'PASS' if real_ok else 'FAIL'}")

    # Overall
    all_ok = pure_ok and clean_ok and real_ok
    print(f"\nOverall Decision Stability: {'PASS' if all_ok else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())

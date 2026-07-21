#!/usr/bin/env -S uv run --frozen
"""M32-020: Paper fill realism measurement.

Submits a batch of market orders through PaperBroker with realism features
enabled, then reports key quality metrics.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from decimal import Decimal
from typing import Any

from execution.brokers.config import BrokerConfig
from execution.brokers.paper import PaperBroker

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


class _MarketOrder:
    """Minimal duck-typed market order."""

    def __init__(self, instrument_id: str, side: str, quantity: int) -> None:
        self.order_id = None
        self.instrument_id = instrument_id
        self.side = side
        self.quantity = Decimal(str(quantity))
        self.price = None
        self.order_type = "market"
        self.stop_price = None
        self.take_profit_price = None
        self.parent_order_id = None


def _realistic_config() -> BrokerConfig:
    """BrokerConfig with all realism features enabled at conservative levels."""
    return BrokerConfig(
        paper_spread_bps=20,  # 0.2 % — tight like ES
        paper_slippage_bps=10,  # 0.1 % — typical
        paper_partial_fill_prob=0.3,  # 30 % chance
        paper_latency_ms=25,  # 25 ms round-trip
        paper_commission_per_contract=0.85,  # ES rate
    )


def _zero_config() -> BrokerConfig:
    """Baseline config with realism features disabled."""
    return BrokerConfig(
        paper_spread_bps=0,
        paper_slippage_bps=0,
        paper_partial_fill_prob=0.0,
        paper_latency_ms=0,
        paper_commission_per_contract=0.0,
    )


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------


async def _run_batch(
    broker: PaperBroker, instrument: str, n_orders: int, base_price: Decimal
) -> list[dict[str, Any]]:
    """Submit ``n_orders`` market buy orders at ``base_price``, alternating
    buy/sell to keep the position small, and record fill details.
    """
    records: list[dict[str, Any]] = []
    price = base_price

    for i in range(n_orders):
        side = "buy" if i % 2 == 0 else "sell"
        qty = 2  # small enough to test partial fills

        start = time.monotonic()
        broker_id = await broker.submit_order(_MarketOrder(instrument, side, qty))
        elapsed_ms = (time.monotonic() - start) * 1000

        # Refresh the price for the next order (random walk +-0.5 %)
        price += base_price * Decimal(str((i % 3 - 1) * 0.002))
        await broker.on_price_update(price)

        # Collect fill(s) for this broker order
        for fill in broker._fills:
            if fill.broker_order_id == broker_id:
                records.append(
                    {
                        "order_idx": i,
                        "broker_id": broker_id,
                        "side": side,
                        "requested_qty": qty,
                        "fill_qty": int(fill.quantity),
                        "fill_price": float(fill.price),
                        "expected_price": float(price),
                        "slippage_bps": _slippage_bps(fill.price, price, side),
                        "commission": float(fill.commission),
                        "latency_ms": round(elapsed_ms, 1),
                    }
                )

    return records


def _slippage_bps(fill_price: Decimal, expected: Decimal, side: str) -> float:
    """Signed slippage in basis points (positive = adverse)."""
    if expected == Decimal("0"):
        return 0.0
    diff = fill_price - expected
    raw_bps = float(diff / expected) * 10_000
    return raw_bps if side == "buy" else -raw_bps


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _report(label: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate metrics from a batch of fill records."""
    if not records:
        return {"label": label, "n_fills": 0}

    n_orders = len({r["broker_id"] for r in records})
    partials = [r for r in records if r["fill_qty"] < r["requested_qty"]]
    prices = [r["fill_price"] for r in records]
    slippages = [r["slippage_bps"] for r in records]
    commissions = [r["commission"] for r in records]
    latencies = [r["latency_ms"] for r in records]

    return {
        "label": label,
        "n_fills": len(records),
        "n_orders": n_orders,
        "partial_fills": len(partials),
        "partial_rate": round(len(partials) / max(len(records), 1), 3),
        "avg_fill_price": round(statistics.mean(prices), 4),
        "min_fill_price": round(min(prices), 4),
        "max_fill_price": round(max(prices), 4),
        "avg_slippage_bps": round(statistics.mean(slippages), 2),
        "min_slippage_bps": round(min(slippages), 2),
        "max_slippage_bps": round(max(slippages), 2),
        "std_slippage_bps": round(statistics.stdev(slippages), 2) if len(slippages) > 1 else 0.0,
        "avg_commission": round(statistics.mean(commissions), 4),
        "total_commission": round(sum(commissions), 4),
        "avg_latency_ms": round(statistics.mean(latencies), 1),
        "max_latency_ms": round(max(latencies), 1),
    }


def _print_report(r: dict[str, Any]) -> None:
    """Print a formatted report block."""
    print(f"  Fills:          {r['n_fills']} ({r['n_orders']} orders)")
    print(f"  Partial fills:  {r['partial_fills']} ({r['partial_rate']:.1%})")
    print(
        f"  Price range:    {r['min_fill_price']} - {r['max_fill_price']} "
        f"(avg {r['avg_fill_price']})"
    )
    print(
        f"  Slippage (bps): avg={r['avg_slippage_bps']:.2f} "
        f"std={r['std_slippage_bps']:.2f}  "
        f"[{r['min_slippage_bps']:.2f}, {r['max_slippage_bps']:.2f}]"
    )
    print(f"  Commission:     avg=${r['avg_commission']:.4f}  total=${r['total_commission']:.4f}")
    print(f"  Latency:        avg={r['avg_latency_ms']:.1f} ms  max={r['max_latency_ms']:.1f} ms\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    instrument = "ES"
    base_price = Decimal("4500")
    n_orders = 50

    print(f"Paper Fill Realism - {n_orders} orders, instrument={instrument}\n")

    # --- Baseline: realism OFF ---
    broker_off = PaperBroker(_zero_config())
    await broker_off.on_price_update(base_price)
    baseline = await _run_batch(broker_off, instrument, n_orders, base_price)
    r_base = _report("realism=OFF", baseline)
    print(f"--- {r_base['label']} ---")
    _print_report(r_base)

    # --- Realism: ON ---
    broker_on = PaperBroker(_realistic_config())
    await broker_on.on_price_update(base_price)
    realistic = await _run_batch(broker_on, instrument, n_orders, base_price)
    r_real = _report("realism=ON", realistic)
    print(f"--- {r_real['label']} ---")
    _print_report(r_real)

    # --- Diff ---
    print("--- Delta (ON - OFF) ---")
    for key in (
        "avg_slippage_bps",
        "partial_rate",
        "avg_commission",
        "avg_latency_ms",
        "avg_fill_price",
    ):
        off = r_base.get(key, 0)
        on_val = r_real.get(key, 0)
        symbol = "+" if on_val > off else "-" if on_val < off else " "
        print(f"  {symbol} {key:25s}  {off:>10.4f}  ->  {on_val:<10.4f}")

    # --- Check acceptability thresholds ---
    print("\nThresholds (Topstep 50K paper-gate):")
    ok = True
    avg_slip = r_real["avg_slippage_bps"]
    if avg_slip > 20:
        print(f"  FAIL avg_slippage_bps = {avg_slip:.2f} (> 20)")
        ok = False
    else:
        print(f"  PASS avg_slippage_bps = {avg_slip:.2f} (<= 20)")

    partial_rate = r_real["partial_rate"]
    if partial_rate > 0.5:
        print(f"  WARN partial_rate = {partial_rate:.2%} (> 50%, may be excessive)")

    avg_lat = r_real["avg_latency_ms"]
    if avg_lat > 200:
        print(f"  FAIL avg_latency_ms = {avg_lat:.1f} ms (> 200)")
        ok = False
    else:
        print(f"  PASS avg_latency_ms = {avg_lat:.1f} ms (<= 200)")

    print(f"\nOverall: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())

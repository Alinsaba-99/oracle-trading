"""Trade CLI command handlers — submit, list, cancel, status, kill."""

from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Any


def _get_broker(broker_type: str = "paper", **kwargs: Any) -> Any:
    """Create and return a broker instance by type name.

    Args:
        broker_type: One of ``"paper"``, ``"ibkr"``, ``"ccxt"``.
        **kwargs: Additional config parameters forwarded to the broker.

    Returns:
        An initialized broker instance.
    """
    from execution.brokers import BrokerConfig
    from execution.brokers.paper import PaperBroker

    config = BrokerConfig(**kwargs)

    if broker_type == "paper":
        return PaperBroker(config)

    if broker_type == "ibkr":
        from execution.brokers.ibkr import IBKRBroker

        return IBKRBroker(config)

    if broker_type == "ccxt":
        from execution.brokers.ccxt_broker import CCXTBroker

        return CCXTBroker(config)

    msg = f"Unknown broker type: {broker_type!r}. Choose from: paper, ibkr, ccxt."
    raise ValueError(msg)


def _get_order_manager(
    broker_type: str = "paper", broker_kwargs: dict[str, Any] | None = None
) -> Any:
    """Create a broker and OrderManager for the given broker type.

    Wires a mandatory risk manager:
    - Paper broker uses ``_PaperRiskAdapter`` (basic validation only).
    - Live brokers will use ``PropFirmOrderRiskAdapter`` once market
      data and contract specs are wired (G2/G4).
    """
    from execution.order_manager.manager import OrderManager

    broker = _get_broker(broker_type, **(broker_kwargs or {}))
    risk = _PaperRiskAdapter()
    return OrderManager(broker, risk_manager=risk)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


class _PaperRiskAdapter:
    """Minimal risk adapter for paper-only CLI operations.

    Performs basic validation (quantity > 0, non-empty instrument) but
    does **not** enforce prop-firm rules, drawdown limits or contract
    caps.  This is safe only for paper / research mode.

    Will be replaced by ``PropFirmOrderRiskAdapter`` once market data
    and contract specs are wired (G2/G4 gates).
    """

    async def check_order(self, request: Any) -> bool:
        if request.quantity is not None and request.quantity <= 0:
            return False
        return bool(request.instrument_id)


async def handle_trade_submit(args: argparse.Namespace) -> int:
    """Submit an order via CLI.

    Usage:
        oracle trade submit --instrument SPY --side buy --qty 100
        oracle trade submit --instrument SPY --side buy --qty 100 --algo vwap
        oracle trade submit --instrument SPY --side buy --qty 100 --price 450 --order-type limit
        oracle trade submit --instrument SPY --side buy --qty 100 --dry-run
        oracle trade submit --instrument SPY --side buy --qty 100 --broker ibkr
    """
    from execution.order_manager.types import OrderRequest

    broker_type: str = getattr(args, "broker", "paper")
    if broker_type != "paper" and not args.dry_run:
        print(
            "Live broker submission is disabled until the certified "
            "risk/OMS/ledger path is available. Use --dry-run or --broker paper."
        )
        return 2

    req = OrderRequest(
        instrument_id=args.instrument,
        side=args.side,
        quantity=Decimal(str(args.qty)),
        order_type=args.order_type or "market",
        price=Decimal(str(args.price)) if args.price else None,
        time_in_force=args.time_in_force or "day",
        execution_algo=args.algo,
        algo_config=args.algo_config or {},
        source="cli",
    )

    if args.dry_run:
        msg = f"DRY RUN: {req.side} {req.quantity} {req.instrument_id}"
        msg += f" via {req.execution_algo or 'market'} on {broker_type}"
        print(msg)
        return 0

    mgr = _get_order_manager(broker_type)
    result = await mgr.submit(req)
    print(f"Order {'REJECTED' if result.status == 'rejected' else 'SUBMITTED'}: {result.order_id}")
    if result.error:
        print(f"  Error: {result.error}")
    return 0 if result.status in ("submitted", "filled") else 1


async def handle_trade_list(args: argparse.Namespace) -> int:
    """List open orders."""
    broker_type: str = getattr(args, "broker", "paper")
    mgr = _get_order_manager(broker_type)
    orders = await mgr.open_orders()
    if not orders:
        print("No open orders")
        return 0
    for o in orders:
        print(f"  {o.order_id[:8]} | {o.side} {o.quantity} {o.instrument_id} | {o.status}")
    return 0


async def handle_trade_cancel(args: argparse.Namespace) -> int:
    """Cancel an order by internal ID."""
    broker_type: str = getattr(args, "broker", "paper")
    mgr = _get_order_manager(broker_type)
    ok = await mgr.cancel(args.order_id)
    if ok:
        print(f"Cancelled: {args.order_id}")
        return 0
    print(f"Order not found or already filled: {args.order_id}")
    return 1


async def handle_trade_status(args: argparse.Namespace) -> int:
    """Check order status by internal ID."""
    broker_type: str = getattr(args, "broker", "paper")
    mgr = _get_order_manager(broker_type)
    await mgr.reconcile()
    order = mgr.get_order(args.order_id)
    if order is None:
        print(f"Order not found: {args.order_id}")
        return 1
    print(f"Order ID:   {order.order_id}")
    print(f"Side:       {order.side.value}")
    print(f"Quantity:   {order.quantity}")
    print(f"Instrument: {order.instrument_id}")
    print(f"Status:     {order.status.value}")
    print(f"Filled:     {order.filled_quantity}")
    if order.avg_fill_price is not None:
        print(f"Avg Price:  {order.avg_fill_price}")
    return 0


async def handle_trade_kill(args: argparse.Namespace) -> int:
    """Cancel ALL open orders."""
    broker_type: str = getattr(args, "broker", "paper")
    mgr = _get_order_manager(broker_type)
    count = await mgr.kill_all()
    print(f"Cancelled {count} open order(s)")
    return 0

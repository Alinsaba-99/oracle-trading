"""Trade CLI command handlers — submit, list, cancel, status, kill."""

from __future__ import annotations

import argparse
from decimal import Decimal


async def handle_trade_submit(args: argparse.Namespace) -> int:
    """Submit an order via CLI.

    Usage:
        oracle trade submit --instrument SPY --side buy --qty 100
        oracle trade submit --instrument SPY --side buy --qty 100 --algo vwap
        oracle trade submit --instrument SPY --side buy --qty 100 --price 450 --order-type limit
        oracle trade submit --instrument SPY --side buy --qty 100 --dry-run
    """
    from execution.brokers import BrokerConfig
    from execution.brokers.paper import PaperBroker
    from execution.order_manager.manager import OrderManager
    from execution.order_manager.types import OrderRequest

    config = BrokerConfig()
    broker = PaperBroker(config)
    mgr = OrderManager(broker)

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
        msg += f" via {req.execution_algo or 'market'}"
        print(msg)
        return 0

    result = await mgr.submit(req)
    print(f"Order {'REJECTED' if result.status == 'rejected' else 'SUBMITTED'}: {result.order_id}")
    if result.error:
        print(f"  Error: {result.error}")
    return 0 if result.status == "submitted" else 1


async def handle_trade_list(_args: argparse.Namespace) -> int:
    """List open orders."""
    from execution.brokers import BrokerConfig
    from execution.brokers.paper import PaperBroker
    from execution.order_manager.manager import OrderManager

    mgr = OrderManager(PaperBroker(BrokerConfig()))
    orders = mgr.open_orders()
    if not orders:
        print("No open orders")
        return 0
    for o in orders:
        print(f"  {o.order_id[:8]} | {o.side} {o.quantity} {o.instrument_id} | {o.status}")
    return 0


async def handle_trade_cancel(args: argparse.Namespace) -> int:
    """Cancel an order by internal ID."""
    from execution.brokers import BrokerConfig
    from execution.brokers.paper import PaperBroker
    from execution.order_manager.manager import OrderManager

    mgr = OrderManager(PaperBroker(BrokerConfig()))
    ok = await mgr.cancel(args.order_id)
    if ok:
        print(f"Cancelled: {args.order_id}")
        return 0
    print(f"Order not found or already filled: {args.order_id}")
    return 1


async def handle_trade_status(args: argparse.Namespace) -> int:
    """Check order status by internal ID."""
    from execution.brokers import BrokerConfig
    from execution.brokers.paper import PaperBroker
    from execution.order_manager.manager import OrderManager

    mgr = OrderManager(PaperBroker(BrokerConfig()))
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


async def handle_trade_kill(_args: argparse.Namespace) -> int:
    """Cancel ALL open orders."""
    from execution.brokers import BrokerConfig
    from execution.brokers.paper import PaperBroker
    from execution.order_manager.manager import OrderManager

    mgr = OrderManager(PaperBroker(BrokerConfig()))
    count = await mgr.kill_all()
    print(f"Cancelled {count} open order(s)")
    return 0

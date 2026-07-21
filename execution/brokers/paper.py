"""Paper trading broker — simulates fills with configurable slippage / latency.

Semantics (post M32-010):

- ``order_type="market"`` and no ``price`` → fills immediately at the current
  synthetic price (with slippage).
- ``order_type="limit"`` → rests as ``submitted`` until ``on_price_update``
  sees a trade through the limit; then fills.
- ``order_type="stop"`` → rests until the synthetic price trades through
  ``stop_price``; then fills as a market order.
- ``stop_price`` / ``take_profit_price`` on an entry order auto-create
  child bracket legs once the entry fills. The bracket legs are OCO: the
  first one to trigger cancels the other.
- ``on_price_update(price)`` is the single point where the synthetic market
  moves. Tests drive it explicitly; ``submit_order`` on a marketable order
  uses the current synthetic price.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

from execution.brokers.base import BaseBroker
from execution.brokers.config import BrokerConfig
from execution.brokers.types import BrokerFill, BrokerOrder, BrokerPosition


class PaperBroker(BaseBroker):
    """Paper / simulation broker.

    State is kept in-memory only. Prices are synthetic (default ~$100)
    unless a test drives ``on_price_update`` with an explicit series.
    """

    def __init__(self, config: BrokerConfig | None = None) -> None:
        super().__init__(config)
        self._orders: dict[str, BrokerOrder] = {}
        self._fills: list[BrokerFill] = []
        self._positions: dict[str, Decimal] = {}
        self._order_counter: int = 0
        self._current_price: Decimal = Decimal("100")
        # OCO linkage: entry_id -> {"stop": id, "tp": id}
        self._bracket_children: dict[str, dict[str, str]] = {}
        # M32-012: daily-session bookkeeping.
        self._session_date: date | None = None
        self._daily_pnl: Decimal = Decimal("0")
        self._daily_trade_count: int = 0

    # ------------------------------------------------------------------
    # Connection (no-op — always "connected")
    # ------------------------------------------------------------------
    async def _do_connect(self) -> None:
        pass

    async def _do_disconnect(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Market-data driver
    # ------------------------------------------------------------------
    async def on_price_update(self, price: Decimal | float | int) -> list[BrokerFill]:
        """Update the synthetic market price; trigger any resting stops/limits.

        Returns the list of fills produced by this tick (may be empty).
        """
        # Simulated latency before the price update reaches the broker
        if self._config.paper_latency_ms > 0:
            jitter = random.uniform(0.5, 1.5) * self._config.paper_latency_ms
            await asyncio.sleep(jitter / 1000)

        new_price = Decimal(str(price))
        self._current_price = new_price
        triggered: list[BrokerFill] = []

        # Trigger resting orders whose condition is met. Iterate on a
        # snapshot because fills below may mutate ``_orders`` (bracket OCO).
        for order in list(self._orders.values()):
            if order.status != "submitted":
                continue
            fill = self._maybe_trigger(order, new_price)
            if fill is not None:
                triggered.append(fill)
        return triggered

    # ------------------------------------------------------------------
    # Order lifecycle
    # ------------------------------------------------------------------
    async def submit_order(self, order: Any) -> str:
        """Submit an order. Market orders (no ``price``) fill immediately at
        the current synthetic price. Limit/stop orders rest until triggered.

        If the order carries ``stop_price`` and/or ``take_profit_price`` and
        is an entry, bracket children are created when the entry fills.

        Returns the broker-local order ID.
        """
        # Simulated latency before the order reaches the broker
        if self._config.paper_latency_ms > 0:
            jitter = random.uniform(0.5, 1.5) * self._config.paper_latency_ms
            await asyncio.sleep(jitter / 1000)

        self._order_counter += 1
        broker_id = f"paper_{self._order_counter}"
        local_id = str(getattr(order, "order_id", None) or uuid4())

        order_type = str(getattr(order, "order_type", "market") or "market")
        price = getattr(order, "price", None)
        stop_price = getattr(order, "stop_price", None)
        take_profit_price = getattr(order, "take_profit_price", None)
        parent_id = getattr(order, "parent_order_id", None)

        bo = BrokerOrder(
            broker_order_id=broker_id,
            local_order_id=local_id,
            namespaced_id=f"paper:{broker_id}",
            instrument_id=getattr(order, "instrument_id", ""),
            side=str(getattr(order, "side", "buy")).lower(),
            quantity=getattr(order, "quantity", Decimal("0")),
            status="submitted",
            price=Decimal(str(price)) if price is not None else None,
            order_type=order_type,
            stop_price=Decimal(str(stop_price)) if stop_price is not None else None,
            take_profit_price=(
                Decimal(str(take_profit_price)) if take_profit_price is not None else None
            ),
            parent_order_id=parent_id,
        )
        self._orders[broker_id] = bo

        # Marketable right now? A market order always is; limit/stop only
        # if the current price already crosses their trigger.
        if self._is_marketable(bo, self._current_price):
            self._fill(bo, self._current_price)

        return broker_id

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel a previously submitted (resting) order. Returns False if
        the order is already filled, cancelled, or unknown.
        """
        order = self._orders.get(broker_order_id)
        if order is None:
            return False
        if order.status in ("filled", "cancelled"):
            return False
        order.status = "cancelled"
        return True

    async def amend_order(self, broker_order_id: str, **changes: Any) -> bool:
        """Amend a resting order's attributes. Returns False when the order
        is already filled/cancelled or does not exist.
        """
        order = self._orders.get(broker_order_id)
        if order is None or order.status in ("filled", "cancelled"):
            return False
        for key, value in changes.items():
            if hasattr(order, key) and value is not None:
                if key in ("price", "stop_price", "take_profit_price", "quantity"):
                    object.__setattr__(order, key, Decimal(str(value)))
                else:
                    object.__setattr__(order, key, value)
        return True

    async def order_status(self, broker_order_id: str) -> str:
        """Return the status string, or ``"unknown"``."""
        order = self._orders.get(broker_order_id)
        return order.status if order else "unknown"

    async def get_fills(self) -> list[BrokerFill]:
        """Return all fills recorded by this broker (used by OrderManager reconciliation)."""
        return list(self._fills)

    async def open_orders(self) -> list[BrokerOrder]:
        """Return orders that are still open (not filled/cancelled)."""
        return [o for o in self._orders.values() if o.status not in ("filled", "cancelled")]

    async def cancel_all_orders(self) -> int:
        """Cancel every resting order. Returns the count cancelled (M32-011)."""
        cancelled = 0
        for order in self._orders.values():
            if order.status == "submitted":
                order.status = "cancelled"
                cancelled += 1
        return cancelled

    async def flatten_all(self) -> dict[str, Any]:
        """M32-011: cancel all open orders and close every open position.

        Closes positions at the current synthetic price with market-order
        semantics (immediate fill). Returns a summary dict with counts.
        """
        cancelled = await self.cancel_all_orders()

        flattened = 0
        errors: list[str] = []
        for pos in await self.positions():
            try:
                close_side = "sell" if pos.quantity > 0 else "buy"

                class _Close:
                    order_id = None
                    instrument_id = pos.instrument_id
                    side = close_side
                    quantity = abs(pos.quantity)
                    price = None
                    order_type = "market"

                await self.submit_order(_Close())
                flattened += 1
            except Exception as exc:  # pragma: no cover — defensive
                errors.append(f"{pos.instrument_id}: {exc}")

        return {
            "success": not errors,
            "open_orders_cancelled": cancelled,
            "positions_flattened": flattened,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # M32-012: daily rollover
    # ------------------------------------------------------------------
    async def rollover(self, new_date: date, *, auto_flatten: bool = False) -> dict[str, Any]:
        """M32-012: advance the broker's session date; reset daily counters.

        - ``auto_flatten=False`` (The5ers-style): positions carry overnight;
          only daily counters reset.
        - ``auto_flatten=True`` (Lucid-style intraday-only): open positions
          are flattened at the rollover price, then counters reset.

        Returns a summary with the rollover action taken.
        """
        flatten_summary: dict[str, Any] = {
            "open_orders_cancelled": 0,
            "positions_flattened": 0,
            "errors": [],
        }
        if auto_flatten:
            flatten_summary = await self.flatten_all()

        previous_date = self._session_date
        self._session_date = new_date
        self._daily_pnl = Decimal("0")
        self._daily_trade_count = 0

        return {
            "previous_date": previous_date.isoformat() if previous_date else None,
            "new_date": new_date.isoformat(),
            "auto_flatten": auto_flatten,
            "flatten": flatten_summary,
            "daily_pnl_reset": True,
            "daily_trade_count_reset": True,
        }

    async def daily_state(self) -> dict[str, Any]:
        """Return current daily-session state (for tests + reconciliation)."""
        return {
            "session_date": self._session_date.isoformat() if self._session_date else None,
            "daily_pnl": float(self._daily_pnl),
            "daily_trade_count": self._daily_trade_count,
        }

    # ------------------------------------------------------------------
    # M32-013: snapshot / restore (restart recovery)
    # ------------------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        """Serialize broker state for durable persistence.

        Returns a JSON-safe dict capturing resting orders, fills, positions,
        bracket linkage, and daily counters. Use ``restore`` to rehydrate.
        """
        return {
            "order_counter": self._order_counter,
            "current_price": str(self._current_price),
            "session_date": self._session_date.isoformat() if self._session_date else None,
            "daily_pnl": str(self._daily_pnl),
            "daily_trade_count": self._daily_trade_count,
            "orders": [o.model_dump(mode="json") for o in self._orders.values()],
            "fills": [f.model_dump(mode="json") for f in self._fills],
            "bracket_children": {
                parent: dict(children) for parent, children in self._bracket_children.items()
            },
        }

    @classmethod
    def restore(cls, snapshot: dict[str, Any], config: BrokerConfig | None = None) -> PaperBroker:
        """Rehydrate a PaperBroker from a ``snapshot()`` dict."""
        broker = cls(config)
        broker._order_counter = int(snapshot.get("order_counter", 0))
        broker._current_price = Decimal(str(snapshot.get("current_price", "100")))
        sd = snapshot.get("session_date")
        broker._session_date = date.fromisoformat(sd) if sd else None
        broker._daily_pnl = Decimal(str(snapshot.get("daily_pnl", "0")))
        broker._daily_trade_count = int(snapshot.get("daily_trade_count", 0))

        for order_dict in snapshot.get("orders", []):
            order = BrokerOrder.model_validate(order_dict)
            broker._orders[order.broker_order_id] = order
        for fill_dict in snapshot.get("fills", []):
            broker._fills.append(BrokerFill.model_validate(fill_dict))
        broker._bracket_children = {
            parent: dict(children)
            for parent, children in snapshot.get("bracket_children", {}).items()
        }
        return broker

    async def account_summary(self) -> dict[str, Any]:
        """Return a summary of cash / balance.

        Paper broker tracks everything in-memory; return the last P&L
        approximated from fill prices vs the current synthetic price.
        """
        total_pnl = Decimal("0")
        for fill in self._fills:
            order = self._orders.get(fill.broker_order_id)
            if order is None:
                continue
            entry_price = fill.price
            current_price = self._current_price
            if order.side == "buy":
                pnl = (current_price - entry_price) * fill.quantity
            else:
                pnl = (entry_price - current_price) * fill.quantity
            total_pnl += pnl

        return {
            "cash": float(total_pnl + Decimal("100000")),
            "balance": float(total_pnl + Decimal("100000")),
            "pnl": float(total_pnl),
        }

    async def positions(self) -> list[BrokerPosition]:
        """Return current positions aggregated from fills."""
        net: dict[str, Decimal] = {}
        avg_price: dict[str, Decimal] = {}
        for fill in self._fills:
            order = self._orders.get(fill.broker_order_id)
            if order is None:
                continue
            instrument = order.instrument_id
            signed_qty = fill.quantity if order.side == "buy" else -fill.quantity
            net[instrument] = net.get(instrument, Decimal("0")) + signed_qty
            avg_price[instrument] = fill.price
        return [
            BrokerPosition(
                instrument_id=inst, quantity=qty, avg_price=avg_price.get(inst, Decimal("0"))
            )
            for inst, qty in net.items()
            if qty != Decimal("0")
        ]

    async def stream_orders(self) -> AsyncGenerator[BrokerOrder, None]:
        """Stream order updates (passthrough stub for paper)."""
        if False:
            yield  # pragma: no cover

    async def stream_positions(self) -> AsyncGenerator[BrokerPosition, None]:
        """Stream position updates (passthrough stub for paper)."""
        if False:
            yield  # pragma: no cover

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _is_marketable(self, order: BrokerOrder, current: Decimal) -> bool:
        """Decide whether an order should fill at ``current``."""
        if order.order_type == "market":
            return True
        if order.order_type == "limit":
            if order.price is None:
                return False
            if order.side == "buy":
                return current <= order.price
            return current >= order.price
        if order.order_type in ("stop", "stop_limit"):
            if order.stop_price is None:
                return False
            if order.side == "buy":
                return current >= order.stop_price
            return current <= order.stop_price
        return False

    def _maybe_trigger(self, order: BrokerOrder, current: Decimal) -> BrokerFill | None:
        """Fire a resting limit/stop if the new price crosses its trigger."""
        if not self._is_marketable(order, current):
            return None
        return self._fill(order, current)

    def _fill(self, order: BrokerOrder, trigger_price: Decimal) -> BrokerFill:
        """Mark an order filled at ``trigger_price`` with slippage; spawn
        bracket children if this is an entry; apply OCO if this is a child.

        Realism features (config-gated):
        - **Spread**: buy fills at ask (mid + half spread), sell at bid.
        - **Partial fill**: with ``paper_partial_fill_prob``, only a fraction
          of the order quantity is filled; the remainder stays submitted.
        - **Commission**: per-contract fee from config.
        """
        # -- Spread: buy at ask, sell at bid --------------------------------
        half_spread = Decimal(str(self._config.paper_spread_bps)) / Decimal("20000")
        if order.side == "buy":
            base_price = trigger_price * (Decimal("1") + half_spread)
        else:
            base_price = trigger_price * (Decimal("1") - half_spread)

        # -- Slippage: random component -------------------------------------
        slip = 1 + (random.uniform(-1, 1) * self._config.paper_slippage_bps / 10000)
        fill_price = (base_price * Decimal(str(slip))).quantize(Decimal("0.01"))

        # -- Determine fill quantity (partial fill support) -----------------
        original_qty = order.quantity
        fill_qty = original_qty
        if (
            self._config.paper_partial_fill_prob > 0
            and random.random() < self._config.paper_partial_fill_prob
            and original_qty > 1
        ):
            ratio = random.uniform(0.5, 0.99)
            fill_qty = (original_qty * Decimal(str(ratio))).quantize(
                Decimal("1"), rounding="ROUND_HALF_UP"
            )
            if fill_qty == Decimal("0"):
                fill_qty = Decimal("1")

        # -- Spawn bracket children BEFORE modifying quantity, so they
        # -- inherit the original requested quantity.
        if order.parent_order_id is None and (
            order.stop_price is not None or order.take_profit_price is not None
        ):
            self._spawn_bracket(order)

        # -- Commission -----------------------------------------------------
        commission = Decimal(str(self._config.paper_commission_per_contract)) * fill_qty

        fill = BrokerFill(
            broker_order_id=order.broker_order_id,
            fill_id=str(uuid4()),
            quantity=fill_qty,
            price=fill_price,
            commission=commission,
        )
        self._fills.append(fill)
        order.filled_quantity += fill_qty

        if fill_qty < original_qty:
            order.quantity = original_qty - fill_qty
            # Remainder stays submitted for a future trigger
        else:
            order.quantity = Decimal("0")
            order.status = "filled"

        if order.parent_order_id is not None:
            siblings = self._bracket_children.get(order.parent_order_id, {})
            for sibling_id in siblings.values():
                if sibling_id == order.broker_order_id:
                    continue
                sibling = self._orders.get(sibling_id)
                if sibling is not None and sibling.status == "submitted":
                    sibling.status = "cancelled"
        return fill

    def _spawn_bracket(self, entry: BrokerOrder) -> None:
        """Create stop + take-profit child orders for a filled entry."""
        children: dict[str, str] = {}
        exit_side = "sell" if entry.side == "buy" else "buy"

        if entry.stop_price is not None:
            self._order_counter += 1
            stop_id = f"paper_{self._order_counter}"
            self._orders[stop_id] = BrokerOrder(
                broker_order_id=stop_id,
                local_order_id=str(uuid4()),
                namespaced_id=f"paper:{stop_id}",
                instrument_id=entry.instrument_id,
                side=exit_side,
                quantity=entry.quantity,
                status="submitted",
                order_type="stop",
                stop_price=entry.stop_price,
                parent_order_id=entry.broker_order_id,
            )
            children["stop"] = stop_id

        if entry.take_profit_price is not None:
            self._order_counter += 1
            tp_id = f"paper_{self._order_counter}"
            self._orders[tp_id] = BrokerOrder(
                broker_order_id=tp_id,
                local_order_id=str(uuid4()),
                namespaced_id=f"paper:{tp_id}",
                instrument_id=entry.instrument_id,
                side=exit_side,
                quantity=entry.quantity,
                status="submitted",
                order_type="limit",
                price=entry.take_profit_price,
                parent_order_id=entry.broker_order_id,
            )
            children["tp"] = tp_id

        if children:
            self._bracket_children[entry.broker_order_id] = children

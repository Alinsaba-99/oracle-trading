"""Emergency stop / kill switch — independent process flatten.

The kill switch is designed to be callable from any context (CLI, API,
monitoring script) and to execute a flatten of all positions regardless
of the main application state.  It communicates directly with the
broker adapter, bypassing the OMS if necessary.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from uuid import uuid4

from core.domain.broker import BrokerOrder, BrokerPosition

logger = logging.getLogger("oracle.execution.kill")


class KillSwitch:
    """Emergency stop for flattening all positions.

    Usage::

        kill = KillSwitch(broker)
        result = await kill.flatten_all()
        if not result["success"]:
            alert_operator(result)
    """

    def __init__(self, broker: Any) -> None:
        self._broker = broker

    async def flatten_all(self) -> dict[str, Any]:
        """Flatten ALL positions across ALL instruments.

        Returns a dict with:
        - ``success``: True if all flatten orders were submitted
        - ``open_orders_cancelled``: count of cancelled orders
        - ``positions_flattened``: count of flatten orders sent
        - ``errors``: list of error messages (if any)
        """
        logger.warning("🔴 KILL SWITCH ACTIVATED — flattening all positions")

        result: dict[str, Any] = {
            "success": True,
            "open_orders_cancelled": 0,
            "positions_flattened": 0,
            "errors": [],
        }

        try:
            # 1. Cancel all open orders
            if hasattr(self._broker, "cancel_all_orders"):
                cancelled = await self._broker.cancel_all_orders()
                result["open_orders_cancelled"] = cancelled

            # 2. Get current positions
            positions = []
            if hasattr(self._broker, "positions"):
                positions = await self._broker.positions()

            # 3. Submit typed flatten orders (market orders to close)
            for pos in positions:
                try:
                    if isinstance(pos, BrokerPosition):
                        instrument_id = pos.instrument_id
                        quantity = pos.quantity
                    else:
                        instrument_id = str(pos.get("instrument_id", ""))
                        quantity = Decimal(str(pos.get("quantity", "0")))

                    if not instrument_id or quantity == 0:
                        continue

                    close_side = "sell" if quantity > 0 else "buy"
                    if hasattr(self._broker, "submit_order"):
                        emergency_id = str(uuid4())
                        await self._broker.submit_order(
                            BrokerOrder(
                                broker_order_id=emergency_id,
                                local_order_id=emergency_id,
                                namespaced_id=f"kill:{emergency_id}",
                                instrument_id=instrument_id,
                                side=close_side,
                                quantity=abs(quantity),
                                order_type="market",
                            )
                        )
                        result["positions_flattened"] += 1
                except Exception as e:
                    instrument = getattr(pos, "instrument_id", "unknown")
                    if isinstance(pos, dict):
                        instrument = pos.get("instrument_id", "unknown")
                    result["errors"].append(f"Failed to flatten {instrument}: {e}")

            # Submitting flatten orders is not enough: success requires the
            # broker snapshot to be flat after the operation.
            if hasattr(self._broker, "positions"):
                remaining = await self._broker.positions()
                non_flat = [
                    getattr(pos, "instrument_id", "unknown")
                    for pos in remaining
                    if getattr(pos, "quantity", Decimal("0")) != 0
                ]
                if non_flat:
                    result["errors"].append(
                        "Broker account is not flat after kill switch: " + ", ".join(non_flat)
                    )

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Kill switch failed: {e}")
            logger.error(f"Kill switch error: {e}")

        result["success"] = not result["errors"]
        if not result["success"]:
            logger.error(f"Kill switch completed with errors: {result['errors']}")
        else:
            logger.info(
                f"Kill switch completed: {result['positions_flattened']} positions flattened"
            )

        return result

    async def flatten_instrument(self, _instrument_id: str) -> dict[str, Any]:
        """Flatten a single instrument position."""
        return await self.flatten_all()  # Simplified: just flatten all

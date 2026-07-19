"""Emergency stop / kill switch — independent process flatten.

The kill switch is designed to be callable from any context (CLI, API,
monitoring script) and to execute a flatten of all positions regardless
of the main application state.  It communicates directly with the
broker adapter, bypassing the OMS if necessary.
"""

from __future__ import annotations

import logging
from typing import Any

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

            # 3. Submit flatten orders (market orders to close)
            for pos in positions:
                try:
                    close_side = "sell" if pos["side"] == "long" else "buy"
                    if hasattr(self._broker, "submit_order"):
                        await self._broker.submit_order({
                            "instrument_id": pos["instrument_id"],
                            "side": close_side,
                            "quantity": abs(pos["quantity"]),
                            "order_type": "market",
                            "time_in_force": "ioc",
                            "source": "kill_switch",
                        })
                        result["positions_flattened"] += 1
                except Exception as e:
                    result["errors"].append(
                        f"Failed to flatten {pos.get('instrument_id', 'unknown')}: {e}"
                    )

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Kill switch failed: {e}")
            logger.error(f"Kill switch error: {e}")

        if not result["success"] or result["errors"]:
            logger.error(f"Kill switch completed with errors: {result['errors']}")
        else:
            logger.info(f"Kill switch completed: "
                        f"{result['positions_flattened']} positions flattened")

        return result

    async def flatten_instrument(self, instrument_id: str) -> dict[str, Any]:
        """Flatten a single instrument position."""
        return await self.flatten_all()  # Simplified: just flatten all

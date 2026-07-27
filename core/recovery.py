"""Recovery service — restore Oracle state from PostgreSQL after restart.

Implements G6-103/104: after a process restart, the in-memory
``OrderManager`` has lost its order book.  The PostgreSQL OMS is the
authoritative store; this service reloads:

  - accounts and balances       (from ``accounts`` table)
  - orders in any state         (from ``oms_orders`` table)
  - fills                       (from ``oms_fills`` table)
  - open orders                 (subset with status submitted/partially_filled)
  - idempotency mapping         (client_order_id → order_id)

The recovery is *idempotent*: running it twice produces the same state.
It never re-submits to the broker — it only rebuilds the in-memory
mirrors so subsequent submissions dedupe via ``client_order_id``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

logger = logging.getLogger("oracle.core.recovery")


@dataclass
class RecoveredOrder:
    """In-memory mirror of an OMS order."""

    order_id: str
    account_id: str
    client_order_id: str
    broker_order_id: str | None
    instrument_id: str
    side: str
    quantity: Decimal
    filled_quantity: Decimal
    price: Decimal | None
    status: str
    strategy_id: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status in ("submitted", "partially_filled", "pending")


@dataclass
class RecoveryReport:
    """Result of a recovery run."""

    accounts_loaded: int = 0
    orders_loaded: int = 0
    fills_loaded: int = 0
    open_orders: list[RecoveredOrder] = field(default_factory=list)
    idempotency_map: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class RecoveryService:
    """Rebuild in-memory state from PostgreSQL on startup.

    Usage::

        svc = RecoveryService(oms=postgres_oms, ledger=postgres_ledger)
        report = await svc.recover()
        # report.open_orders → list of orders still alive at restart
        # report.idempotency_map → client_order_id → order_id for dedup
    """

    def __init__(self, oms: Any, ledger: Any) -> None:
        self._oms = oms
        self._ledger = ledger

    async def recover(self, account_id: str | None = None) -> RecoveryReport:
        """Run recovery. Returns a RecoveryReport.

        Args:
            account_id: If provided, restrict recovery to this account.
                        Otherwise recovers all accounts.
        """
        report = RecoveryReport()

        # ── 1. Accounts (ledger) ─────────────────────────────────────
        # PostgresLedger loads accounts into _accounts in its factory.
        if hasattr(self._ledger, "_accounts"):
            report.accounts_loaded = len(self._ledger._accounts)
            logger.info(f"Recovered {report.accounts_loaded} account(s) from ledger")
        else:
            report.warnings.append("Ledger does not expose _accounts — skipping account recovery")

        # ── 2. Orders ────────────────────────────────────────────────
        try:
            rows = await self._oms.get_orders(account_id=account_id)
        except Exception as e:
            report.warnings.append(f"Failed to load orders: {e}")
            return report

        for row in rows:
            try:
                order = RecoveredOrder(
                    order_id=str(row["order_id"]),
                    account_id=str(row["account_id"]),
                    client_order_id=str(row["client_order_id"]),
                    broker_order_id=row.get("broker_order_id"),
                    instrument_id=str(row["instrument_id"]),
                    side=str(row["side"]),
                    quantity=Decimal(str(row["quantity"])),
                    filled_quantity=Decimal(str(row.get("filled_quantity", 0))),
                    price=Decimal(str(row["price"])) if row.get("price") is not None else None,
                    status=str(row["status"]),
                    strategy_id=row.get("strategy_id"),
                )
                report.orders_loaded += 1
                report.idempotency_map[order.client_order_id] = order.order_id
                if order.is_open:
                    report.open_orders.append(order)
            except Exception as e:
                report.warnings.append(f"Skipping malformed order row: {e}")

        logger.info(
            f"Recovered {report.orders_loaded} order(s), "
            f"{len(report.open_orders)} open, "
            f"{len(report.idempotency_map)} idempotency keys"
        )

        # ── 3. Fills ─────────────────────────────────────────────────
        try:
            fills = await self._oms.get_fills()
            report.fills_loaded = len(fills)
            logger.info(f"Recovered {report.fills_loaded} fill(s)")
        except Exception as e:
            report.warnings.append(f"Failed to load fills: {e}")

        return report


__all__ = ["RecoveredOrder", "RecoveryReport", "RecoveryService"]

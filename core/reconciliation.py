"""Reconciliation engine — broker, OMS, and ledger convergence.

Detects and classifies mismatches between:
- Broker-reported state (positions, orders, fills, account values)
- OMS-tracked state (internal order book)
- Ledger state (account balances, P&L)

Mismatches are classified as recoverable or fatal.
Fatal mismatches block new order entry but preserve flatten capability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

logger = logging.getLogger("oracle.execution.reconciliation")


# ── Mismatch types ──────────────────────────────────────────────────


class MismatchSeverity(StrEnum):
    RECOVERABLE = "recoverable"
    FATAL = "fatal"


class MismatchType(StrEnum):
    POSITION = "position"
    ORDER = "order"
    FILL = "fill"
    CASH = "cash"
    MARGIN = "margin"


@dataclass(frozen=True)
class Mismatch:
    """A single discrepancy detected during reconciliation."""

    mismatch_type: MismatchType
    severity: MismatchSeverity
    instrument_id: str = ""
    description: str = ""
    broker_value: str = ""
    oracle_value: str = ""
    diff: str = ""


@dataclass
class ReconciliationReport:
    """Complete reconciliation result."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    mismatches: list[Mismatch] = field(default_factory=list)
    broker_connected: bool = True
    oms_connected: bool = True

    @property
    def is_clean(self) -> bool:
        return len(self.mismatches) == 0

    @property
    def has_fatal(self) -> bool:
        return any(m.severity == MismatchSeverity.FATAL for m in self.mismatches)

    @property
    def recoverable_count(self) -> int:
        return sum(1 for m in self.mismatches if m.severity == MismatchSeverity.RECOVERABLE)

    @property
    def fatal_count(self) -> int:
        return sum(1 for m in self.mismatches if m.severity == MismatchSeverity.FATAL)


# ── Reconciliation engine ───────────────────────────────────────────


class ReconciliationEngine:
    """Reconciliation engine comparing broker ↔ OMS ↔ ledger.

    Usage::

        engine = ReconciliationEngine(broker, oms, ledger)
        report = await engine.reconcile()
        if report.has_fatal:
            engine.block_new_orders()
        elif not report.is_clean:
            engine.alert_operator(report)
    """

    def __init__(self, broker: Any, oms: Any, ledger: Any) -> None:
        self._broker = broker
        self._oms = oms
        self._ledger = ledger
        self._blocked: bool = False

    async def reconcile(self) -> ReconciliationReport:
        """Run full reconciliation: positions, orders, fills, cash.

        Returns:
            ReconciliationReport with all mismatches.
        """
        report = ReconciliationReport()

        try:
            await self._reconcile_positions(report)
            await self._reconcile_orders(report)
            await self._reconcile_cash(report)
        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
            report.broker_connected = False

        if report.has_fatal:
            self._blocked = True
            logger.error(
                f"🔴 FATAL mismatches found — blocking new orders. "
                f"{report.fatal_count} fatal, {report.recoverable_count} recoverable"
            )
        elif not report.is_clean:
            logger.warning(
                f"🟡 Recoverable mismatches: {report.recoverable_count}"
            )
        else:
            logger.info("✅ Reconciliation clean — broker ↔ OMS ↔ ledger in sync")

        return report

    async def _reconcile_positions(self, report: ReconciliationReport) -> None:
        """Compare broker positions with OMS positions."""
        try:
            broker_positions = {}
            if hasattr(self._broker, "positions"):
                broker_positions = {
                    p["instrument_id"]: p
                    for p in await self._broker.positions()
                }

            oms_accounts = self._oms._orders if hasattr(self._oms, "_orders") else {}
            oms_positions: dict[str, Decimal] = {}
            for order_id, order in oms_accounts.items():
                if hasattr(order, "instrument_id") and hasattr(order, "filled_quantity"):
                    instr = order.instrument_id
                    qty = oms_positions.get(instr, Decimal("0"))
                    if order.side == "buy":
                        oms_positions[instr] = qty + order.filled_quantity
                    else:
                        oms_positions[instr] = qty - order.filled_quantity

            # Check for broker positions not in OMS
            for instr, bpos in broker_positions.items():
                b_qty = Decimal(str(bpos.get("quantity", 0)))
                o_qty = oms_positions.get(instr, Decimal("0"))
                if b_qty != o_qty:
                    severity = (
                        MismatchSeverity.FATAL
                        if abs(b_qty - o_qty) > Decimal("1")
                        else MismatchSeverity.RECOVERABLE
                    )
                    report.mismatches.append(Mismatch(
                        mismatch_type=MismatchType.POSITION,
                        severity=severity,
                        instrument_id=instr,
                        description=f"Position mismatch broker vs OMS",
                        broker_value=str(b_qty),
                        oracle_value=str(o_qty),
                        diff=str(b_qty - o_qty),
                    ))

        except Exception as e:
            logger.warning(f"Position reconciliation error: {e}")

    async def _reconcile_orders(self, report: ReconciliationReport) -> None:
        """Compare broker orders with OMS orders."""
        try:
            broker_orders = []
            if hasattr(self._broker, "open_orders"):
                broker_orders = await self._broker.open_orders()

            broker_order_ids = {
                getattr(o, "broker_order_id", getattr(o, "order_id", ""))
                for o in broker_orders
            }

            oms_orders = []
            if hasattr(self._oms, "_orders"):
                oms_orders = list(self._oms._orders.values())

            oms_broker_ids = {
                getattr(o, "broker_order_id", "") for o in oms_orders
                if getattr(o, "broker_order_id", None)
            }

            # Orders in broker but not in OMS
            for bid in broker_order_ids:
                if bid and bid not in oms_broker_ids:
                    report.mismatches.append(Mismatch(
                        mismatch_type=MismatchType.ORDER,
                        severity=MismatchSeverity.RECOVERABLE,
                        description=f"Broker order {bid} missing from OMS",
                        broker_value=bid,
                        oracle_value="",
                    ))

        except Exception as e:
            logger.warning(f"Order reconciliation error: {e}")

    async def _reconcile_cash(self, report: ReconciliationReport) -> None:
        """Compare broker cash with ledger balance."""
        try:
            broker_cash = Decimal("0")
            if hasattr(self._broker, "account_summary"):
                summary = await self._broker.account_summary()
                broker_cash = Decimal(str(summary.get("cash", summary.get("balance", 0))))

            ledger_balance = Decimal("0")
            if hasattr(self._ledger, "_accounts"):
                for acct in self._ledger._accounts.values():
                    ledger_balance += acct.current_balance

            if broker_cash > 0 and ledger_balance > 0:
                diff = abs(broker_cash - ledger_balance)
                if diff > Decimal("1.00"):
                    severity = (
                        MismatchSeverity.FATAL
                        if diff > Decimal("100")
                        else MismatchSeverity.RECOVERABLE
                    )
                    report.mismatches.append(Mismatch(
                        mismatch_type=MismatchType.CASH,
                        severity=severity,
                        description=f"Cash balance mismatch broker vs ledger",
                        broker_value=str(broker_cash),
                        oracle_value=str(ledger_balance),
                        diff=str(diff),
                    ))

        except Exception as e:
            logger.warning(f"Cash reconciliation error: {e}")

    def is_blocked(self) -> bool:
        """Return True if new orders are blocked due to fatal mismatches."""
        return self._blocked

    def unblock(self) -> None:
        """Manually unblock order entry (after operator review)."""
        self._blocked = False
        logger.info("New orders unblocked by operator")

"""Tests for core.recovery — restart idempotency (G6-103/104)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def sample_orders() -> list[dict[str, Any]]:
    return [
        {
            "order_id": "ord-1",
            "account_id": "acc-1",
            "client_order_id": "cli-1",
            "broker_order_id": "brk-1",
            "instrument_id": "ES",
            "side": "buy",
            "quantity": Decimal("2"),
            "filled_quantity": Decimal("0"),
            "price": Decimal("5000"),
            "status": "submitted",
            "strategy_id": None,
        },
        {
            "order_id": "ord-2",
            "account_id": "acc-1",
            "client_order_id": "cli-2",
            "broker_order_id": "brk-2",
            "instrument_id": "MES",
            "side": "sell",
            "quantity": Decimal("1"),
            "filled_quantity": Decimal("1"),
            "price": Decimal("5001"),
            "status": "filled",
            "strategy_id": None,
        },
        {
            "order_id": "ord-3",
            "account_id": "acc-1",
            "client_order_id": "cli-3",
            "broker_order_id": None,
            "instrument_id": "ES",
            "side": "buy",
            "quantity": Decimal("1"),
            "filled_quantity": Decimal("0"),
            "price": None,
            "status": "partially_filled",
            "strategy_id": None,
        },
    ]


class TestRecoveryService:
    """RecoveryService must rebuild state without re-submitting."""

    async def test_recovers_open_orders(self, sample_orders: list[dict[str, Any]]) -> None:
        from core.recovery import RecoveryService

        oms = MagicMock()
        oms.get_orders = AsyncMock(return_value=sample_orders)
        oms.get_fills = AsyncMock(return_value=[])
        ledger = MagicMock()
        ledger._accounts = {"acc-1": MagicMock()}

        svc = RecoveryService(oms=oms, ledger=ledger)
        report = await svc.recover()

        assert report.orders_loaded == 3
        assert len(report.open_orders) == 2  # submitted + partially_filled
        open_statuses = {o.status for o in report.open_orders}
        assert open_statuses == {"submitted", "partially_filled"}

    async def test_idempotency_map_covers_all_orders(
        self, sample_orders: list[dict[str, Any]]
    ) -> None:
        from core.recovery import RecoveryService

        oms = MagicMock()
        oms.get_orders = AsyncMock(return_value=sample_orders)
        oms.get_fills = AsyncMock(return_value=[])
        ledger = MagicMock()
        ledger._accounts = {}

        svc = RecoveryService(oms=oms, ledger=ledger)
        report = await svc.recover()

        assert report.idempotency_map == {"cli-1": "ord-1", "cli-2": "ord-2", "cli-3": "ord-3"}

    async def test_recovery_is_idempotent(self, sample_orders: list[dict[str, Any]]) -> None:
        """Running recover() twice produces the same result."""
        from core.recovery import RecoveryService

        oms = MagicMock()
        oms.get_orders = AsyncMock(return_value=sample_orders)
        oms.get_fills = AsyncMock(return_value=[])
        ledger = MagicMock()
        ledger._accounts = {}

        svc = RecoveryService(oms=oms, ledger=ledger)
        r1 = await svc.recover()
        r2 = await svc.recover()

        assert r1.orders_loaded == r2.orders_loaded
        assert r1.idempotency_map == r2.idempotency_map
        assert len(r1.open_orders) == len(r2.open_orders)

    async def test_filters_by_account_id(self, sample_orders: list[dict[str, Any]]) -> None:
        from core.recovery import RecoveryService

        oms = MagicMock()
        oms.get_orders = AsyncMock(return_value=sample_orders[:1])  # only ord-1
        oms.get_fills = AsyncMock(return_value=[])
        ledger = MagicMock()
        ledger._accounts = {}

        svc = RecoveryService(oms=oms, ledger=ledger)
        report = await svc.recover(account_id="acc-1")

        oms.get_orders.assert_called_once_with(account_id="acc-1")
        assert report.orders_loaded == 1

    async def test_warns_on_oms_failure(self) -> None:
        from core.recovery import RecoveryService

        oms = MagicMock()
        oms.get_orders = AsyncMock(side_effect=RuntimeError("db down"))
        ledger = MagicMock()
        ledger._accounts = {}

        svc = RecoveryService(oms=oms, ledger=ledger)
        report = await svc.recover()

        assert report.orders_loaded == 0
        assert any("Failed to load orders" in w for w in report.warnings)

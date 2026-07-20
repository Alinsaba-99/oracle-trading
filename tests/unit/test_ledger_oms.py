"""Tests for durable ledger, OMS, and outbox."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.ledger import InMemoryLedger
from core.oms import Fill, InMemoryOMS, Order

# =========================================================================
# Ledger tests
# =========================================================================


class TestInMemoryLedger:
    """Ledger invariants and operations."""

    def test_create_account(self) -> None:
        ledger = InMemoryLedger()
        acct = ledger.create_account(initial_balance=Decimal("100000"))
        assert acct.current_balance == Decimal("100000")
        assert acct.status == "active"

    def test_get_account(self) -> None:
        ledger = InMemoryLedger()
        acct = ledger.create_account()
        assert ledger.get_account(acct.account_id) is not None
        assert ledger.get_account("nonexistent") is None

    def test_record_fill_updates_balance(self) -> None:
        ledger = InMemoryLedger()
        acct = ledger.create_account(initial_balance=Decimal("100000"))
        ledger.record_fill(
            account_id=acct.account_id,
            order_id="order-1",
            fill_id="fill-1",
            quantity=Decimal("1"),
            price=Decimal("5000"),
            commission=Decimal("5"),
            realized_pnl=Decimal("250"),
        )
        # 100000 + 250 - 5 = 100245
        assert ledger.get_balance(acct.account_id) == Decimal("100245")

    def test_negative_pnl_reduces_balance(self) -> None:
        ledger = InMemoryLedger()
        acct = ledger.create_account(initial_balance=Decimal("100000"))
        ledger.record_fill(
            account_id=acct.account_id,
            order_id="order-1",
            fill_id="fill-1",
            quantity=Decimal("1"),
            price=Decimal("5000"),
            commission=Decimal("3.50"),
            realized_pnl=Decimal("-150"),
        )
        assert ledger.get_balance(acct.account_id) == Decimal("99846.50")

    def test_insufficient_balance_raises(self) -> None:
        ledger = InMemoryLedger()
        acct = ledger.create_account(initial_balance=Decimal("100"))
        with pytest.raises(ValueError, match="Insufficient balance"):
            ledger.record_fill(
                account_id=acct.account_id,
                order_id="order-1",
                fill_id="fill-1",
                quantity=Decimal("1"),
                price=Decimal("5000"),
                commission=Decimal("0"),
                realized_pnl=Decimal("-200"),
            )

    def test_multiple_fills(self) -> None:
        ledger = InMemoryLedger()
        acct = ledger.create_account(initial_balance=Decimal("100000"))
        for i in range(5):
            ledger.record_fill(
                account_id=acct.account_id,
                order_id=f"order-{i}",
                fill_id=f"fill-{i}",
                quantity=Decimal("1"),
                price=Decimal("100"),
                commission=Decimal("1"),
                realized_pnl=Decimal("50"),
            )
        # 100000 + 5*50 - 5*1 = 100245
        assert ledger.get_balance(acct.account_id) == Decimal("100245")

    def test_entry_count(self) -> None:
        ledger = InMemoryLedger()
        acct = ledger.create_account(initial_balance=Decimal("100000"))
        ledger.record_fill(
            account_id=acct.account_id,
            order_id="o1",
            fill_id="f1",
            quantity=Decimal("1"),
            price=Decimal("100"),
            commission=Decimal("2.50"),
            realized_pnl=Decimal("100"),
        )
        # 2 entries: P&L + commission
        assert len(ledger.get_entries(acct.account_id)) == 2


# =========================================================================
# OMS tests
# =========================================================================


class TestInMemoryOMS:
    """OMS order lifecycle and idempotency."""

    def test_create_order(self) -> None:
        oms = InMemoryOMS()
        order = Order(
            account_id="acct-1",
            client_order_id="client-1",
            instrument_id="ES",
            side="buy",
            quantity=Decimal("1"),
        )
        result = oms.create_order(order)
        assert result.status == "pending"
        assert result.order_id is not None

    def test_idempotency_duplicate_client_id(self) -> None:
        oms = InMemoryOMS()
        order1 = Order(
            account_id="acct-1",
            client_order_id="client-1",
            instrument_id="ES",
            side="buy",
            quantity=Decimal("1"),
        )
        order2 = Order(
            account_id="acct-1",
            client_order_id="client-1",
            instrument_id="NQ",
            side="sell",
            quantity=Decimal("2"),
        )
        result1 = oms.create_order(order1)
        result2 = oms.create_order(order2)
        # Same client_order_id → same order returned
        assert result1.order_id == result2.order_id
        assert result2.instrument_id == "ES"  # Original, not second

    def test_update_order_status(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="acct-1", client_order_id="c1")
        created = oms.create_order(order)
        updated = oms.update_order(Order(**{**created.__dict__, "status": "submitted"}))
        assert updated.status == "submitted"

    def test_cannot_revert_status(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="acct-1", client_order_id="c1")
        created = oms.create_order(order)
        oms.update_order(Order(**{**created.__dict__, "status": "submitted"}))
        with pytest.raises(ValueError, match="Cannot revert"):
            oms.update_order(Order(**{**created.__dict__, "status": "pending"}))

    def test_record_fill_updates_order(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="acct-1", client_order_id="c1", quantity=Decimal("10"))
        created = oms.create_order(order)
        fill = Fill(
            order_id=created.order_id,
            account_id="acct-1",
            quantity=Decimal("10"),
            price=Decimal("5000"),
        )
        oms.record_fill(fill)
        updated = oms.get_order(created.order_id)
        assert updated is not None
        assert updated.status == "filled"
        assert updated.filled_quantity == Decimal("10")

    def test_partial_fill(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="acct-1", client_order_id="c1", quantity=Decimal("10"))
        created = oms.create_order(order)
        fill1 = Fill(
            order_id=created.order_id,
            account_id="acct-1",
            quantity=Decimal("4"),
            price=Decimal("5000"),
        )
        oms.record_fill(fill1)
        updated = oms.get_order(created.order_id)
        assert updated is not None
        assert updated.status == "partially_filled"
        assert updated.filled_quantity == Decimal("4")

    def test_duplicate_broker_fill_is_idempotent(self) -> None:
        ledger = InMemoryLedger()
        account = ledger.create_account(initial_balance=Decimal("100000"))
        oms = InMemoryOMS(ledger=ledger)
        order = oms.create_order(
            Order(
                account_id=account.account_id,
                client_order_id="duplicate-fill",
                quantity=Decimal("1"),
            )
        )
        fill = Fill(
            order_id=order.order_id,
            account_id=account.account_id,
            broker_fill_id="broker-fill-1",
            quantity=Decimal("1"),
            price=Decimal("5000"),
            commission=Decimal("2.50"),
            realized_pnl=Decimal("100"),
        )

        first = oms.record_fill(fill)
        second = oms.record_fill(fill)

        assert second == first
        updated = oms.get_order(order.order_id)
        assert updated is not None
        assert updated.filled_quantity == Decimal("1")
        assert ledger.get_balance(account.account_id) == Decimal("100097.50")

    def test_multiple_fills_complete(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="acct-1", client_order_id="c1", quantity=Decimal("10"))
        created = oms.create_order(order)
        for qty in [Decimal("3"), Decimal("3"), Decimal("4")]:
            oms.record_fill(
                Fill(
                    order_id=created.order_id,
                    account_id="acct-1",
                    quantity=qty,
                    price=Decimal("5000"),
                )
            )
        updated = oms.get_order(created.order_id)
        assert updated is not None
        assert updated.status == "filled"
        assert updated.filled_quantity == Decimal("10")


# =========================================================================
# Outbox tests
# =========================================================================


class TestOutbox:
    """Transactional outbox for reliable event delivery."""

    def test_create_order_emits_event(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="a1", client_order_id="c1")
        oms.create_order(order)
        events = oms.pending_events()
        assert len(events) == 1
        assert events[0].event_type == "order.created"

    def test_update_order_emits_event(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="a1", client_order_id="c1")
        created = oms.create_order(order)
        oms.update_order(Order(**{**created.__dict__, "status": "filled"}))
        events = oms.pending_events()
        assert any(e.event_type == "order.filled" for e in events)

    def test_mark_published(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="a1", client_order_id="c1")
        oms.create_order(order)
        events = oms.pending_events()
        oms.mark_published(events[0].event_id)
        assert len(oms.pending_events()) == 0

    def test_account_snapshot(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="acct-1", client_order_id="c1", quantity=Decimal("5"))
        created = oms.create_order(order)
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="acct-1",
                quantity=Decimal("5"),
                price=Decimal("5000"),
            )
        )
        snap = oms.account_snapshot("acct-1")
        assert snap["account_id"] == "acct-1"
        assert len(snap["orders"]) == 1
        assert len(snap["fills"]) == 1

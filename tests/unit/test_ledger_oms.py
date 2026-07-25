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
            side="sell",
        )
        # SELL credits +5000 + 250 - 5 = 105245
        assert ledger.get_balance(acct.account_id) == Decimal("105245")

    def test_get_account(self) -> None:
        ledger = InMemoryLedger()
        acct = ledger.create_account()
        assert ledger.get_account(acct.account_id) is not None
        assert ledger.get_account("nonexistent") is None

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
            side="sell",
        )
        # 100000 + 5000 - 3.50 - 150 = 104846.50
        assert ledger.get_balance(acct.account_id) == Decimal("104846.50")

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
                realized_pnl=Decimal("0"),
                side="buy",
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
                side="sell",
            )
        # Each fill: +100 + 50 - 1 = +149.  100000 + 5*149 = 100745
        assert ledger.get_balance(acct.account_id) == Decimal("100745")

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
            side="sell",
        )
        # 3 entries: notional + trade + commission
        assert len(ledger.get_entries(acct.account_id)) == 3


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
            side="sell",
        )

        first = oms.record_fill(fill)
        second = oms.record_fill(fill)

        assert second == first
        updated = oms.get_order(order.order_id)
        assert updated is not None
        assert updated.filled_quantity == Decimal("1")
        # SELL: +5000 + 100 - 2.50 = 105097.50
        assert ledger.get_balance(account.account_id) == Decimal("105097.50")

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


# =========================================================================
# B1 — VWAP avg_fill_price tests (audit remediation beta)
# =========================================================================


class TestVWAPFillPrice:
    """Order.avg_fill_price must be the volume-weighted average, not the last fill price."""

    def test_vwap_after_two_fills(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="a", client_order_id="c", quantity=Decimal("10"))
        created = oms.create_order(order)
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("6"),
                price=Decimal("100"),
            )
        )
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("4"),
                price=Decimal("110"),
            )
        )
        updated = oms.get_order(created.order_id)
        assert updated is not None
        # VWAP = (6*100 + 4*110) / 10 = (600 + 440) / 10 = 104
        assert updated.avg_fill_price == Decimal("104"), (
            f"expected VWAP 104, got {updated.avg_fill_price}"
        )

    def test_vwap_three_fills(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="a", client_order_id="c", quantity=Decimal("10"))
        created = oms.create_order(order)
        # 3 @ 100, 4 @ 110, 3 @ 120 → VWAP = (300+440+360)/10 = 110
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("3"),
                price=Decimal("100"),
            )
        )
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("4"),
                price=Decimal("110"),
            )
        )
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("3"),
                price=Decimal("120"),
            )
        )
        updated = oms.get_order(created.order_id)
        assert updated is not None
        assert updated.avg_fill_price == Decimal("110")

    def test_avg_fill_price_decimal_precision(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="a", client_order_id="c", quantity=Decimal("3"))
        created = oms.create_order(order)
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("1"),
                price=Decimal("100"),
            )
        )
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("1"),
                price=Decimal("200"),
            )
        )
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("1"),
                price=Decimal("300"),
            )
        )
        updated = oms.get_order(created.order_id)
        assert updated is not None
        assert updated.avg_fill_price == Decimal("200")


# =========================================================================
# B13 — OMS overfill guard test
# =========================================================================


class TestOverfillGuard:
    """OMS.record_fill must reject cumulative fills that exceed order.quantity."""

    def test_overfill_raises(self) -> None:
        oms = InMemoryOMS()
        order = Order(account_id="a", client_order_id="c", quantity=Decimal("10"))
        created = oms.create_order(order)
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("8"),
                price=Decimal("100"),
            )
        )
        with pytest.raises(ValueError, match="exceed|overfill|cumulative"):
            oms.record_fill(
                Fill(
                    order_id=created.order_id,
                    account_id="a",
                    quantity=Decimal("3"),
                    price=Decimal("110"),
                )
            )

    def test_exact_fill_boundary(self) -> None:
        """A fill that exactly matches remaining quantity is OK."""
        oms = InMemoryOMS()
        order = Order(account_id="a", client_order_id="c", quantity=Decimal("10"))
        created = oms.create_order(order)
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("7"),
                price=Decimal("100"),
            )
        )
        # Exactly fills remaining 3 → no exception
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a",
                quantity=Decimal("3"),
                price=Decimal("110"),
            )
        )
        updated = oms.get_order(created.order_id)
        assert updated is not None
        assert updated.status == "filled"
        assert updated.filled_quantity == Decimal("10")


# =========================================================================
# B2 — Ledger notional debit tests (audit remediation beta)
# =========================================================================


class TestLedgerNotionalDebit:
    """Ledger.record_fill must debit/credit cash for the notional of the trade.

    Without this, balances reflect only realized P&L + commissions and
    do not model position exposure.  For prop-firm readiness we need
    the cash side to reflect ``price * quantity`` debits/credits too.
    """

    def test_fill_creates_notional_entry(self) -> None:
        """record_fill must write an entry of entry_type='notional' for price*qty."""
        ledger = InMemoryLedger()
        acct = ledger.create_account(initial_balance=Decimal("100000"))
        ledger.record_fill(
            account_id=acct.account_id,
            order_id="o1",
            fill_id="f1",
            quantity=Decimal("1"),
            price=Decimal("5000"),
            commission=Decimal("2.50"),
            realized_pnl=Decimal("0"),
            side="buy",
        )
        entries = ledger.get_entries(acct.account_id)
        types = {e.entry_type for e in entries}
        assert "notional" in types, f"missing notional entry in {types}"

    def test_buy_debits_cash_for_notional(self) -> None:
        """A BUY must reduce cash by price*quantity (the asset is acquired)."""
        ledger = InMemoryLedger()
        acct = ledger.create_account(initial_balance=Decimal("100000"))
        # Buy 1 @ 5000 with commission 2.50, no realized P&L
        ledger.record_fill(
            account_id=acct.account_id,
            order_id="o1",
            fill_id="f1",
            quantity=Decimal("1"),
            price=Decimal("5000"),
            commission=Decimal("2.50"),
            realized_pnl=Decimal("0"),
            side="buy",
        )
        # 100000 - 5000 - 2.50 = 94997.50
        assert ledger.get_balance(acct.account_id) == Decimal("94997.50")

    def test_sell_credits_cash_for_notional(self) -> None:
        """A SELL must increase cash by price*quantity."""
        ledger = InMemoryLedger()
        acct = ledger.create_account(initial_balance=Decimal("100000"))
        # Sell 1 @ 5000 with commission 2.50
        ledger.record_fill(
            account_id=acct.account_id,
            order_id="o1",
            fill_id="f1",
            quantity=Decimal("1"),
            price=Decimal("5000"),
            commission=Decimal("2.50"),
            realized_pnl=Decimal("0"),
            side="sell",
        )
        # 100000 + 5000 - 2.50 = 104997.50
        assert ledger.get_balance(acct.account_id) == Decimal("104997.50")


# =========================================================================
# B3 — OMS idempotency persistence tests (audit remediation beta)
# =========================================================================


class TestIdempotencyPersistence:
    """The idempotency map must survive process restarts.

    The in-memory implementation cannot satisfy this on its own, but
    the contract is: serialize the idempotency state to a durable
    store (SQLite minimum, Postgres target) and rebuild on startup.
    This test verifies the durability layer.
    """

    def test_idempotency_state_persisted_to_sqlite(self, tmp_path) -> None:
        """A 'recorded' idempotency state survives across OMS instance restarts."""
        # We test the simple persistence interface: two OMS instances
        # sharing a SQLite-backed idempotency store must reject a
        # duplicate client_order_id after the first is "committed".
        from core.oms_idempotency import SQLiteIdempotencyStore

        db_path = tmp_path / "idempotency.db"
        store1 = SQLiteIdempotencyStore(str(db_path))
        oms1 = InMemoryOMS(idempotency_store=store1)
        order = Order(account_id="a", client_order_id="persistent-client-1", quantity=Decimal("1"))
        oms1.create_order(order)

        # Simulate process restart: build a fresh OMS backed by the same store
        store2 = SQLiteIdempotencyStore(str(db_path))
        oms2 = InMemoryOMS(idempotency_store=store2)
        # Same client_order_id → same order_id from store1, even in fresh OMS
        duplicate = Order(
            account_id="a", client_order_id="persistent-client-1", quantity=Decimal("2")
        )
        returned = oms2.create_order(duplicate)
        assert returned.client_order_id == "persistent-client-1"
        # Critical: it's NOT a new order, but the one that was already recorded
        assert returned.order_id == order.order_id

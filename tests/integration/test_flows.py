"""Integration tests — end-to-end paths across component boundaries.

These tests verify that multiple components work together correctly.
They are intentionally slower than unit tests but validate real
integration points.

Run with: ``pytest tests/integration/ -v``
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.ledger import InMemoryLedger
from core.oms import Fill, InMemoryOMS, Order


class TestOrderToLedgerFlow:
    """Order submission → fill → ledger update integration."""

    def test_full_order_lifecycle(self) -> None:
        """Submit order, record fills, verify ledger balance."""
        ledger = InMemoryLedger()
        oms = InMemoryOMS(ledger=ledger)
        acct = ledger.create_account(account_type="paper", initial_balance=Decimal("100000"))

        # Create order
        order = Order(
            account_id=acct.account_id,
            client_order_id="int-test-1",
            instrument_id="ES",
            side="buy",
            quantity=Decimal("2"),
        )
        created = oms.create_order(order)
        assert created.status == "pending"

        # Submit (simulate)
        submitted = oms.update_order(Order(**{**created.__dict__, "status": "submitted"}))
        assert submitted.status == "submitted"

        # Partial fill 1
        fill1 = Fill(
            order_id=created.order_id,
            account_id=acct.account_id,
            quantity=Decimal("1"),
            price=Decimal("5500"),
            commission=Decimal("2.50"),
            realized_pnl=Decimal("0"),
        )
        oms.record_fill(fill1)

        # Partial fill 2 (completes)
        fill2 = Fill(
            order_id=created.order_id,
            account_id=acct.account_id,
            quantity=Decimal("1"),
            price=Decimal("5510"),
            commission=Decimal("2.50"),
            realized_pnl=Decimal("0"),
        )
        oms.record_fill(fill2)

        # Verify order completed
        final_order = oms.get_order(created.order_id)
        assert final_order is not None
        assert final_order.status == "filled"
        assert final_order.filled_quantity == Decimal("2")

        # Verify ledger: 100000 - 5500 - 2.50 - 5510 - 2.50 = 88985
        # Ledger deducts both notional (price × quantity) and commission.
        assert ledger.get_balance(acct.account_id) == Decimal("88985")

        # Verify outbox events
        events = oms.pending_events()
        event_types = [e.event_type for e in events]
        assert "order.created" in event_types
        assert "order.submitted" in event_types
        assert "order.filled" in event_types


class TestContractToSizing:
    """Contract spec → position sizing integration."""

    def test_es_notional_from_contract(self) -> None:
        """Use ContractSpec to compute notional value."""
        from market.contracts import ES

        notional = ES.notional_value(Decimal("5500"), Decimal("1"))
        assert notional == Decimal("275000")  # 5500 × 50

    def test_mes_equivalent_notional(self) -> None:
        """10 MES = 1 ES in notional."""
        from market.contracts import ES, MES

        es_val = ES.notional_value(Decimal("5500"), Decimal("1"))
        mes_val = MES.notional_value(Decimal("5500"), Decimal("10"))
        assert es_val == mes_val


class TestModeToOMS:
    """Mode guard → OMS integration."""

    def test_research_mode_no_broker(self) -> None:
        """Research mode should not allow broker-backed order submission."""
        from core.domain.mode import OracleMode

        mode = OracleMode.RESEARCH
        assert mode == "research"
        # Research mode must not have broker credentials
        from core.domain.guard import check_credential_isolation

        violations = check_credential_isolation({"ORACLE_MODE": "research"})
        assert violations == []

    def test_paper_mode_requires_api_key(self) -> None:
        """Paper mode must require API key at guard level."""
        from core.domain.guard import ModeGuardError, guard
        from core.domain.mode import OracleMode

        with pytest.raises(ModeGuardError):
            guard(OracleMode.PAPER, env={"ORACLE_MODE": "paper"})

"""BL-616 — Integration suite for the order chain with injected faults.

Exercises the full deterministic chain on every scenario:

    contract spec → risk gate → OrderManager → PaperBroker → fills
                  → InMemoryOMS → InMemoryLedger → ReconciliationEngine

Fault injection targets each seam: risk rejections, duplicate submits,
broker failures, overfills, orphan fills, position/cash divergence.
The chain must stay fail-closed everywhere: a fault either rejects the
order, ignores the poison event, or raises a mismatch — it never
silently invents state.

16 scenarios (target ≥12 per BL-616 AC).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.domain.enums import OrderType
from core.ledger import InMemoryLedger
from core.oms import Fill, InMemoryOMS, Order
from core.reconciliation import MismatchSeverity, MismatchType, ReconciliationEngine
from execution.brokers.config import BrokerConfig
from execution.brokers.paper import PaperBroker
from execution.order_manager.errors import InvalidOrderError
from execution.order_manager.manager import OrderManager
from execution.order_manager.types import FillReport, OrderRequest
from market.contracts import MES
from policy.prop_firm.fixtures import TOPSTEP_TC_50K
from policy.prop_firm.governor import PropFirmRiskGovernor
from policy.prop_firm.order_risk import PropFirmOrderRiskAdapter

INSTRUMENT = "MES"
POINT_VALUE = Decimal("5")  # == MES.point_value
ENTRY = Decimal("6000")
STOP = Decimal("5992")  # 8-point stop → risk_per_lot = 5 × 8 = $40


def _zero_cost_config() -> BrokerConfig:
    """Deterministic fills: no spread, no slippage, no commission."""
    return BrokerConfig(
        paper_spread_bps=0,
        paper_slippage_bps=0,
        paper_partial_fill_prob=0.0,
        paper_latency_ms=0,
        paper_commission_per_contract=0,
    )


def _risk_adapter() -> PropFirmOrderRiskAdapter:
    """Real prop-firm adapter in replay mode, market inputs wired."""
    governor = PropFirmRiskGovernor(
        profile=TOPSTEP_TC_50K, initial_balance=float(TOPSTEP_TC_50K.account_size)
    )
    balance = float(TOPSTEP_TC_50K.account_size)
    governor.update(balance=balance, equity=balance)
    adapter = PropFirmOrderRiskAdapter(governor, replay_only=True)
    adapter.update_market(INSTRUMENT, ENTRY, POINT_VALUE)
    return adapter


def _buy_request(quantity: Decimal = Decimal("1"), **overrides: object) -> OrderRequest:
    defaults: dict[str, object] = {
        "instrument_id": INSTRUMENT,
        "side": "buy",
        "quantity": quantity,
        "order_type": "market",
        "price": ENTRY,
        "stop_price": STOP,
        "source": "bl616",
    }
    defaults.update(overrides)
    return OrderRequest(**defaults)  # type: ignore[arg-type]


def _mirror_broker_orders(broker: PaperBroker, oms: InMemoryOMS, account_id: str) -> int:
    """Mirror every open broker-side order into the OMS.

    PaperBroker spawns resting bracket children (stop/TP) when an entry
    with a protective stop fills; a faithful OMS tracks those too.
    Returns the number of orders newly recorded.
    """
    recorded = 0
    for bo in broker._orders.values():
        if bo.status not in ("submitted",):
            continue
        child = Order(
            account_id=account_id,
            # Unique client id — the OMS idempotency keys on this; an
            # empty default would collide with the entry order.
            client_order_id=bo.broker_order_id,
            broker_order_id=bo.broker_order_id,
            instrument_id=bo.instrument_id,
            side=bo.side,
            order_type=OrderType(bo.order_type),
            quantity=bo.quantity,
            price=bo.price,
            stop_price=bo.stop_price,
            status="submitted",
        )
        oms.create_order(child)
        recorded += 1
    return recorded


class TestChainHappyPath:
    """Scenario 1-3: the clean chain, end to end."""

    async def test_full_chain_market_order_is_clean(self) -> None:
        """Contract→risk→OMS→broker→ledger→reconciliation: zero mismatches."""
        # Contract end of the chain: spec values drive sizing.
        assert MES.point_value == POINT_VALUE
        assert MES.tick_value == Decimal("1.25")
        assert MES.notional_value(ENTRY, Decimal("1")) == ENTRY * MES.multiplier

        broker = PaperBroker(_zero_cost_config())
        await broker.on_price_update(ENTRY)
        mgr = OrderManager(broker, risk_manager=_risk_adapter())

        result = await mgr.submit(_buy_request())
        assert result.status == "submitted"
        fills = await broker.get_fills()
        assert len(fills) == 1

        # Record into durable OMS + ledger (futures accounting: only P&L
        # and commission move cash; no notional entry).
        ledger = InMemoryLedger()
        oms = InMemoryOMS(ledger=ledger)
        acct = ledger.create_account(account_type="paper", initial_balance=Decimal("100000"))
        order = Order(
            account_id=acct.account_id,
            broker_order_id=result.broker_order_id,
            instrument_id=INSTRUMENT,
            side="buy",
            quantity=Decimal("1"),
            status="filled",
            filled_quantity=Decimal("1"),
        )
        oms.create_order(order)
        # The entry carried a protective stop → the broker spawned a
        # bracket child; a faithful OMS tracks it too.
        assert _mirror_broker_orders(broker, oms, acct.account_id) == 1
        ledger.record_fill(
            account_id=acct.account_id,
            order_id=order.order_id,
            fill_id=fills[0].fill_id,
            quantity=Decimal("1"),
            price=fills[0].price,
            side="buy",
            futures=True,
        )

        report = await ReconciliationEngine(broker, oms, ledger).reconcile()
        assert report.is_clean

    async def test_ledger_equity_accounting_round_trip(self) -> None:
        """Equity mode: notional debits/credits + commission are exact."""
        ledger = InMemoryLedger()
        oms = InMemoryOMS(ledger=ledger)
        acct = ledger.create_account(initial_balance=Decimal("100000"))

        # Entry: buy 2 @ 5000
        entry_order = Order(
            account_id=acct.account_id,
            client_order_id="bl616-entry",
            instrument_id="SPY",
            side="buy",
            quantity=Decimal("2"),
        )
        created_entry = oms.create_order(entry_order)
        oms.record_fill(
            Fill(
                order_id=created_entry.order_id,
                account_id=acct.account_id,
                quantity=Decimal("2"),
                price=Decimal("5000"),
                commission=Decimal("2.50"),
            )
        )
        assert ledger.get_balance(acct.account_id) == Decimal("89997.50")

        # Exit: sell 2 @ 5010 (own order — fills against the position)
        exit_order = Order(
            account_id=acct.account_id,
            client_order_id="bl616-exit",
            instrument_id="SPY",
            side="sell",
            quantity=Decimal("2"),
        )
        created_exit = oms.create_order(exit_order)
        oms.record_fill(
            Fill(
                order_id=created_exit.order_id,
                account_id=acct.account_id,
                quantity=Decimal("2"),
                price=Decimal("5010"),
                commission=Decimal("2.50"),
                side="sell",
            )
        )
        # 89997.50 + (2 × 5010) − 2.50 commission = 100015.00
        assert ledger.get_balance(acct.account_id) == Decimal("100015.00")
        final = ledger.get_account(acct.account_id)
        assert final is not None and final.check_invariant()

    async def test_ledger_futures_mode_no_notional(self) -> None:
        """Futures mode: balance moves only by realized_pnl − commission."""
        ledger = InMemoryLedger()
        acct = ledger.create_account(initial_balance=Decimal("50000"))
        entries = ledger.record_fill(
            account_id=acct.account_id,
            order_id="o1",
            fill_id="f1",
            quantity=Decimal("1"),
            price=ENTRY,
            commission=Decimal("0.85"),
            realized_pnl=Decimal("120"),
            side="buy",
            futures=True,
        )
        assert [e.entry_type for e in entries] == ["trade", "commission"]
        assert ledger.get_balance(acct.account_id) == Decimal("50119.15")


class TestRiskGateFaults:
    """Scenario 4-6: the risk gate must reject and keep the broker clean."""

    async def test_missing_stop_is_rejected(self) -> None:
        broker = PaperBroker(_zero_cost_config())
        mgr = OrderManager(broker, risk_manager=_risk_adapter())
        result = await mgr.submit(_buy_request(stop_price=None))
        assert result.status == "rejected"
        assert len(broker._orders) == 0  # nothing reached the broker

    async def test_contract_cap_exceeded_is_rejected(self) -> None:
        broker = PaperBroker(_zero_cost_config())
        await broker.on_price_update(ENTRY)
        mgr = OrderManager(broker, risk_manager=_risk_adapter())
        result = await mgr.submit(_buy_request(quantity=Decimal("60")))  # MES cap = 50
        assert result.status == "rejected"
        assert len(broker._orders) == 0

    async def test_risk_budget_exceeded_is_rejected(self) -> None:
        """Projected stop-loss larger than the per-trade risk budget."""
        broker = PaperBroker(_zero_cost_config())
        await broker.on_price_update(ENTRY)
        mgr = OrderManager(broker, risk_manager=_risk_adapter())
        # 20 lots × $40 = $800 > 1% × $50k = $500 budget.
        result = await mgr.submit(_buy_request(quantity=Decimal("20")))
        assert result.status == "rejected"
        assert len(broker._orders) == 0

    async def test_missing_market_input_is_rejected(self) -> None:
        """No verified market/contract spec → fail-closed."""
        governor = PropFirmRiskGovernor(
            profile=TOPSTEP_TC_50K, initial_balance=float(TOPSTEP_TC_50K.account_size)
        )
        adapter = PropFirmOrderRiskAdapter(governor, replay_only=True)  # no update_market
        broker = PaperBroker(_zero_cost_config())
        mgr = OrderManager(broker, risk_manager=adapter)
        result = await mgr.submit(_buy_request())
        assert result.status == "rejected"
        assert adapter.last_check is not None
        assert "market" in adapter.last_check.reason.lower()


class TestOrderManagerFaults:
    """Scenario 7-10: duplicate, broker failure, overfill, invalid input."""

    async def test_duplicate_submit_is_idempotent(self) -> None:
        broker = PaperBroker(_zero_cost_config())
        await broker.on_price_update(ENTRY)
        mgr = OrderManager(broker, risk_manager=_risk_adapter())
        req = _buy_request()
        first = await mgr.submit(req)
        second = await mgr.submit(req)
        assert first.status == "submitted"
        assert second.order_id == first.order_id
        # No duplicate ENTRY at the broker (the request carries a stop →
        # exactly one bracket child exists alongside the single entry).
        entries = [o for o in broker._orders.values() if o.parent_order_id is None]
        assert len(entries) == 1

    async def test_broker_submit_failure_rejects_cleanly(self) -> None:
        class _ExplodingBroker:
            async def submit_order(self, _order: object) -> str:
                raise RuntimeError("connection lost mid-submit")

        mgr = OrderManager(_ExplodingBroker(), risk_manager=_risk_adapter())
        result = await mgr.submit(_buy_request())
        assert result.status == "rejected"
        assert result.error is not None and "connection lost" in result.error

    async def test_overfill_is_ignored(self) -> None:
        broker = PaperBroker(_zero_cost_config())
        await broker.on_price_update(ENTRY)
        mgr = OrderManager(broker, risk_manager=_risk_adapter())
        result = await mgr.submit(_buy_request(quantity=Decimal("1")))
        await mgr.reconcile()
        order = mgr.get_order(result.order_id)
        assert order is not None and order.filled_quantity == Decimal("1")

        # Poison: replayed fill (same id) and an overfill (new id, qty 5).
        fills = await broker.get_fills()
        await mgr.on_fill(
            FillReport(
                order_id=result.order_id,
                broker_order_id=result.broker_order_id,
                fill_id=fills[0].fill_id,
                quantity=Decimal("1"),
                price=ENTRY,
            )
        )
        await mgr.on_fill(
            FillReport(
                order_id=result.order_id,
                broker_order_id=result.broker_order_id,
                fill_id="poison-fill",
                quantity=Decimal("5"),
                price=ENTRY,
            )
        )
        order = mgr.get_order(result.order_id)
        assert order is not None and order.filled_quantity == Decimal("1")

    async def test_invalid_quantity_raises(self) -> None:
        broker = PaperBroker(_zero_cost_config())
        mgr = OrderManager(broker, risk_manager=_risk_adapter())
        with pytest.raises(InvalidOrderError):
            await mgr.submit(_buy_request(quantity=Decimal("0")))


class TestBrokerFillFaults:
    """Scenario 11-12: partial fills and resting orders."""

    async def test_partial_fills_complete_the_order(self) -> None:
        broker = PaperBroker(_zero_cost_config())
        await broker.on_price_update(ENTRY)
        mgr = OrderManager(broker, risk_manager=_risk_adapter())
        result = await mgr.submit(_buy_request(quantity=Decimal("2")))

        # Simulate two partial fill reports against the order.
        for i, qty in enumerate([Decimal("1"), Decimal("1")]):
            await mgr.on_fill(
                FillReport(
                    order_id=result.order_id,
                    broker_order_id=result.broker_order_id,
                    fill_id=f"partial-{i}",
                    quantity=qty,
                    price=ENTRY,
                )
            )
        order = mgr.get_order(result.order_id)
        assert order is not None
        assert order.filled_quantity == Decimal("2")
        assert order.status.value == "filled"

    async def test_resting_limit_triggers_on_price_update(self) -> None:
        broker = PaperBroker(_zero_cost_config())
        await broker.on_price_update(ENTRY)
        mgr = OrderManager(broker, risk_manager=_risk_adapter())
        result = await mgr.submit(
            _buy_request(order_type="limit", price=Decimal("5990"))  # below market → rests
        )
        assert result.status == "submitted"
        assert len(await broker.get_fills()) == 0

        triggered = await broker.on_price_update(Decimal("5989"))
        assert len(triggered) == 1
        await mgr.reconcile()
        order = mgr.get_order(result.order_id)
        assert order is not None and order.status.value == "filled"


class TestReconciliationFaults:
    """Scenario 13-15: divergence is detected, classified, blocking."""

    async def _chain_with_open_position(
        self,
    ) -> tuple[PaperBroker, InMemoryOMS, InMemoryLedger, object]:
        broker = PaperBroker(_zero_cost_config())
        await broker.on_price_update(ENTRY)
        ledger = InMemoryLedger()
        oms = InMemoryOMS(ledger=ledger)
        acct = ledger.create_account(account_type="paper", initial_balance=Decimal("100000"))
        mgr = OrderManager(broker, risk_manager=_risk_adapter())
        result = await mgr.submit(_buy_request())
        fills = await broker.get_fills()
        order = Order(
            account_id=acct.account_id,
            broker_order_id=result.broker_order_id,
            instrument_id=INSTRUMENT,
            side="buy",
            quantity=Decimal("1"),
            status="filled",
            filled_quantity=Decimal("1"),
        )
        oms.create_order(order)
        # Faithful OMS: mirror the broker-side bracket child (stop) too.
        assert _mirror_broker_orders(broker, oms, acct.account_id) == 1
        ledger.record_fill(
            account_id=acct.account_id,
            order_id=order.order_id,
            fill_id=fills[0].fill_id,
            quantity=Decimal("1"),
            price=fills[0].price,
            side="buy",
            futures=True,
        )
        return broker, oms, ledger, acct

    async def test_position_divergence_is_fatal_and_blocks(self) -> None:
        broker, oms, ledger, _acct = await self._chain_with_open_position()

        # Rogue order: fills at the broker but is never recorded in the OMS.
        class _Rogue:
            order_id = None
            instrument_id = INSTRUMENT
            side = "buy"
            quantity = Decimal("3")
            price = None
            order_type = "market"

        await broker.submit_order(_Rogue())

        engine = ReconciliationEngine(broker, oms, ledger)
        report = await engine.reconcile()
        position_mismatches = [
            m for m in report.mismatches if m.mismatch_type == MismatchType.POSITION
        ]
        assert len(position_mismatches) == 1
        assert position_mismatches[0].severity == MismatchSeverity.FATAL
        assert report.has_fatal
        assert engine.is_blocked()

    async def test_orphan_fill_is_ignored_gracefully(self) -> None:
        broker, oms, ledger, _acct = await self._chain_with_open_position()
        engine = ReconciliationEngine(broker, oms, ledger)

        # Poison: a fill pointing at a broker order nobody knows about.
        report_before = await engine.reconcile()
        assert report_before.is_clean

        class _GhostOrder:
            order_id = None
            broker_order_id = "ghost_999"
            instrument_id = INSTRUMENT
            side = "buy"
            quantity = Decimal("1")
            price = None
            order_type = "market"

        # Inject a fill for an unknown order directly into the broker.
        from execution.brokers.types import BrokerFill

        broker._fills.append(
            BrokerFill(
                broker_order_id="ghost_999",
                fill_id="ghost-fill",
                quantity=Decimal("1"),
                price=ENTRY,
            )
        )
        # No exception, no crash — reconciliation still runs.
        report = await engine.reconcile()
        assert all(m.mismatch_type != MismatchType.CASH for m in report.mismatches)

    async def test_kill_all_cancels_resting_orders(self) -> None:
        broker = PaperBroker(_zero_cost_config())
        await broker.on_price_update(ENTRY)
        mgr = OrderManager(broker, risk_manager=_risk_adapter())
        r1 = await mgr.submit(_buy_request(order_type="limit", price=Decimal("5990")))
        r2 = await mgr.submit(_buy_request(order_type="limit", price=Decimal("5985")))
        assert len(await broker.open_orders()) == 2

        cancelled = await mgr.kill_all()
        assert cancelled == 2
        assert await broker.open_orders() == []
        o1 = mgr.get_order(r1.order_id)
        o2 = mgr.get_order(r2.order_id)
        assert o1 is not None and o1.status.value == "cancelled"
        assert o2 is not None and o2.status.value == "cancelled"

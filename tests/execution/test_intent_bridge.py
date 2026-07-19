"""Tests for the non-bypassable boundary between LLM intent and OMS."""

from decimal import Decimal

from agents.committee import ExecutionPreference, IntentAction, OrderStyle, TradeIntent, TradingMode
from execution.order_manager.intent_bridge import TradeIntentBridge


def _intent(style: OrderStyle = OrderStyle.LIMIT) -> TradeIntent:
    return TradeIntent(
        intent_id="intent-1",
        decision_id="decision-1",
        instrument_id="MES",
        action=IntentAction.INCREASE,
        side="buy",
        quantity=2,
        execution=ExecutionPreference(order_style=style, limit_price=5500.25, stop_price=5488.0),
        rationale="increase exposure after committee approval",
    )


def test_shadow_intent_cannot_reach_oms() -> None:
    assert TradeIntentBridge().to_order_request(_intent(), TradingMode.SHADOW) is None


def test_paper_intent_preserves_idempotency_and_decision_lineage() -> None:
    request = TradeIntentBridge().to_order_request(_intent(), TradingMode.PAPER)

    assert request is not None
    assert request.request_id == "intent-1"
    assert request.strategy_id == "decision-1"
    assert request.source == "llm_fund_manager"
    assert request.quantity == 2
    assert request.price == Decimal("5500.25")


def test_execution_algo_is_selected_without_bypassing_oms() -> None:
    request = TradeIntentBridge().to_order_request(_intent(OrderStyle.TWAP), TradingMode.LIVE)

    assert request is not None
    assert request.execution_algo == "twap"
    assert request.order_type == "limit"

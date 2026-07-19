"""Safe boundary from LLM-authored trade intents to OMS requests."""

from __future__ import annotations

from decimal import Decimal

from agents.committee import OrderStyle, TradeIntent, TradingMode
from execution.order_manager.types import OrderRequest


class TradeIntentBridge:
    """Compile approved intents into requests without submitting them.

    Replay and shadow plans never create executable requests. Paper and live
    requests still have to pass the OrderManager's deterministic risk gate.
    """

    def to_order_request(self, intent: TradeIntent, mode: TradingMode) -> OrderRequest | None:
        if mode in {TradingMode.REPLAY, TradingMode.SHADOW}:
            return None

        order_type = "market" if intent.execution.order_style is OrderStyle.MARKET else "limit"
        execution_algo: str | None = None
        if intent.execution.order_style in {OrderStyle.TWAP, OrderStyle.VWAP}:
            execution_algo = intent.execution.order_style.value

        return OrderRequest(
            request_id=intent.intent_id,
            instrument_id=intent.instrument_id,
            side=intent.side,
            quantity=Decimal(intent.quantity),
            order_type=order_type,
            price=(
                Decimal(str(intent.execution.limit_price))
                if intent.execution.limit_price is not None
                else None
            ),
            stop_price=(
                Decimal(str(intent.execution.stop_price))
                if intent.execution.stop_price is not None
                else None
            ),
            execution_algo=execution_algo,
            algo_config={
                "urgency": intent.execution.urgency.value,
                "max_slippage_bps": intent.execution.max_slippage_bps,
                "action": intent.action.value,
            },
            source="llm_fund_manager",
            strategy_id=intent.decision_id,
        )

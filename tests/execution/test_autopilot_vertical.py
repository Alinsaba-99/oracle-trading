"""First end-to-end paper vertical from portfolio plan to broker submission."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.committee import (
    CommitteeTrigger,
    ExecutionPreference,
    OrderStyle,
    PortfolioPlan,
    PortfolioPlanCompiler,
    PositionTarget,
    TradingMode,
)
from execution.order_manager.intent_bridge import TradeIntentBridge
from execution.order_manager.manager import OrderManager
from policy.prop_firm.governor import PropFirmRiskGovernor
from policy.prop_firm.order_risk import InstrumentRiskInput, PropFirmOrderRiskAdapter
from policy.prop_firm.profile import ContractCap, FirmProgramProfile, SupportMode


def _profile() -> FirmProgramProfile:
    return FirmProgramProfile(
        firm="TEST",
        program="Paper Autopilot",
        stage="evaluation",
        platform="paper",
        account_size=100_000,
        rule_version="test-v1",
        effective_from="2026-01-01",
        source_url="https://example.invalid/rules",
        source_checked_at="2026-01-01T00:00:00Z",
        support_mode=SupportMode.AUTO_SUPPORTED,
        profit_target_pct=0.1,
        max_daily_loss_pct=0.03,
        max_overall_loss_pct=0.06,
        contract_cap=ContractCap(3),
    )


@pytest.mark.asyncio
async def test_portfolio_plan_reaches_broker_only_through_risk_and_oms() -> None:
    now = datetime(2026, 7, 18, 12, tzinfo=UTC)
    plan = PortfolioPlan(
        decision_id="decision-1",
        created_at=now,
        expires_at=now + timedelta(minutes=15),
        mode=TradingMode.PAPER,
        trigger=CommitteeTrigger.REBALANCE,
        objective="increase MES exposure",
        portfolio_thesis="trend and macro evidence agree",
        targets=[
            PositionTarget(
                instrument_id="MES",
                target_contracts=2,
                confidence=0.8,
                thesis="increase long exposure",
                time_horizon="4h",
                execution=ExecutionPreference(
                    order_style=OrderStyle.LIMIT, limit_price=5500, stop_price=5490
                ),
            )
        ],
    )
    intent = PortfolioPlanCompiler().compile(plan, {"MES": 1})[0]
    request = TradeIntentBridge().to_order_request(intent, plan.mode)
    assert request is not None

    risk = PropFirmOrderRiskAdapter(
        PropFirmRiskGovernor(_profile(), 100_000),
        {"MES": InstrumentRiskInput(Decimal("5500"), Decimal("5"))},
    )
    broker = MagicMock()
    broker.submit_order = AsyncMock(return_value="paper-order-1")
    manager = OrderManager(broker=broker, risk_manager=risk)

    result = await manager.submit(request)

    assert result.status == "submitted"
    assert result.broker_order_id == "paper-order-1"
    broker.submit_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_risk_rejection_prevents_broker_side_effect() -> None:
    request = TradeIntentBridge().to_order_request(
        PortfolioPlanCompiler().compile(
            PortfolioPlan(
                created_at=datetime(2026, 7, 18, 12, tzinfo=UTC),
                expires_at=datetime(2026, 7, 18, 12, 15, tzinfo=UTC),
                mode=TradingMode.PAPER,
                trigger=CommitteeTrigger.RISK_ALERT,
                objective="test rejection",
                portfolio_thesis="test",
                targets=[
                    PositionTarget(
                        instrument_id="MES",
                        target_contracts=4,
                        confidence=0.9,
                        thesis="oversized target",
                        time_horizon="4h",
                        execution=ExecutionPreference(limit_price=5500, stop_price=5490),
                    )
                ],
            ),
            {},
        )[0],
        TradingMode.PAPER,
    )
    assert request is not None
    risk = PropFirmOrderRiskAdapter(
        PropFirmRiskGovernor(_profile(), 100_000),
        {"MES": InstrumentRiskInput(Decimal("5500"), Decimal("5"))},
    )
    broker = MagicMock()
    broker.submit_order = AsyncMock(return_value="must-not-run")

    result = await OrderManager(broker=broker, risk_manager=risk).submit(request)

    assert result.status == "rejected"
    broker.submit_order.assert_not_awaited()

"""Tests for application/contracts — authority boundary types.

These contracts are the schema between the intelligence plane
(agents → PortfolioPlan, TradeIntent) and the safety control plane
(execution → broker orders).  They MUST stay frozen and validated.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from application.contracts import (
    ExecutionPreference,
    IntentAction,
    OrderStyle,
    PortfolioPlan,
    PositionTarget,
    TradeIntent,
    TradingMode,
    Urgency,
)


class TestPortfolioPlan:
    def test_minimal_valid_plan(self) -> None:
        now = datetime.now(UTC)
        plan = PortfolioPlan(
            expires_at=now + timedelta(hours=1),
            mode=TradingMode.PAPER,
            objective="Test objective",
            portfolio_thesis="Test thesis",
            targets=[
                PositionTarget(
                    instrument_id="ES",
                    target_contracts=1,
                    confidence=0.7,
                    thesis="Bullish",
                    time_horizon="intraday",
                )
            ],
        )
        assert plan.mode == TradingMode.PAPER
        assert plan.cash_buffer_pct == 0.0
        assert plan.gross_risk_budget_pct == 0.01
        assert len(plan.targets) == 1

    def test_expires_at_must_be_after_created_at(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="expires_at"):
            PortfolioPlan(
                expires_at=now - timedelta(hours=1),
                mode=TradingMode.PAPER,
                objective="x",
                portfolio_thesis="y",
                targets=[],
            )

    def test_targets_must_be_unique_by_instrument(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="unique"):
            PortfolioPlan(
                expires_at=now + timedelta(hours=1),
                mode=TradingMode.PAPER,
                objective="x",
                portfolio_thesis="y",
                targets=[
                    PositionTarget(
                        instrument_id="ES",
                        target_contracts=1,
                        confidence=0.5,
                        thesis="t",
                        time_horizon="1d",
                    ),
                    PositionTarget(
                        instrument_id="ES",
                        target_contracts=2,
                        confidence=0.5,
                        thesis="t",
                        time_horizon="1d",
                    ),
                ],
            )

    def test_plan_is_frozen(self) -> None:
        now = datetime.now(UTC)
        plan = PortfolioPlan(
            expires_at=now + timedelta(hours=1),
            mode=TradingMode.PAPER,
            objective="x",
            portfolio_thesis="y",
            targets=[],
        )
        with pytest.raises(ValidationError):
            plan.objective = "tampered"  # type: ignore[misc]


class TestTradeIntent:
    def test_minimal_valid_intent(self) -> None:
        intent = TradeIntent(
            decision_id="d1",
            instrument_id="ES",
            action=IntentAction.OPEN,
            side="buy",
            quantity=1,
            execution=ExecutionPreference(),
            rationale="test",
        )
        assert intent.action == IntentAction.OPEN
        assert intent.quantity == 1

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match="quantity"):
            TradeIntent(
                decision_id="d1",
                instrument_id="ES",
                action=IntentAction.OPEN,
                side="buy",
                quantity=0,
                execution=ExecutionPreference(),
                rationale="x",
            )


class TestExecutionPreference:
    def test_defaults_are_safe(self) -> None:
        pref = ExecutionPreference()
        assert pref.order_style == OrderStyle.LIMIT
        assert pref.urgency == Urgency.MEDIUM
        assert pref.max_slippage_bps == 10.0

    def test_slippage_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionPreference(max_slippage_bps=-1.0)

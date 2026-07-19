"""Tests for portfolio-plan contracts and deterministic compilation."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from agents.committee import (
    CommitteeTrigger,
    IntentAction,
    PortfolioPlan,
    PortfolioPlanCompiler,
    PositionTarget,
    TradingMode,
)


def _plan(*targets: PositionTarget) -> PortfolioPlan:
    created_at = datetime(2026, 7, 18, tzinfo=UTC)
    return PortfolioPlan(
        decision_id="decision-1",
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=15),
        mode=TradingMode.PAPER,
        trigger=CommitteeTrigger.REBALANCE,
        objective="rebalance risk",
        portfolio_thesis="trend remains positive with controlled exposure",
        targets=list(targets),
        agents_contributing=["macro", "technical", "fund-manager"],
    )


def _target(instrument: str, contracts: int) -> PositionTarget:
    return PositionTarget(
        instrument_id=instrument,
        target_contracts=contracts,
        confidence=0.7,
        thesis=f"target {contracts} contracts",
        time_horizon="4h",
    )


def test_compiler_translates_position_deltas() -> None:
    plan = _plan(_target("MES", 3), _target("MNQ", 0), _target("MGC", -2))

    intents = PortfolioPlanCompiler().compile(plan, {"MES": 1, "MNQ": 2, "MGC": 1})

    assert [(i.instrument_id, i.action, i.side, i.quantity) for i in intents] == [
        ("MES", IntentAction.INCREASE, "buy", 2),
        ("MNQ", IntentAction.CLOSE, "sell", 2),
        ("MGC", IntentAction.REVERSE, "sell", 3),
    ]


def test_compiler_emits_nothing_when_reconciled_position_matches() -> None:
    assert PortfolioPlanCompiler().compile(_plan(_target("MES", 2)), {"MES": 2}) == []


def test_portfolio_plan_rejects_duplicate_targets() -> None:
    with pytest.raises(ValidationError, match="unique"):
        _plan(_target("MES", 1), _target("MES", 2))


def test_portfolio_plan_must_expire_after_creation() -> None:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    with pytest.raises(ValidationError, match="expires_at"):
        PortfolioPlan(
            created_at=now,
            expires_at=now,
            mode=TradingMode.PAPER,
            trigger=CommitteeTrigger.MARKET_REVIEW,
            objective="test",
            portfolio_thesis="test",
            targets=[],
        )

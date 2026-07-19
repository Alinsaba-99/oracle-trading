"""Tests for durable portfolio decision memory and QuantAgents-style feedback."""

from datetime import UTC, datetime, timedelta

import pytest

from agents.committee import (
    CommitteeTrigger,
    DecisionOutcome,
    PortfolioPlan,
    SQLiteDecisionJournal,
    TradingMode,
)


def _plan() -> PortfolioPlan:
    now = datetime(2026, 7, 18, 12, tzinfo=UTC)
    return PortfolioPlan(
        decision_id="decision-1",
        created_at=now,
        expires_at=now + timedelta(minutes=15),
        mode=TradingMode.PAPER,
        trigger=CommitteeTrigger.STRATEGY_REVIEW,
        objective="validate strategy",
        portfolio_thesis="the strategy has positive expected value",
        targets=[],
    )


@pytest.mark.asyncio
async def test_journal_round_trips_plan_and_outcome(tmp_path) -> None:
    journal = SQLiteDecisionJournal(tmp_path / "committee.db")
    await journal.initialize()
    await journal.record_plan(_plan())
    outcome = DecisionOutcome(
        outcome_id="outcome-1",
        decision_id="decision-1",
        simulated_reward=0.04,
        realized_reward=0.02,
        prediction_accuracy=0.8,
        execution_quality=0.7,
        thesis_correct=True,
    )
    await journal.record_outcome(outcome)

    restored = await journal.get_plan("decision-1")
    outcomes = await journal.get_outcomes("decision-1")

    assert restored == _plan()
    assert outcomes == [outcome]
    assert outcomes[0].dual_reward() == pytest.approx(0.03)


def test_dual_reward_uses_available_feedback_only() -> None:
    outcome = DecisionOutcome(
        outcome_id="outcome-1", decision_id="decision-1", simulated_reward=0.04
    )

    assert outcome.dual_reward(simulated_weight=0.2, realized_weight=0.8) == pytest.approx(0.04)


def test_dual_reward_rejects_negative_weights() -> None:
    outcome = DecisionOutcome(outcome_id="outcome-1", decision_id="decision-1")
    with pytest.raises(ValueError, match="cannot be negative"):
        outcome.dual_reward(simulated_weight=-1.0)

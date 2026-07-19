"""Tests for the structured LLM fund manager boundary."""

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from agents.committee import (
    CommitteeTrigger,
    FundManagerResponse,
    LLMFundManager,
    PositionTarget,
    TradingMode,
)
from core.domain.intelligence import EvidenceReference, OpportunityDirection, OpportunityObservation


class FakeLLM:
    model_name = "fake/fund-manager"

    def __init__(self, response: FundManagerResponse) -> None:
        self.response = response
        self.user_prompt = ""

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        temperature: float = 0.1,
        timeout_s: float = 30.0,
    ) -> BaseModel:
        _ = system_prompt, response_model, temperature, timeout_s
        self.user_prompt = user_prompt
        return self.response

    async def count_tokens(self, text: str) -> int:
        return len(text)


def _observation() -> OpportunityObservation:
    now = datetime(2026, 7, 18, 12, tzinfo=UTC)
    evidence = EvidenceReference(
        source="official", observed_at=now, available_at=now, content_hash="hash", credibility=0.9
    )
    return OpportunityObservation(
        observation_id="obs-1",
        agent_id="eliza-news-scout",
        event_time=now,
        available_at=now,
        instruments=["MES"],
        observation_type="macro_surprise",
        direction=OpportunityDirection.BULLISH,
        confidence=0.7,
        novelty=0.8,
        time_horizon="4h",
        summary="surprise improved the risk outlook",
        evidence=[evidence],
    )


@pytest.mark.asyncio
async def test_fund_manager_creates_auditable_portfolio_plan() -> None:
    response = FundManagerResponse(
        objective="increase exposure selectively",
        portfolio_thesis="risk appetite improved",
        targets=[
            PositionTarget(
                instrument_id="MES",
                target_contracts=2,
                confidence=0.72,
                thesis="equity index trend confirmed",
                time_horizon="4h",
                evidence_ids=["obs-1"],
            )
        ],
        source_observation_ids=["obs-1", "hallucinated-observation"],
    )
    llm = FakeLLM(response)
    manager = LLMFundManager(llm)  # type: ignore[arg-type]
    now = datetime(2026, 7, 18, 12, tzinfo=UTC)

    plan = await manager.decide(
        mode=TradingMode.PAPER,
        trigger=CommitteeTrigger.REBALANCE,
        current_positions={"MES": 1},
        analyst_reports=[{"source": "technical", "signal": "buy"}],
        observations=[_observation()],
        constraints={"max_contracts": 3},
        now=now,
    )

    assert plan.targets[0].target_contracts == 2
    assert plan.source_observation_ids == ["obs-1"]
    assert plan.model == "fake/fund-manager"
    assert plan.prompt_version == "fund-manager-v1"
    assert "max_contracts" in llm.user_prompt


@pytest.mark.asyncio
async def test_fund_manager_can_choose_flat_portfolio() -> None:
    llm = FakeLLM(
        FundManagerResponse(
            objective="preserve capital",
            portfolio_thesis="evidence is conflicting",
            targets=[],
            cash_buffer_pct=1.0,
        )
    )
    plan = await LLMFundManager(llm).decide(  # type: ignore[arg-type]
        mode=TradingMode.SHADOW,
        trigger=CommitteeTrigger.RISK_ALERT,
        current_positions={},
        analyst_reports=[],
    )

    assert plan.targets == []
    assert plan.cash_buffer_pct == 1.0

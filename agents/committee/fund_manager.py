"""LLM fund manager that authors portfolio targets, never broker orders."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from agents.committee.contracts import CommitteeTrigger, PortfolioPlan, PositionTarget, TradingMode
from agents.llm import LLMClient
from core.domain.intelligence import OpportunityObservation

FUND_MANAGER_SYSTEM_PROMPT = """You are Oracle's autonomous fund manager.
You decide the desired portfolio, including rebalancing and execution preferences.
Return structured target positions, not raw broker commands.

Rules:
- use integer futures contract targets;
- distinguish the desired portfolio from the current portfolio;
- cite observation IDs that materially support the plan;
- define a thesis, horizon and invalidation conditions for every non-zero target;
- prefer no change when evidence is weak or conflicting;
- respect every supplied constraint;
- never assume that a proposal has passed deterministic risk or prop-firm checks;
- never claim an order was submitted or filled.
"""


class FundManagerResponse(BaseModel):
    """Business content returned by the LLM before technical metadata is added."""

    objective: str
    portfolio_thesis: str
    targets: list[PositionTarget]
    cash_buffer_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    gross_risk_budget_pct: float = Field(default=0.01, gt=0.0, le=1.0)
    source_observation_ids: list[str] = Field(default_factory=list)


class LLMFundManager:
    """Create an auditable portfolio plan through a structured LLM call."""

    def __init__(self, llm_client: LLMClient, prompt_version: str = "fund-manager-v1") -> None:
        self._llm = llm_client
        self._prompt_version = prompt_version

    async def decide(
        self,
        *,
        mode: TradingMode,
        trigger: CommitteeTrigger,
        current_positions: dict[str, int],
        analyst_reports: list[dict[str, Any]],
        debate_summary: dict[str, Any] | None = None,
        observations: list[OpportunityObservation] | None = None,
        constraints: dict[str, Any] | None = None,
        valid_for: timedelta = timedelta(minutes=15),
        now: datetime | None = None,
    ) -> PortfolioPlan:
        created_at = now or datetime.now(UTC)
        observation_data = [item.model_dump(mode="json") for item in observations or []]
        payload = {
            "mode": mode.value,
            "trigger": trigger.value,
            "current_positions": current_positions,
            "analyst_reports": analyst_reports,
            "debate_summary": debate_summary or {},
            "opportunity_observations": observation_data,
            "constraints": constraints or {},
        }
        response = await self._llm.structured_call(
            FUND_MANAGER_SYSTEM_PROMPT,
            json.dumps(payload, sort_keys=True),
            FundManagerResponse,
            temperature=0.1,
        )
        if not isinstance(response, FundManagerResponse):
            response = FundManagerResponse.model_validate(response)

        observation_ids = {item.observation_id for item in observations or []}
        cited_ids = [item for item in response.source_observation_ids if item in observation_ids]
        return PortfolioPlan(
            created_at=created_at,
            expires_at=created_at + valid_for,
            mode=mode,
            objective=response.objective,
            portfolio_thesis=response.portfolio_thesis,
            targets=response.targets,
            cash_buffer_pct=response.cash_buffer_pct,
            gross_risk_budget_pct=response.gross_risk_budget_pct,
            source_observation_ids=cited_ids,
            agents_contributing=[
                str(report.get("source", "unknown")) for report in analyst_reports
            ],
            model=self._llm.model_name,
            prompt_version=self._prompt_version,
        )

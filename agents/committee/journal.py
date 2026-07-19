"""Durable decision journal for portfolio plans and dual feedback."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
from pydantic import BaseModel, Field

from agents.committee.contracts import PortfolioPlan


class DecisionOutcome(BaseModel, frozen=True):
    """Separate strategy quality from realized execution performance."""

    outcome_id: str
    decision_id: str
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    simulated_reward: float | None = None
    realized_reward: float | None = None
    prediction_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    execution_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    thesis_correct: bool | None = None
    notes: list[str] = Field(default_factory=list)

    def dual_reward(self, simulated_weight: float = 0.5, realized_weight: float = 0.5) -> float:
        """Combine simulated and realized feedback without conflating missing data with a loss."""
        if simulated_weight < 0.0 or realized_weight < 0.0:
            raise ValueError("reward weights cannot be negative")
        weighted_values: list[tuple[float, float]] = []
        if self.simulated_reward is not None:
            weighted_values.append((self.simulated_reward, simulated_weight))
        if self.realized_reward is not None:
            weighted_values.append((self.realized_reward, realized_weight))
        total_weight = sum(weight for _, weight in weighted_values)
        if total_weight == 0.0:
            return 0.0
        return sum(value * weight for value, weight in weighted_values) / total_weight


class SQLiteDecisionJournal:
    """Small durable journal suitable for replay/paper before PostgreSQL promotion."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)

    async def initialize(self) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_plans (
                    decision_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY(decision_id) REFERENCES portfolio_plans(decision_id)
                )
                """
            )
            await db.commit()

    async def record_plan(self, plan: PortfolioPlan) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                INSERT INTO portfolio_plans(decision_id, created_at, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(decision_id) DO UPDATE SET
                    created_at = excluded.created_at,
                    payload = excluded.payload
                """,
                (plan.decision_id, plan.created_at.isoformat(), plan.model_dump_json()),
            )
            await db.commit()

    async def record_outcome(self, outcome: DecisionOutcome) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                INSERT INTO decision_outcomes(outcome_id, decision_id, recorded_at, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(outcome_id) DO UPDATE SET
                    decision_id = excluded.decision_id,
                    recorded_at = excluded.recorded_at,
                    payload = excluded.payload
                """,
                (
                    outcome.outcome_id,
                    outcome.decision_id,
                    outcome.recorded_at.isoformat(),
                    outcome.model_dump_json(),
                ),
            )
            await db.commit()

    async def get_plan(self, decision_id: str) -> PortfolioPlan | None:
        async with aiosqlite.connect(self._path) as db:
            cursor = await db.execute(
                "SELECT payload FROM portfolio_plans WHERE decision_id = ?", (decision_id,)
            )
            row = await cursor.fetchone()
        return PortfolioPlan.model_validate_json(row[0]) if row else None

    async def get_outcomes(self, decision_id: str) -> list[DecisionOutcome]:
        async with aiosqlite.connect(self._path) as db:
            cursor = await db.execute(
                """
                SELECT payload FROM decision_outcomes
                WHERE decision_id = ? ORDER BY recorded_at
                """,
                (decision_id,),
            )
            rows = await cursor.fetchall()
        return [DecisionOutcome.model_validate_json(row[0]) for row in rows]

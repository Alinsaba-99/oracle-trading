"""Durable inbox for read-only intelligence produced by external agents."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from core.domain.intelligence import OpportunityObservation


class SQLiteIntelligenceInbox:
    """Persist external observations before they enter the investment committee."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def save(self, observation: OpportunityObservation) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS intelligence_observations (
                    observation_id TEXT PRIMARY KEY,
                    available_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO intelligence_observations(
                    observation_id, available_at, payload
                ) VALUES (?, ?, ?)
                """,
                (
                    observation.observation_id,
                    observation.available_at.isoformat(),
                    observation.model_dump_json(),
                ),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def get(self, observation_id: str) -> OpportunityObservation | None:
        async with aiosqlite.connect(self._path) as db:
            cursor = await db.execute(
                "SELECT payload FROM intelligence_observations WHERE observation_id = ?",
                (observation_id,),
            )
            row = await cursor.fetchone()
        return OpportunityObservation.model_validate_json(row[0]) if row else None

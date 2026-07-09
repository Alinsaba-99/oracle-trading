"""Experiment Registry model."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import aiosqlite
from pydantic import BaseModel, Field

from core.domain.enums import ExperimentStatus, ExperimentType


class Experiment(BaseModel):
    experiment_id: str
    type: ExperimentType
    parent_experiment_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    git_commit: str = ""
    status: ExperimentStatus = ExperimentStatus.running
    dataset_version: str = ""
    feature_version: str = ""
    genome_hash: str | None = None
    config_hash: str = ""
    random_seed: int = 42
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    duration_seconds: float | None = None
    error: str | None = None


class ExperimentContext(BaseModel):
    """Immutable experiment context captured at creation time.
    Used for reproducibility (ADR-007). Phase 1: migrate to PostgreSQL/QuestDB.
    """

    experiment_id: str = Field(default_factory=lambda: str(uuid4()))
    parent_experiment_id: str | None = None
    git_commit: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    random_seed: int = 42
    tags: dict[str, str] = Field(default_factory=dict)


class ExperimentRegistry:
    """Thread-safe experiment registry backed by SQLite.

    Stores experiments in a SQLite database via aiosqlite.
    Each experiment is serialized as JSON and stored alongside its
    parent_experiment_id for WFA (walk-forward analysis) tracking.
    """

    def __init__(self, db_path: str = "experiments/experiments.db") -> None:
        self._db_path = db_path
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_table(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS experiments (
                        id TEXT PRIMARY KEY,
                        parent_id TEXT,
                        data TEXT,
                        created_at TEXT
                    )
                    """
                )
                await db.commit()
            self._initialized = True

    async def async_register(self, ctx: ExperimentContext) -> None:
        """Register a new experiment context asynchronously."""
        await self._ensure_table()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO experiments (id, parent_id, data, created_at) VALUES (?, ?, ?, ?)",
                (
                    ctx.experiment_id,
                    ctx.parent_experiment_id,
                    ctx.model_dump_json(),
                    ctx.timestamp.isoformat(),
                ),
            )
            await db.commit()

    async def async_list(self) -> list[ExperimentContext]:
        """List all registered experiments asynchronously."""
        await self._ensure_table()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("SELECT data FROM experiments ORDER BY created_at")
            rows = await cursor.fetchall()
            return [ExperimentContext.model_validate_json(row[0]) for row in rows]

    async def async_get(self, experiment_id: str) -> ExperimentContext | None:
        """Get an experiment by ID asynchronously."""
        await self._ensure_table()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("SELECT data FROM experiments WHERE id = ?", (experiment_id,))
            row = await cursor.fetchone()
            return ExperimentContext.model_validate_json(row[0]) if row else None

    # ------------------------------------------------------------------
    # Synchronous wrappers (backward compatible)
    # ------------------------------------------------------------------

    @staticmethod
    def __run(coro: Any) -> Any:
        """Execute a coroutine synchronously."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                raise RuntimeError(
                    "Cannot call sync wrapper from within an async context. "
                    "Use async_register / async_list / async_get instead."
                )
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def register(self, ctx: ExperimentContext) -> None:
        """Register a new experiment context (sync wrapper)."""
        self.__run(self.async_register(ctx))

    def list(self) -> list[ExperimentContext]:
        """List all registered experiments (sync wrapper)."""
        return cast(list[ExperimentContext], self.__run(self.async_list()))

    def get(self, experiment_id: str) -> ExperimentContext | None:
        """Get an experiment by ID (sync wrapper)."""
        return cast(ExperimentContext | None, self.__run(self.async_get(experiment_id)))

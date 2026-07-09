"""Experiment Registry model."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from core.domain.enums import ExperimentStatus, ExperimentType


class Experiment(BaseModel):
    experiment_id: str
    type: ExperimentType
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
    git_commit: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    random_seed: int = 42
    tags: dict[str, str] = Field(default_factory=dict)


class ExperimentRegistry:
    """Thread-safe experiment registry backed by JSONL.

    Writes to experiments/_registry.jsonl. Each line is a JSON-serialized
    ExperimentContext. Thread-safe via Lock.
    Phase 1: migrate to PostgreSQL/QuestDB for production.
    """

    def __init__(self, path: str | Path = "experiments/_registry.jsonl") -> None:
        self._path = Path(path)
        self._lock = Lock()
        self._cache: list[ExperimentContext] = []
        self._load_cache()

    def _load_cache(self) -> None:
        if self._path.exists():
            with open(self._path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._cache.append(ExperimentContext.model_validate_json(line))

    def register(self, ctx: ExperimentContext) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a") as f:
                f.write(ctx.model_dump_json() + "\n")
            self._cache.append(ctx)

    def list(self) -> list[ExperimentContext]:
        with self._lock:
            return list(self._cache)

    def get(self, experiment_id: str) -> ExperimentContext | None:
        with self._lock:
            for ctx in self._cache:
                if ctx.experiment_id == experiment_id:
                    return ctx
        return None

"""Reader for past GA experiments stored in the Experiment Registry."""

from __future__ import annotations

from typing import Any


class GARegistryReader:
    """Reads past GA experiments from the Experiment Registry."""

    def __init__(self, db_path: str = "experiments/experiments.db") -> None:
        from core.domain.experiment import ExperimentRegistry

        self._registry = ExperimentRegistry(db_path=db_path)

    def list_runs(self) -> list[dict[str, Any]]:
        """List recent GA runs."""
        experiments = self._registry.list()
        return [
            {"id": e.experiment_id, "timestamp": str(e.timestamp), "tags": dict(e.tags)}
            for e in experiments
            if "ga" in str(e.tags)
        ]

    def get_best_run(self) -> dict[str, Any] | None:
        """Get the run with highest Sharpe (first in list for now)."""
        runs = self.list_runs()
        return runs[0] if runs else None

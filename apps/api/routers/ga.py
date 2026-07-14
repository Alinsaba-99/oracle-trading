"""Genetic Algorithm run viewer endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from apps.api.services.checkpoint_reader import get_ga_run, list_ga_runs

router = APIRouter(prefix="/ga", tags=["ga"])


@router.get("/runs")
async def get_runs() -> dict[str, object]:
    """List available GA runs."""
    return {"runs": list_ga_runs()}


@router.get("/runs/{run_id}")
async def get_run_detail(run_id: str) -> dict[str, object]:
    """Get GA run detail with Pareto front and convergence."""
    run = get_ga_run(run_id)
    if run is None:
        return {"run_id": run_id, "status": "not_found", "pareto_front": [], "convergence": []}

    return {
        "run_id": run.run_id,
        "seed": run.seed,
        "n_generations": run.n_generations,
        "n_islands": run.n_islands,
        "pop_size": run.pop_size,
        "signal_type": run.signal_type,
        "status": "completed",
        "pareto_front": [
            {
                "sharpe": p.sharpe,
                "sortino": p.sortino,
                "calmar": p.calmar,
                "max_drawdown": p.max_drawdown,
                "params": p.params,
            }
            for p in run.pareto_front
        ],
        "convergence": run.convergence,
    }

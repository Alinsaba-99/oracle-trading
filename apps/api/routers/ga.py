from fastapi import APIRouter

router = APIRouter(prefix="/ga", tags=["ga"])

@router.get("/runs")
async def list_runs():
    """List available GA runs."""
    # TODO: scan checkpoints/ directories
    return {"runs": []}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get GA run detail with Pareto front and convergence."""
    # TODO: read checkpoint file
    return {"run_id": run_id, "status": "not_found"}

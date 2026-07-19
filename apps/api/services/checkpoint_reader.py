"""Read GA checkpoint files and extract performance data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from analytics.backtest.store import BacktestResultStore, to_equity_points, to_performance_summary


@dataclass
class ParetoIndividual:
    """A single individual in the Pareto front."""

    sharpe: float = -1.0
    sortino: float = -1.0
    calmar: float = -1.0
    max_drawdown: float = 1.0
    params: dict[str, float] = field(default_factory=dict)


@dataclass
class GARun:
    """Summary of a single GA run."""

    run_id: str = ""
    seed: int = 0
    n_generations: int = 0
    n_islands: int = 0
    pop_size: int = 0
    signal_type: str = ""
    pareto_front: list[ParetoIndividual] = field(default_factory=list)
    convergence: list[dict[str, float]] = field(default_factory=list)
    status: str = "unknown"
    timing_s: float = 0.0


_CHECKPOINT_DIR = Path(__file__).resolve().parents[3] / "checkpoints"


def _scan_checkpoint_dirs() -> list[Path]:
    """Scan checkpoints/ for run directories containing gen_*.json."""
    if not _CHECKPOINT_DIR.exists():
        return []

    runs: list[Path] = []
    # Direct subdirectories (prod_seed42, pb_seed42, etc.)
    for d in _CHECKPOINT_DIR.iterdir():
        if d.is_dir() and list(d.glob("gen_*.json")):
            runs.append(d)

    # Also check legacy/ subdirectory
    legacy = _CHECKPOINT_DIR / "legacy"
    if legacy.exists() and list(legacy.glob("gen_*.json")):
        runs.append(legacy)

    return sorted(runs, key=lambda p: p.stat().st_mtime, reverse=True)


def _read_checkpoint(path: Path) -> dict[str, Any] | None:
    """Read a single checkpoint JSON file."""
    try:
        with open(path) as f:
            return dict(json.load(f))
    except (json.JSONDecodeError, OSError):
        return None


def _decode_params(values: list[float], param_defs: list[dict[str, Any]]) -> dict[str, float]:
    """Decode normalized parameters back to raw values."""
    params: dict[str, float] = {}
    for i, v in enumerate(values):
        if i < len(param_defs):
            pdef = param_defs[i]
            name = pdef.get("name", f"param_{i}")
            low = float(pdef.get("low", 0))
            high = float(pdef.get("high", 1))
            params[name] = low + v * (high - low)
        else:
            params[f"param_{i}"] = float(v)
    return params


def list_ga_runs() -> list[dict[str, Any]]:
    """List all available GA runs."""
    dirs = _scan_checkpoint_dirs()
    result: list[dict[str, Any]] = []

    for d in dirs:
        gens = sorted(d.glob("gen_*.json"), key=lambda p: _gen_number(p))
        if not gens:
            continue

        last = _read_checkpoint(gens[-1])
        if last is None:
            continue

        result.append(
            {
                "run_id": d.name,
                "seed": last.get("seed", 0),
                "n_generations": last.get("generation", 0),
                "n_islands": last.get("n_islands", 0),
                "pop_size": last.get("pop_size_per_island", 0) * last.get("n_islands", 0),
                "signal_type": last.get("signal_type", ""),
                "status": "completed",
                "checkpoint_count": len(gens),
            }
        )

    return result


def _gen_number(path: Path) -> int:
    """Extract generation number from filename like gen_0050.json."""
    try:
        return int(path.stem.split("_")[1])
    except (IndexError, ValueError):
        return 0


def get_ga_run(run_id: str) -> GARun | None:
    """Get detailed data for a single GA run."""
    dirs = _scan_checkpoint_dirs()

    target_dir = None
    for d in dirs:
        if d.name == run_id:
            target_dir = d
            break

    if target_dir is None:
        return None

    gens = sorted(target_dir.glob("gen_*.json"), key=_gen_number)
    if not gens:
        return None

    last_cp = _read_checkpoint(gens[-1])
    if last_cp is None:
        return None

    run = GARun(
        run_id=run_id,
        seed=last_cp.get("seed", 0),
        n_generations=last_cp.get("generation", 0),
        n_islands=last_cp.get("n_islands", 0),
        pop_size=last_cp.get("pop_size_per_island", 0) * last_cp.get("n_islands", 0),
        signal_type=last_cp.get("signal_type", ""),
    )

    param_defs = last_cp.get("config", {}).get("param_defs", [])

    # Extract Pareto front (all individuals from last generation)
    seen: set[str] = set()
    for island in last_cp.get("islands", []):
        for ind in island.get("population", []):
            fit = ind.get("fitness", {}).get("values", [])
            if len(fit) < 4:
                continue
            sharpe = float(fit[0])
            # Skip failed/empty fitness
            if sharpe <= -1000 or (sharpe == -1.0 and all(f == -1.0 for f in fit[:3])):
                continue
            sortino = float(fit[1])
            calmar = float(fit[2])
            maxdd = float(fit[3])

            # Deduplicate
            key = f"{sharpe:.3f}:{sortino:.3f}:{maxdd:.3f}"
            if key in seen:
                continue
            seen.add(key)

            params = _decode_params(ind.get("values", []), param_defs)
            run.pareto_front.append(
                ParetoIndividual(
                    sharpe=sharpe, sortino=sortino, calmar=calmar, max_drawdown=maxdd, params=params
                )
            )

    # Sort by Sharpe descending
    run.pareto_front.sort(key=lambda x: x.sharpe, reverse=True)

    # Convergence: best Sharpe per generation
    for cp_path in gens:
        cp = _read_checkpoint(cp_path)
        if cp is None:
            continue
        gen = cp.get("generation", 0)
        best = -1e6
        for island in cp.get("islands", []):
            for ind in island.get("population", []):
                fit = ind.get("fitness", {}).get("values", [])
                if len(fit) >= 1 and fit[0] is not None:
                    s = float(fit[0])
                    if s > best and s > -1000:
                        best = s
        # anche la media per generazione
        values = []
        for island in cp.get("islands", []):
            for ind in island.get("population", []):
                fit = ind.get("fitness", {}).get("values", [])
                if len(fit) >= 3:
                    try:
                        if float(fit[0]) > -1000:
                            values.append((float(fit[0]), float(fit[1]), float(fit[2])))
                    except (TypeError, ValueError):
                        pass
        if values:
            avg_sharpe = sum(v[0] for v in values) / len(values)
            avg_sortino = sum(v[1] for v in values) / len(values)
            avg_calmar = sum(v[2] for v in values) / len(values)
            if best > -1000:
                run.convergence.append(
                    {
                        "generation": gen,
                        "best_sharpe": round(best, 4),
                        "avg_sharpe": round(avg_sharpe, 4),
                        "avg_sortino": round(avg_sortino, 4),
                        "avg_calmar": round(avg_calmar, 4),
                    }
                )

    return run


def get_latest_run_summary() -> dict[str, Any] | None:
    """Get performance summary — prefer a real persisted BacktestResult.

    When a :class:`BacktestResult` has been persisted (by the backtest
    orchestrator), every field reflects an actual backtest — no
    placeholder zeros.  Falls back to the GA-checkpoint-derived summary
    (partial metrics) only when no real result exists yet.
    """
    result = BacktestResultStore().load_latest()
    if result is not None:
        return to_performance_summary(result)

    runs = list_ga_runs()
    if not runs:
        return None

    latest = runs[0]
    run = get_ga_run(latest["run_id"])
    if run is None or not run.pareto_front:
        return None

    best = run.pareto_front[0]
    return {
        "sharpe": best.sharpe,
        "sortino": best.sortino,
        "calmar": best.calmar,
        "max_drawdown": best.max_drawdown,
        "profit_factor": 0.0,  # not in checkpoint
        "cagr": 0.0,
        "total_return": 0.0,
        "run_id": latest["run_id"],
        "run_seed": latest["seed"],
        "run_generations": latest["n_generations"],
    }


def get_equity_curve() -> list[dict[str, float]]:
    """Return equity curve — from a persisted BacktestResult when available.

    Returns an empty list when no real backtest has been persisted yet.
    """
    result = BacktestResultStore().load_latest()
    if result is not None and result.equity_curve:
        return to_equity_points(result)
    return []

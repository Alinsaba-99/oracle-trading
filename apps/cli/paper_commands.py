"""BL-615 — canonical spec-driven paper runner (``oracle paper run --spec``).

Strangler entry point for the five legacy ``run_*paper*.py`` runners:
every paper run goes through ONE code path (the session engine in
``scripts.run_g6_wp2_paper_sessions._run_session``) driven by a
versioned spec, and produces a reproducible manifest next to the
results: data hash, spec hash, seed, code version, git commit.

Spec format (YAML or JSON)::

    schema_version: 1
    name: bl024-qualification
    data: data/lake/normalized/symbol=ES/tf=1d/
    instrument: MES
    sessions: 100
    window: 95
    ensemble: edge_v2
    seed: 42
    storage: memory

The storage default follows BL-060 (postgres when a DSN is configured,
else memory with a loud warning).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

_SPEC_SCHEMA_VERSION = 1


class PaperRunSpec(BaseModel):
    """Versioned, validated configuration for one canonical paper run."""

    schema_version: int = Field(default=_SPEC_SCHEMA_VERSION, ge=1)
    name: str = "paper-run"
    data: str
    instrument: str = "ES"
    capital: float = Field(default=100_000.0, gt=0)
    point_value: float | None = None  # None → auto (MES=5.0, else 50.0)
    sessions: int = Field(default=100, ge=1)
    window: int = Field(default=95, ge=10)
    ensemble: Literal["regime", "edge_v2"] = "regime"
    max_dd_pct: float = Field(default=3.0, gt=0)
    monte_carlo: bool = False
    seed: int = 42
    verify_pin: bool = False
    storage: Literal["memory", "postgres"] | None = None  # None → BL-060 rule
    dsn: str | None = None
    gate_pass_rate: float = Field(default=0.90, ge=0, le=1)
    gate_mean_sharpe: float = Field(default=-0.5)
    gate_mean_dd_pct: float = Field(default=3.0, gt=0)
    output: str = "logs/paper_canonical/run.json"

    def resolved_point_value(self) -> float:
        if self.point_value is not None:
            return self.point_value
        return 5.0 if self.instrument.upper() == "MES" else 50.0


def load_spec(path: str | Path) -> PaperRunSpec:
    """Load a YAML or JSON spec file into a validated PaperRunSpec."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) if p.suffix.lower() in (".yaml", ".yml") else json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError(f"Spec root must be a mapping, got {type(raw).__name__}")
    return PaperRunSpec.model_validate(raw)


def hash_data(path: str | Path) -> str:
    """SHA-256 fingerprint of a parquet file or a directory of parquets.

    Directories are fingerprinted as the hash of sorted
    ``relative_path:file_sha256`` lines — order-independent content hash.
    """
    p = Path(path)
    if p.is_file():
        return hashlib.sha256(p.read_bytes()).hexdigest()
    entries: list[str] = []
    for f in sorted(p.rglob("*.parquet")):
        fh = hashlib.sha256(f.read_bytes()).hexdigest()
        entries.append(f"{f.relative_to(p)}:{fh}")
    if not entries:
        raise ValueError(f"No parquet files under {p}")
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def hash_spec(spec: PaperRunSpec) -> str:
    """SHA-256 of the canonicalised spec (reproducible identity)."""
    canonical = json.dumps(spec.model_dump(), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _code_version() -> str:
    try:
        from importlib.metadata import version

        return version("oracle")
    except Exception:
        return "unknown"


def _git_commit() -> str:
    try:
        import subprocess

        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True, cwd=Path.cwd()
        ).strip()
    except Exception:
        return "unknown"


def build_windows(df: Any, n: int, window: int, *, monte_carlo: bool, seed: int) -> list[Any]:
    """Slice *n* session windows (sequential or seeded Monte Carlo)."""
    import polars as pl

    df = pl.DataFrame(df) if not isinstance(df, pl.DataFrame) else df
    n_total = len(df)
    if monte_carlo:
        import random as _rnd

        rng = _rnd.Random(seed)
        return [df[rng.randint(0, n_total - window) :][:window] for _ in range(n)]
    step = max(1, (n_total - window) // n) if n_total > window else 1
    # Clamp every start so all windows are exactly ``window`` bars (the
    # legacy runner only padded the last one; short tails were possible
    # when the series admits fewer distinct positions than sessions).
    max_start = n_total - window
    windows = [df[min(i * step, max_start) : min(i * step, max_start) + window] for i in range(n)]
    return windows


def build_ensemble(ensemble_name: str) -> Any | None:
    """Return the signal engine for a spec ensemble name (None = regime default)."""
    if ensemble_name == "edge_v2":
        from analytics.strategy.edge_ensemble_v2 import EdgeEnsembleV2

        return EdgeEnsembleV2()
    if ensemble_name != "regime":
        raise ValueError(f"unknown ensemble {ensemble_name!r} (regime|edge_v2)")
    return None


async def run_paper_spec(spec: PaperRunSpec) -> int:
    """Execute one canonical paper run; write results + manifest.

    Returns 0 when the gate passes, 1 when it is rejected, 2 on setup
    errors (missing data, unknown ensemble).
    """
    # Local imports keep the CLI import cheap; the engine modules pull
    # analytics/polars dependencies.
    import polars as pl

    from scripts.run_g6_wp2_100_sessions import _read_data, _verify_pin_hash
    from scripts.run_g6_wp2_paper_sessions import _run_session

    df = _read_data(spec.data)
    df = pl.DataFrame(df)
    n_total = len(df)
    if n_total < spec.window:
        print(f"ERROR: only {n_total} bars, need at least {spec.window} for one session")
        return 2

    if spec.verify_pin:
        _verify_pin_hash(df)

    try:
        ensemble = build_ensemble(spec.ensemble)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    # BL-060: storage defaults to postgres when a DSN is configured.
    from core.config.storage import resolve_storage_default

    storage, env_dsn = resolve_storage_default(spec.storage)
    dsn = spec.dsn or env_dsn if storage == "postgres" else None
    if spec.storage is None and storage == "memory":
        print(
            "WARNING: no DATABASE_URL/ORACLE_POSTGRES__DSN configured — "
            "using in-memory storage; state will NOT survive a restart (BL-060)"
        )

    capital_dec = Decimal(str(spec.capital))
    point_value_dec = Decimal(str(spec.resolved_point_value()))
    windows = build_windows(
        df, spec.sessions, spec.window, monte_carlo=spec.monte_carlo, seed=spec.seed
    )

    results: list[dict[str, Any]] = []
    for i, df_win in enumerate(windows):
        res = await _run_session(
            session_id=i + 1,
            df_session=df_win,
            instrument=spec.instrument,
            capital=capital_dec,
            point_value=point_value_dec,
            max_dd_pct=spec.max_dd_pct,
            storage=storage,
            dsn=dsn,
            ensemble=ensemble,
        )
        results.append(res)

    n = len(results)
    passed = sum(1 for r in results if r["passed"])
    pnls = [float(r["total_pnl"]) for r in results]
    sharpe_vals = [float(r["sharpe"]) for r in results]
    dd_vals = [float(r["max_drawdown_pct"]) for r in results]
    reconcile_clean = sum(1 for r in results if r["reconcile_clean"])

    mean_sharpe = statistics.mean(sharpe_vals) if sharpe_vals else 0.0
    mean_dd = statistics.mean(dd_vals) if dd_vals else 0.0
    pass_rate = passed / n if n else 0.0
    gate_passed = (
        pass_rate >= spec.gate_pass_rate
        and mean_sharpe >= spec.gate_mean_sharpe
        and mean_dd <= spec.gate_mean_dd_pct
    )

    data_hash = hash_data(spec.data)
    spec_hash = hash_spec(spec)
    started_at = datetime.now(UTC).isoformat()

    output_path = Path(spec.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "schema_version": "paper-canonical-v1",
            "name": spec.name,
            "instrument": spec.instrument,
            "data": spec.data,
            "sessions": n,
            "window": spec.window,
            "ensemble": spec.ensemble,
            "capital": spec.capital,
            "point_value": spec.resolved_point_value(),
            "storage": storage,
            "timestamp": started_at,
        },
        "gate": {
            "decision": "approved" if gate_passed else "rejected",
            "pass_rate": round(pass_rate, 4),
            "mean_sharpe": round(mean_sharpe, 4),
            "mean_drawdown_pct": round(mean_dd, 4),
            "total_pnl": round(sum(pnls), 2),
            "reconcile_clean_rate": round(reconcile_clean / n, 4) if n else 0.0,
            "thresholds": {
                "pass_rate": spec.gate_pass_rate,
                "mean_sharpe": spec.gate_mean_sharpe,
                "mean_dd_pct": spec.gate_mean_dd_pct,
            },
        },
        "results": results,
    }
    output_path.write_text(json.dumps(payload, indent=2, default=str))

    manifest = {
        "schema_version": "paper-run-manifest-v1",
        "run": spec.name,
        "timestamp": started_at,
        "spec": spec.model_dump(),
        "spec_hash": spec_hash,
        "data_path": spec.data,
        "data_hash": data_hash,
        "seed": spec.seed,
        "monte_carlo": spec.monte_carlo,
        "code_version": _code_version(),
        "git_commit": _git_commit(),
        "gate": payload["gate"],
        "output": str(output_path),
    }
    manifest_path = output_path.with_name(output_path.stem + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))

    print(
        f"paper run '{spec.name}': {n} sessions, pass {pass_rate:.2%}, "
        f"mean Sharpe {mean_sharpe:.3f}, mean DD {mean_dd:.2f}% → "
        f"{'APPROVED' if gate_passed else 'REJECTED'}"
    )
    print(f"  results:  {output_path}")
    print(
        f"  manifest: {manifest_path} "
        f"(data sha256 {data_hash[:16]}…, spec sha256 {spec_hash[:16]}…)"
    )
    return 0 if gate_passed else 1


def handle_paper_run(args: argparse.Namespace) -> int:
    """CLI handler: ``oracle paper run --spec <file>``."""
    try:
        spec = load_spec(args.spec)
    except Exception as exc:
        print(f"ERROR: invalid spec file {args.spec}: {exc}")
        return 2
    return asyncio.run(run_paper_spec(spec))


__all__ = [
    "PaperRunSpec",
    "build_ensemble",
    "build_windows",
    "handle_paper_run",
    "hash_data",
    "hash_spec",
    "load_spec",
    "run_paper_spec",
]

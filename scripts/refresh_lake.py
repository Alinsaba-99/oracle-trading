#!/usr/bin/env python3
"""BL-304 — Daily lake refresh: incremental backfill + curated rebuild.

Runs the incremental backfill plan (orchestrator, resumable, idempotent)
and then rebuilds the curated layer. Designed for unattended scheduling
(systemd user timer or crontab).

Exit codes: 0 = all ok; 1 = orchestrator or curation reported failures
(failures are recorded in data/lake/metadata/ingestion_state.json and
data/lake/logs/ingestion_audit.jsonl; a re-run resumes and retries).

Usage:
    uv run python scripts/refresh_lake.py [--tf 1m,1h,1d]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> int:
    print(f"[refresh] $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily lake refresh (BL-304)")
    parser.add_argument(
        "--tf",
        default="1m,1h,1d,5m,15m,30m",
        help="Comma-separated timeframes to rebuild in curated (default: 1m,1h,1d,5m,15m,30m)",
    )
    args = parser.parse_args()

    t0 = datetime.now(UTC)
    print(f"[refresh] start {t0.isoformat()}", flush=True)

    # 1) incremental backfill per plan (only missing bars; skips fresh)
    rc = run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "market.ingestion.cli",
            "run-plan",
            "--incremental",
            "--pause",
            "1",
        ]
    )
    if rc != 0:
        print(
            "[refresh] orchestrator reported failures — see "
            "data/lake/metadata/ingestion_state.json (expected for "
            "ibkr/databento while credentials are missing)",
            flush=True,
        )

    # 2) derive 5m/15m/30m from the freshly-fetched 1m (no extra downloads)
    rc_res = run(
        [
            "uv",
            "run",
            "python",
            "scripts/resample_lake.py",
            "--all",
            "--tfs",
            "5m,15m,30m",
            "--recent-days",
            "45",
        ]
    )
    if rc_res != 0:
        rc = rc_res

    # 3) rebuild curated layer so consumers always read merged files
    for tf in (t.strip() for t in args.tf.split(",") if t.strip()):
        rc_cur = run(["uv", "run", "python", "scripts/build_curated_contracts.py", "--tf", tf])
        if rc_cur != 0:
            rc = rc_cur

    dur = round((datetime.now(UTC) - t0).total_seconds(), 1)
    print(f"[refresh] done in {dur}s — rc={rc}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""BL-307 — Data lake metadata audit + repair.

Audits the lake's provenance bookkeeping:

  1. every ``data/lake/normalized/**/*.parquet`` partition has an entry in
     ``data/lake/metadata/lineage.json``;
  2. every coverage record has the full schema
     (``earliest`` / ``latest`` / ``rows`` / ``sources`` / ``version`` /
     ``last_touch``);
  3. every lineage key still points to an existing partition (no dangling
     references).

With ``--fix``, provenance is reconstructed **from the data itself** — the
``source`` column that the pipeline writes inside each normalized parquet —
never guessed or inferred from neighbouring files. Coverage records are
recomputed from the actual partitions on disk.

Exit codes:
  0  audit clean (or repair succeeded and re-audit is clean)
  1  audit found problems (no --fix, or repair could not fully fix)
  2  usage / internal error

Usage:
    uv run python scripts/audit_lake_metadata.py            # audit only
    uv run python scripts/audit_lake_metadata.py --fix      # audit + repair
    uv run python scripts/audit_lake_metadata.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
LAKE_ROOT = ROOT / "data/lake"
NORM_ROOT = LAKE_ROOT / "normalized"
META_DIR = LAKE_ROOT / "metadata"
LINEAGE_PATH = META_DIR / "lineage.json"
COVERAGE_PATH = META_DIR / "coverage.json"

COVERAGE_REQUIRED = ("earliest", "latest", "rows", "sources", "version", "last_touch")

#: Columns that must exist in every normalized partition.
PARTITION_REQUIRED = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "symbol",
    "source",
    "timeframe",
)


def load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def atomic_write(path: Path, data: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str, sort_keys=True))
    tmp.replace(path)


def partition_rel_paths() -> list[str]:
    """Partition keys in the canonical lineage format.

    The pipeline writes ``path.relative_to(LAKE_ROOT)`` (e.g.
    ``normalized/symbol=X/tf=1m/...``), so keys are relative to
    ``data/lake/``, not to the repo root.
    """
    return sorted(p.relative_to(LAKE_ROOT).as_posix() for p in NORM_ROOT.rglob("*.parquet"))


def read_sources(rel: str) -> list[str] | None:
    """Read the ``source`` column of one partition (provenance from the data)."""
    path = LAKE_ROOT / rel
    try:
        df = pl.scan_parquet(path).select("source").unique().collect()
        return sorted(str(v) for v in df["source"].to_list())
    except Exception:
        return None


def audit() -> dict[str, Any]:
    lineage = load_json(LINEAGE_PATH, {})
    if not isinstance(lineage, dict):
        lineage = {}
    coverage = load_json(COVERAGE_PATH, {})
    if not isinstance(coverage, dict):
        coverage = {}

    parts = partition_rel_paths()

    missing_lineage = [p for p in parts if p not in lineage]
    dangling = [k for k in lineage if not (LAKE_ROOT / k).exists()]

    incomplete_cov: list[str] = []
    for key, rec in coverage.items():
        if not isinstance(rec, dict):
            incomplete_cov.append(f"{key} (non-dict)")
            continue
        if "rows" in rec and not all(c in rec for c in COVERAGE_REQUIRED):
            incomplete_cov.append(key)

    # Partitions whose schema lacks the source column (cannot be repaired
    # from data — provenance would have to be guessed).
    bad_schema: list[str] = []
    if missing_lineage:
        for rel in missing_lineage:
            path = LAKE_ROOT / rel
            try:
                cols = pl.scan_parquet(path).collect_schema().names()
            except Exception:
                bad_schema.append(f"{rel} (unreadable)")
                continue
            if not all(c in cols for c in PARTITION_REQUIRED):
                bad_schema.append(f"{rel} (missing columns)")

    return {
        "partitions_total": len(parts),
        "missing_lineage": missing_lineage,
        "dangling_lineage": dangling,
        "coverage_total": len(coverage),
        "coverage_incomplete": incomplete_cov,
        "unrepairable_partitions": bad_schema,
    }


def repair() -> dict[str, Any]:
    """Rebuild lineage/coverage from the actual partition data."""
    lineage = load_json(LINEAGE_PATH, {})
    if not isinstance(lineage, dict):
        lineage = {}
    coverage = load_json(COVERAGE_PATH, {})
    if not isinstance(coverage, dict):
        coverage = {}

    parts = partition_rel_paths()
    missing = [p for p in parts if p not in lineage]

    fixed_lineage = 0
    unrepairable: list[str] = []
    if missing:

        def _one(rel: str) -> tuple[str, list[str] | None]:
            return rel, read_sources(rel)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_one, rel): rel for rel in missing}
            for fut in as_completed(futures):
                rel, srcs = fut.result()
                if srcs is None:
                    unrepairable.append(rel)
                    continue
                lineage[rel] = srcs
                fixed_lineage += 1

    # Normalize keys: older tooling wrote repo-root-relative keys
    # ("data/lake/normalized/..."); the canonical format is lake-root
    # relative ("normalized/..."). Rewrite so dangling references are real.
    rewritten = 0
    for key in [k for k in lineage if k.startswith("data/lake/")]:
        canonical = key[len("data/lake/") :]
        lineage[canonical] = sorted({*lineage.get(canonical, []), *lineage[key]})
        del lineage[key]
        rewritten += 1

    # Drop dangling references (keys whose partition no longer exists).
    dangling = [k for k in lineage if not (LAKE_ROOT / k).exists()]
    for k in dangling:
        del lineage[k]

    if fixed_lineage or rewritten or dangling:
        atomic_write(LINEAGE_PATH, lineage)

    # Recompute coverage for every series from its partitions.
    fixed_cov = 0
    by_series: dict[str, list[str]] = {}
    for rel in parts:
        # normalized/symbol=X/tf=TF/year=Y/month=MM.parquet
        try:
            sym = rel.split("/symbol=", 1)[1].split("/", 1)[0]
            tf = rel.split("/tf=", 1)[1].split("/", 1)[0]
        except IndexError:
            continue
        by_series.setdefault(f"{sym}|{tf}", []).append(rel)

    for key, rels in by_series.items():
        rec = coverage.get(key, {})
        if isinstance(rec, dict) and all(c in rec for c in COVERAGE_REQUIRED):
            continue  # already complete
        earliest: str | None = None
        latest: str | None = None
        rows = 0
        src_set: set[str] = set()
        ok = True
        for rel in rels:
            path = LAKE_ROOT / rel
            try:
                df = pl.scan_parquet(path).select("timestamp", "source").collect()
            except Exception:
                ok = False
                break
            if df.is_empty():
                continue
            ts_min = df["timestamp"].min()
            ts_max = df["timestamp"].max()
            if earliest is None or str(ts_min) < earliest:
                earliest = str(ts_min)
            if latest is None or str(ts_max) > latest:
                latest = str(ts_max)
            rows += df.height
            src_set.update(str(s) for s in df["source"].unique().to_list())
        if not ok:
            continue
        coverage[key] = {
            "earliest": earliest,
            "latest": latest,
            "rows": rows,
            "sources": sorted(src_set),
            "version": int(rec.get("version", 0)) + 1 if isinstance(rec, dict) else 1,
            "last_touch": datetime.now(UTC).isoformat(),
        }
        fixed_cov += 1
    atomic_write(COVERAGE_PATH, coverage)

    return {
        "lineage_fixed": fixed_lineage,
        "lineage_rewritten": rewritten,
        "dangling_removed": len(dangling),
        "coverage_fixed": fixed_cov,
        "unrepairable": unrepairable,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="BL-307 lake metadata audit")
    parser.add_argument("--fix", action="store_true", help="repair from partition data")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    report = audit()

    if args.fix and (report["missing_lineage"] or report["coverage_incomplete"]):
        fix = repair()
        report = audit()  # re-audit after repair
        report["repair"] = fix

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"partitions total:        {report['partitions_total']}")
        print(f"missing lineage:         {len(report['missing_lineage'])}")
        print(f"dangling lineage:        {len(report['dangling_lineage'])}")
        print(f"coverage total:          {report['coverage_total']}")
        print(f"coverage incomplete:     {len(report['coverage_incomplete'])}")
        print(f"unrepairable partitions: {len(report['unrepairable_partitions'])}")
        if "repair" in report:
            r = report["repair"]
            print(
                f"repair: lineage_fixed={r['lineage_fixed']} "
                f"rewritten={r['lineage_rewritten']} "
                f"dangling_removed={r['dangling_removed']} "
                f"coverage_fixed={r['coverage_fixed']} "
                f"unrepairable={len(r['unrepairable'])}"
            )
        if report["missing_lineage"][:5]:
            print("sample missing:", *report["missing_lineage"][:5], sep="\n  ")
        if report["coverage_incomplete"][:5]:
            print("sample incomplete coverage:", *report["coverage_incomplete"][:5], sep="\n  ")

    if report["missing_lineage"] or report["dangling_lineage"] or report["coverage_incomplete"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

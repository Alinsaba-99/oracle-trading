#!/usr/bin/env python3
"""Analyze past MAS runs from the Experiment Registry.

Usage:
    python -m experiments.scripts.analyze_mas --last 10
    python -m experiments.scripts.analyze_mas --instrument SPY
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


def _fetch_recent(limit: int = 10, instrument: str | None = None) -> list[dict[str, Any]]:
    """Fetch recent MAS run records from the Experiment Registry.

    Returns an empty list when the registry is unavailable.
    """
    try:
        from core.domain.experiment import ExperimentRegistry

        registry = ExperimentRegistry()
    except ImportError:
        return []
    except Exception:
        return []

    try:
        all_records = registry.list()
        records = all_records[-limit:]
    except Exception:
        return []

    if instrument:
        records = [r for r in records if getattr(r, "instrument", None) == instrument]

    result: list[dict[str, Any]] = []
    for rec in records:
        entry: dict[str, Any] = {
            "id": getattr(rec, "experiment_id", getattr(rec, "id", "?")),
            "timestamp": str(getattr(rec, "timestamp", "?")),
            "instrument": getattr(rec, "instrument", "?"),
            "tags": dict(getattr(rec, "tags", {})),
        }
        result.append(entry)

    return result


def _compute_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate statistics across MAS runs."""
    instruments: dict[str, int] = {}
    for r in records:
        instr = r.get("instrument", "unknown")
        instruments[instr] = instruments.get(instr, 0) + 1

    return {
        "total_runs": len(records),
        "unique_instruments": len(instruments),
        "instruments": instruments,
    }


def _display_results(records: list[dict[str, Any]], verbose: bool = False) -> None:
    """Print records and stats to stdout."""
    if not records:
        print("No MAS run records found.")
        return

    stats = _compute_stats(records)
    print(f"MAS Run Analysis — {stats['total_runs']} record(s) found")
    print(f"  Unique instruments: {stats['unique_instruments']}")
    for instr, count in stats["instruments"].items():
        print(f"    {instr}: {count} run(s)")
    print()

    # Print individual records
    for i, rec in enumerate(records, 1):
        print(f"  {i}. [{rec['id']}] {rec['timestamp']}")
        print(f"       instrument: {rec['instrument']}")
        if verbose:
            print(f"       tags: {rec['tags']}")
    print()

    # Summary line
    if stats["total_runs"] > 0:
        success = sum(
            1 for r in records if r.get("tags", {}).get("status") == "completed"
        )
        failed = sum(
            1 for r in records if r.get("tags", {}).get("status") == "failed"
        )
        if success or failed:
            print(f"  Completed: {success}  |  Failed: {failed}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="analyze_mas",
        description="Analyze past MAS experiment runs from the Experiment Registry",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=10,
        help="Number of recent records to fetch",
    )
    parser.add_argument(
        "--instrument",
        type=str,
        default=None,
        help="Filter by instrument symbol",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed record information",
    )

    args = parser.parse_args()

    records = _fetch_recent(limit=args.last, instrument=args.instrument)
    _display_results(records, verbose=args.verbose)
    sys.exit(0)


if __name__ == "__main__":
    main()

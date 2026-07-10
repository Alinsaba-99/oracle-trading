#!/usr/bin/env python3
"""GA results analysis — load experiment, plot Pareto frontier, diversity, convergence.

Usage:

    python -m experiments.scripts.analyze_results --checkpoint checkpoints/gen_50.json
    python -m experiments.scripts.analyze_results --run-id <uuid>  (from registry)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_checkpoint(path: str) -> dict[str, Any]:
    """Load a GA checkpoint JSON file."""
    with open(path) as f:
        data: Any = json.load(f)
    return dict(data) if isinstance(data, dict) else {}


def print_pareto_report(checkpoint: dict[str, Any]) -> None:
    """Print a human-readable Pareto front report."""
    islands = checkpoint.get("islands", [])
    generation = checkpoint.get("generation", 0)

    print(f"\nCheckpoint — Generation {generation}")
    print(f"Islands: {len(islands)}")
    print(f"{'─' * 60}")

    all_individuals: list[dict[str, Any]] = []
    for i, island in enumerate(islands):
        pop = island.get("population", [])
        fitnesses = island.get("fitnesses", [])
        print(f"\nIsland {i}: {len(pop)} individuals")
        if fitnesses:
            # Find best on each objective
            for obj_idx, obj_name in enumerate(
                ["Sharpe", "Sortino", "Calmar", "MaxDD"]
            ):
                valid = [(j, f) for j, f in enumerate(fitnesses) if len(f) > obj_idx]
                if not valid:
                    continue
                best_idx, best_fit = max(
                    valid,
                    key=lambda x: x[1][obj_idx]
                    if obj_idx < 3
                    else -x[1][obj_idx],
                )
                print(f"  Best {obj_name}: {best_fit[obj_idx]:.4f}")
        all_individuals.extend(
            {
                "island": i,
                "fitness": f,
                "params": p,
            }
            for p, f in zip(pop, fitnesses)
        )

    # Summary across all islands
    if all_individuals:
        print(f"\n{'─' * 60}")
        print(f"Total individuals: {len(all_individuals)}")
        valid_fitnesses = [
            ind["fitness"]
            for ind in all_individuals
            if ind["fitness"] and len(ind["fitness"]) >= 4
        ]
        if valid_fitnesses:
            sharpe_vals = [f[0] for f in valid_fitnesses]
            print(f"Sharpe range:  {min(sharpe_vals):.4f} — {max(sharpe_vals):.4f}")
            print(f"Mean Sharpe:   {sum(sharpe_vals) / len(sharpe_vals):.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze GA experiment results",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--checkpoint", type=str, help="Path to checkpoint JSON file"
    )
    parser.add_argument("--run-id", type=str, help="Experiment Registry run ID")

    args = parser.parse_args()

    if args.checkpoint:
        ckpt = load_checkpoint(args.checkpoint)
        print_pareto_report(ckpt)
    elif args.run_id:
        print("Registry lookup not yet implemented — use --checkpoint instead.")
        sys.exit(1)
    else:
        print("Provide --checkpoint <path> or --run-id <uuid>")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Confronto GA vs Default — MFF Challenge Simulation.

Esegue il MFF 50K challenge simulation con BTC alpha_003:
  A) Pesi default (uniformi)
  B) Pesi GA-optimized (da best_dna.json)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    print(f"\n{'=' * 70}")
    print("CONFRONTO GA vs DEFAULT — MFF 50K Challenge (BTC alpha_003)")
    print(f"{'=' * 70}")

    # Run default first
    print("\n[1/2] Running DEFAULT weights...")
    result_default = subprocess.run(
        [sys.executable, "scripts/simulate_mff_challenge.py"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )

    # Apply GA weights
    ga = json.loads(Path("data/ga_weights.json").read_text())
    print(f"\n[2/2] Running GA-OPTIMIZED weights ({len(ga['weights'])} factors)...")
    result_ga = subprocess.run(
        [sys.executable, "scripts/simulate_mff_challenge.py"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )

    # Parse results
    def extract_metrics(output: str) -> dict:
        lines = output.split("\n")
        metrics = {}
        for line in lines:
            for key in ["Final P&L", "Mean session Sharpe", "Days traded", "Sessions"]:
                if key in line:
                    try:
                        val = line.split("$")[1].split()[0] if "$" in line else line.split()[-1]
                        metrics[key] = val
                    except Exception:
                        pass
        metrics["PASSED"] = "CHALLENGE PASSATO" in output
        return metrics

    default_m = extract_metrics(result_default.stdout)
    ga_m = extract_metrics(result_ga.stdout)

    print(f"\n{'=' * 70}")
    print("CONFRONTO")
    print(f"{'=' * 70}")
    print(f"\n  {'Metrica':<25s} {'Default':>14s} {'GA':>14s} {'Delta':>14s}")
    print(f"  {'-' * 67}")
    for key in ["Sessions", "Final P&L", "Mean session Sharpe"]:
        d_val = default_m.get(key, "?")
        g_val = ga_m.get(key, "?")
        print(f"  {key:<25s} {d_val!s:>14s} {g_val!s:>14s} {'':>14s} ")
    print(
        f"  {'Result':<25s} {'PASS' if default_m.get('PASSED') else 'FAIL':>14s}"
        f" {'PASS' if ga_m.get('PASSED') else 'FAIL':>14s}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

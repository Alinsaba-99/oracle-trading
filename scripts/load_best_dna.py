#!/usr/bin/env python3
"""Load best DNA from GA evolution and apply to AdaptiveEnsemble.

Usage::
    # Apply best DNA from latest GA evolution run
    uv run --frozen python scripts/load_best_dna.py

    # Apply a specific DNA file
    # uv run --frozen python scripts/load_best_dna.py  # --dna <path>
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.strategy.adaptive_ensemble import AdaptiveEnsemble


def find_latest_dna() -> str | None:
    files = sorted(glob.glob("logs/ga_evolution/best_dna_*.json"))
    return files[-1] if files else None


def load_dna(path: str) -> dict[str, float]:
    data = json.loads(Path(path).read_text())
    # Convert from array of weights + factor names to dict
    best = data.get("best", {})
    weights_list = best.get("weights", [])
    top_factors = best.get("top_factors", [])

    # Best approach: factor_weights from the full run_ga script
    # If we have the full weights array, build from it
    if "history" in data and len(weights_list) > 0:
        # The run_ga_evolution.py saves weights
        # We need the factor names that were used
        factor_names = [
            "ema_trend",
            "rsi_rev",
            "donchian_breakout",
            "bband_rev",
            "roc_momentum",
            "zscore_rev",
            "keltner_rev",
            "adx_trend",
            "macd_trend",
            "volume_breakout",
            "alpha_003",
            "alpha_020",
            "alpha_044",
            "alpha_050",
            "alpha_063",
        ]
        result = {}
        for name, w in zip(factor_names, weights_list, strict=False):
            result[name] = w
        return result

    # Fallback: build from top factors only (uniform weights for top, zero for rest)
    if top_factors:
        result = {name: 1.0 / len(top_factors) for name in top_factors}
        return result

    return {}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dna", help="Path to DNA JSON file")
    parser.add_argument("--asset", default="ES")
    parser.add_argument("--tf", default="1d")
    args = parser.parse_args()

    if args.dna:
        dna_path = args.dna
    else:
        dna_path = find_latest_dna()
        if not dna_path:
            print("❌ Nessun DNA trovato in logs/ga_evolution/. Esegui prima run_ga_evolution.py")
            return 1
        print(f"  Usando DNA: {dna_path}")

    weights = load_dna(dna_path)
    if not weights:
        print("❌ Nessun peso trovato nel DNA file")
        return 1

    print(f"  Applicando pesi GA: {weights}")

    # Create ensemble and set weights
    ensemble = AdaptiveEnsemble(args.asset, args.tf)
    ensemble.set_factor_weights(weights)
    info = ensemble.get_info()
    print(f"  Ensemble info: weights={info.weights}")

    # Save weights for paper runner consumption
    out = Path("data/ga_weights.json")
    out.write_text(json.dumps({"weights": weights, "source": dna_path}, indent=2))
    print(f"  Pesi salvati in {out}")
    print("  ✅ GA weights applicati. Usare --weights data/ga_weights.json nelle paper session.")

    return 0


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))

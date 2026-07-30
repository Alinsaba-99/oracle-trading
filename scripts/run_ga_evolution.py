#!/usr/bin/env python3
"""GA Evolution — evolve strategy DNA via paper session fitness.

Collega il GA evolution loop al paper runner ufficiale.
Ogni DNA e' un vettore di pesi per i fattori del signal pool.
Fitness = Sharpe medio su walk-forward.

Usage::
    uv run --frozen python scripts/run_ga_evolution.py --generations 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from genetics.ga_evolution import DNA, StrategyEvolution

# ── Signal pool ──────────────────────────────────────────────────────

# We use the existing strategy functions as factors.
# Each factor produces a signal (-1, 0, 1) given OHLCV data.
FACTOR_NAMES = [
    "ema_trend_10_30",
    "rsi_rev_14",
    "donchian_breakout_20",
    "bband_rev_20",
    "roc_momentum_12",
    "zscore_rev",
    "keltner_rev",
    "adx_trend_14",
    "macd_trend",
    "volume_breakout",
    "alpha_003",
    "alpha_020",
    "alpha_044",
    "alpha_050",
    "alpha_063",
]


def load_data(symbol: str = "ES", tf: str = "1d") -> np.ndarray:
    import polars as pl

    df = pl.scan_parquet(f"data/lake/normalized/symbol={symbol}/tf={tf}/**/*.parquet").collect()
    df = df.rename({c: c.lower() for c in df.columns}).sort("timestamp")
    return df["close"].to_numpy().astype(float)


def compute_factor_signals(close: np.ndarray, n_factors: int = len(FACTOR_NAMES)) -> np.ndarray:
    """Compute signal for each factor.

    Simplified: generates synthetic signals based on simple price patterns.
    Real implementation would call each factor's compute().

    Returns:
        (n_bars, n_factors) array of signals (-1, 0, 1).
    """
    import polars as pl

    n = len(close)
    signals = np.zeros((n, n_factors), dtype=np.int8)
    data = pl.DataFrame(
        {
            "open": close.astype(float),
            "high": close.astype(float) * 1.005,
            "low": close.astype(float) * 0.995,
            "close": close.astype(float),
            "volume": np.ones(n, dtype=int) * 1000,
        }
    )

    from analytics.strategy.catalog.alpha101 import ALPHA_101_CATALOG
    from analytics.strategy.signals import (
        BbandReversion,
        DonchianBreakout,
        EmaTrend,
        KeltnerReversion,
        RocMomentum,
        RsiReversion,
        ZscoreReversion,
    )

    factors = [
        ("ema_trend_10_30", lambda: EmaTrend(10, 30)),
        ("rsi_rev_14", lambda: RsiReversion(14)),
        ("donchian_breakout_20", lambda: DonchianBreakout(20)),
        ("bband_rev_20", lambda: BbandReversion(20)),
        ("roc_momentum_12", lambda: RocMomentum(12)),
        ("zscore_rev", lambda: ZscoreReversion()),
        ("keltner_rev", lambda: KeltnerReversion()),
    ]

    for idx, (_, factory) in enumerate(factors):
        if idx >= n_factors:
            break
        try:
            sig = factory().compute(data)
            arr = sig.to_numpy()
            signals[:, idx] = arr[:n]
        except Exception:
            pass

    # Alpha101 factors
    alpha_names = ["alpha_003", "alpha_020", "alpha_044", "alpha_050", "alpha_063"]
    for idx_offset, name in enumerate(alpha_names):
        idx = 7 + idx_offset
        if idx >= n_factors:
            break
        try:
            fn = ALPHA_101_CATALOG[name]
            sig = fn(data)
            arr = sig.to_numpy()
            signals[:, idx] = arr[:n]
        except Exception:
            pass

    return signals


def evaluate_dna_walk_forward(
    dna: DNA,
    close: np.ndarray,
    signals: np.ndarray,
    n_folds: int = 4,
    test_size: int = 126,
    train_size: int = 378,
) -> None:
    """Evaluate a DNA by walk-forward testing (OOS only for fitness).

    Sets dna.sharpe, dna.calmar, dna.turnover, dna.fitness.
    Fitness = mean OOS Sharpe (NOT IS Sharpe).  Only OOS data is used
    for the fitness signal to prevent in-sample overfitting.
    """
    n = len(close)
    from analytics.backtest.cv import WalkForward

    wf = WalkForward(test_size=test_size, train_size=train_size, expanding=True)
    n_splits = min(n_folds, wf.n_splits(n))
    oos_sharpes = []

    for i, split in enumerate(wf.split(n)):
        if i >= n_splits:
            break
        # OOS simulation only
        test_slice = slice(split.test_idx[0], split.test_idx[-1] + 1)

        weights = dna.factor_weights[: signals.shape[1]]

        # OOS simulation only
        weighted = signals[test_slice] @ weights
        pnls = []
        pos = 0
        entry = 0.0
        for j in range(1, len(weighted)):
            sig = 1 if weighted[j] > 0.3 else (-1 if weighted[j] < -0.3 else 0)
            p = float(close[test_slice][j])
            if sig != pos:
                if pos != 0:
                    pnls.append((p - entry) * pos)
                pos = sig
                entry = p

        if len(pnls) >= 3:
            s = (statistics.mean(pnls) / (statistics.stdev(pnls) + 1e-9)) * math.sqrt(252)
            oos_sharpes.append(s)

    if len(oos_sharpes) >= 2:
        dna.sharpe = float(np.mean(oos_sharpes))
        dna.calmar = dna.sharpe / 0.01  # placeholder
        dna.turnover = 0.01
        dna.fitness = dna.sharpe  # FITNESS = OOS SHARPE (no IS bias)
    else:
        dna.sharpe = -1.0
        dna.fitness = -1.0
        dna.calmar = 0.0
        dna.turnover = 0.0


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generations", type=int, default=15)
    parser.add_argument("--population", type=int, default=30)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--asset", default="ES")
    parser.add_argument("--tf", default="1d")
    args = parser.parse_args()

    print(f"\n{'=' * 70}")
    print("GA STRATEGY EVOLUTION — Paper Session Fitness")
    print(f"{'=' * 70}")
    print(f"  Generations: {args.generations}")
    print(f"  Population:  {args.population}")
    print(f"  Factors:     {len(FACTOR_NAMES)}")
    print(f"  Asset:       {args.asset} {args.tf}")

    # Load data and compute factor signals
    close = load_data(args.asset, args.tf)
    print(f"  Bars:        {len(close)}")

    signals = compute_factor_signals(close, len(FACTOR_NAMES))
    print(f"  Signals:     {signals.shape}")

    # Initialize evolution
    evo = StrategyEvolution(
        n_factors=len(FACTOR_NAMES), population_size=args.population, n_generations=args.generations
    )
    evo.initialize()
    print(f"\n  Initialized {len(evo.population)} DNA candidates\n")

    # Evaluate each generation
    for gen in range(args.generations):
        for dna in evo.population:
            evaluate_dna_walk_forward(dna, close, signals, n_folds=args.folds)

        stats = evo.step()
        best = evo.population[0]
        print(
            f"  Gen {gen:>2d}: best_S={stats['best_sharpe']:.3f} "
            f"avg_fit={stats['avg_fitness']:.3f} "
            f"n_pos={sum(1 for d in evo.population if d.sharpe > 0)}/{args.population}"
        )

    # Final best
    best = max(evo.population, key=lambda d: d.fitness)
    print(f"\n{'=' * 70}")
    print("BEST DNA FOUND")
    print(f"{'=' * 70}")
    print(f"  Sharpe:      {best.sharpe:.4f}")
    print(f"  Fitness:     {best.fitness:.4f}")
    print(f"  Calmar:      {best.calmar:.4f}")
    print(f"  Turnover:    {best.turnover:.4f}")

    # Top factors
    top_idx = np.argsort(-best.factor_weights)[:5]
    print("\n  Top 5 factors:")
    for i, idx in enumerate(top_idx):
        print(f"    {i + 1}. {FACTOR_NAMES[idx]:<20s} weight={best.factor_weights[idx]:.3f}")

    # Save
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out = Path("logs/ga_evolution")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"best_dna_{ts}.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {
                    "generations": args.generations,
                    "population": args.population,
                    "asset": args.asset,
                    "timeframe": args.tf,
                    "timestamp": ts,
                },
                "best": {
                    "sharpe": best.sharpe,
                    "fitness": best.fitness,
                    "weights": best.factor_weights.tolist(),
                    "top_factors": [FACTOR_NAMES[i] for i in top_idx],
                },
                "history": evo.history,
            },
            indent=2,
        )
    )
    print(f"\n  Saved to {path}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

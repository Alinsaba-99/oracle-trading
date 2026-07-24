#!/usr/bin/env python3
"""GA experiment runner — CLI for running the genetic engine with checkpoint/restart.

Usage:

    python -m experiments.scripts.run_ga \\
        --symbol SPY \\
        --from 2015-01-01 --to 2020-12-31 \\
        --pop-size 50 --generations 20 --islands 2 \\
        --seed 42

    python -m experiments.scripts.run_ga --resume checkpoints/gen_10.json

Flags:

    --config PATH        JSON/YAML config file (overridden by CLI flags)
    --symbol SYM         Trading symbol (default: SPY)
    --from DATE          Start date (default: 2015-01-01)
    --to DATE            End date (default: 2020-12-31)
    --pop-size N         Population size (default: 100)
    --generations N      Number of generations (default: 50)
    --islands N          Number of islands (default: 4)
    --seed N             Random seed (default: 42)
    --resume PATH        Resume from checkpoint file
    --checkpoint-interval N  Save checkpoint every N gens (default: 5)
    --n-jobs N           Parallel worker processes (default: CPU count)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import yfinance as yf

from analytics.backtest.config import BacktestConfig
from genetics.config import GAConfig, GenomeConfig, WalkForwardConfig
from genetics.engine import GeneticEngine
from genetics.genome.parameters import CategoricalParameter, ContinuousParameter, IntParameter

logger = logging.getLogger(__name__)

# ── default parameter definitions ────────────────────────────────────

_DEFAULT_PARAMS: list[ContinuousParameter | IntParameter | CategoricalParameter] = [
    # Momentum
    ContinuousParameter("momentum_weight", low=0.0, high=5.0),
    ContinuousParameter("momentum_decay", low=0.5, high=1.0),
    IntParameter("momentum_lookback", low=5, high=120, init_range=(10, 60)),
    # Mean-reversion
    ContinuousParameter("mean_rev_weight", low=0.0, high=5.0),
    IntParameter("rsi_period", low=5, high=50, init_range=(10, 20)),
    IntParameter("rsi_oversold", low=15, high=45, init_range=(25, 35)),
    IntParameter("rsi_overbought", low=55, high=85, init_range=(65, 75)),
    # Volatility
    ContinuousParameter("vol_weight", low=0.0, high=5.0),
    IntParameter("vol_window", low=10, high=100, init_range=(15, 30)),
    # Correlation
    ContinuousParameter("corr_weight", low=0.0, high=5.0),
    # Volume
    ContinuousParameter("volume_weight", low=0.0, high=3.0),
    # Position sizing
    ContinuousParameter("position_size", low=0.01, high=1.0),
    # Entry/exit thresholds
    ContinuousParameter("entry_threshold", low=0.0, high=2.0),
    ContinuousParameter("exit_threshold", low=-0.5, high=0.5),
    # Stop loss / take profit
    ContinuousParameter("stop_loss_pct", low=0.0, high=0.1),
    ContinuousParameter("take_profit_pct", low=0.0, high=0.2),
    # Category switches
    CategoricalParameter("entry_logic", categories=["trend", "mean_rev", "breakout", "hybrid"]),
    CategoricalParameter("exit_logic", categories=["trailing_stop", "fixed_target", "time_stop"]),
]


def _fetch_data(symbol: str, start: str, end: str) -> pl.DataFrame:
    """Fetch OHLCV data from Yahoo Finance."""
    logger.info("Fetching %s from %s to %s ...", symbol, start, end)
    t = yf.Ticker(symbol)
    hist = t.history(start=start, end=end)
    df = pl.DataFrame(
        {
            "timestamp": [
                datetime.strptime(str(d)[:10], "%Y-%m-%d").replace(tzinfo=UTC) for d in hist.index
            ],
            "open": hist["Open"].values,
            "high": hist["High"].values,
            "low": hist["Low"].values,
            "close": hist["Close"].values,
            "volume": hist["Volume"].values,
        }
    )
    logger.info("Fetched %d rows", len(df))
    return df


def _build_config(args: argparse.Namespace) -> GAConfig:
    """Build GAConfig from CLI args."""
    param_defs = _DEFAULT_PARAMS
    genome_config = GenomeConfig(n_params=len(param_defs), param_defs=param_defs)

    return GAConfig(
        genome_config=genome_config,
        pop_size=args.pop_size,
        generations=args.generations,
        n_islands=args.islands,
        seed=args.seed,
        checkpoint_interval=args.checkpoint_interval,
        resume_from=args.resume,
        n_jobs=args.n_jobs,
    )


async def _run(args: argparse.Namespace) -> int:
    """Execute the GA run."""
    config = _build_config(args)
    data = _fetch_data(args.symbol, args.start, args.end)

    backtest_config = BacktestConfig()
    walk_config = WalkForwardConfig(n_splits=5, purge_window=5, embargo=10)

    engine = GeneticEngine(config)
    # Attempt restore if --resume
    if args.resume and Path(args.resume).exists():
        logger.info("Resuming from checkpoint: %s", args.resume)
        engine = GeneticEngine.restore(args.resume, config.genome_config)
        # Update config with CLI overrides
        engine.config.resume_from = args.resume
        engine.config.generations = config.generations

    logger.info(
        "Starting GA run: pop=%d, gens=%d, islands=%d, seed=%d",
        config.pop_size,
        config.generations,
        config.n_islands,
        config.seed,
    )

    result = await engine.run(
        data=data,
        backtest_config=backtest_config,
        walk_forward_config=walk_config,
        registry=None,  # registry logging not yet wired
    )

    # Print summary
    print(f"\n{'=' * 60}")
    print("  GA Run Complete")
    print(f"  Generations: {config.generations}")
    print(f"  Wall time:   {result.timing:.1f}s")
    print(f"  Pareto size: {len(result.pareto_front)}")
    print(f"  Hall of Fame:{len(result.hall_of_fame)}")
    print(f"{'=' * 60}\n")

    if result.pareto_front:
        print("Top Pareto-optimal individuals:")
        for i, ind in enumerate(result.pareto_front[:5]):
            fit = ind.fitness.values if hasattr(ind, "fitness") else "?"
            print(f"  [{i}] fitness={fit}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GA Evolution Experiment Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", type=str, help="JSON/YAML config file")
    parser.add_argument("--symbol", type=str, default="SPY", help="Trading symbol")
    parser.add_argument("--from", dest="start", default="2015-01-01", help="Start date")
    parser.add_argument("--to", dest="end", default="2020-12-31", help="End date")
    parser.add_argument("--pop-size", type=int, default=100, help="Population size")
    parser.add_argument("--generations", type=int, default=50, help="Number of generations")
    parser.add_argument("--islands", type=int, default=4, help="Number of islands")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--resume", type=str, help="Resume from checkpoint path")
    parser.add_argument("--checkpoint-interval", type=int, default=5, help="Checkpoint interval")
    parser.add_argument("--n-jobs", type=int, default=None, help="Parallel workers")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()

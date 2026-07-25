#!/usr/bin/env python3
"""Rolling challenge simulation — realistic prop-firm pass rate estimation.

Simulates launching a new Topstep TC 50K challenge every N trading days over
the full historical dataset, running each strategy on a window matching the
challenge duration (typically 30-90 trading days). Reports the pass rate,
mean P&L, and drawdown distribution.

Usage:
    uv run --frozen python scripts/run_rolling_challenge.py
    uv run --frozen python scripts/run_rolling_challenge.py --strategy donchian_breakout_20
    uv run --frozen python scripts/run_rolling_challenge.py --days 60 --strategy ema_10_30
    uv run --frozen python scripts/run_rolling_challenge.py --all --days 60
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import polars as pl

from analytics.backtest.challenge import ChallengeSimulator
from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines.vectorized import VectorizedEngine
from analytics.strategy.signals import (
    BbandReversion,
    DonchianBreakout,
    EmaTrend,
    RocMomentum,
    RsiReversion,
    TrendFilteredBreakout,
    ZscoreReversion,
)
from policy.prop_firm.fixtures import TOPSTEP_TC_50K


# ── data ─────────────────────────────────────────────────────────────────────
def load_es_data() -> pl.DataFrame:
    """Load ES daily data with normalised lowercase column names."""
    raw = pl.read_parquet("data/ohlcv/ES_1d.parquet")
    rename = {}
    for col in raw.columns:
        lower = col.strip().lower()
        if lower == "date":
            rename[col] = "timestamp"
        elif lower in ("open", "high", "low", "close", "volume"):
            rename[col] = lower
    df = raw.rename(rename).sort("timestamp")
    if df["timestamp"].dtype != pl.Datetime:
        df = df.with_columns(df["timestamp"].cast(pl.Datetime))
    return df


# ── strategy registry ────────────────────────────────────────────────────────
STRATEGIES: dict[str, type] = {
    "ema_trend_20_50": lambda: EmaTrend(fast=20, slow=50),
    "ema_trend_50_200": lambda: EmaTrend(fast=50, slow=200),
    "ema_10_30": lambda: EmaTrend(fast=10, slow=30),
    "rsi_reversion_14": lambda: RsiReversion(period=14, oversold=30.0, exit_level=55.0),
    "rsi_7_25_50": lambda: RsiReversion(period=7, oversold=25.0, exit_level=50.0),
    "bollinger_20": lambda: BbandReversion(period=20, std=2.0),
    "donchian_breakout_20": lambda: DonchianBreakout(period=20),
    "donchian_breakout_30": lambda: DonchianBreakout(period=30),
    "trend_filtered_breakout": lambda: TrendFilteredBreakout(period=20, ma_period=200),
    "roc_momentum_12": lambda: RocMomentum(period=12),
    "zscore_reversion_20": lambda: ZscoreReversion(period=20, entry_z=2.0),
}

CORE = [
    "donchian_breakout_20",
    "trend_filtered_breakout",
    "ema_10_30",
    "rsi_7_25_50",
    "bollinger_20",
    "zscore_reversion_20",
]


# ── rolling challenge simulator ──────────────────────────────────────────────
def rolling_challenge_pass_rate(
    data: pl.DataFrame,
    strategy_name: str,
    strategy_cls: type,
    window_days: int = 60,
    step: int = 20,
    initial_capital: float = 50_000.0,
    warmup: int = 50,  # bars for indicator warm-up
) -> dict:
    """Simulate launching a challenge every *step* bars over the history.

    Returns pass rate, mean P&L, mean max DD, and the detailed outcome list.
    """
    cfg = BacktestConfig(
        initial_capital=Decimal(str(initial_capital)), slippage_bps=3.0, commission_pct=0.0005
    )
    engine = VectorizedEngine()

    n = len(data)
    results: list[dict] = []
    failed_daily = 0
    failed_overall = 0
    passed = 0
    total_pnl = 0.0
    max_dds: list[float] = []
    sharpes: list[float] = []

    sim_start = max(warmup, window_days // 2)  # ensure enough warmup data

    for start in range(sim_start, n - window_days, step):
        end = start + window_days
        if end > n:
            break

        window = data[start:end]
        if len(window) < window_days * 0.8:
            continue  # skip truncated windows

        try:
            sig = strategy_cls()
            bt = engine.run(window, sig, cfg)
        except Exception:
            continue

        equity = bt.equity_curve
        if not equity or len(equity) < 5:
            continue

        initial_cap = initial_capital
        sim = ChallengeSimulator(TOPSTEP_TC_50K, initial_cap)

        today = date.today()
        dates = [today - timedelta(days=len(equity) - 1 - i) for i in range(len(equity))]

        result = sim.run(equity, dates)
        pnl = result.final_balance - initial_cap

        if result.passed:
            passed += 1
        elif result.status.value == "failed_daily":
            failed_daily += 1
        elif result.status.value == "failed_overall":
            failed_overall += 1

        total_pnl += pnl
        max_dds.append(result.max_drawdown_pct)
        sharpes.append(bt.sharpe_ratio)

        results.append(
            {
                "start": start,
                "end": end,
                "passed": result.passed,
                "pnl": pnl,
                "max_dd": result.max_drawdown_pct,
                "sharpe": bt.sharpe_ratio,
                "failure_reason": result.failure_reason,
            }
        )

    total = len(results)
    return {
        "strategy": strategy_name,
        "n_windows": total,
        "passed": passed,
        "failed_daily": failed_daily,
        "failed_overall": failed_overall,
        "pass_rate": passed / total * 100 if total > 0 else 0.0,
        "mean_pnl": total_pnl / total if total > 0 else 0.0,
        "mean_max_dd": np.mean(max_dds) if max_dds else 0.0,
        "median_max_dd": np.median(max_dds) if max_dds else 0.0,
        "mean_sharpe": np.mean(sharpes) if sharpes else 0.0,
        "best_sharpe": max(sharpes) if sharpes else 0.0,
        "worst_sharpe": min(sharpes) if sharpes else 0.0,
    }


def run_all(data: pl.DataFrame, window_days: int, step: int) -> None:
    """Run rolling challenge on all core strategies."""
    print("\n  Rolling Challenge Simulation: Topstep TC 50K")
    print(f"  {''}")
    print(f"  Window:      {window_days} trading days (~{window_days * 1.4:.0f} calendar days)")
    print(f"  Step:        {step} trading days")
    print("  Account:     $50,000")
    print("  Target:      $55,000 (+10%)")
    print("  Max Loss:    $2,000 (trailing EOD)")
    print("  Daily Loss:  $1,000")
    print()
    print(
        f"  {'Strategia':>25s}  {'Pass%':>8s}  {'Win':>4s}/{'Tot':>4s}  "
        f"{'P&L Medio':>10s}  {'DD% Med':>8s}  {'Sharpe':>7s}  {'Ragione':>20s}"
    )
    print("  " + "  ".join(f"{'─' * w}" for w in [25, 8, 4, 4, 10, 8, 7, 20]))

    all_results: list[dict] = []
    for name in CORE:
        cls = STRATEGIES.get(name)
        if cls is None:
            continue
        r = rolling_challenge_pass_rate(data, name, cls, window_days=window_days, step=step)
        all_results.append(r)

        # Determine dominant failure reason
        if r["failed_overall"] > r["failed_daily"]:
            reason = "overall_dd"
        elif r["failed_daily"] > 0:
            reason = "daily_loss"
        else:
            reason = "n/a"

        print(
            f"  {r['strategy']:>25s}  {r['pass_rate']:>7.1f}%  "
            f"{r['passed']:>4d}/{r['n_windows']:>4d}  "
            f"${r['mean_pnl']:>+8.2f}  {r['mean_max_dd'] * 100:>7.2f}%  "
            f"{r['mean_sharpe']:>7.3f}  {reason:>20s}"
        )

    print()
    best = max(all_results, key=lambda r: r["pass_rate"])
    print(
        f"  🏆 Migliore: {best['strategy']} — {best['pass_rate']:.1f}% pass rate "
        f"({best['passed']}/{best['n_windows']} windows)"
    )
    print(
        f"     P&L medio: ${best['mean_pnl']:+.2f} | DD medio: {best['mean_max_dd'] * 100:.2f}% | "
        f"Sharpe medio: {best['mean_sharpe']:.3f}"
    )
    print()


def run_single(data: pl.DataFrame, name: str, window_days: int, step: int) -> None:
    """Run rolling challenge on a single strategy with detail."""
    cls = STRATEGIES.get(name)
    if cls is None:
        print(f"❌ Strategy '{name}' not found. Available: {', '.join(STRATEGIES.keys())}")
        return

    r = rolling_challenge_pass_rate(data, name, cls, window_days=window_days, step=step)
    print(f"\n  📊 {name} — Rolling Challenge ({window_days}d window, step {step})")
    print(f"  {'─' * 50}")
    print(f"  Pass rate:      {r['pass_rate']:.1f}% ({r['passed']}/{r['n_windows']})")
    print(f"  Failed (daily): {r['failed_daily']}")
    print(f"  Failed (overall): {r['failed_overall']}")
    print(f"  Mean P&L:       ${r['mean_pnl']:+.2f}")
    print(f"  Mean max DD:    {r['mean_max_dd'] * 100:.2f}%")
    print(f"  Median max DD:  {r['median_max_dd'] * 100:.2f}%")
    print(
        f"  Mean Sharpe:    {r['mean_sharpe']:.3f} (best {r['best_sharpe']:.3f},"
        f" worst {r['worst_sharpe']:.3f})"
    )
    print()


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Rolling prop-firm challenge simulation")
    parser.add_argument("--strategy", type=str, default=None, help="Single strategy to test")
    parser.add_argument("--all", action="store_true", help="Run all core strategies")
    parser.add_argument(
        "--days", type=int, default=60, help="Challenge window in trading days (default: 60)"
    )
    parser.add_argument("--step", type=int, default=20, help="Step between windows (default: 20)")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Oracle — Rolling Prop-Firm Challenge Simulation           ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    data = load_es_data()
    dmin = data["timestamp"].min().strftime("%Y-%m-%d")
    dmax = data["timestamp"].max().strftime("%Y-%m-%d")
    print(f"\n📊 Dati: {len(data)} barre ES daily ({dmin} → {dmax})")

    if len(data) < 200:
        print("❌ Dati insufficienti")
        sys.exit(1)

    if args.strategy:
        run_single(data, args.strategy, args.days, args.step)
    else:
        run_all(data, args.days, args.step)

    # Always show best strategy analysis
    if not args.strategy:
        print("  ⚠️  Nota: il pass rate è calcolato su finestre rolling indipendenti.")
        print("  I risultati out-of-sample reali dipendono dal regime di mercato al")
        print("  momento del challenge. Per una valutazione completa serve:")
        print("  1. Backtest su periodi bear/sideways (non solo bull 2021-2026)")
        print("  2. Paper trading su dati intraday per intraday drawdown")
        print("  3. Walk-forward con finestre multiple")
        print()


if __name__ == "__main__":
    main()

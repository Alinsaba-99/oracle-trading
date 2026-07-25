#!/usr/bin/env python3
"""Comprehensive backtest + walk-forward + prop-firm challenge evaluation.

Usage:
    uv run --frozen python scripts/run_backtest_evaluation.py
    uv run --frozen python scripts/run_backtest_evaluation.py --walk-forward
    uv run --frozen python scripts/run_backtest_evaluation.py --challenge
    uv run --frozen python scripts/run_backtest_evaluation.py --full
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import polars as pl

from analytics.backtest.challenge import ChallengeSimulator
from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines.vectorized import VectorizedEngine
from analytics.backtest.metrics import MetricsCalculator
from analytics.backtest.walk_forward import WalkForwardEngine
from analytics.strategy.signals import (
    DEFAULT_STRATEGIES,
    BbandReversion,
    DonchianBreakout,
    EmaTrend,
    RocMomentum,
    RsiReversion,
    TrendFilteredBreakout,
    ZscoreReversion,
)
from policy.prop_firm.fixtures import TOPSTEP_TC_50K

# ── config ───────────────────────────────────────────────────────────────────
MC = MetricsCalculator()
VERBOSE = True


def log(msg: str) -> None:
    if VERBOSE:
        print(f"  {msg}")


# ── data loading ─────────────────────────────────────────────────────────────
def load_es_data() -> pl.DataFrame:
    """Load ES daily data and normalise column names to lowercase."""
    raw = pl.read_parquet("data/ohlcv/ES_1d.parquet")
    # The data has uppercase columns (Open/High/Low/Close/Volume/Date)
    rename = {}
    for col in raw.columns:
        lower = col.strip().lower()
        if lower == "date":
            rename[col] = "timestamp"
        elif lower in ("open", "high", "low", "close", "volume"):
            rename[col] = lower
    df = raw.rename(rename)
    # Ensure timestamp is datetime
    if df["timestamp"].dtype != pl.Datetime:
        df = df.with_columns(df["timestamp"].cast(pl.Datetime))
    return df.sort("timestamp")


def check_data_quality(df: pl.DataFrame) -> None:
    """Basic data quality checks."""
    n = len(df)
    nulls = df.null_count().row(0) if n > 0 else {}
    if isinstance(nulls, tuple):
        nulls = dict(zip(df.columns, nulls, strict=False))
    print(f"\n  Dati: {n} barre giornaliere ES")
    print(f"  Intervallo: {df['timestamp'].min()} → {df['timestamp'].max()}")
    if n > 0:
        first_close = df["close"][0]
        last_close = df["close"][-1]
        total_return = (last_close - first_close) / first_close * 100
        print(f"  Prezzo: {first_close:.2f} → {last_close:.2f} ({total_return:+.2f}%)")
    if any(v > 0 for v in (nulls.values() if hasattr(nulls, "values") else [])):
        print(f"  ⚠️  Valori nulli: {nulls}")


# ── backtest ─────────────────────────────────────────────────────────────────
def run_single_backtest(
    engine: VectorizedEngine,
    data: pl.DataFrame,
    signal_name: str,
    signal_cls: type,
    params: dict[str, Any] | None = None,
    config: BacktestConfig | None = None,
) -> dict[str, Any]:
    """Run a single backtest and return key metrics."""
    sig = signal_cls(**(params or {}))
    cfg = config or BacktestConfig(
        initial_capital=Decimal("50000"), slippage_bps=3.0, commission_pct=0.0005
    )
    result = engine.run(data, sig, cfg)
    return {
        "strategy": signal_name,
        "total_return": result.total_return,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "calmar_ratio": result.calmar_ratio,
        "max_drawdown": result.max_drawdown,
        "cagr": result.cagr,
        "total_trades": result.total_trades,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "final_equity": result.final_equity,
        "initial_capital": float(result.initial_capital),
    }


def run_sweep(
    data: pl.DataFrame, strategies: dict[str, type], config: BacktestConfig | None = None
) -> list[dict[str, Any]]:
    """Sweep all strategies and return sorted results."""
    engine = VectorizedEngine()
    results: list[dict[str, Any]] = []
    print(f"\n  Eseguendo {len(strategies)} strategie...")
    for name, cls in strategies.items():
        try:
            r = run_single_backtest(engine, data, name, cls, config=config)
            results.append(r)
            log(
                f"  {name:>25s}  Sharpe={r['sharpe_ratio']:.3f}  "
                f"Return={r['total_return'] * 100:+.2f}%  DD={r['max_drawdown'] * 100:.2f}%  "
                f"Trades={r['total_trades']}"
            )
        except Exception as e:
            log(f"  {name:>25s}  ❌ {e}")

    # Sort by Sharpe descending
    results.sort(key=lambda r: r["sharpe_ratio"], reverse=True)
    return results


def print_results_table(results: list[dict[str, Any]], title: str = "Risultati") -> None:
    """Print a formatted results table."""
    print(f"\n  ═══ {title} ═══")
    print(
        f"  {'Strategia':>25s}  {'Sharpe':>8s}  {'Return%':>8s}  "
        f"{'Sortino':>8s}  {'DD%':>8s}  {'WinRate':>8s}  {'Trades':>8s}"
    )
    print(f"  {'─' * 25}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 8}")
    for r in results:
        ret = r["total_return"] * 100
        dd = r["max_drawdown"] * 100
        wr = r["win_rate"] * 100
        print(
            f"  {r['strategy']:>25s}  {r['sharpe_ratio']:>8.3f}  {ret:>+8.2f}%  "
            f"{r['sortino_ratio']:>8.3f}  {dd:>8.2f}%  {wr:>8.1f}%  {r['total_trades']:>8d}"
        )
    print()


# ── walk-forward ─────────────────────────────────────────────────────────────
def run_walk_forward_sweep(
    data: pl.DataFrame, strategies: dict[str, type], n_splits: int = 5, split_method: str = "time"
) -> list[dict[str, Any]]:
    """Run walk-forward on all strategies."""
    config = BacktestConfig(
        initial_capital=Decimal("50000"), slippage_bps=3.0, commission_pct=0.0005
    )
    results: list[dict[str, Any]] = []
    print(f"\n  Walk-Forward ({split_method}, {n_splits} fold) su {len(strategies)} strategie...")

    for name, cls in strategies.items():
        try:
            sig = cls()
            wf = WalkForwardEngine()
            fold_results = wf.run(data, sig, config, n_splits=n_splits, split_method=split_method)
            combined = wf.combined_metrics()
            sharpe_mean = combined.get("sharpe_ratio_mean", 0.0)
            sharpe_std = combined.get("sharpe_ratio_std", 0.0)
            dd_mean = combined.get("max_drawdown_mean", 0.0)
            oos_sharpe = combined.get("oos_sharpe_ratio", None)
            oos_return = combined.get("oos_total_return", None)

            fold_sharpes = [getattr(r, "sharpe_ratio", 0.0) for r in fold_results]
            fold_dds = [getattr(r, "max_drawdown", 0.0) for r in fold_results]

            results.append(
                {
                    "strategy": name,
                    "wf_sharpe_mean": sharpe_mean,
                    "wf_sharpe_std": sharpe_std,
                    "wf_dd_mean": dd_mean,
                    "wf_dd_std": combined.get("max_drawdown_std", 0.0),
                    "wf_return_mean": combined.get("total_return_mean", 0.0),
                    "oos_sharpe": oos_sharpe if oos_sharpe else 0.0,
                    "oos_return": oos_return if oos_return else 0.0,
                    "fold_sharpes": fold_sharpes,
                    "fold_dds": fold_dds,
                    "n_folds": len(fold_results),
                }
            )
            log(
                f"  {name:>25s}  WF-Sharpe={sharpe_mean:>8.3f}±{sharpe_std:.3f}  "
                f"OOS-Sharpe={oos_sharpe or 0:.3f}  DD={dd_mean * 100:.2f}%"
            )
        except Exception as e:
            log(f"  {name:>25s}  ❌ Walk-forward: {e}")

    results.sort(key=lambda r: r.get("oos_sharpe", 0), reverse=True)
    return results


def print_wf_results(results: list[dict[str, Any]]) -> None:
    """Print walk-forward results."""
    print("\n  ═══ Walk-Forward Results ═══")
    header_cols = [
        ("Strategia", 25),
        ("WF-Sharpe", 10),
        ("OOS-Sharpe", 10),
        ("OOS-Ret%", 10),
        ("DD%", 8),
        ("Fold-Stab", 10),
    ]
    header = "  " + "  ".join(f"{k:>{w}s}" for k, w in header_cols)
    print(header)
    print(f"  {'─' * 25}  {'─' * 10}  {'─' * 10}  {'─' * 10}  {'─' * 8}  {'─' * 10}")
    for r in results:
        wf_sharpe = f"{r['wf_sharpe_mean']:.3f}±{r['wf_sharpe_std']:.3f}"
        oos_sharpe = r.get("oos_sharpe", 0.0)
        oos_ret = r.get("oos_return", 0.0) * 100
        dd = r.get("wf_dd_mean", 0.0) * 100
        # Fold stability: min Sharpe across folds (lower = less robust)
        fold_stab = min(r["fold_sharpes"]) if r["fold_sharpes"] else 0
        cols = (r["strategy"], wf_sharpe, oos_sharpe, oos_ret, dd, fold_stab)
        print(
            f"  {cols[0]:>25s}  {cols[1]:>10s}  {cols[2]:>10.3f}"
            f"  {cols[3]:>+10.2f}%  {cols[4]:>8.2f}%  {cols[5]:>10.3f}"
        )
    print()


# ── challenge simulation ─────────────────────────────────────────────────────
def run_challenge_simulation(equity_curve: list[float], title: str = "") -> dict[str, Any]:
    """Simulate a Topstep Trading Combine 50K challenge over an equity curve."""

    initial = TOPSTEP_TC_50K.account_size
    sim = ChallengeSimulator(TOPSTEP_TC_50K, initial)

    # Generate dates aligned with equity curve
    today = date.today()
    dates = [today - timedelta(days=len(equity_curve) - 1 - i) for i in range(len(equity_curve))]

    result = sim.run(equity_curve, dates)
    return {
        "title": title,
        "passed": result.passed,
        "status": result.status.value,
        "initial_balance": result.initial_balance,
        "final_balance": result.final_balance,
        "total_return": result.total_return,
        "max_drawdown_pct": result.max_drawdown_pct,
        "days_elapsed": result.days_elapsed,
        "target_hit": result.target_hit,
        "failure_reason": result.failure_reason,
        "breaches": result.breaches,
    }


def run_challenge_on_strategy(
    data: pl.DataFrame, signal_name: str, signal_cls: type, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run backtest + challenge simulation on a single strategy."""
    cfg = BacktestConfig(
        initial_capital=Decimal(str(TOPSTEP_TC_50K.account_size)),
        slippage_bps=3.0,
        commission_pct=0.0005,
    )
    engine = VectorizedEngine()
    sig = signal_cls(**(params or {}))
    result = engine.run(data, sig, cfg)
    equity = result.equity_curve

    challenge = run_challenge_simulation(equity, title=signal_name)
    challenge.update(
        {
            "bt_sharpe": result.sharpe_ratio,
            "bt_return": result.total_return,
            "bt_dd": result.max_drawdown,
            "bt_trades": result.total_trades,
        }
    )
    return challenge


def print_challenge_results(challenges: list[dict[str, Any]]) -> None:
    """Print challenge simulation results."""
    print("\n  ═══ Prop-Firm Challenge Simulation (Topstep TC 50K) ═══")
    print("  Regole: Profit Target 10% ($5,000), Max Loss $2,000 (trailing EOD), Daily Loss $1,000")
    print()
    print(
        f"  {'Strategia':>25s}  {'Risultato':>12s}  {'Return%':>8s}  {'DD%':>8s}  "
        f"{'Giorni':>6s}  {'Sharpe':>7s}  {'Trades':>7s}"
    )
    print(f"  {'─' * 25}  {'─' * 12}  {'─' * 8}  {'─' * 8}  {'─' * 6}  {'─' * 7}  {'─' * 7}")
    for c in challenges:
        status = "✅ PASS" if c["passed"] else f"❌ FAIL({c['failure_reason'][:30]})"
        ret = c["total_return"] * 100
        dd = c["max_drawdown_pct"] * 100
        print(
            f"  {c['title']:>25s}  {status:>12s}  {ret:>+8.2f}%  {dd:>8.2f}%  "
            f"{c['days_elapsed']:>6d}  {c['bt_sharpe']:>7.3f}  {c['bt_trades']:>7d}"
        )
    print()


# ── strategy configs for sweep ───────────────────────────────────────────────

# Core strategies with v1 default params
CORE_STRATEGIES: dict[str, type] = {
    "ema_trend_20_50": EmaTrend,
    "ema_trend_50_200": lambda: EmaTrend(fast=50, slow=200),
    "rsi_reversion_14": RsiReversion,
    "bollinger_20": BbandReversion,
    "donchian_breakout_20": DonchianBreakout,
    "trend_filtered_breakout": TrendFilteredBreakout,
    "roc_momentum_12": RocMomentum,
    "zscore_reversion_20": ZscoreReversion,
}

# Extended sweep: parameter variations
EXTENDED_STRATEGIES: dict[str, type] = {
    **CORE_STRATEGIES,
    "ema_10_30": lambda: EmaTrend(fast=10, slow=30),
    "ema_20_100": lambda: EmaTrend(fast=20, slow=100),
    "rsi_7_25_50": lambda: RsiReversion(period=7, oversold=25.0, exit_level=50.0),
    "rsi_21_30_55": lambda: RsiReversion(period=21, oversold=30.0, exit_level=55.0),
    "bollinger_10_2": lambda: BbandReversion(period=10, std=2.0),
    "bollinger_30_2.5": lambda: BbandReversion(period=30, std=2.5),
    "donchian_10": lambda: DonchianBreakout(period=10),
    "donchian_30": lambda: DonchianBreakout(period=30),
    "donchian_50": lambda: DonchianBreakout(period=50),
    "roc_5": lambda: RocMomentum(period=5),
    "roc_21": lambda: RocMomentum(period=21),
    "zscore_10_1.5": lambda: ZscoreReversion(period=10, entry_z=1.5),
    "zscore_30_2.5": lambda: ZscoreReversion(period=30, entry_z=2.5),
}


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest + WF + Challenge evaluation")
    parser.add_argument("--walk-forward", action="store_true", help="Run walk-forward validation")
    parser.add_argument("--challenge", action="store_true", help="Run challenge simulation")
    parser.add_argument("--extended", action="store_true", help="Use extended strategy list")
    parser.add_argument("--full", action="store_true", help="Run all analyses")
    parser.add_argument("--n-splits", type=int, default=6, help="Number of WF splits")
    args = parser.parse_args()

    # Determine what to run
    run_wf = args.walk_forward or args.full
    run_ch = args.challenge or args.full
    strategies = EXTENDED_STRATEGIES if (args.extended or args.full) else CORE_STRATEGIES

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Oracle — Backtest + Walk-Forward + Challenge Evaluation   ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # ── Load data ──────────────────────────────────────────────────────
    print("\n📊 Caricamento dati...")
    data = load_es_data()
    check_data_quality(data)

    if len(data) < 100:
        msg = "\n❌ Dati insufficienti (< 100 barre). "
        msg += "Esegui: uv run --frozen python scripts/refresh_data.py"
        print(msg)
        sys.exit(1)

    # Determine regime context
    n_train = int(len(data) * 0.7)
    train = data[:n_train]
    test = data[n_train:]
    train_close = train["close"].to_numpy()
    test_close = test["close"].to_numpy()
    train_trend = "📈 Bull" if train_close[-1] > train_close[0] else "📉 Bear"
    test_trend = "📈 Bull" if test_close[-1] > test_close[0] else "📉 Bear"
    tmin = train["timestamp"].min().strftime("%Y-%m-%d")
    tmax = train["timestamp"].max().strftime("%Y-%m-%d")
    print(f"\n  Regime training set: {train_trend}  ({tmin} → {tmax})")
    emin = test["timestamp"].min().strftime("%Y-%m-%d")
    emax = test["timestamp"].max().strftime("%Y-%m-%d")
    print(f"  Regime test set:     {test_trend}  ({emin} → {emax})")

    # ── 1. Full-sample backtest sweep ──────────────────────────────────
    print("\n" + "─" * 66)
    print("🔬 FASE 1: Backtest completo su tutti i dati")
    print("─" * 66)
    full_results = run_sweep(data, strategies)
    print_results_table(full_results, "Full-Sample Backtest")

    # ── 2. Out-of-sample backtest ──────────────────────────────────────
    print("─" * 66)
    print("🔬 FASE 2: Backtest out-of-sample (ultimo 30%)")
    print("─" * 66)
    oos_results = run_sweep(test, strategies)
    print_results_table(oos_results, "Out-of-Sample Backtest (30% finale)")

    # ── 3. Walk-Forward Validation ─────────────────────────────────────
    if run_wf:
        print("─" * 66)
        print("🔬 FASE 3: Walk-Forward Validation")
        print("─" * 66)
        wf_results = run_walk_forward_sweep(
            data, CORE_STRATEGIES, n_splits=args.n_splits, split_method="time"
        )
        print_wf_results(wf_results)

        # Top candidates by OOS Sharpe
        print("  ── Top 3 strategie per OOS Sharpe ──")
        for r in wf_results[:3]:
            print(
                f"    {r['strategy']:>25s}  OOS Sharpe={r.get('oos_sharpe', 0):.3f}  "
                f"WF Sharpe={r['wf_sharpe_mean']:.3f}±{r['wf_sharpe_std']:.3f}"
            )

        # Second walk-forward with CPCV for comparison
        print("\n  ── CPCV Walk-Forward (splits più severi) ──")
        wf_cpcv = run_walk_forward_sweep(
            data, CORE_STRATEGIES, n_splits=args.n_splits, split_method="cpcv"
        )
        # Only show top 5
        for r in wf_cpcv[:5]:
            s = r["strategy"]
            wm = r["wf_sharpe_mean"]
            ws = r["wf_sharpe_std"]
            oos = r.get("oos_sharpe", 0)
            print(f"    {s:>25s}  CPCV-Sharpe={wm:.3f}±{ws:.3f}  OOS-Sharpe={oos:.3f}")

    # ── 4. Challenge Simulation ────────────────────────────────────────
    if run_ch:
        print("─" * 66)
        print("🔬 FASE 4: Challenge Simulation (Topstep Trading Combine 50K)")
        print("─" * 66)
        print(
            "  Regole: $50K account, target $55K (+10%), "
            "max loss $2K (trailing EOD), daily loss $1K"
        )
        print("  Slippage: 0.3 bps | Commission: 0.05%")

        # Run challenge on top 6 strategies from the sweep
        top_strategies = [
            (r["strategy"], DEFAULT_STRATEGIES.get(r["strategy"]))
            for r in full_results[:6]
            if r["strategy"] in DEFAULT_STRATEGIES
        ]

        challenge_results = []
        for name, cls in top_strategies:
            if cls is None:
                continue
            try:
                c = run_challenge_on_strategy(data, name, cls)
                challenge_results.append(c)
                status = "✅ PASS" if c["passed"] else "❌ FAIL"
                ret = c["total_return"] * 100
                dd = c["max_drawdown_pct"] * 100
                log(
                    f"  {name:>25s}: {status} (Return={ret:+.2f}%, "
                    f"DD={dd:.2f}%, Sharpe={c['bt_sharpe']:.3f})"
                )
            except Exception as e:
                log(f"  {name:>25s}: ❌ {e}")

        print_challenge_results(challenge_results)

        # Also run challenge on EMA 10/30 (most promising for ES trending)
        print("\n  ── Challenge: EMA 10/30 (parametro ottimizzato per trend ES) ──")
        ema30_challenge = run_challenge_on_strategy(
            data, "ema_10_30", EmaTrend, {"fast": 10, "slow": 30}
        )
        status = "✅ PASS" if ema30_challenge["passed"] else "❌ FAIL"
        print(f"    Risultato: {status}")
        ret = ema30_challenge["total_return"] * 100
        dd = ema30_challenge["max_drawdown_pct"] * 100
        print(f"    Return: {ret:+.2f}%, DD: {dd:.2f}%")
        sharpe = ema30_challenge["bt_sharpe"]
        trades = ema30_challenge["bt_trades"]
        print(f"    Sharpe: {sharpe:.3f}, Trades: {trades}")
        print(f"    Final Balance: ${ema30_challenge['final_balance']:,.2f}")
        if ema30_challenge["failure_reason"]:
            print(f"    Failure reason: {ema30_challenge['failure_reason']}")

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "═" * 66)
    print("📋 RIEPILOGO VALUTAZIONE PROP-FIRM")
    print("═" * 66)
    print("""
  Target: Topstep Trading Combine 50K
  Profit Target: +$5,000 (+10%)
  Max Loss: $2,000 (trailing EOD, locked at initial balance)
  Max Daily Loss: $1,000

  Condizioni per passare:
  1. La strategia deve generare un equity curve che raggiunga $55,000
  2. Senza mai violare il trailing drawdown di $2,000
  3. Senza mai perdere più di $1,000 in un singolo giorno

  Metriche chiave necessarie:
  • Sharpe Ratio > 1.0 (out-of-sample)
  • Max Drawdown < 4% (altrimenti il trailing stop viene violato)
  • Profit Factor > 1.5
  • Consistenza tra fold (walk-forward stabile)
""")

    # Top recommendations
    if full_results:
        top = full_results[0]
        print(f"  🏆 Miglior strategia (full-sample): {top['strategy']}")
        s, r_, dd_ = top["sharpe_ratio"], top["total_return"] * 100, top["max_drawdown"] * 100
        print(f"     Sharpe={s:.3f}, Return={r_:+.2f}%, DD={dd_:.2f}%")

    if run_wf and wf_results:
        top_wf = wf_results[0]
        print(f"\n  🏆 Miglior strategia (walk-forward): {top_wf['strategy']}")
        wf_s = f"{top_wf['wf_sharpe_mean']:.3f}±{top_wf['wf_sharpe_std']:.3f}"
        oos_s = top_wf.get("oos_sharpe", 0)
        print(f"     WF-Sharpe={wf_s}, OOS-Sharpe={oos_s:.3f}")

    print("""
  ⚠️  Avvertenze:
  • Backtest su ES continuo (proxy per MES). I risultati reali possono differire.
  • Slippage e commissioni sono stimati (3 bps / 0.05%).
  • Il challenge simulator NON considera intraday drawdown (usa close-to-close).
  • Nessuna garanzia che i risultati passati si ripetano in live/funded.
  • Per procedere a paper/shadow serve G6 approvato.
""")


if __name__ == "__main__":
    main()

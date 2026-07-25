#!/usr/bin/env python3
"""Test the Lorentzian KNN classifier on BTC 1h data and challenge simulation.

Usage:
    uv run --frozen python scripts/run_lorentzian_test.py
    uv run --frozen python scripts/run_lorentzian_test.py --instrument BTC
    uv run --frozen python scripts/run_lorentzian_test.py --fast
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
from analytics.strategy.lorentzian import LorentzianKNN
from analytics.strategy.risk_sized import sized_backtest
from analytics.strategy.signals import BbandReversion, DonchianBreakout, EmaTrend, RsiReversion
from policy.prop_firm.fixtures import TOPSTEP_TC_50K


# ── data ─────────────────────────────────────────────────────────────────────
def load_intraday(instrument: str, tf: str = "1h") -> pl.DataFrame:
    """Load intraday parquet data."""
    path = f"data/intraday/{instrument}_USD_{tf}.parquet"
    df = pl.read_parquet(path)
    rename = {}
    for col in df.columns:
        lower = col.strip().lower()
        if lower in ("open", "high", "low", "close", "volume"):
            rename[col] = lower
    if rename:
        df = df.rename(rename)
    return df.sort("timestamp")


def load_es_daily() -> pl.DataFrame:
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


# ── single backtest ──────────────────────────────────────────────────────────
def run_bt(data: pl.DataFrame, signal_fn, config=None):
    """Run a single backtest and return result + equity."""
    cfg = config or BacktestConfig(
        initial_capital=Decimal(str(TOPSTEP_TC_50K.account_size)),
        slippage_bps=3.0,
        commission_pct=0.0005,
    )
    engine = VectorizedEngine()
    result = engine.run(data, signal_fn, cfg)
    return result


def run_sized(data, signal_fn):
    cfg = BacktestConfig(
        initial_capital=Decimal(str(TOPSTEP_TC_50K.account_size)),
        slippage_bps=3.0,
        commission_pct=0.0005,
    )
    return sized_backtest(data, signal_fn, settings=cfg)


# ── challenge simulation ─────────────────────────────────────────────────────
def sim_challenge(equity: list[float]) -> dict:
    sim = ChallengeSimulator(TOPSTEP_TC_50K, float(TOPSTEP_TC_50K.account_size))
    today = date.today()
    dates = [today - timedelta(days=len(equity) - 1 - i) for i in range(len(equity))]
    result = sim.run(equity, dates)
    return {
        "passed": result.passed,
        "status": result.status.value,
        "pnl": result.final_balance - float(TOPSTEP_TC_50K.account_size),
        "dd": result.max_drawdown_pct,
    }


# ── rolling challenge ────────────────────────────────────────────────────────
def rolling_pass_rate(
    data: pl.DataFrame, signal_cls, name: str, window: int = 60, step: int = 20, warmup: int = 100
) -> dict:
    n = len(data)
    results = []
    initial = float(TOPSTEP_TC_50K.account_size)

    cfg = BacktestConfig(
        initial_capital=Decimal(str(initial)), slippage_bps=3.0, commission_pct=0.0005
    )

    for start in range(warmup, n - window, step):
        end = start + window
        if end > n:
            break
        window_data = data[start:end]
        if len(window_data) < window * 0.8:
            continue
        try:
            bt_data = window_data
            sig_inst = signal_cls() if isinstance(signal_cls, type) else signal_cls
            engine = VectorizedEngine()
            bt = engine.run(bt_data, sig_inst, cfg)
            equity = bt.equity_curve
            if not equity or len(equity) < 5:
                continue
            ch = sim_challenge(equity)
            results.append(ch)
        except Exception:
            continue

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    return {
        "strategy": name,
        "n_windows": total,
        "passed": passed,
        "pass_rate": passed / total * 100 if total else 0,
        "mean_pnl": np.mean([r["pnl"] for r in results]) if results else 0,
        "mean_dd": np.mean([r["dd"] for r in results]) if results else 0,
    }


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Lorentzian KNN scalping test")
    parser.add_argument("--instrument", choices=["BTC", "ETH", "ES"], default="BTC")
    parser.add_argument("--tf", type=str, default="1h")
    parser.add_argument("--fast", action="store_true", help="Skip challenge simulation")
    parser.add_argument("--sized", action="store_true", help="Use risk-sized backtest")
    parser.add_argument("--window", type=int, default=120, help="Challenge window (hours)")
    parser.add_argument("--step", type=int, default=40)
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Oracle — Lorentzian KNN Scalphawk Evaluation              ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Load data
    if args.instrument == "ES":
        data = load_es_daily()
        print(f"\n📊 ES daily: {len(data)} barre")
    else:
        data = load_intraday(args.instrument, args.tf)
        print(f"\n📊 {args.instrument}/USD {args.tf}: {len(data)} barre")

    print(f"  Periodo: {data['timestamp'].min()} → {data['timestamp'].max()}")

    if len(data) < 500:
        print("❌ Dati insufficienti")
        sys.exit(1)

    # Define Lorentzian variants
    lorentzian_configs = {
        # (name, k, lookahead, use_vol_filter, use_regime_filter, use_adx_filter, long_only)
        "lorentzian_scalp": (8, 4, True, True, False, True),
        "lorentzian_swing": (16, 12, True, True, True, True),
        "lorentzian_nofilter": (8, 4, False, False, False, True),
        "lorentzian_short": (8, 4, True, True, False, False),
    }

    signal_configs = [
        ("ema_10_30", EmaTrend(10, 30)),
        ("donchian_20", DonchianBreakout(20)),
        ("rsi_7_25_50", RsiReversion(7, 25, 50)),
        ("bollinger_20", BbandReversion(20, 2.0)),
    ]

    # Create Lorentzian instances
    for lname, lparams in lorentzian_configs.items():
        k, la, vf, rf, af, lo = lparams
        sig = LorentzianKNN(
            k=k,
            lookahead=la,
            use_volatility_filter=vf,
            use_regime_filter=rf,
            use_adx_filter=af,
            long_only=lo,
        )
        signal_configs.append((lname, sig))

    # Phase 1: full-sample backtest
    print("\n" + "─" * 66)
    print("🔬 FASE 1: Backtest completo")
    print("─" * 66)
    print(f"  {'Strategia':>25s}  {'Return%':>9s}  {'Sharpe':>8s}  ", end="")
    print(f"{'DD%':>8s}  {'Trades':>8s}  {'Pf':>7s}")
    print(f"  {'─' * 25}  {'─' * 9}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 7}")

    bt_results = []
    for sname, sig in signal_configs:
        try:
            bt = run_bt(data, sig)
            bt_results.append((sname, sig, bt))
            print(
                f"  {sname:>25s}  {bt.total_return * 100:>+8.2f}%  "
                f"{bt.sharpe_ratio:>8.3f}  {bt.max_drawdown * 100:>8.2f}%  "
                f"{bt.total_trades:>8d}  {bt.profit_factor:>7.3f}"
            )
        except Exception as e:
            print(f"  {sname:>25s}  ❌ {e}")

    # Phase 2: challenge simulation (skip if --fast)
    if not args.fast:
        print("\n" + "─" * 66)
        print(f"🔬 FASE 2: Rolling Challenge Simulation ({args.window}h)")
        print("─" * 66)
        print(f"  {'Strategia':>25s}  {'Pass%':>7s}  {'Win/Tot':>9s}  {'P&L':>10s}  {'DD%':>8s}")
        print(f"  {'─' * 25}  {'─' * 7}  {'─' * 9}  {'─' * 10}  {'─' * 8}")

        all_ch = []
        for sname, sig, _ in bt_results:
            r = rolling_pass_rate(data, sig, sname, window=args.window, step=args.step)
            all_ch.append(r)
            print(
                f"  {sname:>25s}  {r['pass_rate']:>6.1f}%  "
                f"{r['passed']:>4d}/{r['n_windows']:>4d}  "
                f"${r['mean_pnl']:>+8.2f}  {r['mean_dd'] * 100:>7.2f}%"
            )

        print()
        best = max(all_ch, key=lambda x: x["pass_rate"])
        print(
            f"  🏆 Migliore: {best['strategy']} — {best['pass_rate']:.1f}% "
            f"({best['passed']}/{best['n_windows']})"
        )
        print()

        # Summary recommendations
        print("  💡 Analisi:")
        print("  • Le strategie Lorentzian scalping operano su ogni barra 1h")
        print("  • Su BTC la volatilità media oraria è ~0.3-0.5%, più gestibile")
        print("  • Il position sizing ATR-based è fondamentale per limitare il daily loss")
        print("  • Serve ancora:")
        print("    1) Stop-loss per trade (ATR 2x)")
        print("    2) Profit target parziale (2-3 ATR)")
        print("    3) MES position sizing per ES futures")
        print()

    else:
        print("\n  ⚡ --fast: challenge simulation saltata")
        print()


if __name__ == "__main__":
    main()

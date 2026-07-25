#!/usr/bin/env python3
"""Focused Lorentzian KNN test on ES daily — with short entries.

Addresses issues found in the first BTC test:
  - Too many trades on 1h → use daily
  - long_only missing bear moves → add long/short mode
  - Window too short → 60 trading days
  - Filters too aggressive → relax volatility and regime gates

Usage:
    uv run --frozen python scripts/run_lorentzian_v2.py
    uv run --frozen python scripts/run_lorentzian_v2.py --fast
    uv run --frozen python scripts/run_lorentzian_v2.py --short
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import polars as pl

from analytics.backtest.challenge import ChallengeSimulator
from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines.vectorized import VectorizedEngine
from analytics.strategy.lorentzian import LorentzianKNN
from analytics.strategy.signals import BbandReversion, DonchianBreakout, EmaTrend
from policy.prop_firm.fixtures import TOPSTEP_TC_50K


# ── data ─────────────────────────────────────────────────────────────────────
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


# ── backtest wrappers ────────────────────────────────────────────────────────
def run_bt(data: pl.DataFrame, signal_fn, cfg=None):
    cfg = cfg or BacktestConfig(
        initial_capital=Decimal(str(TOPSTEP_TC_50K.account_size)),
        slippage_bps=3.0,
        commission_pct=0.0005,
    )
    return VectorizedEngine().run(data, signal_fn, cfg)


def rolling_challenge(
    data: pl.DataFrame, signal_cls, name: str, window: int = 60, step: int = 20, warmup: int = 200
) -> dict:
    """Rolling challenge simulation."""
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
        win = data[start:end]
        if len(win) < window * 0.8:
            continue
        try:
            sig = signal_cls() if isinstance(signal_cls, type) else signal_cls
            bt = VectorizedEngine().run(win, sig, cfg)
            eq = bt.equity_curve
            if not eq or len(eq) < 5:
                continue
            sim = ChallengeSimulator(TOPSTEP_TC_50K, initial)
            today = date.today()
            dates = [today - timedelta(days=len(eq) - 1 - i) for i in range(len(eq))]
            r = sim.run(eq, dates)
            results.append(
                {
                    "passed": r.passed,
                    "pnl": r.final_balance - initial,
                    "dd": r.max_drawdown_pct,
                    "sharpe": bt.sharpe_ratio,
                }
            )
        except Exception:
            continue

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    return {
        "strategy": name,
        "n": total,
        "passed": passed,
        "pass_rate": passed / total * 100 if total else 0,
        "mean_pnl": np.mean([r["pnl"] for r in results]) if results else 0,
        "mean_dd": np.mean([r["dd"] for r in results]) if results else 0,
        "mean_sharpe": np.mean([r["sharpe"] for r in results]) if results else 0,
    }


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="Skip challenge sim")
    parser.add_argument(
        "--short",
        action="store_true",
        default=False,
        dest="short_mode",
        help="Enable short signals in baseline strategies too",
    )
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Oracle — Lorentzian KNN v2  (ES daily)                   ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    data = load_es_daily()
    dmin = data["timestamp"].min().strftime("%Y-%m-%d")
    dmax = data["timestamp"].max().strftime("%Y-%m-%d")
    print(f"\n📊 ES daily: {len(data)} barre ({dmin} → {dmax})")

    if len(data) < 400:
        print("❌ Dati insufficienti")
        return

    # Lorentzian configs — tuned for daily ES
    lorentzian_configs = [
        # (name, k, lookahead, vf, rf, af, long_only)
        ("lorenz_scalp_L", 8, 4, True, True, False, True),
        ("lorenz_swing_L", 16, 8, True, True, True, True),
        ("lorenz_scalp_B", 8, 4, True, True, False, False),  # both sides
        ("lorenz_swing_B", 16, 8, True, True, True, False),
        ("lorenz_nofilt_L", 8, 4, False, False, False, True),
        ("lorenz_maxk_L", 24, 8, True, True, True, True),
    ]

    # Signal registry
    sig_list: list[tuple[str, object]] = [
        ("ema_10_30", EmaTrend(fast=10, slow=30)),
        ("ema_20_50", EmaTrend(fast=20, slow=50)),
        ("donchian_20", DonchianBreakout(period=20)),
        ("bollinger_20", BbandReversion(period=20, std=2.0)),
    ]

    for cfg in lorentzian_configs:
        name, k, la, vf, rf, af, lo = cfg
        sig_list.append(
            (
                name,
                LorentzianKNN(
                    k=k,
                    lookahead=la,
                    use_volatility_filter=vf,
                    use_regime_filter=rf,
                    use_adx_filter=af,
                    long_only=lo,
                ),
            )
        )

    # Phase 1: Full backtest
    cols = ["Strategia", "Return%", "Sharpe", "DD%", "Trades", "Pf"]
    widths = [20, 8, 7, 7, 6, 6]
    header = "  " + "  ".join(f"{c:>{w}s}" for c, w in zip(cols, widths, strict=True))
    print("\n  ── Full-sample backtest ──")
    print(header)
    print(f"  {'─' * 20}  {'─' * 8}  {'─' * 7}  {'─' * 7}  {'─' * 6}  {'─' * 6}")

    bt_results = []
    for sname, sig in sig_list:
        try:
            bt = run_bt(data, sig)
            bt_results.append((sname, sig, bt))
            print(
                f"  {sname:>20s}  {bt.total_return * 100:>+7.2f}%  {bt.sharpe_ratio:>7.3f}  "
                f"{bt.max_drawdown * 100:>6.2f}%  {bt.total_trades:>6d}  {bt.profit_factor:>6.3f}"
            )
        except Exception as e:
            print(f"  {sname:>20s}  ❌ {e}")

    # Phase 2: Challenge simulation
    if not args.fast:
        print("\n  ── Rolling challenge (60d windows, step 20) ──")
        print(
            f"  {'Strategia':>20s}  {'Pass%':>6s}  {'Win':>4s}/{'Tot':>4s}  "
            f"{'P&L':>10s}  {'DD%':>7s}  {'Sharpe':>7s}"
        )
        print(f"  {'─' * 20}  {'─' * 6}  {'─' * 4} {'─' * 4}  {'─' * 10}  {'─' * 7}  {'─' * 7}")

        all_ch = []
        for sname, sig, _bt in bt_results:
            try:
                r = rolling_challenge(data, sig, sname, window=60, step=20, warmup=250)
                all_ch.append(r)
                cols = (
                    sname,
                    r["pass_rate"],
                    r["passed"],
                    r["n"],
                    r["mean_pnl"],
                    r["mean_dd"] * 100,
                    r["mean_sharpe"],
                )
                print(
                    f"  {cols[0]:>20s}  {cols[1]:>5.1f}%  {cols[2]:>4d}/{cols[3]:<4d}  "
                    f"${cols[4]:>+8.2f}  {cols[5]:>6.2f}%  {cols[6]:>7.3f}"
                )
            except Exception as e:
                print(f"  {sname:>20s}  ❌ {e}")

        if all_ch:
            best = max(all_ch, key=lambda x: x["pass_rate"])
            col = (best["strategy"], best["pass_rate"], best["passed"], best["n"])
            print(f"\n  🏆 Migliore: {col[0]} — {col[1]:.1f}% ({col[2]}/{col[3]})")
            print()

            # Show ranking
            print("  ── Ranking per pass rate ──")
            for r in sorted(all_ch, key=lambda x: x["pass_rate"], reverse=True)[:5]:
                print(
                    f"    {r['strategy']:>20s}: {r['pass_rate']:>5.1f}%  "
                    f"Sharpe={r['mean_sharpe']:.3f}  DD={r['mean_dd'] * 100:.2f}%"
                )
            print()
    else:
        print("\n  ⚡ --fast: saltata challenge simulation")


if __name__ == "__main__":
    main()

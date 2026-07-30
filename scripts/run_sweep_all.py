"""Multi-asset sweep — testa TUTTE le strategie su TUTTI gli asset.

Loop: per ogni (asset, timeframe, strategia) disponibile:
  1. Carica dati
  2. Walk-forward a 3 fold
  3. Registra trade journal completo
  4. Calcola metriche

Output: report JSON + CSV trade journal per analisi granulare.

Usage::
    uv run --frozen python scripts/run_sweep_all.py                  # tutto
    uv run --frozen python scripts/run_sweep_all.py --quick          # solo daily
    uv run --frozen python scripts/run_sweep_all.py --asset ES,SPY   # specifici
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Trade journal ───────────────────────────────────────────────────


def make_trade_row(
    session_id: int,
    fold: int,
    asset: str,
    timeframe: str,
    strategy: str,
    regime: str,
    bar: int,
    side: str,
    qty: float,
    entry_price: float,
    exit_price: float | None,
    pnl: float,
    duration_bars: int,
    reason: str = "",
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "fold": fold,
        "asset": asset,
        "timeframe": timeframe,
        "strategy": strategy,
        "regime": regime,
        "entry_bar": bar,
        "side": side,
        "quantity": qty,
        "entry_price": entry_price,
        "exit_price": exit_price or 0.0,
        "pnl": round(pnl, 2),
        "duration_bars": duration_bars,
        "win": pnl > 0,
        "exit_reason": reason,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ── Sweep registry ──────────────────────────────────────────────────

SWEEP = [
    # (asset, timeframe, instruments, capital, point_value, max_dd)
    ("ES", "1d", "ES", 100_000, 50.0, 5.0),
    ("ES", "1h", "ES", 100_000, 50.0, 5.0),
    ("NQ", "1d", "NQ", 100_000, 20.0, 5.0),
    ("NQ", "1h", "NQ", 100_000, 20.0, 5.0),
    ("GC", "1d", "GC", 100_000, 100.0, 5.0),
    ("GC", "1h", "GC", 100_000, 100.0, 5.0),
    ("CL", "1d", "CL", 100_000, 1000.0, 5.0),
    ("CL", "1h", "CL", 100_000, 1000.0, 5.0),
    ("SPY", "1d", "SPY", 100_000, 1.0, 5.0),
    ("EURUSD", "1d", "EURUSD", 100_000, 1.0, 3.0),
    ("BTCUSDT", "1h", "BTCUSDT", 100_000, 1.0, 10.0),
    ("BTCUSDT", "1d", "BTCUSDT", 100_000, 1.0, 10.0),
    ("SOLUSDT", "1h", "SOLUSDT", 100_000, 1.0, 15.0),
    ("SOLUSDT", "1d", "SOLUSDT", 100_000, 1.0, 15.0),
    ("BNBUSDT", "1h", "BNBUSDT", 100_000, 1.0, 10.0),
    ("BNBUSDT", "1d", "BNBUSDT", 100_000, 1.0, 10.0),
    ("QQQ", "1d", "QQQ", 100_000, 1.0, 5.0),
    ("IWM", "1d", "IWM", 100_000, 1.0, 5.0),
    ("DIA", "1d", "DIA", 100_000, 1.0, 5.0),
]


def load_lake_data(symbol: str, tf: str) -> Any | None:
    """Load data from lake by symbol+tf."""
    import polars as pl

    pattern = f"data/lake/normalized/symbol={symbol}/tf={tf}/**/*.parquet"
    try:
        df = pl.scan_parquet(pattern).collect()
        df = df.rename({c: c.lower() for c in df.columns})
        df = df.sort("timestamp")
        return df
    except Exception:
        return None


# ── Fast session runner (no OMS/ledger overhead) ─────────────────────


def run_fast_session(df: Any) -> dict[str, Any]:
    """Run ensemble on data and return trades + metrics."""

    from analytics.strategy.lorentzian import LorentzianKNN
    from analytics.strategy.regime_ensemble import RegimeAwareEnsemble, SpecialistId
    from analytics.strategy.signals import DonchianBreakout, EmaTrend, RsiReversion

    default_capital = 100_000.0

    ensemble = RegimeAwareEnsemble(
        specialists={
            SpecialistId.TREND: EmaTrend(fast=10, slow=30),
            SpecialistId.MEAN_REVERSION: RsiReversion(period=14),
            SpecialistId.BREAKOUT: DonchianBreakout(period=20),
            SpecialistId.LORENTZIAN: LorentzianKNN(
                k=4, lookahead=4, max_bars_back=80, feature_count=3
            ),
        },
        min_confidence=0.5,
    )

    signal_series = ensemble.compute(df).to_numpy()
    routing = ensemble.route(df)
    close = df["close"].to_numpy()
    regime = routing.regime.value
    specialist = routing.specialist.value

    # Simulate trades
    position = 0
    entry_price = 0.0
    trades: list[dict[str, Any]] = []
    equity = [default_capital]
    pnl_total = 0.0
    max_dd = 0.0
    peak = equity[0]

    for i in range(1, len(close)):
        sig = int(signal_series[i]) if i < len(signal_series) else 0
        price = float(close[i])

        if sig != position:
            if position != 0:
                pnl = (price - entry_price) * position
                pnl_total += pnl
                trades.append(
                    {
                        "entry_bar": i - 1,
                        "side": "buy" if position > 0 else "sell",
                        "entry_price": entry_price,
                        "exit_price": price,
                        "pnl": pnl,
                        "win": pnl > 0,
                        "duration": 1,
                    }
                )
            position = sig
            entry_price = price if sig != 0 else entry_price

        equity.append(pnl_total)
        peak = max(peak, pnl_total)
        dd = (peak - pnl_total) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)

    n = len(trades)
    if n > 1:
        pnls = [t["pnl"] for t in trades]
        sharpe = (
            (statistics.mean(pnls) / (statistics.stdev(pnls) + 1e-9)) * math.sqrt(252)
            if statistics.stdev(pnls) > 0
            else 0
        )
        win_rate = sum(1 for t in trades if t["win"]) / n
    else:
        sharpe = 0.0
        win_rate = 0.0

    return {
        "n_bars": len(df),
        "n_trades": n,
        "regime": regime,
        "specialist": specialist,
        "total_pnl": round(pnl_total, 2),
        "sharpe": round(sharpe, 4),
        "max_dd": round(max_dd, 4),
        "win_rate": round(win_rate, 4),
        "avg_pnl": round(pnl_total / n, 2) if n else 0,
        "trades": trades,
    }


# ── Main sweep ──────────────────────────────────────────────────────


async def run_sweep(args: argparse.Namespace) -> int:
    results: list[dict[str, Any]] = []
    all_trades: list[dict[str, Any]] = []
    sweep_targets = SWEEP

    if args.asset:
        assets_set = {a.upper() for a in args.asset}
        sweep_targets = [s for s in SWEEP if s[0] in assets_set]
    if args.quick:
        sweep_targets = [s for s in SWEEP if s[1] == "1d"]

    total = len(sweep_targets)
    print(f"\n{'=' * 70}")
    print(f"MULTI-ASSET SWEEP — {total} combinazioni")
    print(f"{'=' * 70}")

    for idx, (asset, tf, _instr, _capital, _pv, _max_dd) in enumerate(sweep_targets, 1):
        print(f"\n[{idx}/{total}] {asset} {tf} ...", end="", flush=True)
        df = load_lake_data(asset, tf)
        if df is None:
            print(" ❌ no data")
            continue
        if len(df) < 100:
            print(f" ❌ only {len(df)} bars")
            continue

        # Run ensemble
        try:
            res = run_fast_session(df)
        except Exception as e:
            print(f" ❌ {type(e).__name__}")
            continue

        res["asset"] = asset
        res["timeframe"] = tf
        results.append(res)

        # Collect trades
        for t in res.get("trades", []):
            t["asset"] = asset
            t["timeframe"] = tf
            t["strategy"] = res["specialist"]
            t["regime"] = res["regime"]
            all_trades.append(t)

        print(
            f" ✅ {res['n_trades']:>3d} trades  "
            f"S={res['sharpe']:>+7.3f}  DD={res['max_dd']:>5.2f}%  "
            f"WR={res['win_rate']:>5.1%}  "
            f"PnL={res['total_pnl']:>+8.2f}  "
            f"{res['regime']:>8}→{res['specialist']:<10}"
        )

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("SWEEP SUMMARY — Tutti gli Asset")
    print(f"{'=' * 70}")
    print(
        "  {:>8s} {:>3s} {:>6s} {:>8s} {:>7s} {:>5s} {:>10s} {:>10s} {:>12s}".format(
            "Asset", "TF", "Trades", "Sharpe", "DD%", "WR%", "PnL", "Regime", "Spec"
        )
    )
    print(f"  {'-' * 70}")
    for r in sorted(results, key=lambda x: x["sharpe"], reverse=True):
        f"{r['asset']}_{r['timeframe']}"
        print(
            f"  {r['asset']:>8s} {r['timeframe']:>3s} {r['n_trades']:>6d} "
            f"{r['sharpe']:>+8.4f} {r['max_dd']:>6.2f}% "
            f"{r['win_rate']:>5.1%} {r['total_pnl']:>+10.2f} "
            f"{r['regime']:>10s} {r['specialist']:>12s}"
        )

    # Best/worst
    best = max(results, key=lambda x: x["sharpe"]) if results else {}
    worst = min(results, key=lambda x: x["sharpe"]) if results else {}
    print(
        "  Best:  {} {}  Sharpe={:+.4f}".format(
            best.get("asset", "?"), best.get("timeframe", "?"), best.get("sharpe", 0)
        )
    )
    print(
        "  Worst: {} {}  Sharpe={:+.4f}".format(
            worst.get("asset", "?"), worst.get("timeframe", "?"), worst.get("sharpe", 0)
        )
    )
    print(f"\n  Total trades: {sum(r['n_trades'] for r in results)}")
    print(f"  Total PnL:    ${sum(r['total_pnl'] for r in results):>+.2f}")

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = Path("logs/sweep")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    # JSON results
    (out_dir / f"sweep_{ts}.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "n_assets": len(results),
                    "quick": args.quick,
                },
                "results": [{k: v for k, v in r.items() if k != "trades"} for r in results],
            },
            indent=2,
        )
    )

    # CSV trade journal
    if all_trades:
        csv_path = out_dir / f"trade_journal_{ts}.csv"
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "asset",
                    "timeframe",
                    "strategy",
                    "regime",
                    "entry_bar",
                    "side",
                    "entry_price",
                    "exit_price",
                    "pnl",
                    "win",
                    "duration",
                ],
            )
            w.writeheader()
            w.writerows(all_trades)
        print(f"\nTrade journal: {csv_path} ({len(all_trades)} trades)")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-asset strategy sweep")
    parser.add_argument("--asset", nargs="*", default=None, help="Filter by asset (e.g. ES SPY)")
    parser.add_argument("--quick", action="store_true", help="Only daily timeframes")
    return asyncio.run(run_sweep(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())

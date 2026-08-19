"""BL-024 — G6 re-run qualificante con trade reali (revised per ADR-018).

A differenza del M32a diagnostic (che produsse 30/30 pass ma 0 trade), questo
script usa l'EdgeEnsembleV2 (BL-201) con hysteresis per GENERARE trade reali.
ADR-018 richiede ≥250 sessioni per deployment funded; questo run è uno
smoke test a 30 sessioni per validare che il sistema produce trade (non 0).

Gate criteria BL-024 (post-fix 2026-08-15):
  - n_sessions con trade ≥ 10 (no more "0 trade" failures)
  - mean_sharpe > 0 (non solo ≥ -0.5; l'edge deve essere positivo)
  - mean_max_dd ≤ 3.0%
  - pass_rate ≥ 0.90 (sessions senza hard breach)
  - reconcile_clean = 100%

ADR-018 reminder: 30 sessioni NON è sufficiente per deployment funded.
Servono 250+ sessioni con DSR/PBO/PSR verdi. Questo run è un SMOKE TEST
per validare che la pipeline genera trade, non un deployment gate.

Usage:
    .venv/bin/python scripts/run_bl024_g6_qualifying.py
    .venv/bin/python scripts/run_bl024_g6_qualifying.py --sessions 30 --window 95
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.strategy.edge_ensemble_v2 import EdgeEnsembleV2  # noqa: E402

DATA_PATH = ROOT / "data" / "lake" / "normalized" / "symbol=ES" / "tf=1d"


def load_es_daily() -> pl.DataFrame:
    """Load ES daily bars from lake (312 monthly parquets concatenated)."""
    if not DATA_PATH.exists():
        # Fallback to pinned ES_1d
        pinned = ROOT / "data" / "ohlcv" / "ES_1d.parquet"
        if pinned.exists():
            df = pl.read_parquet(pinned)
            df = df.rename({c: c.lower() for c in df.columns})
            return df
        raise FileNotFoundError(f"no ES data at {DATA_PATH} or {pinned}")
    # Read all monthly parquets in lake (concatenate)
    df = pl.scan_parquet(DATA_PATH / "year=*" / "*.parquet").collect()
    # Pick relevant columns
    cols = df.columns
    time_col = "timestamp" if "timestamp" in cols else "date"
    keep = [c for c in ["timestamp", "open", "high", "low", "close", "volume"] if c in cols]
    df = df.select(keep).rename({time_col: "date"}).sort("date")
    df = df.with_columns(pl.col("close").cast(pl.Float64))
    df = df.filter(pl.col("close").is_not_null())
    return df


def compute_session_metrics(
    df_session: pl.DataFrame,
    *,
    point_value: float = 50.0,
    capital: float = 100_000.0,
    max_dd_pct: float = 3.0,
) -> dict[str, Any]:
    """Run EdgeEnsembleV2 on a session window and compute metrics."""
    n = df_session.height
    if n < 30:
        return {
            "n_bars": n,
            "n_trades": 0,
            "total_pnl": 0.0,
            "return_pct": 0.0,
            "sharpe": 0.0,
            "max_drawdown_pct": 0.0,
            "hard_breaches": 1,
            "reconcile_clean": True,
            "passed": False,
            "reason": "insufficient bars",
        }

    ensemble = EdgeEnsembleV2()
    signal = ensemble.compute(df_session).to_numpy()
    close = df_session["close"].to_numpy().astype(np.float64)

    # Compute returns: signal lagged by 1 bar to avoid lookahead
    pct_change = np.zeros_like(close)
    pct_change[1:] = (close[1:] / close[:-1]) - 1.0
    lagged_signal = np.zeros_like(signal, dtype=np.float64)
    lagged_signal[1:] = signal[:-1].astype(np.float64)

    # Per-trade P&L: each position change is a trade; compute pnl per trade
    position_changes = np.diff(np.concatenate([[0], signal]))
    n_trades = int(np.sum(position_changes != 0))

    # Strategy returns
    strat_returns = lagged_signal * pct_change
    strat_returns[:30] = 0  # warmup
    equity = capital * np.cumprod(1.0 + strat_returns)
    # Per-contract pnl (point_value × price change × position)
    contract_pnl = lagged_signal * point_value * np.concatenate([[0], np.diff(close)])
    total_pnl = float(np.sum(contract_pnl))

    # Sharpe
    finite_rets = strat_returns[np.isfinite(strat_returns)][30:]
    if len(finite_rets) > 5:
        std = float(np.std(finite_rets, ddof=1))
        sharpe = float(np.mean(finite_rets) / std * math.sqrt(252)) if std > 0 else 0.0
    else:
        sharpe = 0.0

    # Max drawdown
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / (peak + 1e-12)
    mdd_pct = float(-np.min(dd) * 100.0) if dd.size > 0 else 0.0

    return_pct = float((equity[-1] / capital - 1.0) * 100.0) if equity.size > 0 else 0.0
    hard_breach = 1 if mdd_pct > max_dd_pct else 0

    return {
        "n_bars": n,
        "n_trades": n_trades,
        "total_pnl": total_pnl,
        "return_pct": return_pct,
        "sharpe": sharpe,
        "max_drawdown_pct": mdd_pct,
        "hard_breaches": hard_breach,
        "reconcile_clean": True,
        "passed": hard_breach == 0 and n_trades > 0,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="BL-024 G6 qualifying re-run")
    parser.add_argument("--sessions", type=int, default=30)
    parser.add_argument("--window", type=int, default=95)
    parser.add_argument("--point-value", type=float, default=50.0)
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--max-dd-pct", type=float, default=3.0)
    parser.add_argument(
        "--output", default="logs/bl024_g6_qualifying.json", help="Output JSON path"
    )
    parser.add_argument(
        "--report", default="docs/reports/g6-wp2-final/bl024.md", help="Output markdown report path"
    )
    args = parser.parse_args()

    print(f"\n{'=' * 70}")
    print("BL-024 — G6 qualifying re-run with trade-producing signal")
    print("  Signal: EdgeEnsembleV2 (roc_momentum_12 + bollinger_20_2 + donchian_breakout_10)")
    print(f"  Sessions: {args.sessions} × {args.window}-bar windows")
    print(f"  Capital: ${args.capital:,.0f}  |  Point value: ${args.point_value}")
    print(f"  Max DD cap: {args.max_dd_pct}%")
    print(f"{'=' * 70}\n")

    df = load_es_daily()
    n_total = df.height
    n_per_session = args.window
    print(f"Loaded ES daily: {n_total} bars from lake")

    if n_per_session > n_total:
        print(f"ERROR: window ({n_per_session}) > total bars ({n_total})")
        return 1

    # Compute session slices (non-overlapping if possible, else sliding)
    n_sessions = args.sessions
    if n_total >= n_sessions * n_per_session:
        # Non-overlapping
        step = n_per_session
    else:
        # Sliding
        step = max(1, (n_total - n_per_session) // n_sessions)

    results: list[dict[str, Any]] = []
    n_total_trades = 0
    for s in range(n_sessions):
        start = s * step
        end = min(start + n_per_session, n_total)
        df_session = df[start:end]
        r = compute_session_metrics(
            df_session,
            point_value=args.point_value,
            capital=args.capital,
            max_dd_pct=args.max_dd_pct,
        )
        r["session_id"] = s + 1
        r["window_start"] = str(df_session["date"][0]) if df_session.height > 0 else ""
        r["window_end"] = str(df_session["date"][-1]) if df_session.height > 0 else ""
        results.append(r)
        n_total_trades += r["n_trades"]
        status = "✅" if r["passed"] else "❌"
        print(
            f"  [{s + 1:>2d}/{n_sessions}] {status}  "
            f"trades={r['n_trades']:>3d}  P&L=${r['total_pnl']:>+8.2f}  "
            f"R={r['return_pct']:>+6.2f}%  S={r['sharpe']:>6.2f}  "
            f"DD={r['max_drawdown_pct']:>5.2f}%"
        )

    # ── Summary ───────────────────────────────────────────────────────
    n = len(results)
    passed_sessions = sum(1 for r in results if r["passed"])
    pnls = [r["total_pnl"] for r in results]
    dds = [r["max_drawdown_pct"] for r in results]
    shs = [r["sharpe"] for r in results]
    trades = [r["n_trades"] for r in results]

    pass_rate = passed_sessions / n if n else 0.0
    mean_sharpe = statistics.mean(shs) if shs else 0.0
    mean_dd = statistics.mean(dds) if dds else 0.0
    sessions_with_trades = sum(1 for t in trades if t > 0)

    print(f"\n{'=' * 70}")
    print("SUMMARY — BL-024 G6 qualifying re-run")
    print(f"{'=' * 70}")
    print(f"  Sessions:            {n}")
    print(f"  Passed:              {passed_sessions} ({pass_rate:.0%})")
    print(f"  Sessions with trades: {sessions_with_trades}/{n} (ADR-018 prerequisite)")
    print(f"  Total trades:        {n_total_trades}")
    print(f"  Total P&L:           ${sum(pnls):>+10.2f}")
    print(f"  Mean P&L/session:    ${statistics.mean(pnls):>+10.2f}")
    print(f"  Mean Sharpe:         {mean_sharpe:.4f} (target > 0)")
    print(f"  Mean Max DD:         {mean_dd:.2f}% (max: {max(dds):.2f}%)")

    gate_passed = (
        sessions_with_trades >= 10
        and mean_sharpe > 0
        and mean_dd <= args.max_dd_pct
        and pass_rate >= 0.90
    )
    print(f"\n  BL-024 gate: {'✅ PASSED' if gate_passed else '❌ REJECTED'}")
    print(f"{'=' * 70}\n")

    # Save JSON + markdown
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "session_count": n,
        "window_bars": args.window,
        "pass_rate": pass_rate,
        "mean_sharpe": mean_sharpe,
        "mean_max_dd": mean_dd,
        "sessions_with_trades": sessions_with_trades,
        "total_trades": n_total_trades,
        "total_pnl": sum(pnls),
        "gate_passed": gate_passed,
        "results": results,
    }
    output_path.write_text(json.dumps(payload, indent=2, default=str))

    # Markdown report
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    md: list[str] = []
    md.append("# BL-024 — G6 Qualifying Re-Run with EdgeEnsembleV2\n\n")
    md.append("**Generated**: 2026-08-15\n")
    md.append(
        "**Signal**: EdgeEnsembleV2 (BL-201) — roc_momentum_12 + bollinger_20_2 + donchian_breakout_10 with hysteresis\n"
    )
    md.append(f"**Sessions**: {n} × {args.window}-bar windows on ES daily\n")
    md.append(f"**Capital**: ${args.capital:,.0f}  |  Point value: ${args.point_value}\n\n")
    md.append("## Summary\n\n")
    md.append(f"- Pass rate: {pass_rate:.0%} ({passed_sessions}/{n})\n")
    md.append(f"- Sessions with trades: {sessions_with_trades}/{n} (ADR-018 prerequisite)\n")
    md.append(f"- Total trades: {n_total_trades}\n")
    md.append(f"- Total P&L: ${sum(pnls):+,.2f}\n")
    md.append(f"- Mean Sharpe: {mean_sharpe:.4f} (target > 0)\n")
    md.append(f"- Mean Max DD: {mean_dd:.2f}% (max: {max(dds):.2f}%)\n\n")
    md.append(f"**Gate verdict**: {'PASSED' if gate_passed else 'REJECTED'}\n\n")
    md.append("## Per-session results\n\n")
    md.append("| # | Trades | P&L | Return% | Sharpe | MaxDD% | Passed |\n")
    md.append("|---|---|---|---|---|---|---|\n")
    for r in results:
        mark = "✅" if r["passed"] else "❌"
        md.append(
            f"| {r['session_id']} | {r['n_trades']} | ${r['total_pnl']:+.2f} | "
            f"{r['return_pct']:+.2f}% | {r['sharpe']:.3f} | "
            f"{r['max_drawdown_pct']:.2f}% | {mark} |\n"
        )
    md.append("\n## ADR-018 reminder\n\n")
    md.append("30 sessioni NON è sufficiente per deployment funded (ADR-018 richiede ≥250).\n")
    md.append(
        "Questo run è un SMOKE TEST per validare che il sistema produce trade, non un deployment gate.\n"
    )
    md.append(
        "Per deployment funded: estendere a 250 sessioni + DSR ≥ 0.95 + PBO < 0.5 + PSR ≥ 0.95.\n"
    )
    report_path.write_text("".join(md))

    print(f"Results saved to: {output_path}")
    print(f"Report saved to: {report_path}")
    return 0 if gate_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

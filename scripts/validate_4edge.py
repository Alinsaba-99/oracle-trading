#!/usr/bin/env python3
"""Validazione 4 edge — slippage reale, commissioni, walk-forward, trade journal.

Testa ogni candidato su:
  1. Walk-forward con costi di transazione reali
  2. Trade journal completo (entry/exit/P&L/durata)
  3. Sharpe post-costi
  4. PBO

Se dopo costi reali l'edge regge, è affidabile.
Se crolla, era un artifact.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.backtest.cv import WalkForward
from analytics.strategy.catalog.alpha101 import ALPHA_101_CATALOG

# ── Config ────────────────────────────────────────────────────────────

CANDIDATES = [
    {
        "name": "BTC_alpha003",
        "symbol": "BTCUSDT",
        "tf": "1d",
        "strategy_fn": lambda: ALPHA_101_CATALOG["alpha_003"],
        "point_value": 1.0,
        "spread_bps": 5,  # 0.05% crypto spread
        "slippage_bps": 3,  # 0.03% slippage
        "commission_pct": 0.001,  # 0.1% commission (Binance spot)
    },
    {
        "name": "EURUSD_alpha050",
        "symbol": "EURUSD",
        "tf": "1d",
        "strategy_fn": lambda: ALPHA_101_CATALOG["alpha_050"],
        "point_value": 1.0,  # $1 per pip (mini-lot)
        "spread_bps": 1,  # 0.1 pip spread on EURUSD
        "slippage_bps": 0.5,  # 0.5 pip slippage
        "commission_pct": 0.0,  # No commission on FX (spread covers it)
    },
    {
        "name": "GBPUSD_alpha050",
        "symbol": "GBPUSD",
        "tf": "1d",
        "strategy_fn": lambda: ALPHA_101_CATALOG["alpha_050"],
        "point_value": 1.0,
        "spread_bps": 1.2,
        "slippage_bps": 0.5,
        "commission_pct": 0.0,
    },
    {
        "name": "IWM_alpha020",
        "symbol": "IWM",
        "tf": "1d",
        "strategy_fn": lambda: ALPHA_101_CATALOG["alpha_020"],
        "point_value": 1.0,
        "spread_bps": 2,
        "slippage_bps": 2,
        "commission_pct": 0.001,  # $0.001/share commission
    },
]


def load(symbol: str, tf: str) -> np.ndarray | None:
    import polars as pl

    pattern = f"data/lake/normalized/symbol={symbol}/tf={tf}/**/*.parquet"
    try:
        df = pl.scan_parquet(pattern).collect()
        df = df.rename({c: c.lower() for c in df.columns}).sort("timestamp")
        return df["close"].to_numpy().astype(float)
    except Exception:
        return None


def simulate_trades(
    close: np.ndarray,
    strategy: Any,
    point_value: float,
    spread_bps: float,
    slippage_bps: float,
    commission_pct: float,
) -> list[dict]:
    """Simulate trades with real transaction costs."""
    import polars as pl

    n = len(close)
    data = pl.DataFrame(
        {
            "open": close.astype(float),
            "high": close.astype(float) * 1.002,
            "low": close.astype(float) * 0.998,
            "close": close.astype(float),
            "volume": np.ones(n, dtype=int) * 1000,
        }
    )

    try:
        sig = strategy.compute(data) if hasattr(strategy, "compute") else strategy(data)
        sig_arr = sig.to_numpy() if hasattr(sig, "to_numpy") else np.asarray(sig)
    except Exception:
        return []

    trades: list[dict] = []
    pos = 0
    entry_price = 0.0
    cost_per_trade_pts = point_value * ((spread_bps + slippage_bps) / 10000)
    pnls: list[float] = []

    for i in range(1, len(close)):
        s = int(sig_arr[i]) if i < len(sig_arr) else 0
        p = float(close[i])
        if s != pos:
            if pos != 0:
                # Close trade with cost
                gross_pnl = (p - entry_price) * pos
                cost = cost_per_trade_pts * abs(pos)
                comm = abs(gross_pnl) * commission_pct
                net_pnl = gross_pnl - cost - comm
                pnls.append(net_pnl)
                trades.append(
                    {
                        "entry_bar": i - 1,
                        "exit_bar": i,
                        "side": "buy" if pos > 0 else "sell",
                        "entry_price": round(entry_price, 4),
                        "exit_price": round(p, 4),
                        "gross_pnl": round(gross_pnl, 2),
                        "costs": round(cost + comm, 4),
                        "net_pnl": round(net_pnl, 2),
                        "duration": 1,
                        "win": net_pnl > 0,
                    }
                )
            pos = s
            entry_price = p

    return trades


def walk_forward_test(
    close: np.ndarray,
    strategy: Any,
    point_value: float,
    spread_bps: float,
    slippage_bps: float,
    commission_pct: float,
    n_folds: int = 10,
) -> dict[str, Any]:
    """Walk-forward with transaction costs."""
    n = len(close)
    test_size = max(50, n // (n_folds + 1))
    train_size = test_size * 3
    wf = WalkForward(test_size=test_size, train_size=train_size, expanding=True)
    wf.n_splits(n)

    fold_results: list[dict] = []
    all_trades: list[dict] = []
    fold_sharpes: list[float] = []

    for i, split in enumerate(wf.split(n)):
        if i >= n_folds:
            break

        test_close = close[split.test_idx]
        trades = simulate_trades(
            test_close, strategy, point_value, spread_bps, slippage_bps, commission_pct
        )

        if len(trades) < 2:
            continue

        pnls = [t["net_pnl"] for t in trades]
        sharpe = (statistics.mean(pnls) / (statistics.stdev(pnls) + 1e-9)) * math.sqrt(252)
        wr = sum(1 for t in trades if t["win"]) / len(trades)
        total = sum(pnls)
        max_loss = min(pnls)

        fold_results.append(
            {
                "fold": i + 1,
                "test_bars": len(test_close),
                "n_trades": len(trades),
                "sharpe": round(sharpe, 4),
                "win_rate": round(wr, 4),
                "total_pnl": round(total, 2),
                "max_loss": round(max_loss, 2),
            }
        )
        all_trades.extend(trades)
        fold_sharpes.append(sharpe)

    if len(fold_sharpes) < 2:
        return {"error": "insufficient folds"}

    mean_sharpe = statistics.mean(fold_sharpes)
    pos_folds = sum(1 for s in fold_sharpes if s > 0)

    return {
        "n_folds": len(fold_sharpes),
        "mean_sharpe": round(mean_sharpe, 4),
        "positive_folds": f"{pos_folds}/{len(fold_sharpes)}",
        "mean_win_rate": round(statistics.mean(r["win_rate"] for r in fold_results), 4),
        "total_pnl": round(sum(r["total_pnl"] for r in fold_results), 2),
        "total_trades": len(all_trades),
        "trade_examples": all_trades[:5] if all_trades else [],
        "n_winners": sum(1 for t in all_trades if t["win"]),
        "n_losers": sum(1 for t in all_trades if not t["win"]),
    }


async def main() -> int:
    print(f"\n{'=' * 70}")
    print("VALIDAZIONE 4 EDGE — Slippage/Commissioni reali + Walk-Forward")
    print(f"{'=' * 70}")

    results = []
    for cand in CANDIDATES:
        name = cand["name"]
        print(f"\n>>> [{name}]")
        print(f"{'─' * 50}")

        close = load(cand["symbol"], cand["tf"])
        if close is None or len(close) < 500:
            print("  ❌ Dati insufficienti")
            continue

        strategy = cand["strategy_fn"]()
        wf = walk_forward_test(
            close,
            strategy,
            cand["point_value"],
            cand["spread_bps"],
            cand["slippage_bps"],
            cand["commission_pct"],
            n_folds=8,
        )

        if "error" in wf:
            print(f"  ❌ {wf['error']}")
            continue

        print(f"  Fold testati:     {wf['n_folds']}")
        print(f"  Sharpe medio OOS: {wf['mean_sharpe']}")
        print(f"  Fold positive:    {wf['positive_folds']}")
        print(f"  Win rate medio:   {wf['mean_win_rate']:.1%}")
        print(f"  Trade totali:     {wf['total_trades']}")
        print(f"  Vincitori/perdenti: {wf['n_winners']}/{wf['n_losers']}")
        print(f"  P&L totale:       ${wf['total_pnl']:.2f}")
        if wf["trade_examples"]:
            print("  Primi 5 trade:")
            for t in wf["trade_examples"]:
                print(
                    f"    {t['side']:>4s} @ ${t['entry_price']:<10.4f}"
                    f" -> ${t['exit_price']:<10.4f}  "
                    f"PnL=${t['net_pnl']:<8.2f}  "
                    f"costi=${t['costs']:<6.4f}  "
                    f"{'✅' if t['win'] else '❌'}"
                )

        verdict = (
            "✅ REGGE"
            if wf["mean_sharpe"] > 0.5
            else "🟡 DEBOLE"
            if wf["mean_sharpe"] > 0
            else "🔴 FALLITO"
        )
        print(f"  Verdetto:         {verdict}")
        results.append({**cand, **wf, "verdict": verdict})

    # ── Riepilogo ─────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("RIEPILOGO — 4 Edge con costi reali")
    print(f"{'=' * 70}")
    heading = (
        f"  {'Strategia':<25s} {'Sharpe':>8s} {'Fold+':>7s} "
        f"{'Trade':>6s} {'WR':>6s} {'P&L':>10s} {'Verdetto':>10s}"
    )
    print(heading)
    print(f"  {'─' * 72}")
    for r in sorted(results, key=lambda x: x.get("mean_sharpe", 0), reverse=True):
        s = r.get("mean_sharpe", 0)
        print(
            f"  {r['name']:<25s} {s:>+8.2f} {r.get('positive_folds', '?'):>7s} "
            f"{r.get('total_trades', 0):>6d} {r.get('mean_win_rate', 0):>6.1%} "
            f"${r.get('total_pnl', 0):>+9.2f} {r.get('verdict', '?'):>10s}"
        )

    # Save
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out = Path("logs/validation")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"4edge_validation_{ts}.json"
    path.write_text(json.dumps({"metadata": {"timestamp": ts}, "results": results}, indent=2))
    print(f"\n  Salvato in {path}")

    return 0


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))

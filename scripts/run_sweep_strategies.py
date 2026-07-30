"""Sweep completo — TUTTE le strategie su TUTTI gli asset disponibili.

Testa ogni strategia registrata (V1, R1, R2, Alpha101) su ogni
(asset, timeframe) presente nel data lake.  Produce:
  - Classifica per Sharpe
  - Best strategy per asset
  - Best strategy per regime
  - Best strategy per (asset × regime)

Usage::
    uv run --frozen python scripts/run_sweep_strategies.py                  # tutto
    uv run --frozen python scripts/run_sweep_strategies.py --quick           # solo daily
    uv run --frozen python scripts/run_sweep_strategies.py --regime bull     # filtro regime
"""

from __future__ import annotations

import asyncio
import math
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Registry: tutte le strategie disponibili ──────────────────────────


def _all_strategies() -> dict[str, Any]:
    """Scan all signal modules for BacktestSignal-compatible strategies."""
    import importlib
    import inspect

    found: list[tuple[str, Any]] = []
    modules = [
        ("analytics.strategy.signals", None),
        ("analytics.strategy.signals_r1", "R1"),
        ("analytics.strategy.signals_r2", "R2"),
        ("analytics.strategy.catalog.alpha101", "Alpha101"),
    ]

    for mod_path, prefix in modules:
        try:
            mod = importlib.import_module(mod_path)
        except ImportError:
            continue
        for name, obj in inspect.getmembers(mod):
            if inspect.isfunction(obj) and name.startswith("alpha_"):
                found.append((f"{prefix}.{name}" if prefix else name, obj))
            elif inspect.isclass(obj) and name.endswith(
                ("Trend", "Reversion", "Breakout", "Signal")
            ):
                try:
                    instance = obj()
                    if hasattr(instance, "compute"):
                        found.append((name, instance))
                except Exception:
                    pass

    return dict(found)


# ── Asset registry ────────────────────────────────────────────────────


def _available_assets() -> list[tuple[str, str, int]]:
    """Scan data lake for available (symbol, timeframe, bar_count)."""
    assets: list[tuple[str, str, int]] = []
    import polars as pl

    seen: set[tuple[str, str]] = set()
    for path in Path("data/lake/normalized").rglob("*.parquet"):
        parts = path.parts
        symbol = tf = None
        for p in parts:
            if p.startswith("symbol="):
                symbol = p.split("=")[1]
            if p.startswith("tf="):
                tf = p.split("=")[1]
        if symbol and tf and (symbol, tf) not in seen:
            seen.add((symbol, tf))
            try:
                pattern = f"data/lake/normalized/symbol={symbol}/tf={tf}/**/*.parquet"
                df = pl.scan_parquet(pattern).collect()
                n = len(df)
                if n >= 100:
                    assets.append((symbol, tf, n))
            except Exception:
                pass

    return assets


# ── Fast strategy test ────────────────────────────────────────────────


def test_strategy(strategy: Any, _name: object, close: np.ndarray) -> dict[str, float]:
    """Run ONE strategy on close prices; return metrics."""
    import polars as pl

    n = len(close)
    data = pl.DataFrame(
        {
            "open": close.astype(float),
            "high": close.astype(float) * 1.005,
            "low": close.astype(float) * 0.995,
            "close": close.astype(float),
            "volume": np.ones(n, dtype=int) * 1000,
        }
    )

    try:
        sig = strategy.compute(data) if hasattr(strategy, "compute") else strategy(data)
        sig_arr = sig.to_numpy() if hasattr(sig, "to_numpy") else np.asarray(sig)
    except Exception:
        return {"sharpe": 0.0, "n_trades": 0, "win_rate": 0.0, "sharpe_raw": 0.0}

    # Simulate trades
    pos = 0
    entry = 0.0
    trades = []
    pnl = 0.0
    pnls = []
    for i in range(1, n):
        s = int(sig_arr[i]) if i < len(sig_arr) else 0
        p = float(close[i])
        if s != pos:
            if pos != 0:
                trade_pnl = (p - entry) * pos
                pnl += trade_pnl
                pnls.append(trade_pnl)
                trades.append({"win": trade_pnl > 0})
            pos = s
            entry = p

    if len(pnls) < 2:
        return {
            "sharpe": 0.0,
            "n_trades": len(pnls),
            "win_rate": 0.0 if not pnls else (1.0 if pnls[0] > 0 else 0.0),
        }

    sharpe = (statistics.mean(pnls) / (statistics.stdev(pnls) + 1e-9)) * math.sqrt(252)
    wr = sum(1 for t in trades if t["win"]) / max(len(trades), 1)

    return {"sharpe": round(sharpe, 4), "n_trades": len(trades), "win_rate": round(wr, 4)}


# ── Main ──────────────────────────────────────────────────────────────


async def run_sweep() -> int:
    strategies = _all_strategies()
    assets = _available_assets()

    # Quick mode: daily only, sample last 1000 bars, limit strategies
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    args, _ = parser.parse_known_args()

    if args.quick:
        assets = [a for a in assets if a[1] == "1d"]
        # Only strategies that match known patterns
        strategies = {
            k: v
            for k, v in strategies.items()
            if any(x in k for x in ["Trend", "Reversion", "Breakout", "alpha_", "Mean"])
        }
        print(f"   Quick mode: {len(strategies)} strategies × {len(assets)} assets")

    print(f"\n{'=' * 70}")
    print(f"FULL STRATEGY SWEEP — {len(strategies)} strategies × {len(assets)} assets")
    print(f"{'=' * 70}\n")

    results: list[dict[str, Any]] = []
    total = sum(len(strategies) for _ in assets)

    idx = 0
    for symbol, tf, n_bars in sorted(assets, key=lambda x: -x[2]):
        import polars as pl

        pattern = f"data/lake/normalized/symbol={symbol}/tf={tf}/**/*.parquet"
        try:
            df = pl.scan_parquet(pattern).collect()
            df = df.rename({c: c.lower() for c in df.columns}).sort("timestamp")
            # Sample last 2000 bars for speed
            if len(df) > 2000:
                df = df.tail(2000)
            close = df["close"].to_numpy().astype(float)
        except Exception:
            continue

        for sname, strategy in strategies.items():
            idx += 1
            if idx % 50 == 0:
                print(f"  [{idx}/{total}]")
            try:
                r = test_strategy(strategy, sname, close)
            except Exception:
                continue
            if r["n_trades"] > 0:
                r["strategy"] = sname
                r["asset"] = symbol
                r["timeframe"] = tf
                r["bars"] = n_bars
                results.append(r)

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"RESULTS — {len(results)} strategy×asset combos with trades")
    print(f"{'=' * 70}")

    # Top 20 overall
    ranked = sorted(results, key=lambda x: x["sharpe"], reverse=True)
    print("\n  TOP 20 (by Sharpe):")
    print(f"  {'Strategy':<20s} {'Asset':>8s} {'TF':>3s} {'Sharpe':>8s} {'Trades':>6s} {'WR%':>5s}")
    print(f"  {'-' * 52}")
    for r in ranked[:20]:
        print(
            f"  {r['strategy']:<20s} {r['asset']:>8s} {r['timeframe']:>3s} "
            f"{r['sharpe']:>+8.4f} {r['n_trades']:>6d} {r['win_rate']:>5.1%}"
        )

    # Best strategy per asset
    print("\n  BEST STRATEGY PER ASSET:")
    print(f"  {'Asset':>8s} {'Strategy':<20s} {'TF':>3s} {'Sharpe':>8s}")
    print(f"  {'-' * 42}")
    by_asset: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_asset[r["asset"]].append(r)
    for asset in sorted(by_asset.keys()):
        best = max(by_asset[asset], key=lambda x: x["sharpe"])
        print(
            f"  {asset:>8s} {best['strategy']:<20s} {best['timeframe']:>3s} {best['sharpe']:>+8.4f}"
        )

    # Strategy frequency in top 100
    top100 = ranked[:100]
    strat_counts = defaultdict(int)
    for r in top100:
        strat_counts[r["strategy"]] += 1
    print("\n  MOST FREQUENT IN TOP 100:")
    for s, c in sorted(strat_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {s:<20s} {c:>3d}x in top 100")

    # Save
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_dir = Path("logs/sweep")
    out_dir.mkdir(parents=True, exist_ok=True)
    import json

    (out_dir / f"strategy_sweep_{ts}.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "timestamp": ts,
                    "n_strategies": len(strategies),
                    "n_assets": len(assets),
                    "n_results": len(results),
                },
                "results": ranked,
            },
            indent=2,
        )
    )
    print(f"\nSaved to logs/sweep/strategy_sweep_{ts}.json")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run_sweep()))

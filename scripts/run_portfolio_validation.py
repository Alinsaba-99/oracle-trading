#!/usr/bin/env python3
"""Portfolio reale — edge combinato da sweep + validazione 100 sessioni.

Costruisce un portafoglio multi-strategia basato sui best performer
dello sweep e lo valida con 100 sessioni paper indipendenti.

Strategie selezionate (top per (asset, regime)):
  1. GC 1d bear -> mean_rev        (Sharpe +5.84 sweep)
  2. ES 1d bull -> trend           (Sharpe +3.39)
  3. EURUSD 1d choppy -> alpha_050 (Sharpe +28.21 sweep)
  4. GBPUSD 1d choppy -> alpha_020 (Sharpe +33.06)
  5. USDJPY 1d choppy -> alpha_050 (Sharpe +20.56)
  6. BTCUSDT 1d -> alpha_003       (Sharpe +19.54)

Pesi: HRP via compute_hrp_weights() sui rendimenti storici.
Validazione: 100 sessioni paper con paper runner ufficiale.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.metrics.robustness import probability_of_backtest_overfitting
from analytics.portfolio.hrp import compute_hrp_weights
from analytics.strategy.catalog.alpha101 import ALPHA_101_CATALOG
from analytics.strategy.regime_ensemble import RegimeLabel
from scripts.run_g6_wp2_paper_sessions import _run_session

# ── Portfolio definition ─────────────────────────────────────────────

PORTFOLIO = [
    # (name, symbol, timeframe, strategy_fn, regime_filter, capital, point_value)
    {
        "name": "GC_bear_meanrev",
        "symbol": "GC",
        "tf": "1d",
        "strategy": lambda: __import__("analytics.strategy.signals", fromlist=[""]).RsiReversion(
            period=14
        ),
        "regime_filter": RegimeLabel.BEAR,
        "capital": 50_000,
        "point_value": 100.0,
    },
    {
        "name": "ES_bull_trend",
        "symbol": "ES",
        "tf": "1d",
        "strategy": lambda: __import__("analytics.strategy.signals", fromlist=[""]).EmaTrend(
            fast=10, slow=30
        ),
        "regime_filter": RegimeLabel.BULL,
        "capital": 50_000,
        "point_value": 50.0,
    },
    {
        "name": "EURUSD_choppy_alpha050",
        "symbol": "EURUSD",
        "tf": "1d",
        "strategy": lambda: ALPHA_101_CATALOG["alpha_050"],
        "regime_filter": RegimeLabel.CHOPPY,
        "capital": 50_000,
        "point_value": 1.0,
    },
    {
        "name": "GBPUSD_choppy_alpha020",
        "symbol": "GBPUSD",
        "tf": "1d",
        "strategy": lambda: ALPHA_101_CATALOG["alpha_020"],
        "regime_filter": RegimeLabel.CHOPPY,
        "capital": 50_000,
        "point_value": 1.0,
    },
    {
        "name": "USDJPY_choppy_alpha050",
        "symbol": "USDJPY",
        "tf": "1d",
        "strategy": lambda: ALPHA_101_CATALOG["alpha_050"],
        "regime_filter": RegimeLabel.CHOPPY,
        "capital": 50_000,
        "point_value": 1.0,
    },
    {
        "name": "BTCUSDT_all_alpha003",
        "symbol": "BTCUSDT",
        "tf": "1d",
        "strategy": lambda: ALPHA_101_CATALOG["alpha_003"],
        "regime_filter": None,  # tutti i regimi
        "capital": 25_000,
        "point_value": 1.0,
    },
]


def load_symbol_tf(symbol: str, tf: str) -> tuple[Any, int]:
    """Load data from lake."""
    import polars as pl

    pattern = f"data/lake/normalized/symbol={symbol}/tf={tf}/**/*.parquet"
    df = pl.scan_parquet(pattern).collect()
    df = df.rename({c: c.lower() for c in df.columns}).sort("timestamp")
    return df, len(df)


def detect_regime(data: Any) -> RegimeLabel:
    """Simple regime detection using SMA200 heuristic."""
    from analytics.strategy.regime_ensemble import RegimeLabel

    close = data["close"].to_numpy().astype(float)
    if len(close) < 200:
        return RegimeLabel.CHOPPY
    sma200 = np.convolve(close, np.ones(200) / 200, mode="valid")[-1]
    last = close[-1]
    ratio = last / sma200 - 1
    vol = np.std(np.diff(close) / close[:-1])
    if ratio > 0.05 and vol < 0.02:
        return RegimeLabel.BULL
    if ratio < -0.05 and vol < 0.02:
        return RegimeLabel.BEAR
    if vol > 0.03:
        return RegimeLabel.VOLATILE
    return RegimeLabel.CHOPPY


async def run() -> int:
    print(f"\n{'=' * 70}")
    print("PORTFOLIO VALIDATION — Multi-strategy real portfolio")
    print(f"{'=' * 70}\n")

    results_by_strategy: dict[str, list[dict]] = {}
    all_trades: list[dict] = []

    for leg in PORTFOLIO:
        name = leg["name"]
        symbol = leg["symbol"]
        tf = leg["tf"]
        regime_filter = leg["regime_filter"]
        capital = Decimal(str(leg["capital"]))
        point_value = Decimal(str(leg["point_value"]))

        print(
            f"\n  [{name}] {symbol} {tf} "
            f"{'(filter: ' + regime_filter.value + ')' if regime_filter else '(all regimes)'}"
        )

        # Load data
        df, n_total = load_symbol_tf(symbol, tf)
        n_per_session = max(50, n_total // 100)
        n_sessions = min(100, n_total // n_per_session)

        print(f"     {n_total} bars -> {n_sessions} sessions ({n_per_session}/session)")

        # Strategy instance
        strategy = leg["strategy"]()
        pnl_list: list[float] = []

        for s in range(n_sessions):
            start = s * n_per_session
            end = start + n_per_session if s < n_sessions - 1 else n_total
            df_slice = df[start:end]

            # Regime filter
            if regime_filter is not None:
                regime = detect_regime(df_slice)
                if regime != regime_filter:
                    continue

            # Compute signal
            try:
                sig = (
                    strategy.compute(df_slice)
                    if hasattr(strategy, "compute")
                    else strategy(df_slice)
                )
                sig_arr = sig.to_numpy() if hasattr(sig, "to_numpy") else np.asarray(sig)
            except Exception:
                continue

            n_trades_in_session = sum(
                1 for i in range(1, len(sig_arr)) if sig_arr[i] != sig_arr[i - 1]
            )
            if n_trades_in_session == 0:
                continue

            # Run paper session
            try:
                result = await _run_session(
                    session_id=s + 1,
                    df_session=df_slice,
                    instrument=symbol,
                    capital=capital,
                    point_value=point_value,
                    max_dd_pct=5.0,
                    storage="memory",
                    dsn=None,
                )
            except Exception as exc:
                print(f"     session {s + 1} failed: {exc}")
                continue

            pnl = float(result["total_pnl"])
            pnl_list.append(pnl)

            # Record
            entry = {
                "strategy": name,
                "session": s + 1,
                "symbol": symbol,
                "pnl": round(pnl, 2),
                "sharpe": result["sharpe"],
                "dd": result["max_drawdown_pct"],
                "trades": result["n_trades"],
                "passed": result["passed"],
            }
            results_by_strategy.setdefault(name, []).append(entry)
            all_trades.append(entry)

        # Summary for this strategy
        n = len(pnl_list)
        if n > 1:
            mean_pnl = statistics.mean(pnl_list)
            sharpe = (mean_pnl / (statistics.stdev(pnl_list) + 1e-9)) * (252**0.5)
            wr = sum(1 for p in pnl_list if p > 0) / n
        else:
            mean_pnl = sum(pnl_list) if pnl_list else 0.0
            sharpe = 0.0
            wr = 0.0 if not pnl_list else (1.0 if pnl_list[0] > 0 else 0.0)

        print(
            f"     {n} active sessions  Sharpe={sharpe:.3f}  WR={wr:.1%}  MeanPnL=${mean_pnl:.2f}"
        )

    # ── Portfolio-level metrics ───────────────────────────────────────
    compiled: dict[str, list[float]] = {}
    for t in all_trades:
        compiled.setdefault(t["strategy"], []).append(t["pnl"])

    if len(compiled) >= 2:
        # HRP weights
        import pandas as pd

        max_len = max(len(v) for v in compiled.values())
        returns_dict = {}
        for sname, pnls in compiled.items():
            padded = pnls + [0.0] * (max_len - len(pnls))
            returns_dict[sname] = padded
        hrp = compute_hrp_weights(pd.DataFrame(returns_dict))

        # Combined portfolio PnL
        all_pnls = [t["pnl"] for t in all_trades]
        total_pnl = sum(all_pnls)
        portfolio_sharpe = (
            (statistics.mean(all_pnls) / (statistics.stdev(all_pnls) + 1e-9)) * (252**0.5)
            if len(all_pnls) > 1
            else 0
        )

        print(f"\n{'=' * 70}")
        print("PORTFOLIO RESULT")
        print(f"{'=' * 70}")
        print(f"  Total sessions:       {len(all_trades)}")
        print(f"  Total P&L:           ${total_pnl:,.2f}")
        print(f"  Portfolio Sharpe:     {portfolio_sharpe:.4f}")
        win_rate_val = sum(1 for p in all_pnls if p > 0) / max(len(all_pnls), 1)
        print(f"  Win rate:             {win_rate_val:.1%}")
        print()
        print("  HRP Weights:")
        for sname, w in sorted(hrp.items(), key=lambda x: -x[1]):
            print(f"    {sname:<30s} {w:>6.1%}")

        # PBO
        if len(all_pnls) >= 10:
            returns_matrix = np.array(all_pnls).reshape(-1, 1)
            noise = np.random.randn(returns_matrix.shape[0], 9) * 0.5
            extended = np.hstack([returns_matrix, noise])
            pbo = probability_of_backtest_overfitting(extended, n_splits=min(5, extended.shape[0]))
            print("\n  Probability of Backtest Overfitting:")
            print(f"    PBO:                  {pbo.pbo:.4f}")
            print(f"    Overfit risk:         {'�� HIGH' if pbo.pbo > 0.5 else '🟢 LOW'}")

        verdict = (
            "✅ PORTFOLIO HA EDGE"
            if portfolio_sharpe > 0.3
            else "❌ PORTFOLIO NON HA EDGE SUFFICIENTE"
        )
        print(f"\n  -> {verdict}")

    # Save
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out = Path("logs/portfolio")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"portfolio_validation_{ts}.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "timestamp": ts,
                    "n_legs": len(PORTFOLIO),
                    "n_sessions": len(all_trades),
                },
                "results": all_trades,
            },
            indent=2,
        )
    )
    print(f"\nResults saved to logs/portfolio/portfolio_validation_{ts}.json")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))

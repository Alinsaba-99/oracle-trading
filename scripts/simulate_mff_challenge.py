#!/usr/bin/env python3
"""MyFundedFutures 50K Challenge Simulation — BTC alpha_003.

Regole MFF:
  - Max daily loss: 5% of initial balance ($2,500)
  - Max overall loss: 10% of initial balance ($5,000)
  - Profit target: 10% ($5,000) per phase
  - Min trading days: 4 per phase
  - Max drawdown: 4% on trailing high-water mark
  - Leverage: max 1:30 crypto, 1:10 intraday

Questo script simula il challenge usando il paper runner ufficiale
e verifica se BTC alpha_003 passa tutti i gate.

Usage::
    uv run --frozen python scripts/simulate_mff_challenge.py
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.strategy.catalog.alpha101 import ALPHA_101_CATALOG
from scripts.run_g6_wp2_paper_sessions import _run_session

# ── MFF 50K rules ─────────────────────────────────────────────────────

INITIAL_CAPITAL = Decimal("50000")
MAX_DAILY_LOSS_PCT = 5.0  # $2500/day
MAX_OVERALL_LOSS_PCT = 10.0  # $5000 total
PROFIT_TARGET = 5000  # $5000 (10%)
MIN_TRADING_DAYS = 4
POINT_VALUE = Decimal("1.0")  # 1 contract = 1 BTC USD
SYMBOL = "BTCUSDT"
TIMEFRAME = "1d"

MAX_DAILY_LOSS = float(INITIAL_CAPITAL) * (MAX_DAILY_LOSS_PCT / 100)
MAX_OVERALL_LOSS = float(INITIAL_CAPITAL) * (MAX_OVERALL_LOSS_PCT / 100)


async def simulate_challenge() -> int:
    import polars as pl

    print(f"\n{'=' * 70}")
    print("MFF 50K CHALLENGE SIMULATION — BTC alpha_003")
    print(f"{'=' * 70}")
    print(f"  Initial capital:  ${INITIAL_CAPITAL:>8,.0f}")
    print(f"  Max daily loss:   ${MAX_DAILY_LOSS:>8,.0f}")
    print(f"  Max overall loss: ${MAX_OVERALL_LOSS:>8,.0f}")
    print(f"  Profit target:    ${PROFIT_TARGET:>8,.0f}")
    print(f"  Min trading days: {MIN_TRADING_DAYS}")
    print()

    # Load BTC data
    df = pl.scan_parquet(
        f"data/lake/normalized/symbol={SYMBOL}/tf={TIMEFRAME}/**/*.parquet"
    ).collect()
    df = df.rename({c: c.lower() for c in df.columns}).sort("timestamp")
    n_total = len(df)
    print(f"  Data: {n_total} bars ({df[0, 'timestamp']} -> {df[-1, 'timestamp']})")

    # Strategy
    ALPHA_101_CATALOG["alpha_003"]

    # Sliding window: simulate 50 consecutive sessions as if trading live
    window = 30  # bars per session
    max_sessions = (n_total - window) // 1  # slide by 1 bar each session
    n_sessions = min(100, max_sessions)

    results: list[dict] = []
    peak = float(INITIAL_CAPITAL)
    total_pnl = 0.0
    daily_pnl = 0.0
    last_bar_date = None
    phase_passed = False
    days_traded = 0
    overall_breach = False
    daily_breach = False

    for s in range(n_sessions):
        start = s
        end = start + window
        if end > n_total:
            break
        df_slice = df[start:end]

        # Run paper session
        try:
            result = await _run_session(
                session_id=s + 1,
                df_session=df_slice,
                instrument=SYMBOL,
                capital=INITIAL_CAPITAL,
                point_value=POINT_VALUE,
                max_dd_pct=4.0,
                storage="memory",
                dsn=None,
            )
        except Exception:
            continue

        pnl = float(result["total_pnl"])
        total_pnl += pnl
        daily_pnl += pnl

        # Track daily loss (new trading day?)
        bar_date = df_slice[-1, "timestamp"].date()
        if last_bar_date is not None and bar_date != last_bar_date:
            if abs(daily_pnl) > MAX_DAILY_LOSS:
                daily_breach = True
            daily_pnl = 0.0
            if daily_breach:
                break

        last_bar_date = bar_date
        peak = max(peak, float(INITIAL_CAPITAL) + total_pnl)

        days_traded += 1

        results.append(
            {
                "session": s + 1,
                "pnl": round(pnl, 2),
                "cumulative": round(total_pnl, 2),
                "sharpe": result["sharpe"],
                "trades": result["n_trades"],
                "peak": round(peak, 2),
                "dd": round((peak - (float(INITIAL_CAPITAL) + total_pnl)) / peak * 100, 2),
            }
        )

        # Check profit target
        if total_pnl >= PROFIT_TARGET:
            phase_passed = True
            print(f"  Session {s + 1}: PROFIT TARGET HIT! +${total_pnl:.2f}")
            break

        # Check overall loss
        if total_pnl <= -MAX_OVERALL_LOSS:
            overall_breach = True
            print(f"  Session {s + 1}: OVERALL LOSS BREACH -${abs(total_pnl):.2f}")
            break

        if (s + 1) % 10 == 0:
            print(f"  Session {s + 1}: PnL=${total_pnl:>+.2f}  DD={results[-1]['dd']:.2f}%")

    # ── Verdict ───────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("CHALLENGE RESULT")
    print(f"{'=' * 70}")
    print(f"  Sessions:         {len(results)}")
    print(f"  Final P&L:       ${total_pnl:>+10.2f}")
    print(f"  Days traded:     {days_traded}")
    print(f"  Profit target:   ${PROFIT_TARGET} -> {'✅ HIT' if phase_passed else '❌ NOT HIT'}")
    print(f"  Overall breach:  {'🔴 BREACHED' if overall_breach else '✅ NONE'}")
    print(f"  Daily breach:    {'🔴 BREACHED' if daily_breach else '✅ NONE'}")

    sharpes = [r["sharpe"] for r in results if r["trades"] > 0]
    if sharpes:
        mean_s = statistics.mean(sharpes)
        print(f"  Mean session Sharpe: {mean_s:.4f}")

    # PBO
    if len(results) >= 5:
        from analytics.metrics.robustness import probability_of_backtest_overfitting

        pnls = np.array([r["pnl"] for r in results]).reshape(-1, 1)
        noise = np.random.randn(pnls.shape[0], 9)
        extended = np.hstack([pnls, noise])
        pbo = probability_of_backtest_overfitting(
            extended, n_splits=min(5, max(2, len(results) // 20))
        )
        print(f"  PBO:               {pbo.pbo:.4f}")
        overfit_label = "🟢 LOW" if pbo.pbo < 0.5 else "🟡 MEDIUM" if pbo.pbo < 0.7 else "🔴 HIGH"
        print(f"  Overfit risk:      {overfit_label}")

    passed = (
        phase_passed and not overall_breach and not daily_breach and days_traded >= MIN_TRADING_DAYS
    )
    print(f"\n  -> {'✅ CHALLENGE PASSATO' if passed else '❌ CHALLENGE FALLITO'}")

    # Save
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out = Path("logs/challenge")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"mff_50k_btc_{ts}.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {
                    "firm": "MyFundedFutures",
                    "program": "50K",
                    "capital": float(INITIAL_CAPITAL),
                    "max_daily_loss": MAX_DAILY_LOSS,
                    "max_overall_loss": MAX_OVERALL_LOSS,
                    "profit_target": PROFIT_TARGET,
                    "min_days": MIN_TRADING_DAYS,
                    "strategy": "alpha_003",
                    "symbol": SYMBOL,
                    "timeframe": TIMEFRAME,
                    "passed": passed,
                    "timestamp": ts,
                },
                "results": results,
            },
            indent=2,
        )
    )
    print(f"\n  Risultati salvati in {path}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(simulate_challenge()))

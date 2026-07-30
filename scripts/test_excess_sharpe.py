#!/usr/bin/env python3
"""Excess Sharpe — edge vs buy-and-hold benchmark.

Testa ogni strategia contro il benchmark buy-and-hold sullo stesso
periodo out-of-sample.  Se excess Sharpe > 0, l'edge è reale.
Se <= 0, era solo esposizione al mercato (beta).
"""

from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.backtest.cv import WalkForward
from analytics.strategy.catalog.alpha101 import ALPHA_101_CATALOG

CANDIDATES = [
    {
        "name": "BTC_alpha003",
        "symbol": "BTCUSDT",
        "tf": "1d",
        "strategy_fn": lambda: ALPHA_101_CATALOG["alpha_003"],
        "point_value": 1.0,
        "spread_bps": 5,
        "slippage_bps": 3,
        "commission_pct": 0.001,
    },
    {
        "name": "EURUSD_alpha050",
        "symbol": "EURUSD",
        "tf": "1d",
        "strategy_fn": lambda: ALPHA_101_CATALOG["alpha_050"],
        "point_value": 1.0,
        "spread_bps": 1,
        "slippage_bps": 0.5,
        "commission_pct": 0.0,
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
        "commission_pct": 0.001,
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


def buy_hold_sharpe(close: np.ndarray) -> float:
    """Annualised Sharpe of buy-and-hold."""
    rets = np.diff(close) / close[:-1]
    if np.std(rets) == 0:
        return 0.0
    return float(np.mean(rets) / np.std(rets) * np.sqrt(252))


def strategy_sharpe(
    close: np.ndarray,
    strategy: object,
    spread_bps: float,
    slippage_bps: float,
    commission_pct: float,
) -> tuple[float, int]:
    """Annualised Sharpe of strategy on this slice."""
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
        return 0.0, 0

    pos = 0
    entry = 0.0
    cost_per = (spread_bps + slippage_bps) / 10000
    pnls = []
    for i in range(1, len(close)):
        s = int(sig_arr[i])
        p = float(close[i])
        if s != pos:
            if pos != 0:
                gross = (p - entry) * pos
                costs = cost_per * abs(pos) + abs(gross) * commission_pct
                pnls.append(gross - costs)
            pos = s
            entry = p

    if len(pnls) < 3:
        return 0.0, len(pnls)

    return (statistics.mean(pnls) / (statistics.stdev(pnls) + 1e-9)) * math.sqrt(252), len(pnls)


def main() -> int:
    print(f"\n{'=' * 70}")
    print("EXCESS SHARPE — Edge vs Buy-and-Hold Benchmark")
    print(f"{'=' * 70}")
    print()
    print("  Il test: per ogni fold walk-forward, calcola lo Sharpe")
    print("  della strategia e lo Sharpe del buy-and-hold.")
    print("  Excess Sharpe < 0 significa che la strategia non batte")
    print("  semplicemente comprare e tenere l'asset.")
    print()

    for cand in CANDIDATES:
        name = cand["name"]
        symbol = cand["symbol"]
        strategy = cand["strategy_fn"]()

        close = load(symbol, cand["tf"])
        if close is None or len(close) < 500:
            print(f"  {name}: ❌ dati insufficienti\n")
            continue

        n = len(close)
        test_size = max(50, n // 9)
        train_size = test_size * 3
        wf = WalkForward(test_size=test_size, train_size=train_size, expanding=True)

        strat_sharpes = []
        bh_sharpes = []
        excess_sharpes = []
        fold_trades = []

        for i, split in enumerate(wf.split(n)):
            if i >= 6:
                break
            test = close[split.test_idx]
            if len(test) < 30:
                continue

            s_sharpe, n_trades = strategy_sharpe(
                test, strategy, cand["spread_bps"], cand["slippage_bps"], cand["commission_pct"]
            )
            b_sharpe = buy_hold_sharpe(test)

            strat_sharpes.append(s_sharpe)
            bh_sharpes.append(b_sharpe)
            excess_sharpes.append(s_sharpe - b_sharpe)
            fold_trades.append(n_trades)

        if not strat_sharpes:
            print(f"  {name}: ❌ nessun fold valido\n")
            continue

        m_s = statistics.mean(strat_sharpes)
        m_b = statistics.mean(bh_sharpes)
        m_e = statistics.mean(excess_sharpes)
        pos_excess = sum(1 for e in excess_sharpes if e > 0)

        print(f"  [{name}] {symbol} {cand['tf']}")
        print(f"    Fold testati:     {len(strat_sharpes)}")
        print(f"    Trade medi/fold:  {statistics.mean(fold_trades):.0f}")
        print()
        print(f"    Sharpe strategia: {m_s:>+8.3f}")
        print(f"    Sharpe buy-hold:  {m_b:>+8.3f}")
        print(f"    Excess Sharpe:    {m_e:>+8.3f}")
        print(f"    Fold excess > 0:  {pos_excess}/{len(excess_sharpes)}")
        print()

        abs_edge = m_e > 0.3 and pos_excess / len(excess_sharpes) > 0.5
        tag = "ALPHA REALE" if abs_edge else "SOLO BETA"
        verdict = f"    -> {tag}"
        print(verdict)
        print()

        # Explain why
        if m_e <= 0:
            print("    Perche': la strategia long-biased approfitta del trend rialzista")
            print(f"    di {symbol}, ma non fa meglio di buy-and-hold. L'alpha e' negativo.")
            if symbol == "BTCUSDT":
                print("    BTC e' salito +100x dal 2017 — qualsiasi long fa +Sharpe.")
            elif symbol in ("EURUSD", "GBPUSD"):
                print("    FX ha rendimenti buy-hold vicini a 0, quindi anche un piccolo")
                print("    profitto si traduce in excess Sharpe positivo.")
        print()

    return 0


if __name__ == "__main__":
    main()

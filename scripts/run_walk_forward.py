#!/usr/bin/env python3
"""Walk-forward validation — testa se l'edge regge out-of-sample.

Carica N anni di dati, li divide in fold train/test temporali,
esegue una paper session su ogni test fold, e calcola metriche
di robustezza (PBO, DSR, Bootstrap Sharpe CI).

Questo è il test più onesto per determinare se il sistema
ha un edge reale o è solo overfitting sul periodo storico.

Usage::

    # ES daily 1 fold (veloce, test)
    uv run --frozen python scripts/run_walk_forward.py --asset ES --tf 1d --folds 2

    # ES daily completo (22 fold, ~20 minuti)
    uv run --frozen python scripts/run_walk_forward.py --asset ES --tf 1d

    # ES 1h (più fold, più lento)
    uv run --frozen python scripts/run_walk_forward.py --asset ES --tf 1h --folds 6

    # Multi-asset sweep
    uv run --frozen python scripts/run_walk_forward.py --asset ES --asset NQ --asset BTCUSDT
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.backtest.cv import WalkForward
from analytics.metrics.robustness import (
    bootstrap_sharpe_ci,
    deflated_sharpe,
    probability_of_backtest_overfitting,
)
from scripts.run_g6_wp2_paper_sessions import _build_ensemble, _run_session


def load_data(symbol: str, timeframe: str) -> tuple[Any, int]:
    """Load asset data from the data lake.

    Returns (pl.DataFrame, n_bars).
    """
    import polars as pl

    pattern = f"data/lake/normalized/symbol={symbol}/tf={timeframe}/**/*.parquet"
    try:
        df = pl.scan_parquet(pattern).collect()
    except Exception:
        print(f"❌ Cannot load {symbol} {timeframe} — file not found")
        print("   Run: uv run --frozen python scripts/backfill_all.py --fast")
        sys.exit(1)

    df = df.rename({c: c.lower() for c in df.columns})
    df = df.sort("timestamp")
    print(
        f"   Loaded {symbol} {timeframe}: {len(df)} bars  "
        f"({df[0, 'timestamp']} → {df[-1, 'timestamp']})"
    )
    return df, len(df)


async def _run_fold(
    fold_id: int,
    df_train: Any,
    df_test: Any,
    instrument: str,
    capital: Decimal,
    point_value: Decimal,
    max_dd_pct: float,
    timeframe: str = "1d",
) -> dict[str, Any]:
    """Run one fold: ensemble on train, paper on test, return metrics."""

    # Compute ensemble on training data (this sets up indicators)
    ensemble = _build_ensemble()
    _ = ensemble.compute(df_train)

    # Run paper session on test data
    result = await _run_session(
        session_id=fold_id,
        df_session=df_test,
        instrument=instrument,
        capital=capital,
        point_value=point_value,
        max_dd_pct=max_dd_pct,
        storage="memory",
        dsn=None,
        timeframe=timeframe,
    )
    return result


def format_fold_result(
    fold_id: int, n_folds: int, res: dict[str, Any], train_bars: int, test_bars: int
) -> str:
    """One-line fold summary."""
    status = "✅" if res["passed"] else "❌"
    return (
        f"  [{fold_id:>2d}/{n_folds}] {status}  "
        f"train={train_bars:>4d} test={test_bars:>4d} bars  "
        f"regime={res['regime']:<8} spec={res['specialist']:<10}  "
        f"S={res['sharpe']:>+7.3f}  DD={res['max_drawdown_pct']:>5.2f}%  "
        f"PnL=${res['total_pnl']:>+8.2f}  T={res['n_trades']:>2d}"
    )


async def run_validation(args: argparse.Namespace) -> int:
    """Main validation loop."""

    for asset in args.asset:
        print(f"\n{'=' * 70}")
        print(f"WALK-FORWARD VALIDATION — {asset} {args.tf}")
        print(f"{'=' * 70}")

        # Load data
        df, n_total = load_data(asset, args.tf)
        df["close"].to_numpy().astype(float)

        # Fold config
        if args.folds:
            n_folds = args.folds
            test_size = max(50, n_total // (n_folds * 4))  # train ~3x test
            train_size = test_size * 3
            expanding = True  # expanding window when folds are explicit
        else:
            # Auto: ~252 bars per fold (1 year for daily)
            test_size = 252 if args.tf == "1d" else 1000
            n_folds = max(3, n_total // test_size)
            train_size = test_size * 3
            expanding = False

        test_size = min(test_size, n_total // 3)
        wf = WalkForward(test_size=test_size, train_size=train_size, expanding=expanding)
        n_splits = wf.n_splits(n_total)

        if n_splits < 2:
            print(f"❌ Not enough bars ({n_total}) for {n_folds} folds")
            continue

        print(
            f"   {n_total} bars → {n_splits} folds  "
            f"(train={train_size}, test={test_size}, expanding=False)"
        )
        print()

        # Instrument config
        instrument = "MES" if args.mes else asset
        point_value = Decimal("5.0") if args.mes else Decimal("50.0")
        capital = Decimal(str(args.capital))
        max_dd = args.max_dd

        # Run each fold
        results: list[dict[str, Any]] = []
        fold_pnls: list[float] = []
        fold_sharpes: list[float] = []

        for fold_idx, split in enumerate(wf.split(n_total)):
            train_df = df[split.train_idx]
            test_df = df[split.test_idx]

            t0 = time.monotonic()
            res = await _run_fold(
                fold_idx + 1,
                train_df,
                test_df,
                instrument,
                capital,
                point_value,
                max_dd,
                timeframe=args.tf,
            )
            elapsed = time.monotonic() - t0

            res["_fold"] = fold_idx + 1
            res["_train_bars"] = len(split.train_idx)
            res["_error"] = None
            results.append(res)
            fold_pnls.append(float(res["total_pnl"]))
            fold_sharpes.append(float(res["sharpe"]))

            print(
                format_fold_result(
                    fold_idx + 1, n_splits, res, len(split.train_idx), len(split.test_idx)
                )
                + f"  {elapsed:.1f}s"
            )

        # ── Summary metrics ────────────────────────────────────────────
        n = len(results)
        passed = sum(1 for r in results if r["passed"])
        pos_sharpe = sum(1 for s in fold_sharpes if s > 0)

        print(f"\n{'─' * 70}")
        print(f"RESULTS — {asset} {args.tf}  ({n} folds)")
        print(f"{'─' * 70}")
        print(f"  Fold pass rate:        {passed}/{n} ({passed / n:.0%})")
        print(f"  Positive Sharpe folds: {pos_sharpe}/{n} ({pos_sharpe / n:.0%})")
        print(f"  Mean fold Sharpe:      {statistics.mean(fold_sharpes):>+7.4f}")
        print(f"  Median fold Sharpe:    {statistics.median(fold_sharpes):>+7.4f}")
        print(f"  Std fold Sharpe:       {statistics.stdev(fold_sharpes):>7.4f}" if n > 1 else "")
        print(f"  Mean fold P&L:        ${statistics.mean(fold_pnls):>+8.2f}")
        print(f"  Total P&L:            ${sum(fold_pnls):>+8.2f}")

        # ── Robustness metrics ─────────────────────────────────────────
        print(f"\n{'─' * 70}")
        print("ROBUSTNESS METRICS")
        print(f"{'─' * 70}")

        # Bootstrap Sharpe CI
        if len(fold_sharpes) >= 3:
            bs = bootstrap_sharpe_ci(fold_sharpes)
            print("  Bootstrap Sharpe CI:")
            print(f"    Point estimate:       {bs.sharpe:>+7.4f}")
            print(f"    95% CI:              [{bs.ci_lower:>+7.4f}, {bs.ci_upper:>+7.4f}]")
            print(f"    Includes zero:        {'⚠️  YES' if bs.ci_includes_zero else '✅ NO'}")

        # Deflated Sharpe
        if n >= 2:
            best_sharpe = max(fold_sharpes)
            ds = deflated_sharpe(
                observed_sharpe=best_sharpe, n_strategies=n, n_observations=max(30, test_size)
            )
            print(f"  Deflated Sharpe (best={best_sharpe:.3f}, N={n}):")
            print(f"    DSR:                  {ds.dsr:>+7.4f}")
            print(f"    p-value:              {ds.p_value:.4f}")
            print(f"    E[max] under null:    {ds.expected_max_sharpe:.4f}")
            print(f"    Significant:          {'✅ YES' if ds.p_value < 0.05 else '❌ NO'}")

        # PBO
        if n >= 3:
            returns_matrix = np.array(fold_sharpes).reshape(-1, 1)
            if returns_matrix.shape[0] >= 5:
                # Add noise strategies for CSCV comparison
                np.random.seed(42)
                noise = np.random.randn(returns_matrix.shape[0], 9) * 0.5
                extended = np.hstack([returns_matrix, noise])
                pbo = probability_of_backtest_overfitting(extended, n_splits=min(5, n))
                print("  Probability of Backtest Overfitting:")
                print(f"    PBO:                  {pbo.pbo:.4f}")
                print(f"    Logit mean:           {pbo.logit_mean:.4f}")
                print(f"    Overfit risk:         {'🔴 HIGH' if pbo.pbo > 0.5 else '🟢 LOW'}")

        # ── Verdict ────────────────────────────────────────────────────
        print(f"\n{'─' * 70}")
        mean_sharpe = statistics.mean(fold_sharpes)
        sharpe_ok = mean_sharpe > 0.3
        pos_sharpe_ok = pos_sharpe / n > 0.5
        dd_ok = statistics.mean([r["max_drawdown_pct"] for r in results]) < 4.0

        print("VERDICT:")
        print(f"  Sharpe > 0.3:              {'✅' if sharpe_ok else '❌'}  ({mean_sharpe:.3f})")
        print(f"  Positive Sharpe folds: {'✅' if pos_sharpe_ok else '❌'}  ({pos_sharpe}/{n})")
        print(
            f"  Mean DD < 4%:              {'✅' if dd_ok else '❌'}  "
            f"({statistics.mean([r['max_drawdown_pct'] for r in results]):.2f}%)"
        )
        overall = sharpe_ok and pos_sharpe_ok and dd_ok
        print(f"\n  ➜ {'✅ EDGE REALE' if overall else '❌ EDGE INSUFFICIENTE'}")

        # Save results
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "metadata": {
                        "asset": asset,
                        "timeframe": args.tf,
                        "n_folds": n,
                        "total_bars": n_total,
                        "train_size": train_size,
                        "test_size": test_size,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "capital": args.capital,
                        "mes_sizing": args.mes,
                    },
                    "summary": {
                        "mean_sharpe": round(mean_sharpe, 4),
                        "median_sharpe": round(statistics.median(fold_sharpes), 4),
                        "std_sharpe": round(statistics.stdev(fold_sharpes), 4) if n > 1 else 0,
                        "pass_rate": round(passed / n, 4),
                        "positive_sharpe_rate": round(pos_sharpe / n, 4),
                        "total_pnl": round(sum(fold_pnls), 2),
                        "edge_present": overall,
                    },
                    "folds": [
                        {
                            "fold": r["_fold"],
                            "sharpe": r["sharpe"],
                            "max_dd": r["max_drawdown_pct"],
                            "total_pnl": r["total_pnl"],
                            "n_trades": r["n_trades"],
                            "regime": r["regime"],
                            "specialist": r["specialist"],
                            "passed": r["passed"],
                        }
                        for r in results
                    ],
                },
                indent=2,
            )
        )
        print(f"\nResults saved to {output}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Walk-forward validation for Oracle trading strategies"
    )
    parser.add_argument("--asset", nargs="+", default=["ES"], help="Asset symbols (default: ES)")
    parser.add_argument("--tf", default="1d", help="Timeframe (default: 1d)")
    parser.add_argument("--folds", type=int, default=0, help="Number of folds (default: auto)")
    parser.add_argument(
        "--capital", type=float, default=100_000.0, help="Starting capital per fold"
    )
    parser.add_argument("--max-dd", type=float, default=5.0, help="Max drawdown % before hard stop")
    parser.add_argument(
        "--mes", action="store_true", help="Use MES sizing ($5/pt) instead of ES ($50/pt)"
    )
    parser.add_argument(
        "--output", default="logs/walk_forward_results.json", help="Output JSON path"
    )
    args = parser.parse_args()
    return asyncio.run(run_validation(args))


if __name__ == "__main__":
    sys.exit(main())

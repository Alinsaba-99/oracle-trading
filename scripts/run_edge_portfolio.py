"""BL-200 Edge Portfolio — explore edge candidates on ES daily.

Output: `logs/edge_portfolio.json` with per-strategy metrics + ranking.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from analytics.backtest.challenge import ChallengeSimulator
from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines.vectorized import VectorizedEngine
from analytics.backtest.metrics import MetricsCalculator
from analytics.strategy.signals import (
    BbandReversion,
    DonchianBreakout,
    EmaTrend,
    KeltnerReversion,
    RocMomentum,
    RsiReversion,
    TrendFilteredBreakout,
    ZscoreReversion,
)
from policy.prop_firm.fixtures import TOPSTEP_TC_50K

CANDIDATES: dict[str, tuple[type, dict]] = {
    "ema_trend_10_30": (EmaTrend, {"fast": 10, "slow": 30}),
    "ema_trend_20_50": (EmaTrend, {"fast": 20, "slow": 50}),
    "ema_trend_50_200": (EmaTrend, {"fast": 50, "slow": 200}),
    "donchian_breakout_10": (DonchianBreakout, {"period": 10}),
    "donchian_breakout_20": (DonchianBreakout, {"period": 20}),
    "donchian_breakout_50": (DonchianBreakout, {"period": 50}),
    "trend_filtered_breakout_20_200": (TrendFilteredBreakout, {"period": 20, "ma_period": 200}),
    "rsi_reversion_14_30_55": (RsiReversion, {"period": 14, "oversold": 30.0, "exit_level": 55.0}),
    "rsi_reversion_7_25_50": (RsiReversion, {"period": 7, "oversold": 25.0, "exit_level": 50.0}),
    "bollinger_20_2": (BbandReversion, {"period": 20, "std": 2.0}),
    "bollinger_30_2.5": (BbandReversion, {"period": 30, "std": 2.5}),
    "keltner_20_2": (KeltnerReversion, {"period": 20, "mult": 2.0}),
    "zscore_20_2": (ZscoreReversion, {"period": 20, "entry_z": 2.0}),
    "zscore_30_2.5": (ZscoreReversion, {"period": 30, "entry_z": 2.5}),
    "roc_momentum_12": (RocMomentum, {"period": 12}),
    "roc_momentum_21": (RocMomentum, {"period": 21}),
}


def load_es(path: Path) -> pl.DataFrame:
    raw = pl.read_parquet(path)
    rename = {
        c: c.lower()
        for c in raw.columns
        if c.strip().lower() in ("open", "high", "low", "close", "volume", "date", "timestamp")
    }
    for col in raw.columns:
        low = col.strip().lower()
        if low in ("date", "timestamp"):
            rename[col] = "timestamp"
    df = raw.rename(rename)
    if "timestamp" in df.columns and df["timestamp"].dtype != pl.Datetime:
        df = df.with_columns(pl.col("timestamp").cast(pl.Datetime))
    return df.sort("timestamp")


def run_challenge(equity: list[float], start_date: date) -> dict:
    sim = ChallengeSimulator(TOPSTEP_TC_50K, TOPSTEP_TC_50K.account_size)
    n = len(equity)
    if n < 2:
        return {
            "passed": False,
            "status": "insufficient_data",
            "max_dd_pct": 0.0,
            "days_elapsed": 0,
        }
    dates = [start_date + timedelta(days=i) for i in range(n)]
    result = sim.run(equity, dates)
    return {
        "passed": result.passed,
        "status": result.status.value,
        "total_return": result.total_return,
        "max_dd_pct": result.max_drawdown_pct,
        "days_elapsed": result.days_elapsed,
        "target_hit": result.target_hit,
        "failure_reason": result.failure_reason,
    }


def monte_carlo_pass_rate(equity_curve: list[float], n_sims: int = 100, seed: int = 42) -> float:
    """Bootstrap: shuffle the per-bar return series and re-run the challenge."""
    import random

    if len(equity_curve) < 30:
        return 0.0
    initial = equity_curve[0]
    rets = [
        (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
        for i in range(1, len(equity_curve))
    ]
    rng = random.Random(seed)
    passes = 0
    for _ in range(n_sims):
        shuffled = rets[:]
        rng.shuffle(shuffled)
        new_curve = [initial]
        for r in shuffled:
            new_curve.append(new_curve[-1] * (1 + r))
        sim = ChallengeSimulator(TOPSTEP_TC_50K, initial)
        n = len(new_curve)
        start = date(2025, 1, 1)
        dates = [start + timedelta(days=i) for i in range(n)]
        if sim.run(new_curve, dates).passed:
            passes += 1
    return passes / n_sims


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/ohlcv/ES_1d.parquet")
    parser.add_argument("--output", default="logs/edge_portfolio.json")
    parser.add_argument("--initial-capital", type=float, default=TOPSTEP_TC_50K.account_size)
    parser.add_argument("--mc-sims", type=int, default=200)
    parser.add_argument("--split-train-pct", type=float, default=0.6)
    args = parser.parse_args()

    df = load_es(Path(args.data))
    if "close" not in df.columns:
        print("FATAL: no close column")
        return 1
    n = len(df)
    n_train = int(n * args.split_train_pct)
    train = df[:n_train]
    test = df[n_train:]
    print(f"Data: {n} bars; train {n_train}; test {n - n_train}")
    print(f"Train first/last close: {train['close'][0]:.2f} → {train['close'][-1]:.2f}")
    print(f"Test first/last close:  {test['close'][0]:.2f} → {test['close'][-1]:.2f}")
    start_date = date(2025, 1, 1)

    cfg = BacktestConfig(
        initial_capital=Decimal(str(args.initial_capital)), slippage_bps=3.0, commission_pct=0.0005
    )
    engine = VectorizedEngine()
    mc = MetricsCalculator()
    results = []

    print(
        f"\n{'strategy':<32s} {'sharpe':>8s} {'dd%':>8s} {'pf':>6s} {'wr%':>6s} {'train_pass':>12s} {'test_pass':>11s} {'mc_pass%':>10s}"
    )
    print("-" * 110)
    for name, (cls, params) in CANDIDATES.items():
        sig = cls(**params)
        try:
            r_train = engine.run(train, sig, cfg)
            train_equity = engine.equity_curve().to_list()
        except Exception as e:
            print(f"{name:<32s} TRAIN ERROR: {e}")
            continue
        try:
            r_test = engine.run(test, sig, cfg)
            test_equity = engine.equity_curve().to_list()
        except Exception as e:
            print(f"{name:<32s} TEST ERROR:  {e}")
            continue

        train_ch = run_challenge(train_equity, start_date)
        test_ch = run_challenge(test_equity, start_date + timedelta(days=n_train))
        mc_pass = monte_carlo_pass_rate(test_equity, n_sims=args.mc_sims)

        results.append(
            {
                "strategy": name,
                "params": params,
                "train": {
                    "sharpe": r_train.sharpe_ratio,
                    "max_dd_pct": r_train.max_drawdown * 100,
                    "profit_factor": r_train.profit_factor,
                    "win_rate": r_train.win_rate,
                    "total_return": r_train.total_return,
                    "total_trades": r_train.total_trades,
                    "challenge_passed": train_ch["passed"],
                    "challenge_max_dd_pct": train_ch["max_dd_pct"],
                },
                "test": {
                    "sharpe": r_test.sharpe_ratio,
                    "max_dd_pct": r_test.max_drawdown * 100,
                    "profit_factor": r_test.profit_factor,
                    "win_rate": r_test.win_rate,
                    "total_return": r_test.total_return,
                    "total_trades": r_test.total_trades,
                    "challenge_passed": test_ch["passed"],
                    "challenge_max_dd_pct": test_ch["max_dd_pct"],
                },
                "mc_pass_rate_test": mc_pass,
            }
        )
        print(
            f"{name:<32s} "
            f"{r_train.sharpe_ratio:>8.3f} "
            f"{r_train.max_drawdown * 100:>8.2f} "
            f"{r_train.profit_factor:>6.2f} "
            f"{r_train.win_rate * 100:>6.1f} "
            f"{'PASS' if train_ch['passed'] else 'FAIL':>12s} "
            f"{'PASS' if test_ch['passed'] else 'FAIL':>11s} "
            f"{mc_pass * 100:>9.1f}%"
        )

    scored = sorted(
        results,
        key=lambda r: (
            (1 if r["test"]["challenge_passed"] else 0),
            r["mc_pass_rate_test"],
            r["test"]["sharpe"],
        ),
        reverse=True,
    )
    print(
        f"\n{'strategy':<32s} {'test_pass':>10s} {'mc_pass%':>10s} {'test_sharpe':>12s} {'test_dd%':>10s}"
    )
    print("-" * 80)
    for r in scored:
        print(
            f"{r['strategy']:<32s} "
            f"{'PASS' if r['test']['challenge_passed'] else 'FAIL':>10s} "
            f"{r['mc_pass_rate_test'] * 100:>9.1f}% "
            f"{r['test']['sharpe']:>12.3f} "
            f"{r['test']['max_dd_pct']:>10.2f}"
        )

    summary = {
        "metadata": {
            "data": args.data,
            "n_bars": n,
            "split_train_pct": args.split_train_pct,
            "initial_capital": args.initial_capital,
            "mc_sims": args.mc_sims,
            "timestamp": date.today().isoformat(),
        },
        "ranking": [
            {
                "strategy": r["strategy"],
                "test_passed": r["test"]["challenge_passed"],
                "mc_pass_rate": r["mc_pass_rate_test"],
                "test_sharpe": r["test"]["sharpe"],
                "test_dd_pct": r["test"]["max_dd_pct"],
                "test_pf": r["test"]["profit_factor"],
            }
            for r in scored
        ],
        "details": results,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nResults saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

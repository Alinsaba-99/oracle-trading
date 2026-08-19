"""Smoke test for LaneBBacktester with SimFin data.

Run: SIMFIN_API_KEY=... .venv/bin/python scripts/run_lane_b_backtest.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.fundamental.simfin_loader import SimFinLoader  # noqa: E402
from analytics.strategy.lane_b_backtester import LaneBBacktestConfig, LaneBBacktester  # noqa: E402


def main() -> int:
    api_key = os.environ.get("SIMFIN_API_KEY")
    if not api_key:
        print("FAIL: SIMFIN_API_KEY env var not set")
        return 1

    parser = argparse.ArgumentParser(description="Lane B backtest (BL-505b/c)")
    parser.add_argument("--start", default="2015-01-01", help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-12-31", help="Backtest end date (YYYY-MM-DD)")
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--rebalance-months", type=int, default=3)
    parser.add_argument("--top-n", type=int, default=15, help="Default 15 (v2; was 25 in v1)")
    parser.add_argument("--min-f-score", type=int, default=8, help="Default 8 (v2; was 7 in v1)")
    parser.add_argument("--magic-rank-max", type=int, default=50)
    parser.add_argument(
        "--return-12m-min",
        type=float,
        default=-0.10,
        help="Default -0.10 (v2; was -0.20 in v1 — tighter, no falling knife)",
    )
    parser.add_argument("--return-12m-max", type=float, default=0.50)
    parser.add_argument(
        "--benchmark-simfin-id",
        type=int,
        default=1072401,
        help="Default 1072401 = SPY ETF. Set 0 to disable benchmark.",
    )
    parser.add_argument(
        "--target-annual-vol",
        type=float,
        default=0.12,
        help="Target annualized volatility for position sizing (BL-505d/e)",
    )
    parser.add_argument(
        "--per-idea-stop-loss",
        type=float,
        default=0.20,
        help="Stop-loss per idea as fraction (BL-505d default 0.20 = -20% exits). Set 0 to disable.",
    )
    parser.add_argument("--output", default="docs/reports/lane-b/backtest_result.json")
    parser.add_argument("--report", default="docs/reports/lane-b/backtest_report.md")
    args = parser.parse_args()

    loader = SimFinLoader(api_key=api_key)
    config = LaneBBacktestConfig(
        initial_capital=args.capital,
        rebalance_months=args.rebalance_months,
        top_n_holdings=args.top_n,
        min_f_score=args.min_f_score,
        magic_rank_max=args.magic_rank_max,
        return_12m_min=args.return_12m_min,
        return_12m_max=args.return_12m_max,
        benchmark_simfin_id=args.benchmark_simfin_id if args.benchmark_simfin_id > 0 else None,
        target_annual_vol=args.target_annual_vol,
        per_idea_stop_loss_pct=args.per_idea_stop_loss if args.per_idea_stop_loss > 0 else None,
    )
    bt = LaneBBacktester(loader=loader, config=config)

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)
    print(f"Running Lane B backtest from {start.date()} to {end.date()}")
    print(
        f"Config: top_n={config.top_n_holdings}, min_f_score={config.min_f_score}, "
        f"return_12m_min={config.return_12m_min}, benchmark_spy={config.benchmark_simfin_id}"
    )
    print()

    result = bt.run(start_date=start, end_date=end)

    print(f"\n{'=' * 60}")
    print("Lane B Backtest Result")
    print(f"{'=' * 60}")
    print(f"Rebalances: {result.n_rebalances}")
    print(f"Holdings per rebalance: {result.n_holdings_per_rebalance}")
    print(f"Total return: {result.total_return:.2%}")
    print(f"Annual return: {result.annual_return:.2%}")
    print(f"Sharpe: {result.sharpe}")
    print(f"Max DD: {result.max_drawdown:.2%}")
    print(f"Unique tickers held: {result.n_unique_tickers}")
    print(f"Hit rate (positive-return rebalances): {result.hit_rate:.2%}")
    if result.benchmark_return is not None:
        print(f"Benchmark (SPY) return: {result.benchmark_return:.2%}")
        print(f"Alpha vs benchmark: {result.alpha_vs_benchmark:.2%}")

    # Save JSON
    output_dir = ROOT / "docs" / "reports" / "lane-b"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "config": {
            "initial_capital": config.initial_capital,
            "rebalance_months": config.rebalance_months,
            "top_n_holdings": config.top_n_holdings,
            "min_f_score": config.min_f_score,
            "magic_rank_max": config.magic_rank_max,
            "return_12m_min": config.return_12m_min,
            "return_12m_max": config.return_12m_max,
            "benchmark_simfin_id": config.benchmark_simfin_id,
        },
        "start": str(start.date()),
        "end": str(end.date()),
        "result": {
            "n_rebalances": result.n_rebalances,
            "n_holdings_per_rebalance": result.n_holdings_per_rebalance,
            "total_return": result.total_return,
            "annual_return": result.annual_return,
            "sharpe": result.sharpe,
            "max_drawdown": result.max_drawdown,
            "n_unique_tickers": result.n_unique_tickers,
            "hit_rate": result.hit_rate,
            "benchmark_return": result.benchmark_return,
            "alpha_vs_benchmark": result.alpha_vs_benchmark,
        },
    }
    output_path = output_dir / "backtest_result.json"
    output_path.write_text(json.dumps(payload, indent=2, default=str))

    # Markdown report
    md: list[str] = []
    md.append("# Lane B Backtest Report (BL-505c)\n\n")
    md.append("**Generated**: 2026-08-15\n")
    md.append(f"**Period**: {start.date()} → {end.date()}\n")
    md.append(
        f"**Config**: top_n={config.top_n_holdings}, min_f_score={config.min_f_score}, "
        f"return_12m_min={config.return_12m_min}, benchmark_spy={config.benchmark_simfin_id}\n\n"
    )
    md.append("## Summary\n\n")
    md.append(f"- Rebalances: {result.n_rebalances}\n")
    md.append(f"- Total return: {result.total_return:.2%}\n")
    md.append(f"- Annual return: {result.annual_return:.2%}\n")
    md.append(f"- Sharpe: {result.sharpe}\n")
    md.append(f"- Max DD: {result.max_drawdown:.2%}\n")
    md.append(f"- Unique tickers held: {result.n_unique_tickers}\n")
    md.append(f"- Hit rate: {result.hit_rate:.2%}\n")
    if result.benchmark_return is not None:
        md.append(f"- Benchmark (SPY) return: {result.benchmark_return:.2%}\n")
        md.append(f"- Alpha vs SPY: {result.alpha_vs_benchmark:.2%}\n")
    md.append(f"\n**Holdings per rebalance**: {result.n_holdings_per_rebalance}\n")
    (output_dir / "backtest_report.md").write_text("".join(md))

    print(f"\nResult saved to: {output_path}")
    print(f"Report saved to: {output_dir / 'backtest_report.md'}")
    return 0


if __name__ == "__main__":
    import argparse

    sys.exit(main())

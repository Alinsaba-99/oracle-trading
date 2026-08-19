"""Step 3 Opzione C — Composite Lane B vs Legacy AND backtest confronto.

Run LaneBBacktester.run() su SimFin real 185 tickers (cached in data/simfin/),
2020-01-01 → 2025-08-14, due config:
  1. legacy (use_composite=False, default AND screen: F>=8, magic<=50, -0.10<=ret<=0.50)
  2. composite (use_composite=True, weights 40% Piotroski + 40% Greenblatt + 20% Lakonishok,
     threshold 0.65)

Output: JSON + markdown report con confronto Sharpe / MaxDD / n_unique_tickers /
hit_rate / total_return / alpha_vs_spy per le due config.

Usage:
    uv run --env-file .env python scripts/run_lane_b_composite_compare.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    simfin_key = os.environ.get("SIMFIN_API_KEY", "")
    if not simfin_key:
        print("ERROR: SIMFIN_API_KEY not set")
        return 1

    from analytics.fundamental.simfin_loader import SimFinLoader
    from analytics.strategy.lane_b_backtester import LaneBBacktestConfig, LaneBBacktester

    loader = SimFinLoader(api_key=simfin_key)

    start = datetime(2020, 1, 1)
    end = datetime(2025, 8, 14)

    configs = [
        ("legacy", LaneBBacktestConfig(use_composite=False)),
        (
            "composite",
            LaneBBacktestConfig(
                use_composite=True,
                composite_threshold=0.65,
                composite_weights=(0.40, 0.40, 0.20),
                composite_return_band=(-0.20, 0.50),
            ),
        ),
    ]

    results: dict[str, dict[str, Any]] = {}
    for name, cfg in configs:
        print(f"\n{'=' * 70}\nLane B backtest: {name}\n{'=' * 70}")
        bt = LaneBBacktester(loader, cfg)
        try:
            res = bt.run(start_date=start, end_date=end)
        except Exception as exc:
            print(f"FAIL: {exc}")
            results[name] = {"error": str(exc)}
            continue
        results[name] = {
            "n_rebalances": res.n_rebalances,
            "n_holdings_per_rebalance": res.n_holdings_per_rebalance,
            "total_return": res.total_return,
            "annual_return": res.annual_return,
            "sharpe": res.sharpe,
            "max_drawdown": res.max_drawdown,
            "n_unique_tickers": res.n_unique_tickers,
            "hit_rate": res.hit_rate,
            "benchmark_return": res.benchmark_return,
            "alpha_vs_benchmark": res.alpha_vs_benchmark,
        }
        print(
            f"  n_rebalances={res.n_rebalances}, "
            f"holdings={[min(r, 99) for r in res.n_holdings_per_rebalance[:6]]}..."
        )
        print(f"  total_return={res.total_return:.4%}, annual={res.annual_return:.4%}")
        print(f"  sharpe={res.sharpe}, max_dd={res.max_drawdown:.4%}")
        print(f"  n_unique_tickers={res.n_unique_tickers}, hit_rate={res.hit_rate:.4%}")
        print(f"  benchmark={res.benchmark_return}, alpha={res.alpha_vs_benchmark}")

    # Save report
    out_dir = ROOT / "docs/reports/lane-b-composite"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y-%m-%d")
    json_path = out_dir / f"{ts}-compare.json"
    md_path = out_dir / f"{ts}-compare.md"

    json_path.write_text(json.dumps(results, indent=2, default=str))

    md: list[str] = []
    md.append("# Lane B Composite vs Legacy — Backtest confronto\n\n")
    md.append(f"**Generated**: {datetime.now(UTC).isoformat()}\n")
    md.append(f"**Period**: {start.date()} → {end.date()}\n")
    md.append("**Source**: SimFin bulk (cached `data/simfin/`)\n\n")

    md.append("## Confronto metriche\n\n")
    md.append("| Metric | Legacy AND | Composite |\n")
    md.append("|---|---|---|\n")
    keys = [
        "n_rebalances",
        "total_return",
        "annual_return",
        "sharpe",
        "max_drawdown",
        "n_unique_tickers",
        "hit_rate",
        "benchmark_return",
        "alpha_vs_benchmark",
    ]
    for k in keys:
        legacy_v = results.get("legacy", {}).get(k)
        comp_v = results.get("composite", {}).get(k)
        if isinstance(legacy_v, float) and abs(legacy_v) < 100:
            legacy_s = (
                f"{legacy_v:.4%}"
                if "return" in k or "drawdown" in k or "rate" in k
                else f"{legacy_v:.4f}"
            )
        else:
            legacy_s = str(legacy_v)
        if isinstance(comp_v, float) and abs(comp_v) < 100:
            comp_s = (
                f"{comp_v:.4%}"
                if "return" in k or "drawdown" in k or "rate" in k
                else f"{comp_v:.4f}"
            )
        else:
            comp_s = str(comp_v)
        md.append(f"| {k} | {legacy_s} | {comp_s} |\n")

    md.append("\n## Verdetto\n\n")
    legacy = results.get("legacy", {})
    composite = results.get("composite", {})
    if "error" in legacy or "error" in composite:
        md.append("One or both runs failed — see errors above.\n")
    else:
        ls = legacy.get("sharpe", 0) or 0
        cs = composite.get("sharpe", 0) or 0
        if cs > ls:
            md.append(
                f"**Composite Sharpe {cs:.3f} > Legacy {ls:.3f}** — adottare `use_composite=True` come default.\n"
            )
        else:
            md.append(
                f"**Legacy Sharpe {ls:.3f} ≥ Composite {cs:.3f}** — mantenere `use_composite=False` (legacy AND screen).\n"
            )
        cd = abs(composite.get("max_drawdown", 0))
        ld = abs(legacy.get("max_drawdown", 0))
        if cd < ld:
            md.append(f"Composite Max DD {cd:.2%} < Legacy {ld:.2%} — better risk-adjusted.\n")
        else:
            md.append(f"Composite Max DD {cd:.2%} ≥ Legacy {ld:.2%} — no DD improvement.\n")
        cu = composite.get("n_unique_tickers", 0)
        lu = legacy.get("n_unique_tickers", 0)
        md.append(f"Unique tickers: legacy {lu}, composite {cu} (composite should be >= legacy).\n")

    md_path.write_text("".join(md))
    print(f"\nJSON: {json_path}")
    print(f"Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

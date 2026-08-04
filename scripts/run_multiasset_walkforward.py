#!/usr/bin/env python3
"""BL-023 Fase 2 — multi-asset walk-forward CLI (see analytics/qualification/walkforward.py).

Usage:
    uv run --frozen python scripts/run_multiasset_walkforward.py
    uv run --frozen python scripts/run_multiasset_walkforward.py --signals donchian_breakout
    uv run --frozen python scripts/run_multiasset_walkforward.py --assets ES SPY BTCUSDT
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.qualification.walkforward import (
    EXPECTED_ROWS,
    REPORT_DIR,
    SIGNAL_FACTORY,
    TRAIN_CUTOFF,
    evaluate,
    format_markdown,
    format_row,
    load_frame,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--assets",
        nargs="+",
        default=["ES", "SPY", "BTCUSDT"],
        help="lake symbols to walk forward (default: ES SPY BTCUSDT)",
    )
    parser.add_argument(
        "--signals",
        nargs="+",
        default=list(SIGNAL_FACTORY),
        help="candidate signals (default: trend-family winners of Fase 5c)",
    )
    parser.add_argument("--output", type=Path, default=REPORT_DIR / "walkforward.json")
    parser.add_argument("--markdown-output", type=Path, default=REPORT_DIR / "walkforward.md")
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    for symbol in args.assets:
        if symbol not in EXPECTED_ROWS:
            print(f"FATAL: no row pin for {symbol} (add to EXPECTED_ROWS)")
            return 2
        df = load_frame(symbol)
        for signal_name in args.signals:
            if signal_name not in SIGNAL_FACTORY:
                print(f"FATAL: unknown signal {signal_name!r}")
                return 2
            result = evaluate(symbol, signal_name, df)
            results.append(result)
            print(format_row(result))

    # Per-signal multi-asset verdict: >= 2/3 assets confirm.
    verdicts: dict[str, Any] = {}
    any_survivor = False
    print(
        f"\n{'─' * 78}\nMULTI-ASSET VERDICT "
        f"(edge = S_test>=0.3 AND luck<0.1 AND S_test>BH_S)\n{'─' * 78}"
    )
    for signal_name in args.signals:
        rows = [r for r in results if r["signal"] == signal_name]
        confirmed = [r["symbol"] for r in rows if r["edge_confirmed"]]
        survives = len(confirmed) >= 2 and len(rows) >= 2
        any_survivor = any_survivor or survives
        mean_s = statistics.mean(r["sharpe_test"] for r in rows) if rows else 0.0
        print(
            f"  {signal_name:<24s} {'✅ SOPRAVVIVE' if survives else '❌ NON SOPRAVVIVE'}"
            f"  ({len(confirmed)}/{len(rows)} asset: {', '.join(confirmed) or 'nessuno'})"
            f"  mean S_test={mean_s:+.3f}"
        )
        verdicts[signal_name] = {
            "assets_confirmed": confirmed,
            "survives_multiasset": bool(survives),
            "mean_sharpe_test": round(mean_s, 4),
        }

    report = {
        "method": "multi-asset walk-forward, signal-level (long/flat, shift(1), no lookahead)",
        "train_cutoff": TRAIN_CUTOFF.isoformat(),
        "test_period": ">= 2023-01-01 (walk-forward proxy of the M31 gate windows)",
        "verdict_rule": (
            "edge confirmed = S_test>=0.3 AND luck_p<0.1 AND S_test>BH_S; survives = >=2/3 assets"
        ),
        "assets": args.assets,
        "signals": args.signals,
        "results": results,
        "verdicts": verdicts,
        "overall": {"any_signal_survives": bool(any_survivor)},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(format_markdown(report), encoding="utf-8")
    print(f"\nJSON report: {args.output}")
    print(f"MD report:   {args.markdown_output}")

    if args.require_pass and not any_survivor:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

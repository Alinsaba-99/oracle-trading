#!/usr/bin/env python3
"""BL-735 — Live paper tearsheet from the durable execution store.

Reads the equity curve from the BL-729 SQLite store (populated live by
the BL-730 runner) and renders a quantstats HTML tearsheet plus a ffn
stats block, re-using the BL-711 factory tearsheet renderer.

Usage::

    python scripts/paper_report.py --db data/paper/paper.db
    python scripts/paper_report.py --db data/paper/paper.db --out docs/reports/paper

Output: ``<out>/paper_tearsheet.html`` + a one-line console summary
(equity, return since inception, drawdown, fills, last heartbeat).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Oracle — live paper tearsheet (BL-735)")
    p.add_argument("--db", type=Path, default=Path("data/paper/paper.db"))
    p.add_argument("--out", type=Path, default=Path("docs/reports/paper"))
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    from analytics.research.factory.tearsheet import render_html_tearsheet
    from execution.store import ExecutionStore

    if not args.db.exists():
        print(f"error: store not found: {args.db}")
        return 1

    store = ExecutionStore(args.db)
    try:
        snapshots = store.equity_curve()
        stats = store.stats()
        last_hb = store.latest_heartbeat()
    finally:
        store.close()

    if not snapshots:
        print("error: no equity snapshots in store — is the runner (BL-730) running?")
        return 1

    equity = pd.Series({pd.Timestamp(s.ts): float(s.equity) for s in snapshots}).sort_index()
    args.out.mkdir(parents=True, exist_ok=True)
    out_html = args.out / "paper_tearsheet.html"
    render_html_tearsheet(equity, out_html, title="Oracle — Paper Trading (live)")

    total_ret = equity.iloc[-1] / equity.iloc[0] - 1.0
    dd = (equity / equity.cummax() - 1.0).min()
    print(f"tearsheet: {out_html}")
    print(
        f"snapshots={len(equity)} fills={stats.get('fills', 0)} "
        f"orders={stats.get('orders', 0)} | equity {equity.iloc[0]:,.0f} → "
        f"{equity.iloc[-1]:,.0f} ({total_ret:+.2%}), maxDD {dd:.2%}, "
        f"last heartbeat {last_hb.ts if last_hb else 'never'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

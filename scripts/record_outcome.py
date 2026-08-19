"""BL-506 — Record an outcome for a previously-registered thesis.

After a thesis is closed (exit reason: target_hit / stop_hit / time_stop /
invalidation / manual_close), record the outcome so the trial ledger can
compute hit rate and trigger alerts.

Usage:
    python scripts/record_outcome.py \\
        --thesis-id THESIS-2026-09-01-INTC-1 \\
        --exit-reason target_hit \\
        --entry-actual 20.0 \\
        --exit-actual 30.0 \\
        --pnl-pct 0.50 \\
        --pnl-amount 125.0 \\
        --bars-held 280
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.research.trial_ledger import TrialLedger  # noqa: E402

VALID_EXIT_REASONS = {"target_hit", "stop_hit", "time_stop", "invalidation", "manual_close"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Record an outcome for a Lane B thesis")
    parser.add_argument("--thesis-id", required=True)
    parser.add_argument(
        "--exit-reason",
        required=True,
        choices=sorted(VALID_EXIT_REASONS),
        help="One of: " + ", ".join(sorted(VALID_EXIT_REASONS)),
    )
    parser.add_argument("--entry-actual", type=float, default=None)
    parser.add_argument("--exit-actual", type=float, default=None)
    parser.add_argument("--pnl-pct", type=float, default=None)
    parser.add_argument("--pnl-amount", type=float, default=None)
    parser.add_argument("--bars-held", type=int, default=None)
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--db",
        default="data/trial_ledger.db",
        help="Path to trial_ledger.db (default data/trial_ledger.db)",
    )
    args = parser.parse_args()

    db_path = ROOT / args.db if not Path(args.db).is_absolute() else Path(args.db)
    ledger = TrialLedger(db_path=str(db_path))

    try:
        ledger.record_outcome(
            thesis_id=args.thesis_id,
            exit_reason=args.exit_reason,
            entry_actual=args.entry_actual,
            exit_actual=args.exit_actual,
            pnl_pct=args.pnl_pct,
            pnl_amount=args.pnl_amount,
            bars_held=args.bars_held,
            notes=args.notes,
        )
        print(f"\n✅ Outcome recorded for thesis: {args.thesis_id}")
        print(f"   exit_reason: {args.exit_reason}")
        if args.entry_actual is not None:
            print(f"   entry: ${args.entry_actual:.2f}  exit: ${args.exit_actual:.2f}")
        if args.pnl_pct is not None:
            print(
                f"   P&L: {args.pnl_pct:+.2%}"
                + (f" (${args.pnl_amount:+.2f})" if args.pnl_amount is not None else "")
            )
        if args.bars_held is not None:
            print(f"   bars held: {args.bars_held}")

        # Show updated hit rate
        hr = ledger.hit_rate()
        print(f"\n   Updated cumulative hit rate: {hr['hit_rate']:.1%}")
        print(f"   Outcomes recorded: {hr['n_with_outcome']}")
        return 0
    except ValueError as e:
        print(f"\n❌ Validation failed: {e}", file=sys.stderr)
        return 1
    finally:
        ledger.close()


if __name__ == "__main__":
    sys.exit(main())

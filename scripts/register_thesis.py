"""BL-506 — Register a turnaround thesis in the trial ledger.

Pre-registers the thesis BEFORE the trade is taken. The hash SHA-256
makes the registration tamper-evident (no HARKing after the fact).

Usage:
    python scripts/register_thesis.py \\
        --thesis-id THESIS-2026-09-01-INTC-1 \\
        --ticker INTC \\
        --entry-target 20.0 \\
        --stop-target 18.0 \\
        --target-price 30.0 \\
        --position-pct 0.025 \\
        --catalyst "Pat Gelsinger CEO turnaround + 18A process" \\
        --invalidation "CEO departure OR 18A delay >2Q OR GM<35%" \\
        --horizon-days 365 \\
        --f-score 7 \\
        --magic-rank 30 \\
        --return-12m -0.15 \\
        --notes "Operatore conosce prodotti Intel da quando ha memoria"

The script:
1. Validates the thesis fields (position_pct ≤ 5%, stop < entry, target > entry)
2. Writes to trial_ledger.db
3. Returns the pre_hash for tamper-evidence
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.research.trial_ledger import TrialLedger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a Lane B turnaround thesis")
    parser.add_argument("--thesis-id", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--entry-target", type=float, required=True)
    parser.add_argument("--stop-target", type=float, required=True)
    parser.add_argument("--target-price", type=float, required=True)
    parser.add_argument("--position-pct", type=float, required=True)
    parser.add_argument("--catalyst", required=True)
    parser.add_argument("--invalidation", required=True)
    parser.add_argument("--horizon-days", type=int, required=True)
    parser.add_argument("--f-score", type=int, default=None)
    parser.add_argument("--magic-rank", type=int, default=None)
    parser.add_argument("--return-12m", type=float, default=None)
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--db",
        default="data/trial_ledger.db",
        help="Path to trial_ledger.db (default data/trial_ledger.db)",
    )
    args = parser.parse_args()

    db_path = ROOT / args.db if not Path(args.db).is_absolute() else Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    ledger = TrialLedger(db_path=str(db_path))
    try:
        pre_hash = ledger.register_thesis(
            thesis_id=args.thesis_id,
            ticker=args.ticker,
            entry_target=args.entry_target,
            stop_target=args.stop_target,
            target_price=args.target_price,
            position_pct=args.position_pct,
            catalyst=args.catalyst,
            invalidation=args.invalidation,
            horizon_days=args.horizon_days,
            f_score=args.f_score,
            magic_rank=args.magic_rank,
            return_12m=args.return_12m,
            notes=args.notes,
        )
        print(f"\n✅ Thesis registered: {args.thesis_id}")
        print(f"   ticker: {args.ticker}")
        print(
            f"   entry: ${args.entry_target:.2f}  stop: ${args.stop_target:.2f}  target: ${args.target_price:.2f}"
        )
        print(f"   position_pct: {args.position_pct:.1%}  horizon: {args.horizon_days}d")
        print(f"   catalyst: {args.catalyst}")
        print(f"   invalidation: {args.invalidation}")
        print(f"\n   pre_hash (SHA-256): {pre_hash}")
        print(f"   db: {db_path}")
        return 0
    except ValueError as e:
        print(f"\n❌ Validation failed: {e}", file=sys.stderr)
        return 1
    finally:
        ledger.close()


if __name__ == "__main__":
    sys.exit(main())

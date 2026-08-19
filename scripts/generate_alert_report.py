"""BL-506b — Generate alert report for the trial ledger.

Prints a markdown report with:
- Cumulative hit rate over time
- Rolling hit rate (last 10 outcomes)
- Max consecutive failures
- Alerts (5 consecutive failures → warning; <30% cumulative after 20 outcomes → critical)
- Meta-kill rule status (50 outcomes < 30% → meta-kill triggered)

Usage:
    python scripts/generate_alert_report.py
    python scripts/generate_alert_report.py --db data/trial_ledger.db --output docs/reports/lane-b/alerts/2026-09.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.research.trial_ledger import TrialLedger  # noqa: E402
from analytics.research.trial_ledger_alerts import generate_alert_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate alert report for trial ledger")
    parser.add_argument(
        "--db",
        default="data/trial_ledger.db",
        help="Path to trial_ledger.db (default data/trial_ledger.db)",
    )
    parser.add_argument("--output", default=None, help="Output file (default: stdout)")
    parser.add_argument(
        "--consecutive-failure-threshold",
        type=int,
        default=5,
        help="Number of consecutive failures that triggers warning (default 5)",
    )
    parser.add_argument(
        "--cumulative-hit-rate-threshold",
        type=float,
        default=0.30,
        help="Cumulative hit rate below which critical alert triggers (default 0.30)",
    )
    parser.add_argument(
        "--cumulative-n-outcomes-threshold",
        type=int,
        default=20,
        help="Minimum outcomes before cumulative alert (default 20)",
    )
    args = parser.parse_args()

    db_path = ROOT / args.db if not Path(args.db).is_absolute() else Path(args.db)
    if not db_path.exists():
        print(f"❌ Trial ledger not found: {db_path}", file=sys.stderr)
        print("   Register a thesis first with scripts/register_thesis.py", file=sys.stderr)
        return 1

    ledger = TrialLedger(db_path=str(db_path))
    try:
        report = generate_alert_report(
            ledger,
            consecutive_failure_threshold=args.consecutive_failure_threshold,
            cumulative_hit_rate_threshold=args.cumulative_hit_rate_threshold,
            cumulative_n_outcomes_threshold=args.cumulative_n_outcomes_threshold,
        )
    finally:
        ledger.close()

    if args.output:
        out_path = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report)
        print(f"✅ Report saved to: {out_path}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Perpetual backfill runner for the Oracle data lake.

Runs the backfill plan in a continuous loop, sleeping between passes.
Each pass is resumable: already-completed entries are skipped instantly.
Failed entries are retried on the next pass.

Usage:
    python scripts/run_backfill.py                  # loop forever
    python scripts/run_backfill.py --once           # single pass, then exit
    python scripts/run_backfill.py --max-runtime 3600  # cap each pass at 1h
    python scripts/run_backfill.py --sleep 300         # 5 min between passes

Ctrl-C stops cleanly after the current fetch completes.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
import types

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("oracle.backfill")

_stop = False


def _handle_sigint(_sig: int, _frame: types.FrameType | None) -> None:
    global _stop
    logger.info("SIGINT received — will stop after current fetch")
    _stop = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit")
    parser.add_argument(
        "--max-runtime", type=float, default=None, help="Max seconds per pass (default: unlimited)"
    )
    parser.add_argument(
        "--sleep", type=float, default=60.0, help="Seconds to sleep between passes (default: 60)"
    )
    parser.add_argument(
        "--pause-between",
        type=float,
        default=0.5,
        help="Seconds between individual fetches within a pass",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_sigint)

    from market.ingestion.orchestrator import run_plan, status

    pass_num = 0
    while not _stop:
        pass_num += 1
        s = status()
        completed = len(s.get("completed", []))
        failed = len(s.get("failed", {}))
        logger.info("=== Pass %d start (completed=%d failed=%d) ===", pass_num, completed, failed)

        rc = run_plan(max_runtime_s=args.max_runtime, pause_between_s=args.pause_between)

        s = status()
        completed = len(s.get("completed", []))
        failed = len(s.get("failed", {}))
        logger.info(
            "=== Pass %d done rc=%d (completed=%d failed=%d) ===", pass_num, rc, completed, failed
        )

        if args.once or _stop:
            break

        if not _stop:
            logger.info("Sleeping %.0fs before next pass ...", args.sleep)
            for _ in range(int(args.sleep)):
                if _stop:
                    break
                time.sleep(1.0)

    logger.info("Backfill runner stopped after %d pass(es).", pass_num)
    return 0


if __name__ == "__main__":
    sys.exit(main())

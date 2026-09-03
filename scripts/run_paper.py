#!/usr/bin/env python3
"""BL-730 — Always-on paper trading runner entrypoint.

Wires :class:`execution.runner.PaperRunner` with the default
``LakePriceProvider`` and ``NoopSignalSource``, loads config from a
YAML file (see ``config/paper.yaml``), and runs until SIGTERM / SIGINT.

Usage::

    uv run python -u scripts/run_paper.py --config config/paper.yaml
    uv run python -u scripts/run_paper.py --symbols SPY,QQQ --db /tmp/p.db
    uv run python -u scripts/run_paper.py --config config/paper.yaml --max-cycles 10

Exit codes:
    0 — clean shutdown (SIGTERM / SIGINT / ``--max-cycles`` reached).
    2 — 3 consecutive cycle failures (a supervisor should restart).

The script is deliberately thin — every interesting decision lives in
``execution/runner.py``.  CLI args only override YAML fields; the YAML
file is the source of truth for production deploys.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logger = logging.getLogger("oracle.paper_runner")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Oracle — always-on paper runner")
    p.add_argument(
        "--config",
        type=Path,
        default=Path("config/paper.yaml"),
        help="Path to YAML config (default: config/paper.yaml).",
    )
    p.add_argument(
        "--db", type=Path, default=None, help="Override db_path (defaults to YAML / stores)."
    )
    p.add_argument(
        "--symbols", type=str, default=None, help="Comma-separated symbols (overrides YAML)."
    )
    p.add_argument(
        "--tick-interval",
        type=float,
        default=None,
        help="Tick interval in seconds (overrides YAML).",
    )
    p.add_argument(
        "--starting-cash", type=Decimal, default=None, help="Starting paper cash (overrides YAML)."
    )
    p.add_argument(
        "--max-cycles", type=int, default=None, help="Stop after N cycles (useful for smoke tests)."
    )
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


async def _run(args: argparse.Namespace) -> int:
    """Async entrypoint — separated so tests can re-use the runner directly."""
    from alerting import build_default_alerter
    from execution.runner import PaperRunner, PaperRunnerConfig

    # Build config from YAML; CLI flags override.
    if not args.config.exists():
        cfg = PaperRunnerConfig()
    else:
        cfg = PaperRunnerConfig.from_yaml(args.config)

    if args.db is not None:
        cfg.db_path = str(args.db)
    if args.symbols is not None:
        cfg.symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if args.tick_interval is not None:
        cfg.tick_interval_s = float(args.tick_interval)
    if args.starting_cash is not None:
        cfg.starting_cash = Decimal(str(args.starting_cash))

    logger.info(
        "paper_runner_starting db=%s symbols=%s tick=%ss max_cycles=%s",
        cfg.db_path,
        cfg.symbols,
        cfg.tick_interval_s,
        args.max_cycles,
    )

    runner = PaperRunner(cfg, alerter=build_default_alerter(environment="PAPER"))
    await runner.setup()

    # Optional smoke-test bound: stop the loop after N cycles by setting
    # the stop event once we've reached the limit. This avoids the loop
    # waiting on SIGTERM when the user wants a one-shot run.
    if args.max_cycles is not None:

        async def _stop_after_max() -> None:
            target = int(args.max_cycles)
            while runner._cycle_index < target and not runner._stop_event.is_set():
                await asyncio.sleep(0.001)
            runner.request_stop()

        _stop_task = asyncio.create_task(_stop_after_max())
        _ = _stop_task  # fire-and-forget; the task sets _stop_event on the runner

    return await runner.run()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    code = asyncio.run(_run(args))
    raise SystemExit(code)


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()

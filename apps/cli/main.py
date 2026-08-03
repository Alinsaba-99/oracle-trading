"""Oracle CLI — command line entry point."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import version
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    import polars as pl


def main() -> None:
    """Oracle CLI entry point.

    Starts with a mode guard: only RESEARCH and PAPER are allowed for
    CLI operations today.  Set ``ORACLE_MODE`` env var explicitly.
    """
    from core.domain.guard import current_mode, guard

    mode = current_mode()
    guard(mode)
    parser = argparse.ArgumentParser(
        prog="oracle", description="Systematic Trading Intelligence Platform"
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # config validate
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_sub = config_parser.add_subparsers(dest="config_action")
    validate_parser = config_sub.add_parser("validate", help="Validate config file")
    validate_parser.add_argument("--file", type=str, default=None, help="Path to config file")

    # plugins list
    plugins_parser = subparsers.add_parser("plugins", help="Plugin management")
    plugins_sub = plugins_parser.add_subparsers(dest="plugins_action")
    plugins_sub.add_parser("list", help="List registered plugins")

    # nats ping
    nats_parser = subparsers.add_parser("nats", help="NATS event bus")
    nats_sub = nats_parser.add_subparsers(dest="nats_action")
    nats_sub.add_parser("ping", help="Test NATS connection")

    # backtest run / list / compare
    bt_parser = subparsers.add_parser("backtest", help="Backtesting operations")
    bt_sub = bt_parser.add_subparsers(dest="backtest_action", help="Backtest command")

    # backtest run
    run_parser = bt_sub.add_parser("run", help="Run a single backtest")
    run_parser.add_argument("--instrument", type=str, default="SPY", help="Instrument symbol")
    run_parser.add_argument(
        "--engine",
        type=str,
        default="vectorized",
        choices=["vectorized", "nautilus"],
        help="Backtest engine",
    )
    run_parser.add_argument(
        "--from", dest="from_", type=str, default=None, help="Start date (YYYY-MM-DD or YYYY)"
    )
    run_parser.add_argument("--fast", type=int, default=50, help="SMA fast period")
    run_parser.add_argument(
        "--to", dest="to_", type=str, default=None, help="End date (YYYY-MM-DD or YYYY)"
    )
    run_parser.add_argument("--slow", type=int, default=200, help="SMA slow period")

    # backtest list
    list_parser = bt_sub.add_parser("list", help="List previous backtests")
    list_parser.add_argument("--status", type=str, default=None, help="Filter by status")

    # backtest compare
    compare_parser = bt_sub.add_parser("compare", help="Compare two backtest results")
    compare_parser.add_argument("id1", type=str, help="First result ID")
    compare_parser.add_argument("id2", type=str, help="Second result ID")

    # agent run / debate / status
    agent_parser = subparsers.add_parser("agent", help="Multi-Agent System")
    agent_sub = agent_parser.add_subparsers(dest="agent_action", help="MAS command")

    # agent run
    agent_run_parser = agent_sub.add_parser("run", help="Run full MAS analysis pipeline")
    agent_run_parser.add_argument("--instrument", type=str, default="SPY", help="Instrument symbol")
    agent_run_parser.add_argument("--json", action="store_true", help="JSON output")
    agent_run_parser.add_argument("--table", action="store_true", help="Table output")
    agent_run_parser.add_argument("--verbose", action="store_true", help="Verbose output")

    # agent debate
    agent_debate_parser = agent_sub.add_parser("debate", help="Run debate-only analysis")
    agent_debate_parser.add_argument(
        "--instrument", type=str, default="SPY", help="Instrument symbol"
    )

    # agent status
    agent_sub.add_parser("status", help="Show configured agents and status")

    # trade submit / list / cancel / status / kill
    trade_parser = subparsers.add_parser("trade", help="Trade execution")
    trade_sub = trade_parser.add_subparsers(dest="trade_action", help="Trade command")

    # trade submit
    trade_submit_parser = trade_sub.add_parser("submit", help="Submit an order")
    trade_submit_parser.add_argument(
        "--instrument", type=str, required=True, help="Instrument symbol"
    )
    trade_submit_parser.add_argument(
        "--side", type=str, required=True, choices=["buy", "sell"], help="Order side"
    )
    trade_submit_parser.add_argument("--qty", type=float, required=True, help="Order quantity")
    trade_submit_parser.add_argument(
        "--algo", type=str, default=None, help="Execution algo (vwap, twap, iceberg)"
    )
    trade_submit_parser.add_argument("--price", type=float, default=None, help="Limit price")
    trade_submit_parser.add_argument(
        "--order-type",
        type=str,
        default="market",
        choices=["market", "limit", "stop"],
        help="Order type",
    )
    trade_submit_parser.add_argument(
        "--time-in-force",
        type=str,
        default="day",
        choices=["day", "gtc", "ioc", "fok"],
        help="Time in force",
    )
    trade_submit_parser.add_argument(
        "--broker",
        type=str,
        default="paper",
        choices=["paper", "ibkr", "ccxt"],
        help="Broker to use",
    )
    trade_submit_parser.add_argument(
        "--dry-run", action="store_true", help="Print order without submitting"
    )
    trade_submit_parser.add_argument(
        "--algo-config", type=str, default=None, help="JSON algo config (EXPERIMENTAL)"
    )
    trade_submit_parser.add_argument(
        "--risk-adapter",
        type=str,
        default="paper",
        choices=["paper", "propfirm"],
        help="Risk adapter: 'paper' (basic) or 'propfirm' (full Topstep compliance, "
        "requires --stop-price and replay context)",
    )
    trade_submit_parser.add_argument(
        "--stop-price",
        type=float,
        default=None,
        help="Protective stop price (required for --risk-adapter=propfirm)",
    )
    trade_sub.add_parser("list", help="List open orders")

    # trade cancel
    trade_cancel_parser = trade_sub.add_parser("cancel", help="Cancel an order")
    trade_cancel_parser.add_argument("order_id", type=str, help="Internal order ID")

    # trade status
    trade_status_parser = trade_sub.add_parser("status", help="Check order status")
    trade_status_parser.add_argument("order_id", type=str, help="Internal order ID")

    # trade kill
    trade_sub.add_parser("kill", help="Cancel ALL open orders")

    # trade reconcile — runs ReconciliationEngine (broker ↔ OMS ↔ ledger)
    trade_reconcile_parser = trade_sub.add_parser(
        "reconcile", help="Run broker↔OMS↔ledger reconciliation and report mismatches"
    )
    trade_reconcile_parser.add_argument(
        "--broker",
        type=str,
        default="paper",
        choices=["paper", "ibkr", "ccxt"],
        help="Broker to reconcile against",
    )
    trade_reconcile_parser.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="Exit non-zero if any mismatch (fatal or recoverable) is found",
    )

    args = parser.parse_args()

    if args.version:
        try:
            ver = version("oracle")
        except Exception:
            ver = "0.1.0"
        print(f"oracle v{ver}")
        sys.exit(0)

    if args.command == "config":
        _handle_config(args)
    elif args.command == "plugins":
        _handle_plugins(args)
    elif args.command == "nats":
        _handle_nats(args)
    elif args.command == "backtest":
        _handle_backtest(args)
    elif args.command == "agent":
        if args.agent_action == "run":
            _handle_agent_run(args)
        elif args.agent_action == "debate":
            _handle_agent_debate(args)
        elif args.agent_action == "status":
            _handle_agent_status(args)
        else:
            agent_parser.print_help()
    elif args.command == "trade":
        if args.trade_action == "submit":
            _handle_trade_submit(args)
        elif args.trade_action == "list":
            _handle_trade_list(args)
        elif args.trade_action == "cancel":
            _handle_trade_cancel(args)
        elif args.trade_action == "status":
            _handle_trade_status(args)
        elif args.trade_action == "kill":
            _handle_trade_kill(args)
        elif args.trade_action == "reconcile":
            _handle_trade_reconcile(args)
        else:
            trade_parser.print_help()
    else:
        parser.print_help()


def _handle_config(args: argparse.Namespace) -> None:
    from core.config import ConfigLoader

    loader = ConfigLoader()
    file_path = args.file
    if file_path:
        try:
            loader.validate(file_path)
            print(f"Config valid: {file_path}")
            sys.exit(0)
        except Exception as e:
            print(f"Config invalid: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        settings = loader.load()
        print(f"Environment: {settings.environment}")
        print(f"Log level: {settings.log_level}")
        print(f"NATS: {settings.nats.url}")
        sys.exit(0)


def _handle_plugins(_args: argparse.Namespace) -> None:
    from core.plugin import PluginDiscovery

    discovery = PluginDiscovery()
    plugins = discovery.discover_all()
    if plugins:
        print(f"Found {len(plugins)} plugin(s):")
        for p in plugins:
            print(f"  - {p.__name__}")
    else:
        print("No plugins found")
    sys.exit(0)


def _handle_nats(_args: argparse.Namespace) -> None:
    import asyncio

    from core.config import OracleSettings
    from core.events import EventBusClient

    async def ping() -> None:
        settings = OracleSettings()
        client = EventBusClient(settings.nats)
        try:
            await client.connect()
            print(f"Connected to NATS at {settings.nats.url}")
            await client.close()
            sys.exit(0)
        except Exception as e:
            print(f"NATS connection failed: {e}", file=sys.stderr)
            sys.exit(1)

    asyncio.run(ping())


def _handle_backtest(args: argparse.Namespace) -> None:
    """Dispatch backtest subcommands."""
    if args.backtest_action == "run":
        _handle_backtest_run(args)
    elif args.backtest_action == "list":
        _handle_backtest_list(args)
    elif args.backtest_action == "compare":
        _handle_backtest_compare(args)
    else:
        print("Usage: oracle backtest run|list|compare")
        sys.exit(1)


def _synthetic_ohlcv(
    n_periods: int = 1260, start_price: float = 100.0, start_date: str | None = None
) -> pl.DataFrame:
    """Generate synthetic OHLCV for demo / development backtests."""
    from datetime import UTC, datetime

    import numpy as np
    import polars as pl

    if start_date is not None:
        from datetime import timedelta

        # Accept "2015" or "2015-01-01"
        if len(start_date) == 4 and start_date.isdigit():
            start_date = f"{start_date}-01-01"
        dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC)
        end_dt = dt + timedelta(days=n_periods)
        dates = pl.datetime_range(start=dt, end=end_dt, interval="1d", eager=True, closed="left")
    else:
        dates = _n_dates(n_periods)
    sine = np.sin(np.linspace(0, 4 * np.pi, n_periods))
    price = start_price + sine * start_price * 0.15
    noise = np.random.default_rng(42).normal(0, start_price * 0.005, n_periods)
    close = price + noise
    return pl.DataFrame(
        {
            "timestamp": dates,
            "open": price,
            "high": price * 1.02,
            "low": price * 0.98,
            "close": close,
            "volume": np.full(n_periods, 1_000_000),
        }
    )


def _n_dates(n: int) -> pl.Series:
    """Return a Polars datetime series with *n* daily intervals (UTC)."""
    from datetime import UTC, datetime, timedelta

    import polars as pl

    dt = datetime(2020, 1, 1, tzinfo=UTC)
    end = dt + timedelta(days=n)
    return pl.datetime_range(start=dt, end=end, interval="1d", eager=True, closed="left")


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse a date string (YYYY or YYYY-MM-DD) into a UTC datetime."""
    if date_str is None:
        return None
    from datetime import UTC, datetime

    parts = date_str.split("-")
    if len(parts) == 1:
        return datetime(int(parts[0]), 1, 1, tzinfo=UTC)
    if len(parts) == 3:
        return datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=UTC)
    raise ValueError(f"Invalid date format: {date_str!r} (use YYYY or YYYY-MM-DD)")


def _handle_backtest_run(args: argparse.Namespace) -> None:
    """Run a single backtest (``oracle backtest run``)."""
    from analytics.backtest.engines.vectorized import sma_crossover_signal
    from analytics.backtest.orchestrator import BacktestOrchestrator

    start = _parse_date(args.from_)
    end = _parse_date(args.to_)
    instrument = args.instrument

    print(f"Running backtest: instrument={instrument} engine={args.engine}")
    print(f"  SMA crossover ({args.fast}/{args.slow})")
    print(f"  Period: {args.from_ or 'earliest'} → {args.to_ or 'latest'}")

    # Generate synthetic data for the requested period
    n_periods = 1260
    if start and end:
        n_periods = max((end - start).days, 252)

    data = _synthetic_ohlcv(n_periods=n_periods, start_date=args.from_ or "2015-01-01")

    orchestrator = BacktestOrchestrator()
    signal = sma_crossover_signal(fast=args.fast, slow=args.slow)
    result = orchestrator.run(
        signal=signal, engine=args.engine, instrument_id=instrument, data=data
    )

    print(f"\n── Results: {result.run_id[:8]} ──")
    print(f"  Total Return:  {result.total_return:.2%}")
    print(f"  Sharpe Ratio:  {result.sharpe_ratio:.4f}")
    print(f"  Sortino Ratio: {result.sortino_ratio:.4f}")
    print(f"  Calmar Ratio:  {result.calmar_ratio:.4f}")
    print(f"  Max Drawdown:  {result.max_drawdown:.2%}")
    print(f"  CAGR:          {result.cagr:.2%}")
    print(f"  Volatility:    {result.volatility:.2%}")
    print(f"  Total Trades:  {result.total_trades}")
    print(f"  Win Rate:      {result.win_rate:.2%}")
    print(f"  Profit Factor: {result.profit_factor:.4f}")
    print(f"  Final Equity:  ${result.final_equity:,.2f}")
    sys.exit(0)


def _handle_backtest_list(args: argparse.Namespace) -> None:
    """List previous backtest experiments (``oracle backtest list``)."""
    from core.domain.experiment import ExperimentRegistry

    registry = ExperimentRegistry()
    try:
        experiments = registry.list()
    except Exception as exc:
        print(f"Could not read experiment registry: {exc}", file=sys.stderr)
        sys.exit(1)

    if not experiments:
        print("No backtests found in the experiment registry.")
        sys.exit(0)

    # Filter by status if requested
    filtered = experiments
    if args.status:
        filtered = [e for e in experiments if e.tags.get("status") == args.status]

    print(f"Backtest experiments ({len(filtered)}):")
    print(f"  {'ID':<40} {'Date':<26} {'Instrument':<12} {'Sharpe':<10} {'Return':<10}")
    print(f"  {'─' * 40} {'─' * 26} {'─' * 12} {'─' * 10} {'─' * 10}")
    for exp in filtered:
        eid = exp.experiment_id[:36]
        ts = exp.timestamp.strftime("%Y-%m-%d %H:%M") if exp.timestamp else "?"
        instr = exp.tags.get("instrument", "?")
        sharpe = exp.tags.get("sharpe_ratio", "?")
        ret = exp.tags.get("total_return", "?")
        print(f"  {eid:<40} {ts:<26} {instr:<12} {sharpe:<10} {ret:<10}")
    sys.exit(0)


def _handle_backtest_compare(args: argparse.Namespace) -> None:
    """Compare two backtest results (``oracle backtest compare``)."""
    from core.domain.experiment import ExperimentRegistry

    registry = ExperimentRegistry()

    def _load(id_: str) -> dict[str, str] | None:
        try:
            exp = registry.get(id_)
            if exp is None:
                return None
            return {"id": exp.experiment_id, **exp.tags}
        except Exception:
            return None

    r1 = _load(args.id1)
    r2 = _load(args.id2)

    if r1 is None:
        print(f"Experiment not found: {args.id1}", file=sys.stderr)
        sys.exit(1)
    if r2 is None:
        print(f"Experiment not found: {args.id2}", file=sys.stderr)
        sys.exit(1)

    metrics = ["sharpe_ratio", "sortino_ratio", "total_return", "total_trades"]
    print(f"Comparison: {args.id1[:8]} vs {args.id2[:8]}")
    print(f"  {'Metric':<20} {'Result 1':<20} {'Result 2':<20}")
    print(f"  {'─' * 20} {'─' * 20} {'─' * 20}")
    for m in metrics:
        v1 = r1.get(m, "?")
        v2 = r2.get(m, "?")
        print(f"  {m:<20} {v1!s:<20} {v2!s:<20}")


def _handle_agent_run(args: argparse.Namespace) -> None:
    """Run full MAS analysis pipeline (``oracle agent run``)."""
    import asyncio

    from apps.cli.agent_commands import handle_agent_run

    sys.exit(asyncio.run(handle_agent_run(args)))


def _handle_agent_debate(args: argparse.Namespace) -> None:
    """Run debate-only analysis (``oracle agent debate``)."""
    import asyncio

    from apps.cli.agent_commands import handle_agent_debate

    sys.exit(asyncio.run(handle_agent_debate(args)))


def _handle_agent_status(args: argparse.Namespace) -> None:
    """Show configured agents (``oracle agent status``)."""
    from apps.cli.agent_commands import handle_agent_status

    sys.exit(handle_agent_status(args))


def _handle_trade_submit(args: argparse.Namespace) -> None:
    """Submit a trade order."""
    import asyncio

    from apps.cli.trade_commands import handle_trade_submit

    sys.exit(asyncio.run(handle_trade_submit(args)))


def _handle_trade_list(args: argparse.Namespace) -> None:
    """List open orders."""
    import asyncio

    from apps.cli.trade_commands import handle_trade_list

    sys.exit(asyncio.run(handle_trade_list(args)))


def _handle_trade_cancel(args: argparse.Namespace) -> None:
    """Cancel an order."""
    import asyncio

    from apps.cli.trade_commands import handle_trade_cancel

    sys.exit(asyncio.run(handle_trade_cancel(args)))


def _handle_trade_status(args: argparse.Namespace) -> None:
    """Check order status."""
    import asyncio

    from apps.cli.trade_commands import handle_trade_status

    sys.exit(asyncio.run(handle_trade_status(args)))


def _handle_trade_kill(args: argparse.Namespace) -> None:
    """Cancel all open orders."""
    import asyncio

    from apps.cli.trade_commands import handle_trade_kill

    sys.exit(asyncio.run(handle_trade_kill(args)))


def _handle_trade_reconcile(args: argparse.Namespace) -> None:
    """Run ReconciliationEngine and report mismatches.

    Builds a fresh broker, OMS, and ledger; runs reconciliation; prints
    a human-readable summary.  Exits 0 if clean, 1 if --fail-on-mismatch
    and any mismatch is found, 2 on unexpected error.
    """
    import asyncio as _asyncio

    from apps.cli.trade_commands import _get_broker
    from core.ledger import InMemoryLedger
    from core.oms import InMemoryOMS
    from core.reconciliation import ReconciliationEngine

    async def _run() -> int:
        broker_type = getattr(args, "broker", "paper")
        broker = _get_broker(broker_type)
        oms = InMemoryOMS()
        ledger = InMemoryLedger()
        report = await ReconciliationEngine(broker, oms, ledger).reconcile()
        if report.is_clean:
            print("✅ Reconciliation clean — broker ↔ OMS ↔ ledger in sync")
            return 0
        print(
            f"⚠️  {len(report.mismatches)} mismatches "
            f"({report.fatal_count} fatal, {report.recoverable_count} recoverable)"
        )
        for m in report.mismatches:
            print(
                f"  - [{m.severity.value}] {m.mismatch_type.value}: {m.description} "
                f"(broker={m.broker_value} oracle={m.oracle_value} diff={m.diff})"
            )
        if getattr(args, "fail_on_mismatch", False):
            return 1
        return 0

    try:
        sys.exit(_asyncio.run(_run()))
    except Exception as e:  # pragma: no cover - CLI guard
        print(f"ERROR: reconciliation failed: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

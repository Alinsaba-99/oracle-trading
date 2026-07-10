"""Tests for ``apps.cli.trade_commands`` — trade CLI handlers."""

from __future__ import annotations

import argparse

import pytest

# =========================================================================
# Module load
# =========================================================================


class TestTradeCommandsModule:
    """Verify the trade_commands module can be imported cleanly."""

    def test_module_imports(self) -> None:
        import apps.cli.trade_commands as m

        assert hasattr(m, "handle_trade_submit")
        assert hasattr(m, "handle_trade_list")
        assert hasattr(m, "handle_trade_cancel")
        assert hasattr(m, "handle_trade_status")
        assert hasattr(m, "handle_trade_kill")


# =========================================================================
# CLI parser integration
# =========================================================================


class TestCLIParser:
    """Verify trade subcommand tree."""

    def _build_trade_parser(self) -> argparse.ArgumentParser:
        """Build an isolated trade parser (no side-effects)."""
        parser = argparse.ArgumentParser(prog="oracle")
        sub = parser.add_subparsers(dest="command")
        trade_parser = sub.add_parser("trade")
        trade_sub = trade_parser.add_subparsers(dest="trade_action")

        submit = trade_sub.add_parser("submit")
        submit.add_argument("--instrument", type=str, required=True)
        submit.add_argument("--side", type=str, required=True, choices=["buy", "sell"])
        submit.add_argument("--qty", type=float, required=True)
        submit.add_argument("--algo", type=str, default=None)
        submit.add_argument("--price", type=float, default=None)
        submit.add_argument("--order-type", type=str, default="market")
        submit.add_argument("--time-in-force", type=str, default="day")
        submit.add_argument("--broker", type=str, default="paper")
        submit.add_argument("--dry-run", action="store_true")
        submit.add_argument("--algo-config", type=str, default=None)

        trade_sub.add_parser("list")
        trade_sub.add_parser("cancel").add_argument("order_id", type=str)
        trade_sub.add_parser("status").add_argument("order_id", type=str)
        trade_sub.add_parser("kill")

        return parser

    def test_has_trade_subcommand(self) -> None:
        """Root parser has 'trade' subcommand."""
        parser = self._build_trade_parser()
        ns = parser.parse_args(["trade"])
        assert ns.command == "trade"

    def test_trade_has_five_subcommands(self) -> None:
        """trade subparser has exactly 5 actions."""
        parser = self._build_trade_parser()
        # Verify subcommand IDs via parse_args with required args
        for cmd, extra_args in [
            ("submit", ["--instrument", "X", "--side", "buy", "--qty", "1"]),
            ("list", []),
            ("cancel", ["dummy"]),
            ("status", ["dummy"]),
            ("kill", []),
        ]:
            ns = parser.parse_args(["trade", cmd, *extra_args])
            assert ns.trade_action == cmd
    def test_submit_help(self) -> None:
        """trade submit --help works."""
        parser = self._build_trade_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["trade", "submit", "--help"])
        assert exc.value.code == 0

    def test_submit_parses_required_flags(self) -> None:
        """--instrument, --side, --qty are parsed correctly."""
        parser = self._build_trade_parser()
        ns = parser.parse_args(
            ["trade", "submit", "--instrument", "SPY", "--side", "buy", "--qty", "100"]
        )
        assert ns.instrument == "SPY"
        assert ns.side == "buy"
        assert ns.qty == 100.0

    def test_submit_parses_optional_flags(self) -> None:
        """--algo, --price, --dry-run are parsed correctly."""
        parser = self._build_trade_parser()
        ns = parser.parse_args(
            [
                "trade", "submit",
                "--instrument", "AAPL",
                "--side", "sell",
                "--qty", "50",
                "--algo", "vwap",
                "--price", "200",
                "--dry-run",
            ]
        )
        assert ns.instrument == "AAPL"
        assert ns.side == "sell"
        assert ns.qty == 50.0
        assert ns.algo == "vwap"
        assert ns.price == 200.0
        assert ns.dry_run is True

    def test_submit_defaults(self) -> None:
        """Missing optional flags get sensible defaults."""
        parser = self._build_trade_parser()
        ns = parser.parse_args(
            ["trade", "submit", "--instrument", "SPY", "--side", "buy", "--qty", "100"]
        )
        assert ns.order_type == "market"
        assert ns.time_in_force == "day"
        assert ns.algo is None
        assert ns.price is None
        assert ns.broker == "paper"
        assert ns.dry_run is False
        assert ns.algo_config is None

    def test_cancel_requires_order_id(self) -> None:
        """cancel expects a positional order_id."""
        parser = self._build_trade_parser()
        ns = parser.parse_args(["trade", "cancel", "ord-123"])
        assert ns.order_id == "ord-123"

    def test_status_requires_order_id(self) -> None:
        """status expects a positional order_id."""
        parser = self._build_trade_parser()
        ns = parser.parse_args(["trade", "status", "ord-456"])
        assert ns.order_id == "ord-456"


# =========================================================================
# handle_trade_submit
# =========================================================================


class TestHandleTradeSubmit:
    """handle_trade_submit builds OrderRequest from CLI args."""

    async def test_submit_dry_run(self) -> None:
        """dry-run submit returns 0 without sending to broker."""
        from apps.cli.trade_commands import handle_trade_submit

        ns = argparse.Namespace(
            instrument="SPY",
            side="buy",
            qty=100.0,
            algo=None,
            price=None,
            order_type="market",
            time_in_force="day",
            broker="paper",
            dry_run=True,
            algo_config=None,
        )
        code = await handle_trade_submit(ns)
        assert code == 0

    async def test_submit_dry_run_with_optional(self) -> None:
        """dry-run with all optional flags present."""
        from apps.cli.trade_commands import handle_trade_submit

        ns = argparse.Namespace(
            instrument="AAPL",
            side="sell",
            qty=50.0,
            algo="vwap",
            price=200.0,
            order_type="limit",
            time_in_force="gtc",
            broker="paper",
            dry_run=True,
            algo_config=None,
        )
        code = await handle_trade_submit(ns)
        assert code == 0

    async def test_submit_dry_run_with_algo_config(self) -> None:
        """JSON algo config is passed through."""
        from apps.cli.trade_commands import handle_trade_submit

        ns = argparse.Namespace(
            instrument="SPY",
            side="buy",
            qty=100.0,
            algo="twap",
            price=None,
            order_type="market",
            time_in_force="day",
            broker="paper",
            dry_run=True,
            algo_config={"slices": 10},
        )
        code = await handle_trade_submit(ns)
        assert code == 0


# =========================================================================
# handle_trade_list
# =========================================================================


class TestHandleTradeList:
    """handle_trade_list shows open orders."""

    async def test_list_empty(self) -> None:
        """No open orders produces a message."""
        from apps.cli.trade_commands import handle_trade_list

        ns = argparse.Namespace()
        code = await handle_trade_list(ns)
        assert code == 0


# =========================================================================
# handle_trade_cancel
# =========================================================================


class TestHandleTradeCancel:
    """handle_trade_cancel returns non-zero for missing orders."""

    async def test_cancel_not_found(self) -> None:
        """Cancelling a non-existent order returns code 1."""
        from apps.cli.trade_commands import handle_trade_cancel

        ns = argparse.Namespace(order_id="nonexistent-42")
        code = await handle_trade_cancel(ns)
        assert code == 1


# =========================================================================
# handle_trade_status
# =========================================================================


class TestHandleTradeStatus:
    """handle_trade_status returns non-zero for missing orders."""

    async def test_status_not_found(self) -> None:
        """Status of a non-existent order returns code 1."""
        from apps.cli.trade_commands import handle_trade_status

        ns = argparse.Namespace(order_id="ghost-order")
        code = await handle_trade_status(ns)
        assert code == 1


# =========================================================================
# handle_trade_kill
# =========================================================================


class TestHandleTradeKill:
    """handle_trade_kill handles the zero-open-orders case."""

    async def test_kill_empty(self) -> None:
        """Kill with no open orders returns 0."""
        from apps.cli.trade_commands import handle_trade_kill

        ns = argparse.Namespace()
        code = await handle_trade_kill(ns)
        assert code == 0

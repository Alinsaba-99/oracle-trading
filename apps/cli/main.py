"""Oracle CLI — command line entry point."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import version


def main() -> None:
    """Oracle CLI entry point."""
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
        print(f"Redis: {settings.redis.url}")
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


if __name__ == "__main__":
    main()

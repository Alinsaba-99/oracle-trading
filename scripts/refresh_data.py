#!/usr/bin/env python3
"""Refresh all market data used by Oracle qualification tests.

Usage::

    uv run --frozen python scripts/refresh_data.py
    uv run --frozen python scripts/refresh_data.py --futures-only
"""

from __future__ import annotations

import argparse

from market.data_sources import DataFetcher


def refresh_all() -> None:
    """Download fresh data for all instruments."""
    f = DataFetcher()
    print("🔄 Aggiornamento dati...")

    # Futures (daily, 1y)
    futures = ["ES", "NQ", "GC", "CL"]
    for sym in futures:
        print(f"  📊 {sym}=F...", end="", flush=True)
        try:
            df = f.yfinance_futures(sym, period="1y")
            print(f" ✅ {len(df)} barre")
        except Exception as e:
            print(f" ❌ {e}")

    # Crypto (daily, 1000 candles)
    pairs = [("binance", "BTC/USDT"), ("binance", "ETH/USDT")]
    for exchange, pair in pairs:
        print(f"  🪙 {pair}...", end="", flush=True)
        try:
            df = f.ccxt_ohlcv(exchange, pair, "1d", limit=1000)
            print(f" ✅ {len(df)} barre")
        except Exception as e:
            print(f" ❌ {e}")

    print("✅ Aggiornamento completato!")


def refresh_futures_only() -> None:
    """Download fresh data for futures only."""
    f = DataFetcher()
    print("🔄 Aggiornamento futures...")
    for sym in ["ES", "NQ", "GC", "CL"]:
        print(f"  📊 {sym}=F...", end="", flush=True)
        try:
            df = f.yfinance_futures(sym, period="1y")
            print(f" ✅ {len(df)} barre")
        except Exception as e:
            print(f" ❌ {e}")
    print("✅ Futures aggiornati!")


def refresh_multi_timeframe(symbol: str) -> None:
    """Fetch multi-timeframe data for a symbol.

    Downloads 1d, 1h, 15m data where available.
    """
    f = DataFetcher()
    print(f"🔄 Multi-timeframe per {symbol}...")

    # Detect symbol type
    if "/" in symbol:
        # Crypto via CCXT
        for tf in ["1d", "4h", "1h", "15m"]:
            print(f"  🪙 {symbol} {tf}...", end="", flush=True)
            try:
                df = f.ccxt_ohlcv("binance", symbol, tf, limit=500)
                print(f" ✅ {len(df)} barre")
            except Exception as e:
                print(f" ❌ {e}")
    else:
        # Futures via yfinance
        for interval, period in [("1d", "1y"), ("1h", "6mo")]:
            print(f"  📊 {symbol}=F {interval}...", end="", flush=True)
            try:
                df = f.yfinance_futures(symbol, period=period, interval=interval)
                print(f" ✅ {len(df)} barre")
            except Exception as e:
                print(f" ❌ {e}")
    print("✅ Multi-timeframe completato!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh Oracle market data")
    parser.add_argument("--futures-only", action="store_true", help="Only refresh futures")
    parser.add_argument(
        "--multi-timeframe", type=str, default=None,
        help="Fetch multi-timeframe data for a symbol (e.g. ES, BTC/USDT)"
    )
    args = parser.parse_args()

    if args.multi_timeframe:
        refresh_multi_timeframe(args.multi_timeframe)
    elif args.futures_only:
        refresh_futures_only()
    else:
        refresh_all()

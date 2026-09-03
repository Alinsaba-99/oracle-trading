#!/usr/bin/env python3
"""BL-718 — Backfill USD-M perpetual klines from Binance Vision (futures/um).

Downloads monthly klines ZIPs (no key) into raw per-symbol parquet files:

    data/lake/raw/perp/{SYM}_1h.parquet  [open_time_ms, open, high, low, close, volume]

Futures/um klines CSV carries a header row. Availability (BTCUSDT 1h):
2019-09 → current month. Idempotent like the funding backfill.

Used for EF-007 (perp-basis-carry): perp close vs lake spot close.

Usage:
    uv run --frozen python scripts/backfill_perp_klines_vision.py
    uv run --frozen python scripts/backfill_perp_klines_vision.py --symbols BTCUSDT --tf 1h
"""

from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

BASE = "https://data.binance.vision/data/futures/um/monthly/klines"
OUT_DIR = Path("data/lake/raw/perp")
EARLIEST = date(2019, 9, 1)  # first futures/um monthly klines ZIP


def month_iter(start: date, end: date) -> Iterator[str]:
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1


def fetch_month(symbol: str, tf: str, ym: str, retries: int = 4) -> pd.DataFrame | None:
    """Download + parse one monthly klines ZIP. Returns None on 404."""
    url = f"{BASE}/{symbol}/{tf}/{symbol}-{tf}-{ym}.zip"
    payload = None
    for attempt in range(retries):
        req = Request(url, headers={"User-Agent": "oracle-trading/1.0 (research)"})
        try:
            with urlopen(req, timeout=120) as resp:
                payload = resp.read()
            break
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        except URLError:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    assert payload is not None
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        name = zf.namelist()[0]
        df = pd.read_csv(zf.open(name), header=None, skiprows=1)
    df = df.iloc[:, :6]
    df.columns = ["open_time_ms", "open", "high", "low", "close", "volume"]
    return df


def backfill(symbol: str, tf: str, start: date, end: date, sleep: float = 0.2) -> Path:
    out_path = OUT_DIR / f"{symbol}_{tf}.parquet"
    existing = pd.read_parquet(out_path) if out_path.exists() else None
    last_ms = int(existing["open_time_ms"].max()) if existing is not None and len(existing) else 0

    frames = [] if existing is None else [existing]
    n_new = 0
    for ym in month_iter(start, end):
        df = fetch_month(symbol, tf, ym)
        if df is None:
            continue
        new = df[df["open_time_ms"] > last_ms]
        if len(new) == 0:
            continue
        frames.append(new)
        n_new += len(new)
        time.sleep(sleep)

    if not frames:
        print(f"  {symbol} {tf}: no data")
        return out_path
    merged = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset="open_time_ms", keep="last")
        .sort_values("open_time_ms")
        .reset_index(drop=True)
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_path, index=False)
    print(f"{symbol} {tf}: {len(merged)} rows ({n_new} new) → {out_path}")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    parser.add_argument("--tf", default="1h")
    parser.add_argument("--start", default=EARLIEST.isoformat())
    parser.add_argument("--end", default=date.today().strftime("%Y-%m"))
    args = parser.parse_args()

    start = (
        date.fromisoformat(f"{args.start}-01")
        if len(args.start) == 7
        else date.fromisoformat(args.start)
    )
    end_y, end_m = (int(x) for x in args.end.split("-"))
    if max((start.year, start.month), (end_y, end_m)) > (date.today().year, date.today().month):
        print("end month is in the future; clamping to current month", file=sys.stderr)
        end_y, end_m = date.today().year, date.today().month

    for symbol in args.symbols.split(","):
        symbol = symbol.strip().upper()
        if symbol:
            backfill(symbol, args.tf, start, date(end_y, end_m, 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

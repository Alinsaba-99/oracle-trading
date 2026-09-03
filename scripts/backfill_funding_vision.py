#!/usr/bin/env python3
"""BL-718 — Backfill funding rates from Binance Vision (futures/um).

Downloads monthly fundingRate ZIPs (no key, no auth) for the requested
symbols and merges them into a single Parquet per symbol:

    data/lake/raw/funding/{SYM}.parquet  [calc_time_ms, funding_rate, funding_interval_hours]

CSV schema (header present):
    calc_time (ms), funding_interval_hours, last_funding_rate

Availability (BTCUSDT): 2020-06 → current month. Downloads are
idempotent: re-running refreshes only months newer than the last
ingested calc_time.

Usage:
    uv run --frozen python scripts/backfill_funding_vision.py                  # BTC/ETH/SOL
    uv run --frozen python scripts/backfill_funding_vision.py --symbols BTCUSDT
    uv run --frozen python scripts/backfill_funding_vision.py --start 2020-06 --end 2026-08
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

BASE = "https://data.binance.vision/data/futures/um/monthly/fundingRate"
OUT_DIR = Path("data/lake/raw/funding")
EARLIEST = date(2020, 6, 1)  # first monthly fundingRate ZIP on Vision


def month_iter(start: date, end: date) -> Iterator[str]:
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1


def fetch_month(symbol: str, ym: str, retries: int = 4) -> pd.DataFrame | None:
    """Download + parse one monthly funding ZIP. Returns None on 404."""
    url = f"{BASE}/{symbol}/{symbol}-fundingRate-{ym}.zip"
    payload = None
    for attempt in range(retries):
        req = Request(url, headers={"User-Agent": "oracle-trading/1.0 (research)"})
        try:
            with urlopen(req, timeout=60) as resp:
                payload = resp.read()
            break
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        except URLError:
            # S3 drops the connection intermittently; back off and retry
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    assert payload is not None  # retry loop either returned 404 or raised
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        name = zf.namelist()[0]
        df = pd.read_csv(zf.open(name))
    df = df.rename(columns={"calc_time": "calc_time_ms", "last_funding_rate": "funding_rate"})[
        ["calc_time_ms", "funding_interval_hours", "funding_rate"]
    ]
    return df


def backfill(symbol: str, start: date, end: date, sleep: float = 0.2) -> Path:
    out_path = OUT_DIR / f"{symbol}.parquet"
    existing = pd.read_parquet(out_path) if out_path.exists() else None
    last_ms = int(existing["calc_time_ms"].max()) if existing is not None and len(existing) else 0

    frames = [] if existing is None else [existing]
    n_new = 0
    for ym in month_iter(start, end):
        df = fetch_month(symbol, ym)
        if df is None:
            continue
        new = df[df["calc_time_ms"] > last_ms]
        if len(new) == 0:
            continue
        frames.append(new)
        n_new += len(new)
        print(f"  {symbol} {ym}: +{len(new)} rows")
        time.sleep(sleep)  # polite S3 pacing

    if len(frames) == 0:
        print(f"  {symbol}: no data")
        return out_path
    merged = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset="calc_time_ms", keep="last")
        .sort_values("calc_time_ms")
        .reset_index(drop=True)
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_path, index=False)
    print(f"{symbol}: {len(merged)} total rows ({n_new} new) → {out_path}")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
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
        if not symbol:
            continue
        backfill(symbol, start, date(end_y, end_m, 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Derive 1h/4h/1d lake partitions from on-disk 1m bars (no network).

Several symbols were backfilled at 1m only, so the strategy search — which
samples 1h/4h/1d — cannot see them at all. The 1m bars already hold every
higher aggregate, so this rebuilds them locally instead of re-downloading
years of history.

Buckets are wall-clock aligned via ``group_by_dynamic``. Existing Dukascopy
4h partitions are session-relative and inconsistent within a month, so
``--overwrite`` is required to replace them.

Usage:
    python -m scripts.resample_lake --plan
    python -m scripts.resample_lake --all
    python -m scripts.resample_lake --symbols EURAUD,GBPJPY --tfs 1h,4h,1d
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parent.parent))

from market.ingestion import metadata_io as meta

log = logging.getLogger("oracle.resample_lake")

LAKE_ROOT = Path("data/lake")
NORM_ROOT = LAKE_ROOT / "normalized"

SOURCE_TAG = "resample:1m"

#: group_by_dynamic rule per target timeframe.
TF_RULES: dict[str, str] = {"1h": "1h", "4h": "4h", "1d": "1d"}

#: Lake parquet column order — must match Pipeline._write_normalized.
LAKE_COLUMNS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "symbol",
    "source",
    "timeframe",
]


def tf_dir(symbol: str, tf: str) -> Path:
    return NORM_ROOT / f"symbol={symbol}" / f"tf={tf}"


def partition_files(symbol: str, tf: str) -> list[Path]:
    base = tf_dir(symbol, tf)
    if not base.exists():
        return []
    return sorted(base.glob("year=*/month=*.parquet"))


def lake_symbols() -> list[str]:
    if not NORM_ROOT.exists():
        return []
    return sorted(p.name.split("=", 1)[1] for p in NORM_ROOT.glob("symbol=*") if p.is_dir())


def available_tfs(symbol: str) -> set[str]:
    """Timeframes that actually have at least one partition file on disk."""
    root = NORM_ROOT / f"symbol={symbol}"
    if not root.exists():
        return set()
    found = set()
    for p in root.glob("tf=*"):
        if p.is_dir() and any(p.glob("year=*/month=*.parquet")):
            found.add(p.name.split("=", 1)[1])
    return found


def read_source_1m(symbol: str) -> pl.DataFrame | None:
    """Load every 1m partition for a symbol, deduped and sorted."""
    parts = partition_files(symbol, "1m")
    if not parts:
        return None
    frames = []
    for path in parts:
        try:
            frames.append(pl.read_parquet(path))
        except Exception as exc:
            log.warning("unreadable partition %s: %s", path, exc)
    if not frames:
        return None
    df = pl.concat(frames, how="vertical_relaxed")
    if df.is_empty():
        return None
    return df.unique(subset=["timestamp"], keep="last").sort("timestamp")


def resample(df: pl.DataFrame, symbol: str, tf: str) -> pl.DataFrame:
    """Aggregate 1m OHLCV into ``tf`` buckets, dropping incomplete buckets."""
    rule = TF_RULES[tf]
    out = (
        df.sort("timestamp")
        .group_by_dynamic("timestamp", every=rule, closed="left", label="left")
        .agg(
            pl.col("open").first().alias("open"),
            pl.col("high").max().alias("high"),
            pl.col("low").min().alias("low"),
            pl.col("close").last().alias("close"),
            pl.col("volume").sum().alias("volume"),
            pl.len().alias("n_bars"),
        )
        .sort("timestamp")
    )
    # A bucket built from a single 1m print is a data gap, not a real bar;
    # keeping it would fabricate zero-range candles that break ATR/stops.
    out = out.filter(pl.col("n_bars") >= 2).drop("n_bars")
    if out.is_empty():
        return out
    return out.with_columns(
        pl.lit(symbol).alias("symbol"),
        pl.lit(SOURCE_TAG).alias("source"),
        pl.lit("").alias("timeframe"),
    ).select(LAKE_COLUMNS)


def write_partitions(df: pl.DataFrame, symbol: str, tf: str, *, overwrite: bool) -> int:
    """Write ``df`` into year/month partitions. Returns partitions written."""
    if df.is_empty():
        return 0
    tagged = df.with_columns(
        pl.col("timestamp").dt.year().alias("_year"), pl.col("timestamp").dt.month().alias("_month")
    )
    written = 0
    for (year, month), group in tagged.group_by(["_year", "_month"]):
        part_dir = tf_dir(symbol, tf) / f"year={year}"
        part_dir.mkdir(parents=True, exist_ok=True)
        part_file = part_dir / f"month={int(month):02d}.parquet"
        block = group.drop(["_year", "_month"]).select(LAKE_COLUMNS)

        if part_file.exists() and not overwrite:
            try:
                existing = pl.read_parquet(part_file)
                block = pl.concat([existing, block], how="vertical_relaxed")
            except Exception as exc:
                log.warning("could not merge %s, rewriting: %s", part_file, exc)
        block = block.unique(subset=["timestamp"], keep="last").sort("timestamp")
        block.select(LAKE_COLUMNS).write_parquet(part_file)
        written += 1
    return written


def update_metadata(symbol: str, tf: str) -> None:
    """Refresh coverage + lineage from what is actually on disk for symbol/tf."""
    parts = partition_files(symbol, tf)
    if not parts:
        return

    frames = [pl.read_parquet(p) for p in parts]
    df = pl.concat(frames, how="vertical_relaxed").unique(subset=["timestamp"], keep="last")
    if df.is_empty():
        return

    ts = df["timestamp"]
    earliest = ts.min()
    latest = ts.max()

    def _iso(value: object) -> str:
        if isinstance(value, datetime):
            # Lake parquet is tz-naive UTC; coverage.json stores tz-aware.
            return value.replace(tzinfo=UTC).isoformat()
        return str(value)

    coverage = meta.load_coverage()
    key = meta.coverage_key(symbol, tf)
    entry = coverage.get(key, {})
    sources = sorted({*entry.get("sources", []), SOURCE_TAG})
    coverage[key] = {
        "earliest": _iso(earliest),
        "latest": _iso(latest),
        # True count from disk, not the additive counter the pipeline keeps.
        "rows": int(df.height),
        "sources": sources,
        "last_touch": datetime.now(UTC).isoformat(),
        "version": int(entry.get("version", 0)) + 1,
    }
    meta.save_coverage(coverage)

    lineage = meta.load_lineage()
    for path in parts:
        rel = path.relative_to(LAKE_ROOT).as_posix()
        tags = sorted({*lineage.get(rel, []), SOURCE_TAG})
        lineage[rel] = tags
    meta.save_lineage(lineage)


def build_plan(symbols: list[str], tfs: list[str], *, overwrite: bool) -> list[tuple[str, str]]:
    """Pairs of (symbol, tf) that need deriving: has 1m, missing the target."""
    plan: list[tuple[str, str]] = []
    for symbol in symbols:
        have = available_tfs(symbol)
        if "1m" not in have:
            continue
        for tf in tfs:
            if tf in have and not overwrite:
                continue
            plan.append((symbol, tf))
    return plan


def run(symbols: list[str], tfs: list[str], *, overwrite: bool, dry_run: bool) -> int:
    plan = build_plan(symbols, tfs, overwrite=overwrite)
    if not plan:
        print("Nothing to do — every requested symbol/timeframe already exists.")
        return 0

    print(f"Plan: {len(plan)} symbol/timeframe pairs to derive from 1m")
    by_symbol: dict[str, list[str]] = {}
    for symbol, tf in plan:
        by_symbol.setdefault(symbol, []).append(tf)
    for symbol, tf_list in sorted(by_symbol.items()):
        print(f"  {symbol}: {', '.join(tf_list)}")
    if dry_run:
        return 0

    total_rows = 0
    for symbol, tf_list in sorted(by_symbol.items()):
        # Read the 1m history once and reuse it for every target timeframe.
        print(f"\n[{symbol}] loading 1m bars…", flush=True)
        src = read_source_1m(symbol)
        if src is None:
            log.warning("%s: no readable 1m data, skipping", symbol)
            continue
        print(f"[{symbol}] {src.height:,} 1m bars", flush=True)

        for tf in tf_list:
            out = resample(src, symbol, tf)
            if out.is_empty():
                log.warning("%s %s: resample produced no rows", symbol, tf)
                continue
            n_parts = write_partitions(out, symbol, tf, overwrite=overwrite)
            update_metadata(symbol, tf)
            total_rows += out.height
            print(
                f"[{symbol}] {tf}: {out.height:,} bars -> {n_parts} partitions "
                f"({out['timestamp'].min()} .. {out['timestamp'].max()})",
                flush=True,
            )

    print(f"\nDone. {total_rows:,} aggregated bars written.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", help="Comma-separated symbols (default: all with 1m data)")
    parser.add_argument("--tfs", default="1h,4h,1d", help="Comma-separated target timeframes")
    parser.add_argument("--all", action="store_true", help="Process every symbol with 1m data")
    parser.add_argument("--plan", action="store_true", help="Show what would be done, then exit")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rebuild timeframes that already exist (needed to replace session-relative 4h)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    elif args.all or args.plan:
        symbols = lake_symbols()
    else:
        parser.error("pass --symbols, --all, or --plan")

    tfs = [t.strip() for t in args.tfs.split(",") if t.strip()]
    unknown = [t for t in tfs if t not in TF_RULES]
    if unknown:
        parser.error(f"unsupported timeframes {unknown}; choose from {list(TF_RULES)}")

    sys.exit(run(symbols, tfs, overwrite=args.overwrite, dry_run=args.plan))


if __name__ == "__main__":
    main()

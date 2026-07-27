"""BL-301 — Pipeline orchestrator: incremental fetch + merge + audit.

Public API:

  status(symbol=None, tf=None) -> CoverageReport
  fetch(symbol, tf, source, *, start=None, end=None, full=False)
        -> FetchReport

Storage layout (Hive-style):

  data/lake/raw/<source>/<file>             immutable, by source
  data/lake/normalized/symbol=<S>/tf=<TF>/year=<YYYY>/month=<MM>.parquet
  data/lake/curated/<SYMBOL>_<TF>.parquet     merged, latest-only convenience

The pipeline always writes normalized partitions; curated is rebuilt
on demand to keep complexity low. The :class:`DataRegistry` reads
directly from normalized partitions for time-range queries.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timezone

UTC = UTC, timezone
UTC = timezone.utc
from pathlib import Path

import polars as pl

from market.ingestion import metadata_io as meta
from market.ingestion.normalize import make_batch
from market.ingestion.sources import get_source
from market.ingestion.types import AssetSpec, OHLCVBar, SourceId

logger = logging.getLogger("oracle.market.ingestion.pipeline")

LAKE_ROOT = Path("data/lake")
RAW_ROOT = LAKE_ROOT / "raw"
NORM_ROOT = LAKE_ROOT / "normalized"
CURATED_ROOT = LAKE_ROOT / "curated"


@dataclass
class CoverageReport:
    """Result of :meth:`Pipeline.status`."""

    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    total_rows: int = 0
    total_files: int = 0


@dataclass
class FetchReport:
    """Result of :meth:`Pipeline.fetch`."""

    source: str
    symbol: str
    timeframe: str
    rows_in: int = 0
    rows_out: int = 0
    rows_rejected: int = 0
    partitions_written: int = 0
    duration_s: float = 0.0
    note: str = ""


class Pipeline:
    """Incremental, idempotent data lake pipeline.

    Idempotency: if you call fetch() twice with overlapping ranges,
    the second call is a no-op for already-fetched timestamps (de-duplicated
    by (symbol, tf, timestamp) before writing).
    """

    def __init__(self) -> None:
        NORM_ROOT.mkdir(parents=True, exist_ok=True)
        CURATED_ROOT.mkdir(parents=True, exist_ok=True)
        meta.META_DIR.mkdir(parents=True, exist_ok=True)
        self.coverage = meta.load_coverage()

    def status(self, symbol: str | None = None, tf: str | None = None) -> CoverageReport:
        report = CoverageReport()
        for key, info in self.coverage.items():
            if symbol and not key.startswith(f"{symbol}|"):
                continue
            if tf and not key.endswith(f"|{tf}"):
                continue
            report.covered.append(key)
            report.total_rows += int(info.get("rows", 0))
        sym_keys = set()
        for path in NORM_ROOT.glob("symbol=*"):
            for tf_dir in path.glob("tf=*"):
                for year_dir in tf_dir.glob("year=*"):
                    n_files = sum(1 for _ in year_dir.glob("*.parquet"))
                    report.total_files += n_files
                    sym_keys.add(f"{path.name.split('=', 1)[1]}|{tf_dir.name.split('=', 1)[1]}")
        report.missing = [k for k in sym_keys if k not in report.covered]
        return report

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        source: SourceId,
        *,
        start: date | None = None,
        end: date | None = None,
        full: bool = False,
    ) -> FetchReport:
        t0 = time.monotonic()
        src = get_source(source)
        spec = src.asset_spec(symbol)
        if end is None:
            end = date.today()
        if start is None:
            start = self._infer_start(symbol, timeframe, source, full=full)
        report = FetchReport(source=str(source), symbol=symbol, timeframe=timeframe)
        try:
            raw_iter = src.fetch_range(symbol, timeframe, start, end)
            batch = make_batch(spec, source, raw_iter)
            report.rows_in = batch.source_rows_total
            report.rows_rejected = batch.source_rejected
            partitions = self._write_normalized(spec, source, timeframe, batch.bars)
            report.rows_out = sum(df.height for df in partitions.values())
            report.partitions_written = len(partitions)
            self._update_coverage(spec, timeframe, batch.bars, source)
            self._update_lineage(spec, timeframe, partitions, source)
            meta.save_coverage(self.coverage)
        except Exception as exc:
            report.note = f"FAILED: {type(exc).__name__}: {exc}"
            logger.exception("fetch failed: %s", report)
        report.duration_s = round(time.monotonic() - t0, 2)
        meta.append_audit_log(
            source=str(source),
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            rows_in=report.rows_in,
            rows_out=report.rows_out,
            rows_rejected=report.rows_rejected,
            note=report.note,
        )
        return report

    def _infer_start(self, symbol: str, timeframe: str, source: SourceId, *, full: bool) -> date:
        if full:
            spec = get_source(source).asset_spec(symbol)
            return spec.earliest_available or date(2010, 1, 1)
        cov = self.coverage.get(meta.coverage_key(symbol, timeframe), {})
        latest = cov.get("latest")
        if latest:
            return datetime.fromisoformat(latest).date()
        spec = get_source(source).asset_spec(symbol)
        return spec.earliest_available or date(2010, 1, 1)

    def _write_normalized(
        self, spec: AssetSpec, source: SourceId, timeframe: str, bars: list[OHLCVBar]
    ) -> dict[Path, pl.DataFrame]:
        """Group bars by (year, month) and write each partition as parquet."""
        if not bars:
            return {}
        records = [
            {
                "timestamp": b.timestamp,
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "volume": float(b.volume),
                "symbol": b.symbol,
                "source": str(b.source),
                "timeframe": b.timeframe,
            }
            for b in bars
        ]
        df = pl.DataFrame(records).with_columns(
            pl.col("timestamp").dt.replace_time_zone(None),
            pl.col("timestamp").dt.year().alias("year"),
            pl.col("timestamp").dt.month().alias("month"),
        )
        df = df.unique(subset=["timestamp"], keep="last").sort("timestamp")
        partitions: dict[Path, pl.DataFrame] = {}
        for (year, month), group in df.group_by(["year", "month"]):
            part_dir = NORM_ROOT / f"symbol={spec.symbol}" / f"tf={timeframe}" / f"year={year}"
            part_dir.mkdir(parents=True, exist_ok=True)
            part_file = part_dir / f"month={int(month):02d}.parquet"
            existing = pl.read_parquet(part_file) if part_file.exists() else None
            if existing is not None:
                merged = pl.concat([existing, group.drop(["year", "month"])])
                merged = merged.unique(subset=["timestamp"], keep="last").sort("timestamp")
            else:
                merged = group.drop(["year", "month"])
            merged.write_parquet(part_file)
            partitions[part_file] = merged
        return partitions

    def _update_coverage(
        self, spec: AssetSpec, timeframe: str, bars: list[OHLCVBar], source: SourceId
    ) -> None:
        if not bars:
            return
        key = meta.coverage_key(spec.symbol, timeframe)
        cov = self.coverage.get(key, {"rows": 0, "sources": []})
        earliest = min(cov.get("earliest", "9999"), min(b.timestamp.isoformat() for b in bars))
        latest = max(cov.get("latest", "0000"), max(b.timestamp.isoformat() for b in bars))
        cov.update(
            {
                "earliest": earliest,
                "latest": latest,
                "rows": int(cov.get("rows", 0)) + len(bars),
                "sources": list(set(cov.get("sources", []) + [str(source)])),
                "last_touch": datetime.now(UTC).isoformat(),
                "version": int(cov.get("version", 0)) + 1,
            }
        )
        self.coverage[key] = cov

    def _update_lineage(
        self,
        spec: AssetSpec,
        timeframe: str,
        partitions: dict[Path, pl.DataFrame],
        source: SourceId,
    ) -> None:
        lineage = meta.load_lineage()
        for path in partitions:
            rel = path.relative_to(LAKE_ROOT).as_posix()
            entries = lineage.setdefault(rel, [])
            if str(source) not in entries:
                entries.append(str(source))
            lineage[rel] = entries
        meta.save_lineage(lineage)


def cli_status() -> int:
    p = Pipeline()
    s = p.status()
    print(f"Covered: {len(s.covered)} (symbol,tf) pairs")
    print(f"Total rows: {s.total_rows}")
    print(f"Total partition files: {s.total_files}")
    if s.missing:
        print("Missing coverage:")
        for k in s.missing:
            print(f"  - {k}")
    return 0


def cli_fetch(
    symbol: str,
    timeframe: str,
    source: str,
    *,
    start: str | None = None,
    end: str | None = None,
    full: bool = False,
) -> int:
    p = Pipeline()
    sd = date.fromisoformat(start) if start else None
    ed = date.fromisoformat(end) if end else None
    r = p.fetch(symbol, timeframe, SourceId(source), start=sd, end=ed, full=full)
    print(
        f"[{r.source}] {r.symbol} {r.timeframe}: "
        f"in={r.rows_in} out={r.rows_out} rej={r.rows_rejected} "
        f"partitions={r.partitions_written} {r.duration_s}s {r.note}"
    )
    return 0 if not r.note.startswith("FAILED") else 1

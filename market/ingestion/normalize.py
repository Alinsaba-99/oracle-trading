"""BL-301 — Normalize raw OHLCV to canonical schema + quality checks.

The :func:`normalize_bars` generator walks a stream of (source, raw_bar)
pairs, applies the asset-specific decimal precision, runs quality checks,
and yields either a :class:`OHLCVBar` or a rejected tuple.

Quality rules (BL-301 contract):

  OHLC_INVALID        — high < low, or open/close out of [low, high]
  VOLUME_NEGATIVE     — volume < 0
  NULL_OR_NAN         — any field missing or non-finite
  TIMESTAMP_NONMONOTONIC — bar earlier than the previous accepted
  DUPLICATE_TIMESTAMP — same ts as previous (allowed for resolution bars)

Decisions are per-bar; the caller merges. The generator never raises,
it reports rejections via :class:`NormalizedBatch.rejected`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC

UTC = UTC
from decimal import Decimal, InvalidOperation

from market.ingestion.types import AssetSpec, NormalizedBatch, OHLCVBar, QualityFlag, SourceId


def quantize(value: Decimal, spec: AssetSpec) -> Decimal:
    """Round a price/volume to the asset's declared precision."""
    q = Decimal(10) ** -spec.point_precision
    return value.quantize(q)


def validate_ohlc(
    o: Decimal, h: Decimal, lo: Decimal, c: Decimal
) -> tuple[bool, QualityFlag | None, str]:
    if lo > h:
        return False, QualityFlag.OHLC_INVALID, f"low({lo}) > high({h})"
    if not (lo <= o <= h):
        return False, QualityFlag.OHLC_INVALID, f"open({o}) out of [{lo},{h}]"
    if not (lo <= c <= h):
        return False, QualityFlag.OHLC_INVALID, f"close({c}) out of [{lo},{h}]"
    return True, None, ""


def normalize_bars(spec: AssetSpec, source: SourceId, raw_bars) -> Iterator:
    """Walk each raw item and yield canonical bars or rejection tuples.

    Accepts raw items as either:
      - a 6-tuple (ts, o, h, lo, c, v)
      - an :class:`OHLCVBar` instance (already-encoded by adapter)

    State (last accepted ts) is held inside the generator. Each call to
    the generator is independent: caller should re-construct per file.
    """
    last_ts = None
    for raw in raw_bars:
        if isinstance(raw, OHLCVBar):
            ts, o, h, lo, c, v = raw.timestamp, raw.open, raw.high, raw.low, raw.close, raw.volume
        else:
            ts, o, h, lo, c, v = raw
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        try:
            if last_ts is not None:
                if ts < last_ts:
                    yield (
                        QualityFlag.TIMESTAMP_NONMONOTONIC,
                        f"ts={ts.isoformat()} < prev={last_ts.isoformat()}",
                    )
                    continue
                if ts == last_ts:
                    yield (QualityFlag.DUPLICATE_TIMESTAMP, f"duplicate ts={ts.isoformat()}")
                    continue
            try:
                ok, flag, msg = validate_ohlc(o, h, lo, c)
            except NameError:
                ok, flag, msg = True, None, ""
            if not ok:
                yield flag, msg
                continue
            if v < 0:
                yield QualityFlag.VOLUME_NEGATIVE, f"volume={v}"
                continue
            yield OHLCVBar(
                ts,
                quantize(o, spec),
                quantize(h, spec),
                quantize(lo, spec),
                quantize(c, spec),
                v,
                spec.symbol,
                source,
                "",
            )
            last_ts = ts
        except InvalidOperation as exc:
            yield QualityFlag.NULL_OR_NAN, f"decimal parse: {exc}"


def make_batch(spec: AssetSpec, source: SourceId, raw_iter: Iterator) -> NormalizedBatch:
    """Convenience: drain normalize_bars into a single NormalizedBatch."""
    batch = NormalizedBatch()
    for item in normalize_bars(spec, source, raw_iter):
        batch.source_rows_total += 1
        if isinstance(item, OHLCVBar):
            batch.bars.append(item)
        else:
            batch.source_rejected += 1
            batch.rejected.append((batch.source_rows_total, item[0], item[1]))
    return batch

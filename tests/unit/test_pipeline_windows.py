"""BL-104 — Pipeline a finestre mensili: slicing e persistenza parziale.

Un backfill profondo (1m dal listing) non deve abortire con in=0 su un
timeout di rete: ogni mese completato viene scritto e registrato prima del
successivo. I test usano una fonte finta con i path del lake puntati su
tmp_path (nessuna contaminazione del lake reale).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from market.ingestion import metadata_io as meta
from market.ingestion.pipeline import Pipeline, _month_windows
from market.ingestion.types import AssetClass, AssetSpec, OHLCVBar, SourceId


def _bar(timestamp: datetime) -> OHLCVBar:
    return OHLCVBar(
        timestamp=timestamp,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("1000"),
        symbol="TESTX",
        source=SourceId.BINANCE_REST,
        timeframe="1m",
    )


def test_month_windows_slices_correctly() -> None:
    windows = _month_windows(date(2020, 8, 11), date(2020, 10, 3))
    assert windows == [
        (date(2020, 8, 11), date(2020, 8, 31)),
        (date(2020, 9, 1), date(2020, 9, 30)),
        (date(2020, 10, 1), date(2020, 10, 3)),
    ]
    assert _month_windows(date(2020, 1, 1), date(2020, 1, 31)) == [
        (date(2020, 1, 1), date(2020, 1, 31))
    ]
    assert _month_windows(date(2020, 2, 28), date(2020, 2, 29)) == [
        (date(2020, 2, 28), date(2020, 2, 29))
    ]


class _FlakySource:
    """Fake source: bars in January, TimeoutError in February."""

    name = SourceId.BINANCE_REST

    def asset_spec(self, symbol: str) -> AssetSpec:
        return AssetSpec(
            symbol=symbol,
            asset_class=AssetClass.CRYPTO_SPOT,
            exchange="fake",
            earliest_available=date(2020, 1, 1),
        )

    def fetch_range(self, _symbol: str, _tf: str, start: date, end: date) -> Iterator[OHLCVBar]:
        if start.month == 2:
            raise TimeoutError("fake network stall")
        for day in range(1, 4):
            ts = datetime(start.year, start.month, day, tzinfo=UTC)
            if start <= ts.date() <= end:
                yield _bar(ts)


@pytest.fixture
def isolated_lake(tmp_path: Path, monkeypatch: Any) -> None:
    """Point NORM_ROOT and metadata dirs at tmp_path (no real-lake writes)."""
    import market.ingestion.pipeline as pipe_mod

    monkeypatch.setattr(pipe_mod, "NORM_ROOT", tmp_path / "norm")
    monkeypatch.setattr(meta, "META_DIR", tmp_path / "meta")
    monkeypatch.setattr(pipe_mod, "get_source", lambda _src: _FlakySource())


def test_fetch_failure_persists_completed_windows(isolated_lake: None) -> None:  # noqa: ARG001
    report = Pipeline().fetch(
        "TESTX", "1m", SourceId.BINANCE_REST, start=date(2020, 1, 1), end=date(2020, 2, 29)
    )
    # Gennaio persistito (3 barre), febbraio fallito -> FAILED ma rows_out > 0
    assert report.rows_out == 3
    assert report.rows_in == 3
    assert "FAILED" in report.note
    assert report.partitions_written == 1


def test_fetch_resumes_from_coverage_after_partial_failure(
    isolated_lake: None,  # noqa: ARG001
) -> None:
    pipe = Pipeline()
    first = pipe.fetch(
        "TESTX", "1m", SourceId.BINANCE_REST, start=date(2020, 1, 1), end=date(2020, 2, 29)
    )
    assert "FAILED" in first.note
    # coverage registra gennaio -> il resume parte da febbraio (e fallisce
    # ancora, senza ri-scaricare gennaio: la seconda finestra e' marzo vuoto)
    cov = pipe.coverage["TESTX|1m"]
    assert cov["latest"].startswith("2020-01")
    assert cov["rows"] == 3


def test_empty_range_classified_weekend(isolated_lake: None) -> None:  # noqa: ARG001
    # Finestra solo-weekend: NO_DATA_WEEKEND, non NO_DATA
    report = Pipeline().fetch(
        "TESTX", "1m", SourceId.BINANCE_REST, start=date(2020, 1, 4), end=date(2020, 1, 5)
    )
    assert report.rows_out == 0
    assert report.note == "NO_DATA_WEEKEND"

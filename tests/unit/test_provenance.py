"""Tests for point-in-time data provenance and lineage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.data.provenance import (
    DataLineage,
    DataNotAvailableError,
    DataProvenance,
    ProvenancedRecord,
    require_cutoff,
)


class TestDataProvenance:
    """Provenance chain invariants."""

    def test_auto_ingested_at(self) -> None:
        p = DataProvenance()
        assert p.ingested_at is not None
        assert p.ingested_at.tzinfo == timezone.utc

    def test_auto_record_id(self) -> None:
        p1 = DataProvenance()
        p2 = DataProvenance()
        assert p1.record_id != p2.record_id

    def test_default_revision_none(self) -> None:
        p = DataProvenance()
        assert p.revision_id is None

    def test_available_at_defaults_to_published(self) -> None:
        pub = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        p = DataProvenance(published_at=pub)
        assert p.available_at is None  # Doesn't auto-default
        # But is_available_at uses published_at as fallback
        assert p.is_available_at(datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc))

    def test_is_available_before_published(self) -> None:
        pub = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        p = DataProvenance(published_at=pub)
        assert not p.is_available_at(datetime(2026, 6, 1, 11, 0, tzinfo=timezone.utc))

    def test_is_available_after_published(self) -> None:
        pub = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        p = DataProvenance(published_at=pub)
        assert p.is_available_at(datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc))

    def test_available_at_overrides_published(self) -> None:
        pub = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        avail = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
        p = DataProvenance(published_at=pub, available_at=avail)
        assert not p.is_available_at(datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc))
        assert p.is_available_at(datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc))

    def test_to_dict_contains_timestamps(self) -> None:
        p = DataProvenance(source="yfinance")
        d = p.to_dict()
        assert d["source"] == "yfinance"
        assert "ingested_at" in d
        assert "record_id" in d

    def test_to_dict_datetime_as_iso(self) -> None:
        p = DataProvenance()
        d = p.to_dict()
        assert isinstance(d["ingested_at"], str)

    def test_default_source_license(self) -> None:
        p = DataProvenance()
        assert p.source_license == ""


class TestProvenancedRecord:
    """Record with embedded provenance."""

    def test_record_holds_data(self) -> None:
        prov = DataProvenance(source="test")
        rec = ProvenancedRecord(provenance=prov, data={"price": 100.0})
        assert rec.data["price"] == 100.0
        assert rec.provenance.source == "test"


class TestDataLineage:
    """Transformation lineage tracking."""

    def test_lineage_starts_empty(self) -> None:
        lineage = DataLineage()
        assert lineage.to_dict() == []

    def test_add_step(self) -> None:
        lineage = DataLineage()
        lineage.add_step("normalize", "raw_1", "norm_1")
        steps = lineage.to_dict()
        assert len(steps) == 1
        assert steps[0]["step"] == "normalize"
        assert steps[0]["input_id"] == "raw_1"
        assert steps[0]["output_id"] == "norm_1"

    def test_multiple_steps(self) -> None:
        lineage = DataLineage()
        lineage.add_step("raw→normalized", "raw_1", "norm_1")
        lineage.add_step("normalized→feature", "norm_1", "feat_1")
        assert len(lineage.to_dict()) == 2


class TestCutoff:
    """Cutoff enforcement."""

    def test_cutoff_returns_cutoff(self) -> None:
        cutoff = datetime(2026, 6, 1, tzinfo=timezone.utc)
        assert require_cutoff(cutoff) == cutoff

    def test_cutoff_none_returns_now(self) -> None:
        result = require_cutoff()
        assert result is not None
        assert result.tzinfo == timezone.utc

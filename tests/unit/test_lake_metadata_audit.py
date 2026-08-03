"""BL-307 — Lake metadata audit: lineage/coverage completeness gate.

The audit is the repo's guardrail against silent provenance loss: every
partition under ``data/lake/normalized`` must be traceable in
``lineage.json``, and every coverage record must carry the full schema.
Runs against the real lake (fast — metadata + file scan only).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
AUDIT_SCRIPT = REPO / "scripts" / "audit_lake_metadata.py"


def _load_audit_module() -> Any:
    spec = importlib.util.spec_from_file_location("audit_lake_metadata", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None, "audit script not importable"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["audit_lake_metadata"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not (REPO / "data/lake/normalized").exists(), reason="lake not present")
def test_no_partition_without_lineage() -> None:
    mod = _load_audit_module()
    report = mod.audit()
    missing = report["missing_lineage"]
    assert not missing, (
        f"{len(missing)} partition(s) without lineage — run "
        f"`uv run python scripts/audit_lake_metadata.py --fix`:\n"
        + "\n".join(f"  {p}" for p in missing[:10])
    )


@pytest.mark.skipif(not (REPO / "data/lake/normalized").exists(), reason="lake not present")
def test_no_dangling_lineage_references() -> None:
    mod = _load_audit_module()
    report = mod.audit()
    assert not report["dangling_lineage"], (
        f"{len(report['dangling_lineage'])} lineage key(s) point to missing files"
    )


@pytest.mark.skipif(not (REPO / "data/lake/normalized").exists(), reason="lake not present")
def test_coverage_schema_complete() -> None:
    mod = _load_audit_module()
    report = mod.audit()
    incomplete = report["coverage_incomplete"]
    assert not incomplete, (
        f"{len(incomplete)} coverage record(s) missing schema fields — run "
        f"`uv run python scripts/audit_lake_metadata.py --fix`:\n"
        + "\n".join(f"  {k}" for k in incomplete[:10])
    )

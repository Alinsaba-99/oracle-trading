"""Unit tests for ``scripts.monitor_prop_rules`` (BL-725).

Covers:

* clean verification when all files match the manifest;
* drift detection when a snapshot's bytes change;
* missing file detection (manifest references an absent file);
* untracked file detection (a file lives in the snapshot root but is
  not in the manifest);
* stale manifest (no SNAPSHOTS.tsv at all);
* fixture profile whose `source_url` is not in the manifest;
* profile marked newer than the snapshot's ``fetched_at``
  (firm page updated after the fixture was verified);
* CLI exit code semantics: ``--check-only`` returns 0 when clean, 1
  when drift detected.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "monitor_prop_rules.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from monitor_prop_rules import (  # noqa: E402
    STATUS_DRIFT,
    STATUS_OK,
    IntegrityReport,
    ManifestRow,
    PropRuleMonitor,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write_manifest(path: Path, rows: list[ManifestRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["url\tdest\tfetched_at\tsha256\tbytes"]
    for r in rows:
        lines.append(f"{r.url}\t{r.dest}\t{r.fetched_at}\t{r.sha256}\t{r.bytes_}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_snapshot(root: Path, rel: str, body: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


@pytest.fixture
def fixture_root(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a fake snapshot dir + manifest + fixtures.py."""
    snap_root = tmp_path / "docs" / "firm_sources"
    manifest_path = snap_root / "SNAPSHOTS.tsv"
    fixtures_path = tmp_path / "fixtures.py"
    return snap_root, manifest_path, fixtures_path


# ---------------------------------------------------------------------------
# ManifestRow parsing
# ---------------------------------------------------------------------------


def test_manifest_row_parses_valid_line() -> None:
    row = ManifestRow.from_line(
        "https://ftmo.com/x\tftmo/2026-08-22-trading-objectives.html\t"
        "2026-08-22T10:00:00+00:00\tabcdef0123456789abcd\t123456"
    )
    assert row is not None
    assert row.url == "https://ftmo.com/x"
    assert row.dest == "ftmo/2026-08-22-trading-objectives.html"
    assert row.sha256 == "abcdef0123456789abcd"
    assert row.bytes_ == 123456


def test_manifest_row_rejects_short_line() -> None:
    assert ManifestRow.from_line("only\tthree\tfields") is None


def test_manifest_row_rejects_non_int_bytes() -> None:
    assert ManifestRow.from_line("u\td\t2026-08-22T10:00:00+00:00\tsha\tnotanumber") is None


# ---------------------------------------------------------------------------
# check_integrity — clean
# ---------------------------------------------------------------------------


def test_check_clean(
    fixture_root: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    snap_root, manifest_path, _ = fixture_root
    body = b"<html>hello</html>"
    _make_snapshot(snap_root, "ftmo/2026-08-22.html", body)
    import hashlib

    sha = hashlib.sha256(body).hexdigest()
    _write_manifest(
        manifest_path,
        [
            ManifestRow(
                url="https://ftmo.com/x",
                dest="ftmo/2026-08-22.html",
                fetched_at="2026-08-22T10:00:00+00:00",
                sha256=sha,
                bytes_=len(body),
            )
        ],
    )

    monitor = PropRuleMonitor(
        snapshot_root=snap_root, manifest_path=manifest_path, fixtures_path=manifest_path
    )
    # Disable fixture cross-check for this test (covered separately).
    monkeypatch.setattr(monitor, "iter_fixture_profiles", lambda: [])
    report = monitor.check_integrity()
    assert report.status == STATUS_OK
    assert report.drift_count == 0
    assert report.manifest_present is True
    assert report.manifest_rows == 1
    assert report.snapshots_on_disk == 1
    assert isinstance(report, IntegrityReport)


# ---------------------------------------------------------------------------
# check_integrity — drift
# ---------------------------------------------------------------------------


def test_drift_when_file_changes(
    fixture_root: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    snap_root, manifest_path, _ = fixture_root
    body = b"<html>hello</html>"
    path = _make_snapshot(snap_root, "ftmo/x.html", body)
    import hashlib

    sha = hashlib.sha256(body).hexdigest()
    _write_manifest(
        manifest_path,
        [
            ManifestRow(
                url="https://ftmo.com/x",
                dest="ftmo/x.html",
                fetched_at="2026-08-22T10:00:00+00:00",
                sha256=sha,
                bytes_=len(body),
            )
        ],
    )

    # Mutate the file AFTER the manifest was written.
    path.write_bytes(b"<html>hello MODIFIED</html>")

    monitor = PropRuleMonitor(
        snapshot_root=snap_root, manifest_path=manifest_path, fixtures_path=manifest_path
    )
    monkeypatch.setattr(monitor, "iter_fixture_profiles", lambda: [])
    report = monitor.check_integrity()
    assert report.status == STATUS_DRIFT
    assert report.drift_count == 1
    drift = report.drifts[0]
    assert drift.kind == "modified_file"
    assert drift.dest == "ftmo/x.html"
    assert drift.expected_sha256 == sha
    assert drift.actual_sha256 != sha


def test_missing_file_detected(
    fixture_root: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    snap_root, manifest_path, _ = fixture_root
    # Manifest references a file that does NOT exist on disk.
    _write_manifest(
        manifest_path,
        [
            ManifestRow(
                url="https://ftmo.com/x",
                dest="ftmo/missing.html",
                fetched_at="2026-08-22T10:00:00+00:00",
                sha256="deadbeef" * 8,
                bytes_=100,
            )
        ],
    )

    monitor = PropRuleMonitor(
        snapshot_root=snap_root, manifest_path=manifest_path, fixtures_path=manifest_path
    )
    monkeypatch.setattr(monitor, "iter_fixture_profiles", lambda: [])
    report = monitor.check_integrity()
    assert report.status == STATUS_DRIFT
    kinds = {d.kind for d in report.drifts}
    assert "missing_file" in kinds
    drift = next(d for d in report.drifts if d.kind == "missing_file")
    assert drift.dest == "ftmo/missing.html"


def test_untracked_file_detected(
    fixture_root: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    snap_root, manifest_path, _ = fixture_root
    # File on disk but not in the manifest.
    _make_snapshot(snap_root, "ftmo/untracked.html", b"<html>x</html>")
    _write_manifest(manifest_path, [])  # empty manifest (header only)

    monitor = PropRuleMonitor(
        snapshot_root=snap_root, manifest_path=manifest_path, fixtures_path=manifest_path
    )
    monkeypatch.setattr(monitor, "iter_fixture_profiles", lambda: [])
    report = monitor.check_integrity()
    assert report.status == STATUS_DRIFT
    kinds = {d.kind for d in report.drifts}
    assert "untracked_file" in kinds
    drift = next(d for d in report.drifts if d.kind == "untracked_file")
    assert drift.dest == "ftmo/untracked.html"


def test_txt_file_is_not_a_snapshot(
    fixture_root: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.txt` extracted companions must not be treated as snapshots."""
    snap_root, manifest_path, _ = fixture_root
    _make_snapshot(snap_root, "ftmo/x.txt", b"extracted text")
    _write_manifest(manifest_path, [])

    monitor = PropRuleMonitor(
        snapshot_root=snap_root, manifest_path=manifest_path, fixtures_path=manifest_path
    )
    monkeypatch.setattr(monitor, "iter_fixture_profiles", lambda: [])
    report = monitor.check_integrity()
    # No drift: .txt is excluded.
    assert report.snapshots_on_disk == 0
    assert report.drift_count == 0


def test_no_manifest_at_all(
    fixture_root: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    snap_root, manifest_path, _ = fixture_root
    # No SNAPSHOTS.tsv, but a snapshot exists.
    _make_snapshot(snap_root, "ftmo/x.html", b"<html>x</html>")

    monitor = PropRuleMonitor(
        snapshot_root=snap_root, manifest_path=manifest_path, fixtures_path=manifest_path
    )
    monkeypatch.setattr(monitor, "iter_fixture_profiles", lambda: [])
    report = monitor.check_integrity()
    assert report.manifest_present is False
    # Without a manifest, every file on disk is "untracked".
    assert report.status == STATUS_DRIFT
    assert {d.kind for d in report.drifts} == {"untracked_file"}


# ---------------------------------------------------------------------------
# Fixtures cross-check
# ---------------------------------------------------------------------------


def test_profile_url_not_in_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A fixture profile whose source_url is absent from the manifest
    is reported as drift."""
    snap_root = tmp_path / "snap"
    snap_root.mkdir(parents=True, exist_ok=True)
    manifest_path = snap_root / "SNAPSHOTS.tsv"
    manifest_path.write_text("url\tdest\tfetched_at\tsha256\tbytes\n", encoding="utf-8")

    monitor = PropRuleMonitor(
        snapshot_root=snap_root,
        manifest_path=manifest_path,
        fixtures_path=manifest_path,  # unused; we monkeypatch the loader
    )
    monkeypatch.setattr(
        monitor,
        "iter_fixture_profiles",
        lambda: [
            {
                "id": "StubCo/X/evaluation/MT5/100000/2026-08-22",
                "source_url": "https://stub.example.invalid/x",
                "source_checked_at": "2026-08-22",
            }
        ],
    )

    report = monitor.check_integrity()
    assert report.status == STATUS_DRIFT
    kinds = {d.kind for d in report.profile_drifts}
    assert "profile_url_not_manifested" in kinds


def test_profile_outdated_when_snapshot_fresher(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When the snapshot fetched_at is NEWER than the profile's
    source_checked_at, the monitor flags 'profile_outdated'."""
    snap_root = tmp_path / "snap"
    snap_root.mkdir(parents=True, exist_ok=True)
    manifest_path = snap_root / "SNAPSHOTS.tsv"

    body = b"<html>x</html>"
    _make_snapshot(snap_root, "ftmo/x.html", body)
    import hashlib

    sha = hashlib.sha256(body).hexdigest()
    _write_manifest(
        manifest_path,
        [
            ManifestRow(
                url="https://ftmo.com/x",
                dest="ftmo/x.html",
                fetched_at="2026-08-25T10:00:00+00:00",  # NEWER
                sha256=sha,
                bytes_=len(body),
            )
        ],
    )

    monitor = PropRuleMonitor(
        snapshot_root=snap_root, manifest_path=manifest_path, fixtures_path=manifest_path
    )
    monkeypatch.setattr(
        monitor,
        "iter_fixture_profiles",
        lambda: [
            {
                "id": "FTMO/X/evaluation/MT5/100000/2026-08-22",
                "source_url": "https://ftmo.com/x",
                "source_checked_at": "2026-08-22",  # OLDER
            }
        ],
    )

    report = monitor.check_integrity()
    assert report.status == STATUS_DRIFT
    kinds = {d.kind for d in report.profile_drifts}
    assert "profile_outdated" in kinds


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


def test_generate_report_writes_json(
    fixture_root: tuple[Path, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snap_root, manifest_path, _ = fixture_root
    body = b"<html>hello</html>"
    _make_snapshot(snap_root, "ftmo/x.html", body)
    import hashlib

    sha = hashlib.sha256(body).hexdigest()
    _write_manifest(
        manifest_path,
        [
            ManifestRow(
                url="https://ftmo.com/x",
                dest="ftmo/x.html",
                fetched_at="2026-08-22T10:00:00+00:00",
                sha256=sha,
                bytes_=len(body),
            )
        ],
    )

    out_dir = tmp_path / "out"
    monitor = PropRuleMonitor(
        snapshot_root=snap_root, manifest_path=manifest_path, fixtures_path=manifest_path
    )
    monkeypatch.setattr(monitor, "iter_fixture_profiles", lambda: [])
    out_path = monitor.generate_report(out_dir)

    assert out_path.exists()
    assert out_path.parent == out_dir
    payload = json.loads(out_path.read_text())
    assert payload["status"] == STATUS_OK
    assert payload["drift_count"] == 0
    # Latest pointer is also written.
    latest = out_dir / "latest.json"
    assert latest.exists()
    assert json.loads(latest.read_text())["status"] == STATUS_OK


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=60)


def test_cli_check_only_clean(
    fixture_root: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    snap_root, manifest_path, _ = fixture_root
    body = b"<html>x</html>"
    _make_snapshot(snap_root, "ftmo/x.html", body)
    import hashlib

    sha = hashlib.sha256(body).hexdigest()
    _write_manifest(
        manifest_path,
        [
            ManifestRow(
                url="https://ftmo.com/x",
                dest="ftmo/x.html",
                fetched_at="2026-08-22T10:00:00+00:00",
                sha256=sha,
                bytes_=len(body),
            )
        ],
    )

    result = _run_cli(
        "--check-only",
        "--snapshot-root",
        str(snap_root),
        "--manifest",
        str(manifest_path),
        "--fixtures",
        str(manifest_path),  # not used in --check-only for a clean run
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "status=ok" in result.stdout


def test_cli_check_only_drift(fixture_root: tuple[Path, Path, Path]) -> None:
    snap_root, manifest_path, _ = fixture_root
    # File on disk but not in the manifest → drift.
    _make_snapshot(snap_root, "ftmo/untracked.html", b"<html>x</html>")
    _write_manifest(manifest_path, [])

    result = _run_cli(
        "--check-only",
        "--snapshot-root",
        str(snap_root),
        "--manifest",
        str(manifest_path),
        "--fixtures",
        str(manifest_path),
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "status=drift" in result.stdout
    assert "untracked_file" in result.stdout


def test_cli_generate_report_default_exit_clean(
    fixture_root: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    snap_root, manifest_path, _ = fixture_root
    out_dir = snap_root.parent / "out"
    body = b"<html>x</html>"
    _make_snapshot(snap_root, "ftmo/x.html", body)
    import hashlib

    sha = hashlib.sha256(body).hexdigest()
    _write_manifest(
        manifest_path,
        [
            ManifestRow(
                url="https://ftmo.com/x",
                dest="ftmo/x.html",
                fetched_at="2026-08-22T10:00:00+00:00",
                sha256=sha,
                bytes_=len(body),
            )
        ],
    )

    result = _run_cli(
        "--out-dir",
        str(out_dir),
        "--snapshot-root",
        str(snap_root),
        "--manifest",
        str(manifest_path),
        "--fixtures",
        str(manifest_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # A JSON file with today's timestamp prefix was written.
    files = list(out_dir.glob("prop-rules-monitor-*.json"))
    assert files, f"expected report in {out_dir}, got {list(out_dir.iterdir())}"
    payload = json.loads(files[0].read_text())
    assert payload["status"] == STATUS_OK

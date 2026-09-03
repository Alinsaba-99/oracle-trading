"""BL-725 — Cron monitor for prop-firm rule snapshots.

Detects drift in ``docs/firm_sources/``:

* HTML snapshots whose bytes / sha256 no longer match the manifest
  (``SNAPSHOTS.tsv``).
* Manifest rows whose destination file is missing on disk.
* HTML files on disk that are not tracked by the manifest.
* ``policy/prop_firm/fixtures.py`` profiles whose ``source_url`` is
  missing from the manifest, or whose ``source_checked_at`` predates
  the snapshot ``fetched_at`` (firm updated the page after the
  fixture was last verified).

Designed to run in CI / cron with ``--check-only``: returns exit
code 0 when clean, 1 on any drift so the cron job fails the build.

Usage::

    # CI gate: 0 = clean, 1 = drift
    python scripts/monitor_prop_rules.py --check-only

    # Save JSON report
    python scripts/monitor_prop_rules.py --out-dir docs/reports/prop-firm

Related:

* BL-720 — snapshot fetcher that *writes* ``SNAPSHOTS.tsv``.
* BL-721 — fixtures verified against the 2026-08-22 snapshots.
* BL-722 — multi-firm prop governor consuming the fixtures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SNAPSHOTS_DIR = REPO / "docs/firm_sources"
MANIFEST = SNAPSHOTS_DIR / "SNAPSHOTS.tsv"
FIXTURES = REPO / "policy" / "prop_firm" / "fixtures.py"
DEFAULT_OUT_DIR = REPO / "docs" / "reports" / "prop-firm"

#: File extensions that ARE snapshots (tracked by manifest).
SNAPSHOT_SUFFIXES = (".html",)

#: Status of a single integrity check.
STATUS_OK = "ok"
STATUS_DRIFT = "drift"


def _collect_profiles(module: object, profile_cls: type) -> list[dict[str, str]]:
    """Read ``profile_cls`` instances off *module* and return serialised rows."""
    rows: list[dict[str, str]] = []
    for name in dir(module):
        obj = getattr(module, name)
        if not isinstance(obj, profile_cls):
            continue
        url = getattr(obj, "source_url", "") or ""
        if not url.startswith(("http://", "https://")):
            continue
        rows.append(
            {
                "id": obj.version_key,
                "source_url": url,
                "source_checked_at": getattr(obj, "source_checked_at", "") or "",
            }
        )
    return rows


@dataclass(frozen=True)
class ManifestRow:
    """One row of ``SNAPSHOTS.tsv``."""

    url: str
    dest: str
    fetched_at: str
    sha256: str
    bytes_: int

    @classmethod
    def from_line(cls, line: str) -> ManifestRow | None:
        parts = line.split("\t")
        if len(parts) < 5:
            return None
        try:
            return cls(
                url=parts[0],
                dest=parts[1],
                fetched_at=parts[2],
                sha256=parts[3].lower(),
                bytes_=int(parts[4]),
            )
        except ValueError:
            return None


@dataclass(frozen=True)
class Drift:
    """A single integrity violation."""

    kind: str  # "modified_file" | "missing_file" | "untracked_file" | "profile_url_not_manifested" | "profile_outdated"
    dest: str  # destination path (relative to SNAPSHOTS_DIR) or profile id
    detail: str
    expected_sha256: str | None = None
    actual_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntegrityReport:
    """Aggregate integrity check result."""

    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str = ""
    snapshots_root: str = ""
    manifest_present: bool = False
    manifest_rows: int = 0
    snapshots_on_disk: int = 0
    drift_count: int = 0
    drifts: list[Drift] = field(default_factory=list)
    profile_count: int = 0
    profile_drifts: list[Drift] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.drift_count or self.profile_drifts:
            return STATUS_DRIFT
        return STATUS_OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "snapshots_root": self.snapshots_root,
            "manifest_present": self.manifest_present,
            "manifest_rows": self.manifest_rows,
            "snapshots_on_disk": self.snapshots_on_disk,
            "drift_count": self.drift_count,
            "profile_drifts_count": len(self.profile_drifts),
            "status": self.status,
            "drifts": [d.to_dict() for d in self.drifts],
            "profile_drifts": [d.to_dict() for d in self.profile_drifts],
        }


class PropRuleMonitor:
    """Verify ``docs/firm_sources/`` matches its manifest + fixtures."""

    def __init__(
        self,
        snapshot_root: Path = SNAPSHOTS_DIR,
        manifest_path: Path = MANIFEST,
        fixtures_path: Path = FIXTURES,
    ) -> None:
        self.snapshot_root = snapshot_root
        self.manifest_path = manifest_path
        self.fixtures_path = fixtures_path

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------
    def load_manifest(self) -> dict[str, ManifestRow]:
        """Return ``{dest: ManifestRow}`` from ``SNAPSHOTS.tsv``.

        The header row is skipped.  Malformed lines are ignored.
        """
        if not self.manifest_path.exists():
            return {}
        rows: dict[str, ManifestRow] = {}
        for line in self.manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("url\t"):
                continue
            row = ManifestRow.from_line(line)
            if row is not None:
                rows[row.dest] = row
        return rows

    # ------------------------------------------------------------------
    # Hashing
    # ------------------------------------------------------------------
    @staticmethod
    def hash_file(path: Path) -> tuple[str, int]:
        """Return ``(sha256, byte_count)`` for *path*."""
        data = path.read_bytes()
        return hashlib.sha256(data).hexdigest(), len(data)

    def iter_snapshot_files(self) -> list[Path]:
        """All snapshot files (``*.html``) under ``snapshot_root``.

        Text-extracted ``.txt`` companions produced by
        ``extract_snapshot_text.py`` are excluded — they are derived
        artifacts, not source snapshots.
        """
        if not self.snapshot_root.exists():
            return []
        return sorted(
            p
            for p in self.snapshot_root.rglob("*")
            if p.is_file() and p.suffix.lower() in SNAPSHOT_SUFFIXES
        )

    # ------------------------------------------------------------------
    # Fixtures (cross-check)
    # ------------------------------------------------------------------
    def iter_fixture_profiles(self) -> list[dict[str, str]]:
        """Return ``[{id, source_url, source_checked_at}, ...]`` from fixtures.py.

        Profiles are detected by importing the module and reading
        ``FirmProgramProfile`` instances whose ``source_url`` looks
        like an http(s) URL.

        ``fixtures_path`` defaults to the real ``policy/prop_firm/fixtures.py``
        (the *only* file that publishes profiles today).  Tests can
        substitute a different module path; if the path is missing or
        cannot be imported we return ``[]`` so the caller records the
        gap as drift without crashing.
        """
        # Lazy import: importlib + import_module so we can point at an
        # arbitrary path (the real fixtures live at policy.prop_firm.fixtures,
        # but a test fixture can ship a minimal stub).
        import importlib
        import importlib.util

        from policy.prop_firm.profile import FirmProgramProfile

        candidates: list[object] = []
        # 1. Try importlib.util.spec_from_file_location with the configured path.
        if self.fixtures_path.exists():
            try:
                spec = importlib.util.spec_from_file_location(
                    "_monitor_prop_rules_fixtures", self.fixtures_path
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)  # type: ignore[union-attr]
                    candidates.extend(_collect_profiles(module, FirmProgramProfile))
            except Exception:
                # Path was given but did not import cleanly — honour the
                # caller's explicit choice and do NOT fall back to the
                # canonical package (else tests/CI passing a TSV or
                # empty file would always trigger drift against the
                # full real fixtures catalogue).
                return []
            # If the path was given but contains no profiles (e.g. a
            # TSV or an empty fixtures file), still honour the explicit
            # choice and skip the fallback to the canonical package.
            if not candidates:
                return []

        # 2. If no candidates were loaded from fixtures_path, fallback to canonical package.
        if not candidates:
            try:
                from policy.prop_firm import fixtures as fx_module

                candidates.extend(_collect_profiles(fx_module, FirmProgramProfile))
            except Exception:  # pragma: no cover — environment failure
                pass

        # Deduplicate by (id, source_url) keeping the first occurrence.
        seen: set[tuple[str, str]] = set()
        out: list[dict[str, str]] = []
        for entry in candidates:
            key = (entry["id"], entry["source_url"])
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
        return out

    # ------------------------------------------------------------------
    # Core check
    # ------------------------------------------------------------------
    def check_integrity(self) -> IntegrityReport:
        """Walk the snapshot dir + fixtures and produce an IntegrityReport."""
        report = IntegrityReport(snapshots_root=str(self.snapshot_root))
        manifest = self.load_manifest()
        report.manifest_present = self.manifest_path.exists()
        report.manifest_rows = len(manifest)

        # 1. Each manifest row → file must exist + sha256 must match.
        manifest_dests = set(manifest)
        for dest, row in manifest.items():
            path = self.snapshot_root / dest
            if not path.exists():
                report.drifts.append(
                    Drift(
                        kind="missing_file",
                        dest=dest,
                        detail=f"manifest references {dest} but file is absent",
                        expected_sha256=row.sha256,
                    )
                )
                continue
            actual_sha, actual_bytes = self.hash_file(path)
            if actual_sha.lower() != row.sha256:
                detail_msg = (
                    f"sha256 mismatch (expected {row.sha256[:16]}…, got {actual_sha[:16]}…)"
                    if actual_bytes == row.bytes_
                    else (
                        f"sha256 mismatch and size changed ({row.bytes_}→{actual_bytes}); "
                        f"expected {row.sha256[:16]}…, got {actual_sha[:16]}…"
                    )
                )
                report.drifts.append(
                    Drift(
                        kind="modified_file",
                        dest=dest,
                        detail=detail_msg,
                        expected_sha256=row.sha256,
                        actual_sha256=actual_sha,
                    )
                )

        # 2. Each snapshot file → must be tracked.
        on_disk = self.iter_snapshot_files()
        report.snapshots_on_disk = len(on_disk)
        for path in on_disk:
            rel = path.relative_to(self.snapshot_root).as_posix()
            if rel not in manifest_dests:
                report.drifts.append(
                    Drift(
                        kind="untracked_file",
                        dest=rel,
                        detail=f"{rel} on disk but absent from SNAPSHOTS.tsv",
                    )
                )

        report.drift_count = len(report.drifts)

        # 3. Fixture profiles cross-reference.
        try:
            profiles = self.iter_fixture_profiles()
            report.profile_count = len(profiles)
            url_to_rows = {row.url: row for row in manifest.values()}
            for prof in profiles:
                url = prof["source_url"]
                row = url_to_rows.get(url)
                if row is None:
                    report.profile_drifts.append(
                        Drift(
                            kind="profile_url_not_manifested",
                            dest=prof["id"],
                            detail=(
                                f"profile {prof['id']} cites {url} but "
                                f"SNAPSHOTS.tsv has no row for it"
                            ),
                        )
                    )
                    continue
                checked = prof["source_checked_at"]
                if checked and row.fetched_at > checked:
                    # Profile is stale vs the snapshot → firm page was
                    # re-fetched AFTER the profile was verified.
                    report.profile_drifts.append(
                        Drift(
                            kind="profile_outdated",
                            dest=prof["id"],
                            detail=(
                                f"profile verified {checked} but snapshot "
                                f"{row.dest} was re-fetched {row.fetched_at}; "
                                f"re-verify rules"
                            ),
                        )
                    )
        except Exception as exc:
            report.profile_drifts.append(
                Drift(
                    kind="fixture_import_failed",
                    dest=str(self.fixtures_path),
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )

        report.finished_at = datetime.now(UTC).isoformat()
        return report

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def generate_report(self, out_dir: Path) -> Path:
        """Write ``prop-rules-monitor-<timestamp>.json`` into *out_dir*.

        Returns the written path.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        report = self.check_integrity()
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out_path = out_dir / f"prop-rules-monitor-{ts}.json"
        out_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        # Latest pointer (overwrite atomically).
        latest = out_dir / "latest.json"
        latest.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_drift_line(drift: Drift) -> str:
    return f"  [{drift.kind}] {drift.dest}: {drift.detail}"


def _print_report(report: IntegrityReport) -> None:
    print(
        f"status={report.status} manifest={report.manifest_rows} "
        f"snapshots={report.snapshots_on_disk} "
        f"drifts={report.drift_count} "
        f"profile_drifts={len(report.profile_drifts)} "
        f"profiles={report.profile_count}"
    )
    for drift in report.drifts:
        print(_format_drift_line(drift))
    for drift in report.profile_drifts:
        print(_format_drift_line(drift))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=("BL-725 — verify docs/firm_sources/ snapshot integrity and fixture alignment.")
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Exit 0 if clean, 1 if drift detected. Suppresses report writing.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Directory to write the JSON report (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        default=SNAPSHOTS_DIR,
        help=f"Snapshots root (default: {SNAPSHOTS_DIR})",
    )
    parser.add_argument(
        "--manifest", type=Path, default=MANIFEST, help=f"Manifest TSV path (default: {MANIFEST})"
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=FIXTURES,
        help=f"Fixtures module path (default: {FIXTURES})",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress drift lines, print only the summary line."
    )
    args = parser.parse_args(argv)

    monitor = PropRuleMonitor(
        snapshot_root=args.snapshot_root, manifest_path=args.manifest, fixtures_path=args.fixtures
    )

    if args.check_only:
        report = monitor.check_integrity()
        if not args.quiet:
            _print_report(report)
        return 0 if report.status == STATUS_OK else 1

    out_path = monitor.generate_report(args.out_dir)
    # Re-check so we can print the same summary.
    report = monitor.check_integrity()
    print(f"report -> {out_path}")
    if not args.quiet:
        _print_report(report)
    return 0 if report.status == STATUS_OK else 1


if __name__ == "__main__":
    sys.exit(main())

"""BL-726 — Pre-registration manifest loader and tree-clean verifier.

This module is the machine-checkable companion to the pre-registration
documents in ``docs/research/prereg/``.  A pre-registration manifest
records every parameter of the strategy variant being qualified, the
exact git commit being qualified, the sample window, and the
pre-registered pass/fail thresholds, BEFORE anyone runs the
qualification.

The contract is deliberately small:

* ``Preregistration`` is a frozen dataclass parsed from JSON
  (``docs/research/prereg/<BL>.manifest.json``).
* ``load_prereg(path)`` deserialises the manifest and validates the
  schema (every numeric threshold has the right sign, the variant
  parameters are within the supported ranges, the code_commit is a
  40-char lowercase hex SHA-1).
* ``verify_clean_tree(expected_commit, repo_root)`` runs ``git rev-parse
  HEAD`` and ``git status --porcelain`` from *repo_root* and asserts the
  working tree has zero changes in any of the qualification-affecting
  paths and the HEAD commit equals *expected_commit*.  This is the
  anti-HARKing gate: the moment someone tweaks a config and re-runs,
  the verifier trips.

Pre-registration is the antidote to two well-documented failure modes:

* **HARKing** (Hypothesizing After the Results are Known) — picking
  the parameters that look best in the qualification run and pretending
  they were always the ones.  The manifest is the immutable record of
  what was promised.
* **Code drift** — running the qualification against a code tree that
  no longer matches the snapshot of the code the thresholds were
  justified against.  ``verify_clean_tree`` closes that hole.

References
----------
* López de Prado (2018). *Advances in Financial Machine Learning*.
  ch.7-12 (PurgedKFold, DSR, PSR, CPCV, PBO).
* Bailey & López de Prado (2014). "The Deflated Sharpe Ratio."
  JPM 40(5).
* ADR-017 (backtest-overfitting validation), ADR-019 (Lane B priority),
  ADR-021 (canonical metrics).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

#: Paths whose modifications invalidate a pre-registration.  Listed as
#: top-level dirs / files so the verifier does not have to walk every
#: nested module (and so the whitelist itself is auditable).
_QUALIFICATION_AFFECTING_PATHS: tuple[str, ...] = (
    "analytics/strategy/",
    "analytics/research/",
    "analytics/qualification/",
    "analytics/metrics/",
    "analytics/fundamental/simfin_loader.py",
)

_HEX_SHA1 = re.compile(r"^[0-9a-f]{40}$")


class PreregError(ValueError):
    """Invalid pre-registration manifest (schema, range, or type error)."""


@dataclass(frozen=True)
class Preregistration:
    """Frozen pre-registration manifest for one strategy variant.

    Attributes
    ----------
    bl_id
        Backlog id (e.g. ``"BL-726"``) the manifest belongs to.
    variant_name
        Human-readable name of the frozen variant (e.g.
        ``"lane_b_composite_aggressive"``).
    code_commit
        40-character hex SHA-1 of the commit being qualified.
    parameters
        Mapping of parameter name to its frozen value.  Values are JSON
        scalars or simple lists; the schema is strategy-specific and is
        NOT enforced beyond requiring a mapping here.
    sample_window
        Dict with at least ``qualification_start`` / ``qualification_end``
        ISO-8601 dates plus any train/validation/bear subwindows.
    thresholds
        Dict of pre-registered pass/fail thresholds (e.g. ``dsr_min``,
        ``pbo_max``, ``haircut_sharpe_min``).  All values are JSON
        scalars; their semantics live in the doc that owns the
        manifest.
    extra
        Free-form bag for anything strategy-specific (parameter locations,
        rationale text, anti-HARKing clause copy, …).  Empty dict if
        the manifest does not need one.
    """

    bl_id: str
    variant_name: str
    code_commit: str
    parameters: dict[str, object]
    sample_window: dict[str, str]
    thresholds: dict[str, object]
    extra: dict[str, object] = field(default_factory=dict)


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise PreregError(msg)


def _as_str_dict(d: object, *, where: str) -> dict[str, str]:
    if not isinstance(d, dict):
        raise PreregError(f"{where} must be a mapping, got {type(d).__name__}")
    out: dict[str, str] = {}
    for k, v in d.items():
        if not isinstance(k, str):
            raise PreregError(f"{where} keys must be strings, got {type(k).__name__}")
        if not isinstance(v, str):
            raise PreregError(f"{where}[{k!r}] must be a string, got {type(v).__name__}")
        out[k] = v
    return out


def _as_str_to_object(d: object, *, where: str) -> dict[str, object]:
    if not isinstance(d, dict):
        raise PreregError(f"{where} must be a mapping, got {type(d).__name__}")
    out: dict[str, object] = {}
    for k, v in d.items():
        if not isinstance(k, str):
            raise PreregError(f"{where} keys must be strings, got {type(k).__name__}")
        out[k] = v
    return out


def load_prereg(path: str | Path) -> Preregistration:
    """Load and validate a pre-registration manifest.

    The schema enforces only the structural invariants that prevent
    downstream bugs (string SHA-1, string keys in the sample window,
    mapping for parameters/thresholds).  Strategy-specific schema
    lives in the owning doc and is enforced there.

    Raises
    ------
    PreregError
        On any structural or type violation.  The manifest is
        REJECTED in that case — fixing it requires a new manifest
        version (do NOT edit a frozen manifest in place).
    """
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PreregError(f"manifest root must be a mapping, got {type(raw).__name__}")

    bl_id = raw.get("bl_id")
    if not isinstance(bl_id, str) or not bl_id:
        raise PreregError("'bl_id' must be a non-empty string")

    variant_name = raw.get("variant_name")
    if not isinstance(variant_name, str) or not variant_name:
        raise PreregError("'variant_name' must be a non-empty string")

    code_commit = raw.get("code_commit")
    if not isinstance(code_commit, str) or not _HEX_SHA1.match(code_commit):
        raise PreregError(
            f"'code_commit' must be a 40-char lowercase hex SHA-1, got {code_commit!r}"
        )

    parameters = _as_str_to_object(raw.get("parameters"), where="parameters")
    sample_window = _as_str_dict(raw.get("sample_window"), where="sample_window")
    for must_have in ("qualification_start", "qualification_end"):
        _require(must_have in sample_window, f"sample_window must contain {must_have!r}")

    thresholds = _as_str_to_object(raw.get("pre_registered_thresholds"), where="thresholds")
    extra = _as_str_to_object(raw.get("extra", {}), where="extra")

    return Preregistration(
        bl_id=bl_id,
        variant_name=variant_name,
        code_commit=code_commit,
        parameters=parameters,
        sample_window=sample_window,
        thresholds=thresholds,
        extra=extra,
    )


def _run_git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise PreregError(
            f"git {' '.join(args)} failed in {repo_root}: "
            f"exit={proc.returncode} stderr={proc.stderr.strip()}"
        )
    return proc.stdout


def verify_clean_tree(expected_commit: str, repo_root: str | Path = ".") -> None:
    """Assert HEAD == expected_commit and the working tree has no diffs
    in any qualification-affecting path.

    Runs ``git rev-parse HEAD`` and ``git status --porcelain`` from
    *repo_root*.  Allowed:

    * untracked files OUTSIDE the qualification-affecting paths;
    * ignored files.

    Anything else (modified tracked files, untracked files inside the
    whitelist, branch switches that change HEAD) trips the verifier.

    Parameters
    ----------
    expected_commit
        40-char hex SHA-1 expected at HEAD.
    repo_root
        Path to the repository root (default current directory).

    Raises
    ------
    PreregError
        When HEAD does not match, when the working tree has any
        tracked-file diff, or when an untracked file sits inside a
        qualification-affecting path.
    """
    root = Path(repo_root)
    if not _HEX_SHA1.match(expected_commit):
        raise PreregError(f"expected_commit must be a 40-char hex SHA-1, got {expected_commit!r}")

    head = _run_git(root, "rev-parse", "HEAD").strip()
    if head != expected_commit:
        raise PreregError(f"HEAD {head!r} does not match pre-registered commit {expected_commit!r}")

    porcelain = _run_git(root, "status", "--porcelain").splitlines()
    offending: list[str] = []
    for line in porcelain:
        # Porcelain v1 format: XY <path> (two status chars + space + path).
        # Tracked modifications show ' M', 'M ', 'MM', 'AM', 'A ', etc.
        # Untracked files show '??'.
        if len(line) < 3:
            continue
        xy = line[:2]
        path = line[3:].strip()
        # Always block tracked modifications anywhere in the tree.
        if xy != "??":
            offending.append(line)
            continue
        # Untracked files: block only if inside a qualification-affecting path.
        if any(path.startswith(p) for p in _QUALIFICATION_AFFECTING_PATHS):
            offending.append(line)

    if offending:
        raise PreregError(
            "working tree not clean in qualification-affecting paths; "
            "offending entries:\n  " + "\n  ".join(offending)
        )


__all__ = ["PreregError", "Preregistration", "load_prereg", "verify_clean_tree"]

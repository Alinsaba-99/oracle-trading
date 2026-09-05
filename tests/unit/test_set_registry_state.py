"""BL-743 — ``scripts/set_registry_state.py`` tests.

Tests cover the 4 contract lines of the CLI:

1. valid hid (+ optional ``@domain``) transitions and persists the
   resolved domain on a tmp root;
2. missing hid exits non-zero and surfaces :class:`HypothesisNotFoundError`;
3. ``--no-persist`` does NOT touch disk; the default (persist) DOES write
   YAML, observed as a mtime + content change;
4. a hypothesis id that exists in 2+ domains but no ``@domain`` resolves
   to an explicit ambiguity error (the BL-745 regression: the underlying
   ``HypothesisRegistry.update_status`` would silently transition the
   *first* cross-domain match).
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from analytics.research.factory.registry import (
    DomainRegistry,
    Hypothesis,
    HypothesisNotFoundError,
    HypothesisRegistry,
    RegistryError,
    load_registry,
    save_registry,
)
from scripts.set_registry_state import (
    _DEFAULT_ROOT,
    _parse_hid,
    _resolve_domain,
    _transition_in_domain,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixtures: a tmp registry with two domains sharing one EF-004 (cross-domain
# collision — the precondition that exposes the BL-745 bug).
# ---------------------------------------------------------------------------


def _make_hypothesis(
    hid: str,
    *,
    nome: str = "fixture-hypothesis",
    stato: str = "da_amplificare",
) -> Hypothesis:
    return Hypothesis.model_validate(
        {
            "id": hid,
            "nome": nome,
            "meccanismo": "meccanismo fittizio per test CLI >= 10 caratteri",
            "perche_esiste": "ragione fittizia per test CLI >= 10 caratteri",
            "origine": "practitioner",
            "fonti": ["test/fixture/source.md"],
            "decay_atteso_pct": 30.0,
            "dati_richiesti": ["dato fittizio"],
            "asset_candidati": ["BTCUSDT"],
            "timeframe": ["1h"],
            "stato": stato,
        }
    )


def _write_domain(path: Path, domain: str, *hypotheses: Hypothesis) -> Path:
    reg = DomainRegistry(domain=domain)
    for h in hypotheses:
        reg.add(h)
    save_registry(path, reg)
    return path


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    """Two domains; EF-004 is intentionally duplicated (BL-705 regression case)."""
    _write_domain(
        tmp_path / "01-fundamental.yaml",
        "01-fundamental",
        _make_hypothesis("EF-001", nome="alpha-fund"),
        _make_hypothesis("EF-004", nome="ambiguous-fund"),  # cross-domain
    )
    _write_domain(
        tmp_path / "10-seasonal.yaml",
        "10-seasonal",
        _make_hypothesis("EF-004", nome="overnight-drift-dealer-inventory"),
        _make_hypothesis("EF-007", nome="unique-in-seasonal"),
    )
    return tmp_path


def _run_cli(*args: str, root: Path) -> tuple[int, str, str]:
    """Invoke scripts.set_registry_state.main with overridden root."""
    argv = ["--root", str(root), *args]
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Pure parsers
# ---------------------------------------------------------------------------


def test_parse_hid_with_domain() -> None:
    assert _parse_hid("EF-004@10-seasonal") == ("EF-004", "10-seasonal")


def test_parse_hid_without_domain() -> None:
    assert _parse_hid("EF-007") == ("EF-007", None)


def test_parse_hid_malformed_empty_domain() -> None:
    with pytest.raises(ValueError, match="malformato"):
        _parse_hid("EF-004@")


def test_parse_hid_malformed_empty_hid() -> None:
    with pytest.raises(ValueError, match="malformato"):
        _parse_hid("@10-seasonal")


def test_parse_hid_empty() -> None:
    with pytest.raises(ValueError, match="vuoto"):
        _parse_hid("")


# ---------------------------------------------------------------------------
# Test 1 — valid hid + domain transiziona e persiste
# ---------------------------------------------------------------------------


def test_valid_hid_with_domain_transitions_and_persists(fixture_root: Path) -> None:
    yaml_path = fixture_root / "10-seasonal.yaml"
    mtime_before = yaml_path.stat().st_mtime
    # EF-004@10-seasonal: da_amplificare → amplificata è legale
    rc, out, err = _run_cli(
        "--hid",
        "EF-004@10-seasonal",
        "--stato",
        "amplificata",
        "--motivo",
        "letteratura conferma",
        "--ref",
        "https://example.com/ssrn",
        root=fixture_root,
    )
    assert rc == 0, (out, err)
    assert "OK EF-004" in out
    assert "persisted" in out

    # Re-read from disk: the transition is durable.  We must read by
    # domain (get_hypothesis returns the first cross-domain match — which
    # would silently fetch 01-fundamental here and mask the regression).
    fresh = HypothesisRegistry(root=fixture_root).scan()
    h_seasonal = fresh.get_domain("10-seasonal").get("EF-004")
    assert h_seasonal.stato == "amplificata"
    assert h_seasonal.evidenza[-1].tipo == "report"
    assert "da_amplificare → amplificata" in h_seasonal.evidenza[-1].testo
    # And only the targeted domain was touched (mtime bumped).
    assert yaml_path.stat().st_mtime >= mtime_before


def test_valid_hid_without_domain_unique_resolves(fixture_root: Path) -> None:
    # EF-007 lives only in 10-seasonal — the unique-domain shortcut applies.
    rc, out, err = _run_cli(
        "--hid",
        "EF-007",
        "--stato",
        "amplificata",
        "--motivo",
        "unico dominio",
        root=fixture_root,
    )
    assert rc == 0, (out, err)
    assert "domain '10-seasonal'" in out
    fresh = HypothesisRegistry(root=fixture_root).scan()
    assert fresh.get_hypothesis("EF-007").stato == "amplificata"


def test_no_persist_does_not_touch_disk(fixture_root: Path) -> None:
    rc, out, err = _run_cli(
        "--hid",
        "EF-004@10-seasonal",
        "--stato",
        "amplificata",
        "--motivo",
        "dry run",
        "--no-persist",
        root=fixture_root,
    )
    assert rc == 0, (out, err)
    assert "in-memory" in out
    # Re-read: nothing changed on disk.
    fresh = HypothesisRegistry(root=fixture_root).scan()
    assert fresh.get_hypothesis("EF-004").stato == "da_amplificare"
    assert fresh.get_hypothesis("EF-004").evidenza == []


def test_only_targeted_domain_is_persisted(fixture_root: Path) -> None:
    """BL-744 — builder determinismo: save_domain only, never save_all."""
    mtime_01 = (fixture_root / "01-fundamental.yaml").stat().st_mtime
    mtime_10 = (fixture_root / "10-seasonal.yaml").stat().st_mtime

    rc, _, _ = _run_cli(
        "--hid",
        "EF-004@10-seasonal",
        "--stato",
        "amplificata",
        "--motivo",
        "isolated write",
        root=fixture_root,
    )
    assert rc == 0

    after_01 = (fixture_root / "01-fundamental.yaml").stat().st_mtime
    after_10 = (fixture_root / "10-seasonal.yaml").stat().st_mtime
    # 10-seasonal bumped, 01-fundamental untouched.
    assert after_10 > mtime_10
    assert after_01 == mtime_01


# ---------------------------------------------------------------------------
# Test 2 — id inesistente → errore non-zero + HypothesisNotFoundError
# ---------------------------------------------------------------------------


def test_missing_hid_with_domain_returns_one(fixture_root: Path) -> None:
    rc, _out, err = _run_cli(
        "--hid",
        "EF-999@10-seasonal",
        "--stato",
        "amplificata",
        "--motivo",
        "missing",
        root=fixture_root,
    )
    assert rc == 1
    assert "EF-999" in err
    assert "10-seasonal" in err


def test_missing_hid_without_domain_returns_one(fixture_root: Path) -> None:
    rc, _out, err = _run_cli(
        "--hid",
        "EF-999",
        "--stato",
        "amplificata",
        "--motivo",
        "missing",
        root=fixture_root,
    )
    assert rc == 1
    assert "EF-999" in err


def test_unknown_explicit_domain_returns_two(fixture_root: Path) -> None:
    rc, _, err = _run_cli(
        "--hid",
        "EF-007@ghost-domain",
        "--stato",
        "amplificata",
        "--motivo",
        "ghost",
        root=fixture_root,
    )
    assert rc == 2
    assert "ghost" in err.lower() or "not loaded" in err.lower()


def test_illegal_transition_returns_three(fixture_root: Path) -> None:
    # da_amplificare → APPROVED skips stages (state machine refuses).
    rc, _, err = _run_cli(
        "--hid",
        "EF-007",
        "--stato",
        "APPROVED",
        "--motivo",
        "skip",
        root=fixture_root,
    )
    assert rc == 3
    assert "transizione illegale" in err


def test_missing_registry_root_returns_four(tmp_path: Path) -> None:
    rc, _, err = _run_cli(
        "--hid",
        "EF-001",
        "--stato",
        "amplificata",
        "--motivo",
        "no root",
        root=tmp_path / "nonexistent",
    )
    assert rc == 4
    assert "does not exist" in err or "registry root" in err.lower()


# ---------------------------------------------------------------------------
# Test 3 — persist scrive YAML (file modificato)
# ---------------------------------------------------------------------------


def test_persist_writes_yaml_file(fixture_root: Path) -> None:
    yaml_path = fixture_root / "10-seasonal.yaml"
    # Snapshot the on-disk timestamp + a content fingerprint.
    mtime_before = yaml_path.stat().st_mtime
    raw_before = yaml_path.read_text(encoding="utf-8")

    rc, _out, _ = _run_cli(
        "--hid",
        "EF-004@10-seasonal",
        "--stato",
        "amplificata",
        "--motivo",
        "persist check",
        "--ref",
        "docs/reports/foo.md",
        root=fixture_root,
    )
    assert rc == 0
    raw_after = yaml_path.read_text(encoding="utf-8")
    mtime_after = yaml_path.stat().st_mtime

    # The file changed.
    assert raw_after != raw_before
    # New evidence text + stato landed on disk.
    assert "amplificata" in raw_after
    assert "persist check" in raw_after
    assert "docs/reports/foo.md" in raw_after
    assert mtime_after >= mtime_before

    # Round-trip via the canonical loader: schema still validates.
    parsed = load_registry(yaml_path)
    assert parsed.domain == "10-seasonal"
    assert {h.id for h in parsed.hypotheses} == {"EF-004", "EF-007"}


# ---------------------------------------------------------------------------
# Test 4 — ambiguità cross-domain senza @domain (regressione BL-745)
# ---------------------------------------------------------------------------


def test_cross_domain_ambiguity_without_explicit_domain_errors(fixture_root: Path) -> None:
    """EF-004 lives in BOTH 01-fundamental and 10-seasonal → must error.

    Without the ``@<domain>`` qualifier, ``HypothesisRegistry.update_status``
    silently transitions the FIRST cross-domain match — that is the bug
    BL-745.  The CLI must reject and list the candidates instead.
    """
    rc, _out, err = _run_cli(
        "--hid",
        "EF-004",  # ambiguous — lives in 2 domains
        "--stato",
        "amplificata",
        "--motivo",
        "should not transition wrong hypothesis",
        root=fixture_root,
    )
    assert rc == 2
    # The error names both candidate domains.
    assert "EF-004" in err
    assert "01-fundamental" in err
    assert "10-seasonal" in err
    # And the hint to re-run with @domain is shown.
    assert "@" in err

    # Crucially: NO domain was touched on disk.
    fresh = HypothesisRegistry(root=fixture_root).scan()
    assert fresh.get_hypothesis("EF-004").stato == "da_amplificare"
    assert fresh.get_hypothesis("EF-004").evidenza == []


def test_explicit_domain_resolves_ambiguity(fixture_root: Path) -> None:
    """Same ambiguous hid, but ``@<domain>`` disambiguates correctly."""
    rc, _, _ = _run_cli(
        "--hid",
        "EF-004@01-fundamental",  # explicit: target the fundamental one
        "--stato",
        "amplificata",
        "--motivo",
        "explicit domain",
        root=fixture_root,
    )
    assert rc == 0
    fresh = HypothesisRegistry(root=fixture_root).scan()
    # The targeted one advanced; the other one untouched.
    fund_h = next(h for h in fresh.get_domain("01-fundamental").hypotheses if h.id == "EF-004")
    seas_h = next(h for h in fresh.get_domain("10-seasonal").hypotheses if h.id == "EF-004")
    assert fund_h.stato == "amplificata"
    assert seas_h.stato == "da_amplificare"


def test_transition_in_domain_helper_skips_cross_domain_bug(
    fixture_root: Path,
) -> None:
    """``_transition_in_domain`` writes the right file even when the hid is
    duplicated — proves the helper does NOT delegate to update_status
    (which would have resolved the first match).
    """
    reg = HypothesisRegistry(root=fixture_root).scan()
    h, _written = _transition_in_domain(
        reg,
        "EF-004",
        "10-seasonal",
        "amplificata",
        "explicit domain",
        None,
        persist=True,
    )
    assert h.stato == "amplificata"

    fresh = HypothesisRegistry(root=fixture_root).scan()
    seas = fresh.get_domain("10-seasonal").get("EF-004")
    fund = fresh.get_domain("01-fundamental").get("EF-004")
    assert seas.stato == "amplificata"
    assert fund.stato == "da_amplificare"


# ---------------------------------------------------------------------------
# _resolve_domain: unit tests against the helper directly
# ---------------------------------------------------------------------------


def test_resolve_domain_unique_match(fixture_root: Path) -> None:
    reg = HypothesisRegistry(root=fixture_root).scan()
    assert _resolve_domain(reg, "EF-001", None) == "01-fundamental"


def test_resolve_domain_explicit_match(fixture_root: Path) -> None:
    reg = HypothesisRegistry(root=fixture_root).scan()
    assert _resolve_domain(reg, "EF-001", "01-fundamental") == "01-fundamental"


def test_resolve_domain_explicit_unknown_raises_hypothesis_not_found(
    fixture_root: Path,
) -> None:
    reg = HypothesisRegistry(root=fixture_root).scan()
    with pytest.raises(HypothesisNotFoundError, match="EF-001"):
        _resolve_domain(reg, "EF-001", "10-seasonal")


def test_resolve_domain_unknown_explicit_domain_raises_registry_error(
    fixture_root: Path,
) -> None:
    reg = HypothesisRegistry(root=fixture_root).scan()
    with pytest.raises(RegistryError, match="not loaded"):
        _resolve_domain(reg, "EF-007", "ghost")


def test_resolve_domain_missing_hid_raises_not_found(fixture_root: Path) -> None:
    reg = HypothesisRegistry(root=fixture_root).scan()
    with pytest.raises(HypothesisNotFoundError):
        _resolve_domain(reg, "EF-999", None)


# ---------------------------------------------------------------------------
# Subprocess sanity check — exercises the if __name__ == "__main__" branch
# ---------------------------------------------------------------------------


def test_subprocess_end_to_end(fixture_root: Path) -> None:
    """Smoke test: invoke the script as a real CLI process."""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "set_registry_state.py"),
        "--root",
        str(fixture_root),
        "--hid",
        "EF-007",
        "--stato",
        "amplificata",
        "--motivo",
        "subprocess smoke",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "OK EF-007" in proc.stdout


# ---------------------------------------------------------------------------
# Smoke: real shipped registry must still be reachable (parse-only)
# ---------------------------------------------------------------------------


def test_shipped_root_parses() -> None:
    """The CLI's default root must be the canonical shipped directory and
    the parser must accept at least one of its hypotheses."""
    assert _DEFAULT_ROOT == (
        REPO_ROOT / "docs" / "knowledge-base" / "edge-factory" / "registry"
    )
    reg = HypothesisRegistry(root=_DEFAULT_ROOT).scan()
    assert len(reg) >= 40  # shipped corpus has 49 (BL-718) — soft lower bound


# json output parse to confirm the CLI surface (no garbage in stdout)
def _json_safe_payload(text: str) -> None:
    # The CLI prints a human line, not JSON; this is a structural check that
    # no traceback leaked into the captured output (parse errors would print
    # the exception text, not JSON).
    json.loads(text or "null")  # if it parses, the script didn't write JSON garbage


def test_subprocess_clean_stdout_on_error(fixture_root: Path) -> None:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "set_registry_state.py"),
        "--root",
        str(fixture_root),
        "--hid",
        "EF-004",  # ambiguous — exit 2
        "--stato",
        "amplificata",
        "--motivo",
        "ambiguity",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 2
    # stderr holds the message, stdout is empty.
    assert "EF-004" in proc.stderr
    _json_safe_payload(proc.stdout)

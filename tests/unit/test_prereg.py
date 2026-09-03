"""BL-726 — Pre-registration manifest loader + tree verifier tests.

The manifest is the anti-HARKing anchor: every value is pinned before
the qualification run, and any drift (code, thresholds, working tree)
trips the verifier.  These tests pin the loader's contract.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from analytics.research.factory.prereg import (
    PreregError,
    Preregistration,
    load_prereg,
    verify_clean_tree,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _good_manifest(extra: dict[str, object] | None = None) -> dict[str, Any]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    base: dict[str, Any] = {
        "bl_id": "BL-726",
        "variant_name": "lane_b_composite_aggressive",
        "code_commit": head,
        "parameters": {
            "use_composite": True,
            "composite_weights": [0.40, 0.40, 0.20],
            "composite_threshold": 0.65,
            "per_idea_stop_loss_pct": 0.05,
            "target_annual_vol": 0.40,
            "rebalance_months": 3,
            "top_n_holdings": 15,
        },
        "sample_window": {
            "qualification_start": "2020-01-01",
            "qualification_end": "2025-08-14",
            "train_subwindow": "2020-01-01 -> 2023-12-31",
            "validation_subwindow": "2024-01-01 -> 2025-08-14",
        },
        "pre_registered_thresholds": {
            "dsr_min": 0.95,
            "psr_min": 0.95,
            "pbo_max": 0.20,
            "haircut_sharpe_min": 0.50,
        },
    }
    if extra:
        base.update(extra)
    return base


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load_prereg
# ---------------------------------------------------------------------------


def test_load_good_manifest(tmp_path: Path) -> None:
    p = _write(tmp_path, _good_manifest())
    pre = load_prereg(p)
    assert isinstance(pre, Preregistration)
    assert pre.bl_id == "BL-726"
    assert pre.variant_name == "lane_b_composite_aggressive"
    assert pre.parameters["composite_threshold"] == 0.65
    assert pre.sample_window["qualification_start"] == "2020-01-01"
    assert pre.thresholds["dsr_min"] == 0.95


def test_load_rejects_root_not_mapping(tmp_path: Path) -> None:
    p = tmp_path / "manifest.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(PreregError, match="manifest root must be a mapping"):
        load_prereg(p)


def test_load_rejects_bad_commit(tmp_path: Path) -> None:
    p = _write(tmp_path, _good_manifest({"code_commit": "deadbeef"}))
    with pytest.raises(PreregError, match="40-char lowercase hex SHA-1"):
        load_prereg(p)


def test_load_rejects_missing_sample_window_keys(tmp_path: Path) -> None:
    bad = _good_manifest()
    del bad["sample_window"]["qualification_end"]
    p = _write(tmp_path, bad)
    with pytest.raises(PreregError, match="qualification_end"):
        load_prereg(p)


def test_load_rejects_non_string_window_values(tmp_path: Path) -> None:
    bad = _good_manifest()
    bad["sample_window"]["qualification_start"] = 20200101
    p = _write(tmp_path, bad)
    with pytest.raises(PreregError, match="must be a string"):
        load_prereg(p)


def test_load_rejects_non_string_bl_id(tmp_path: Path) -> None:
    bad = _good_manifest({"bl_id": 726})
    p = _write(tmp_path, bad)
    with pytest.raises(PreregError, match="'bl_id' must be a non-empty string"):
        load_prereg(p)


def test_load_accepts_optional_extra_bag(tmp_path: Path) -> None:
    p = _write(
        tmp_path, _good_manifest({"extra": {"anti_harking_clause": "no edits after results"}})
    )
    pre = load_prereg(p)
    assert pre.extra["anti_harking_clause"] == "no edits after results"


def test_load_accepts_parameters_with_lists(tmp_path: Path) -> None:
    p = _write(tmp_path, _good_manifest())
    pre = load_prereg(p)
    assert pre.parameters["composite_weights"] == [0.40, 0.40, 0.20]


# ---------------------------------------------------------------------------
# verify_clean_tree — pure-Python branches
# ---------------------------------------------------------------------------


def test_verify_rejects_non_hex_commit(tmp_path: Path) -> None:
    with pytest.raises(PreregError, match="40-char hex SHA-1"):
        verify_clean_tree("not-a-sha", repo_root=tmp_path)


def test_verify_rejects_head_mismatch() -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    # Flip a bit that keeps the string length + hex charset valid.
    bogus = ("0" if head[0] != "0" else "1") + head[1:]
    with pytest.raises(PreregError, match="does not match pre-registered commit"):
        verify_clean_tree(bogus, repo_root=REPO_ROOT)


def test_verify_accepts_clean_repo() -> None:
    """Real repo, clean working tree (after stashing any test pollution).

    Skipped when the test environment has a dirty tree (it just means
    the local dev machine is mid-edit, not that the contract is wrong).
    """
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    if porcelain.strip():
        pytest.skip("working tree is dirty in the test environment; cannot assert clean state")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    verify_clean_tree(head, repo_root=REPO_ROOT)


def test_verify_rejects_untracked_file_in_whitelisted_path() -> None:
    """An untracked file inside analytics/research/ MUST trip the verifier."""
    flag = REPO_ROOT / "analytics" / "research" / "_prereg_test_flag.txt"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("test", encoding="utf-8")
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        with pytest.raises(PreregError, match="qualification-affecting paths"):
            verify_clean_tree(head, repo_root=REPO_ROOT)
    finally:
        flag.unlink(missing_ok=True)


def test_verify_accepts_untracked_file_outside_whitelist(tmp_path: Path) -> None:
    """An untracked file outside the whitelist must NOT trip the verifier.

    Builds a throwaway git repo in *tmp_path* (with one initial commit so
    HEAD exists), drops a file that does NOT start with any whitelist
    prefix, and asserts ``verify_clean_tree`` raises nothing.  The
    whitelist is prefix-based; *tmp_path* lives under /tmp so it cannot
    match ``analytics/...``.
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    # Need at least one commit so HEAD resolves to a real SHA-1.
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "test"], check=True)
    (tmp_path / "README.md").write_text("scratch", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "README.md"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"], check=True, capture_output=True
    )
    head_proc = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    head_local: str = head_proc.stdout.strip()
    # Untracked file outside the whitelist prefix.
    (tmp_path / "scratch.txt").write_text("ok", encoding="utf-8")
    # Should not raise: the scratch.txt is untracked and outside the whitelist.
    verify_clean_tree(head_local, repo_root=tmp_path)


def test_verify_rejects_git_command_failure(tmp_path: Path) -> None:
    """If git fails to even run (no repo), the verifier surfaces that."""
    with pytest.raises(PreregError, match="git rev-parse HEAD failed"):
        # 40 valid hex chars, but no git repo at all.
        verify_clean_tree("0" * 40, repo_root=tmp_path)


# ---------------------------------------------------------------------------
# Round-trip: the actual BL-726 manifest shipped with the repo loads cleanly.
# ---------------------------------------------------------------------------


def test_repo_manifest_loads() -> None:
    manifest_path = REPO_ROOT / "docs" / "research" / "prereg" / "BL-726.manifest.json"
    if not manifest_path.exists():
        pytest.skip("BL-726.manifest.json not present in repo")
    pre = load_prereg(manifest_path)
    assert pre.bl_id == "BL-726"
    assert pre.variant_name == "lane_b_composite_aggressive"
    # The shipped manifest uses the BL-505d aggressive numbers; pin them.
    assert pre.parameters["composite_threshold"] == 0.65
    assert pre.parameters["per_idea_stop_loss_pct"] == 0.05
    assert pre.parameters["target_annual_vol"] == 0.40
    assert pre.thresholds["pbo_max"] == 0.20
    assert pre.thresholds["haircut_sharpe_min"] == 0.50

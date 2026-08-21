"""BL-615 — unit tests for the canonical spec-driven paper runner CLI.

Covers the pure surface of ``apps.cli.paper_commands``: spec loading
(YAML/JSON), hashing (data + spec), window construction (sequential +
Monte Carlo), and ensemble resolution. The full engine path
(``run_paper_spec``) is exercised by the G6 qualifying runs; here we
keep the suite fast and dependency-light.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from apps.cli.paper_commands import (
    PaperRunSpec,
    build_ensemble,
    build_windows,
    hash_data,
    hash_spec,
    load_spec,
)

# ---------------------------------------------------------------------------
# Spec loading
# ---------------------------------------------------------------------------


def test_load_spec_yaml(tmp_path: Path) -> None:
    p = tmp_path / "spec.yaml"
    p.write_text(
        "schema_version: 1\n"
        "name: test-run\n"
        "data: data/lake/normalized/symbol=ES/tf=1d/\n"
        "instrument: MES\n"
        "sessions: 10\n"
        "window: 50\n"
        "ensemble: edge_v2\n"
        "seed: 7\n"
    )
    spec = load_spec(p)
    assert spec.name == "test-run"
    assert spec.instrument == "MES"
    assert spec.sessions == 10
    assert spec.window == 50
    assert spec.ensemble == "edge_v2"
    assert spec.seed == 7
    # MES auto point value
    assert spec.resolved_point_value() == 5.0


def test_load_spec_json_and_defaults(tmp_path: Path) -> None:
    p = tmp_path / "spec.json"
    p.write_text(json.dumps({"data": "x.parquet"}))
    spec = load_spec(p)
    assert spec.name == "paper-run"
    assert spec.instrument == "ES"
    assert spec.sessions == 100
    assert spec.window == 95
    assert spec.ensemble == "regime"
    assert spec.storage is None  # BL-060 rule applied downstream
    # ES default point value
    assert spec.resolved_point_value() == 50.0
    # Explicit point value wins
    assert PaperRunSpec(data="x.parquet", point_value=12.5).resolved_point_value() == 12.5


def test_load_spec_rejects_non_mapping(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("[1, 2, 3]")
    with pytest.raises(ValueError, match="mapping"):
        load_spec(p)


def test_load_spec_rejects_invalid_ensemble(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("data: x.parquet\nensemble: not_real\n")
    with pytest.raises(ValidationError):  # pydantic validation (Literal)
        load_spec(p)


def test_load_spec_rejects_tiny_window(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("data: x.parquet\nwindow: 3\n")
    with pytest.raises(ValidationError):  # pydantic validation (ge=10)
        load_spec(p)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def test_hash_data_file_vs_directory(tmp_path: Path) -> None:
    f1 = tmp_path / "a.parquet"
    f1.write_bytes(b"content-a")
    sub = tmp_path / "sub"
    sub.mkdir()
    f2 = sub / "b.parquet"
    f2.write_bytes(b"content-b")

    # Directory hash is order-independent (sorted relative paths).
    dir_hash = hash_data(tmp_path)
    assert dir_hash == hash_data(tmp_path)
    assert len(dir_hash) == 64
    # A single file hashes to its own sha256, different from dir hash.
    file_hash = hash_data(f1)
    assert file_hash != dir_hash

    # Content change → hash change.
    f2.write_bytes(b"content-B-changed")
    assert hash_data(tmp_path) != dir_hash


def test_hash_data_empty_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No parquet files"):
        hash_data(tmp_path)


def test_hash_spec_is_deterministic() -> None:
    spec = PaperRunSpec(data="x.parquet", name="run-a")
    h1 = hash_spec(spec)
    h2 = hash_spec(PaperRunSpec(data="x.parquet", name="run-a"))
    assert h1 == h2
    # Any field change changes the hash.
    assert hash_spec(PaperRunSpec(data="x.parquet", name="run-b")) != h1


# ---------------------------------------------------------------------------
# Window construction
# ---------------------------------------------------------------------------


def _df(n: int) -> pl.DataFrame:
    return pl.DataFrame({"close": [float(i) for i in range(n)]})


def test_build_windows_sequential_covers_series() -> None:
    df = _df(1000)
    windows = build_windows(df, n=10, window=95, monte_carlo=False, seed=42)
    assert len(windows) == 10
    # Parity with the legacy runner: step = (n_total - window) // n, so
    # every window is full-size and starts advance uniformly.
    assert all(len(w) == 95 for w in windows)
    firsts = [float(w["close"][0]) for w in windows]
    assert firsts == sorted(firsts)
    step = (1000 - 95) // 10
    assert firsts[0] == 0.0 and firsts[1] == float(step)


def test_build_windows_monte_carlo_seeded_reproducible() -> None:
    df = _df(1000)
    w1 = build_windows(df, n=5, window=95, monte_carlo=True, seed=7)
    w2 = build_windows(df, n=5, window=95, monte_carlo=True, seed=7)
    assert all(a.equals(b) for a, b in zip(w1, w2, strict=True))
    w3 = build_windows(df, n=5, window=95, monte_carlo=True, seed=8)
    assert not all(a.equals(b) for a, b in zip(w1, w3, strict=True))


def test_build_windows_short_series_degrades() -> None:
    df = _df(100)  # only one full 95-bar window possible
    windows = build_windows(df, n=10, window=95, monte_carlo=False, seed=42)
    assert len(windows) == 10
    assert all(len(w) == 95 for w in windows)


# ---------------------------------------------------------------------------
# Ensemble resolution
# ---------------------------------------------------------------------------


def test_build_ensemble_regime_is_none() -> None:
    assert build_ensemble("regime") is None


def test_build_ensemble_edge_v2() -> None:
    from analytics.strategy.edge_ensemble_v2 import EdgeEnsembleV2

    assert isinstance(build_ensemble("edge_v2"), EdgeEnsembleV2)


def test_build_ensemble_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unknown ensemble"):
        build_ensemble("nope")

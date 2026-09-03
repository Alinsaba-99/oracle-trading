"""BL-700 — unified hypothesis registry tests.

These tests exercise the cross-domain :class:`HypothesisRegistry` over a
synthetic fixture directory so they don't depend on the current state of
``docs/knowledge-base/edge-factory/registry/`` (which is the data
under test, not the test fixture).  A few tests deliberately point at
the shipped registry to assert the live shape (46 hypotheses across 14
domains).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.research.factory.registry import (
    ALLOWED_TRANSITIONS,
    DomainRegistry,
    Evidence,
    Hypothesis,
    HypothesisNotFoundError,
    HypothesisRegistry,
    RegistryError,
    load_registry,
    save_registry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_SHIPPED_ROOT = Path("docs/knowledge-base/edge-factory/registry")


def _make_hypothesis(
    hid: str = "EF-001",
    *,
    nome: str = "funding-extremum-reversal",
    stato: str = "da_amplificare",
    decay: float = 30.0,
    fonti: list[str] | None = None,
    dati: list[str] | None = None,
) -> Hypothesis:
    return Hypothesis.model_validate(
        {
            "id": hid,
            "nome": nome,
            "meccanismo": "funding rate estremo spinge i marginal trader fuori posizione",
            "perche_esiste": "carry cost rende insostenibile la posizione affollata",
            "origine": "practitioner",
            "fonti": fonti or ["trading-os/knowledge/moondev-repos/RISPOSTE_D1-D15.md"],
            "decay_atteso_pct": decay,
            "dati_richiesti": dati or ["fundingRate 1h"],
            "asset_candidati": ["BTCUSDT"],
            "timeframe": ["1h"],
            "stato": stato,
        }
    )


def _write_domain(path: Path, domain: str, *hypotheses: Hypothesis) -> Path:
    """Write a single-domain YAML at *path* using the canonical schema."""
    reg = DomainRegistry(domain=domain)
    for h in hypotheses:
        reg.add(h)
    save_registry(path, reg)
    return path


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    """A small, fully-clean fixture: 3 domains, globally-unique ids."""
    _write_domain(
        tmp_path / "01-fundamental.yaml",
        "01-fundamental",
        _make_hypothesis("EF-001", nome="novy-marx"),
        _make_hypothesis("EF-002", nome="piotroski"),
    )
    _write_domain(
        tmp_path / "02-macro.yaml", "02-macro", _make_hypothesis("EF-003", nome="yield-curve")
    )
    _write_domain(
        tmp_path / "crypto-microstructure.yaml",
        "crypto-microstructure",
        _make_hypothesis("EF-004", nome="funding-extremum-reversal"),
        _make_hypothesis("EF-005", nome="bb-squeeze", decay=40.0),
    )
    return tmp_path


# ---------------------------------------------------------------------------
# scan / discovery
# ---------------------------------------------------------------------------


def test_scan_loads_every_yaml_in_directory(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    assert r.domains == ["01-fundamental", "02-macro", "crypto-microstructure"]
    assert len(r) == 5
    assert all(isinstance(d, DomainRegistry) for d in [r.get_domain(d) for d in r.domains])


def test_scan_returns_self_for_chaining(fixture_root: Path) -> None:
    r = HypothesisRegistry(root=fixture_root)
    assert r.scan() is r


def test_scan_missing_root_raises() -> None:
    r = HypothesisRegistry(root="/nonexistent/path/should/not/exist")
    with pytest.raises(RegistryError, match="does not exist"):
        r.scan()


def test_scan_resets_previously_loaded_state(fixture_root: Path) -> None:
    r = HypothesisRegistry(root=fixture_root)
    r.scan()
    assert r.domains  # non-empty

    # Create a new (smaller) tree and rescan — old domains should be gone.
    alt = fixture_root.parent / "alt"
    alt.mkdir()
    _write_domain(alt / "only.yaml", "only", _make_hypothesis("EF-099", nome="alone"))
    r.scan(alt)
    assert r.domains == ["only"]
    assert len(r) == 1


def test_scan_uses_default_root_when_none() -> None:
    # Smoke test: default root points at the shipped registry and the
    # scan is non-empty.  Does not assert specific content (the data
    # is governed by other tests below).
    r = HypothesisRegistry().scan()
    assert len(r) >= 46


# ---------------------------------------------------------------------------
# get_hypothesis / get_domain / list_hypotheses
# ---------------------------------------------------------------------------


def test_get_hypothesis_cross_domain(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    h = r.get_hypothesis("EF-003")
    assert h.id == "EF-003"
    assert h.nome == "yield-curve"
    assert r._domain_of("EF-003") == "02-macro"


def test_get_hypothesis_missing_raises(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    with pytest.raises(HypothesisNotFoundError, match="EF-999"):
        r.get_hypothesis("EF-999")


def test_get_domain_unknown_raises(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    with pytest.raises(RegistryError, match="not loaded"):
        r.get_domain("ghost")


def test_list_hypotheses_no_filter_returns_all(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    all_hyps = r.list_hypotheses()
    assert len(all_hyps) == 5
    assert {h.id for h in all_hyps} == {"EF-001", "EF-002", "EF-003", "EF-004", "EF-005"}


def test_list_hypotheses_filter_by_domain(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    crypto = r.list_hypotheses(domain="crypto-microstructure")
    assert [h.id for h in crypto] == ["EF-004", "EF-005"]
    # Sorting is by id within each domain (load order).
    fund = r.list_hypotheses(domain="01-fundamental")
    assert [h.id for h in fund] == ["EF-001", "EF-002"]


def test_list_hypotheses_filter_by_status(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    # Push EF-002 to "amplificata" and verify the filter isolates it.
    r.update_status("EF-002", "amplificata", "letteratura conferma")
    amplificata = r.list_hypotheses(stato="amplificata")
    assert [h.id for h in amplificata] == ["EF-002"]


def test_list_hypotheses_combined_filters(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    res = r.list_hypotheses(domain="crypto-microstructure", stato="da_amplificare")
    assert len(res) == 2
    assert all(h.stato == "da_amplificare" for h in res)
    assert {h.id for h in res} == {"EF-004", "EF-005"}


def test_iter_yields_all_hypotheses(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    ids = sorted(h.id for h in r)
    assert ids == ["EF-001", "EF-002", "EF-003", "EF-004", "EF-005"]


# ---------------------------------------------------------------------------
# update_status / save_all
# ---------------------------------------------------------------------------


def test_update_status_transitions_and_records_evidence(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    h = r.update_status("EF-001", "amplificata", "paper SSRN confermato", ref="https://ssrn/x")
    assert h.stato == "amplificata"
    assert len(h.evidenza) == 1
    assert h.evidenza[0].tipo == "report"
    assert "da_amplificare → amplificata" in h.evidenza[0].testo
    assert h.evidenza[0].ref == "https://ssrn/x"


def test_update_status_marks_domain_dirty(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    assert r.dirty_domains == []
    r.update_status("EF-001", "amplificata", "ok")
    assert r.dirty_domains == ["01-fundamental"]
    r.update_status("EF-004", "morta", "confutata")
    assert r.dirty_domains == ["01-fundamental", "crypto-microstructure"]


def test_update_status_without_persist_does_not_touch_disk(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    r.update_status("EF-001", "amplificata", "in-memory only")
    # Re-scan from disk: state must be reverted to the original.
    fresh = HypothesisRegistry().scan(fixture_root)
    h = fresh.get_hypothesis("EF-001")
    assert h.stato == "da_amplificare"
    assert h.evidenza == []


def test_update_status_with_persist_writes_yaml(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    written = r.update_status("EF-001", "amplificata", "ok", persist=True)
    assert written.id == "EF-001"
    # Re-read from disk: state survived.
    fresh = HypothesisRegistry().scan(fixture_root)
    h = fresh.get_hypothesis("EF-001")
    assert h.stato == "amplificata"
    assert len(h.evidenza) == 1


def test_save_all_persists_every_dirty_domain(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    r.update_status("EF-001", "amplificata", "x")
    r.update_status("EF-004", "morta", "y")
    written = r.save_all()
    assert {p.name for p in written} == {"01-fundamental.yaml", "crypto-microstructure.yaml"}
    assert r.dirty_domains == []
    # And the disk reflects it.
    fresh = HypothesisRegistry().scan(fixture_root)
    assert fresh.get_hypothesis("EF-001").stato == "amplificata"
    assert fresh.get_hypothesis("EF-004").stato == "morta"


def test_update_status_illegal_transition_propagates(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    with pytest.raises(RegistryError, match="transizione illegale"):
        r.update_status("EF-001", "APPROVED", "skip terminal")  # skips stages
    with pytest.raises(RegistryError, match="transizione illegale"):
        r.update_status("EF-001", "non_esistente", "x")


def test_update_status_unknown_id_raises(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    with pytest.raises(HypothesisNotFoundError):
        r.update_status("EF-999", "amplificata", "nope")


def test_state_machine_terminology_matches_design_spec() -> None:
    """Reference check: every stato in the design spec is in the transition table."""
    expected_states = {
        "da_amplificare",
        "amplificata",
        "in_qualifica",
        "APPROVED",
        "REJECTED",
        "morta",
        "morta_per_dati",
    }
    assert set(ALLOWED_TRANSITIONS) == expected_states


# ---------------------------------------------------------------------------
# validate_all
# ---------------------------------------------------------------------------


def test_validate_all_clean_on_fixture(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    assert r.validate_all() == []


def test_validate_all_detects_cross_domain_duplicate_ids(tmp_path: Path) -> None:
    # Two domains both shipping EF-001 — same bug as the live registry.
    _write_domain(tmp_path / "a.yaml", "alpha", _make_hypothesis("EF-001", nome="alpha-hyp"))
    _write_domain(tmp_path / "b.yaml", "beta", _make_hypothesis("EF-001", nome="beta-hyp"))
    r = HypothesisRegistry().scan(tmp_path)
    issues = r.validate_all()
    assert any("duplicate id EF-001" in i for i in issues)
    assert any("'alpha'" in i and "'beta'" in i for i in issues)


def test_validate_all_detects_empty_sources(tmp_path: Path) -> None:
    h = Hypothesis.model_validate(
        {
            "id": "EF-001",
            "nome": "funding-extremum-reversal",
            "meccanismo": "funding rate estremo spinge i marginal trader fuori posizione",
            "perche_esiste": "carry cost rende insostenibile la posizione affollata",
            "origine": "practitioner",
            "fonti": [],
            "decay_atteso_pct": 30.0,
            "dati_richiesti": ["fundingRate 1h"],
            "asset_candidati": ["BTCUSDT"],
            "timeframe": ["1h"],
        }
    )
    _write_domain(tmp_path / "d.yaml", "d", h)
    r = HypothesisRegistry().scan(tmp_path)
    issues = r.validate_all()
    assert any("no sources in fonti" in i for i in issues)


def test_validate_all_detects_empty_dati_richiesti_entry(tmp_path: Path) -> None:
    h = Hypothesis.model_validate(
        {
            "id": "EF-001",
            "nome": "funding-extremum-reversal",
            "meccanismo": "funding rate estremo spinge i marginal trader fuori posizione",
            "perche_esiste": "carry cost rende insostenibile la posizione affollata",
            "origine": "practitioner",
            "fonti": ["trading-os/knowledge/moondev-repos/RISPOSTE_D1-D15.md"],
            "decay_atteso_pct": 30.0,
            "dati_richiesti": ["fundingRate 1h", "   "],
            "asset_candidati": ["BTCUSDT"],
            "timeframe": ["1h"],
        }
    )
    _write_domain(tmp_path / "d.yaml", "d", h)
    r = HypothesisRegistry().scan(tmp_path)
    issues = r.validate_all()
    assert any("empty entry in dati_richiesti" in i for i in issues)


def test_validate_all_detects_bad_evidence_timestamp(tmp_path: Path) -> None:
    """Bypass Pydantic validation by patching the hypothesis in memory."""
    h = _make_hypothesis("EF-001")
    h.evidenza.append(
        Evidence.model_validate(
            {"data": "not-a-date", "tipo": "test", "testo": "smoke", "ref": None}
        )
    )
    _write_domain(tmp_path / "d.yaml", "d", h)
    r = HypothesisRegistry().scan(tmp_path)
    issues = r.validate_all()
    assert any("not ISO-8601" in i for i in issues)


def test_validate_all_detects_unknown_state(tmp_path: Path) -> None:
    """Inject a state value Pydantic would normally reject."""
    h = _make_hypothesis("EF-001")
    _write_domain(tmp_path / "d.yaml", "d", h)
    r = HypothesisRegistry().scan(tmp_path)
    # Bypass the Literal guard (would fail at load) by mutating after scan.
    r.get_hypothesis("EF-001").stato = "inventato"  # type: ignore[assignment]
    issues = r.validate_all()
    assert any("unknown stato" in i for i in issues)


def test_validate_all_detects_schema_version_mismatch(tmp_path: Path) -> None:
    _write_domain(tmp_path / "d.yaml", "d", _make_hypothesis("EF-001"))
    # Corrupt the schema_version after writing.
    reg = load_registry(tmp_path / "d.yaml")
    reg.schema_version = 999
    save_registry(tmp_path / "d.yaml", reg)
    r = HypothesisRegistry().scan(tmp_path)
    issues = r.validate_all()
    assert any("schema_version 999" in i for i in issues)


# ---------------------------------------------------------------------------
# Live (shipped) data shape
# ---------------------------------------------------------------------------


def test_shipped_registry_has_14_domains_and_46_hypotheses() -> None:
    if not _SHIPPED_ROOT.exists():
        pytest.skip("shipped registry not in cwd")
    r = HypothesisRegistry().scan()
    assert len(r.domains) == 14
    assert len(r) == 46


def test_shipped_registry_status_histogram_is_mostly_amplification_stage() -> None:
    if not _SHIPPED_ROOT.exists():
        pytest.skip("shipped registry not in cwd")
    r = HypothesisRegistry().scan()
    counts = r.count_by_status()
    # 46 hypotheses total.  The corpus was mined at Stage 1 (BL-701/702);
    # since Sprint 2 (BL-704/BL-718, 2026-09-03) the 7 crypto-microstructure
    # entries have advanced through the state machine (amplificata /
    # APPROVED / REJECTED / morta), so the pre-amplification count is
    # 46 minus the advanced ones — everything else must still be
    # da_amplificare and the total must stay 46 (no lost hypotheses).
    advanced = sum(v for k, v in counts.items() if k != "da_amplificare")
    assert counts.get("da_amplificare", 0) + advanced == 46
    assert sum(counts.values()) == 46
    assert advanced <= 7  # only the crypto domain has been through sprints


def test_shipped_registry_validate_all_flags_known_data_bug() -> None:
    """Live data has cross-domain EF-001 collisions (BL-700 audit)."""
    if not _SHIPPED_ROOT.exists():
        pytest.skip("shipped registry not in cwd")
    r = HypothesisRegistry().scan()
    issues = r.validate_all()
    # Cross-domain duplicate IDs are a real, known issue in the shipped
    # 14-domain corpus.  Validate that we surface it.
    assert any("duplicate id" in i for i in issues)


def test_count_helpers(fixture_root: Path) -> None:
    r = HypothesisRegistry().scan(fixture_root)
    assert r.count_by_domain() == {"01-fundamental": 2, "02-macro": 1, "crypto-microstructure": 2}
    assert r.count_by_status() == {"da_amplificare": 5}

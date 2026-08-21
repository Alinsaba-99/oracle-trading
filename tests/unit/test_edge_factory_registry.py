"""BL-700 — golden tests for the Edge Research Factory hypothesis registry.

The registry is the single source of truth for every edge hypothesis:
append-only, controlled state machine, validated YAML round-trip.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from analytics.research.factory.registry import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    DomainRegistry,
    Hypothesis,
    RegistryError,
    load_registry,
    save_registry,
)


def _hyp(hid: str = "EF-001", **kwargs: object) -> Hypothesis:
    base: dict[str, object] = {
        "id": hid,
        "nome": "funding-extremum-reversal",
        "meccanismo": "funding rate estremo spinge i marginal trader fuori posizione",
        "perche_esiste": "il costo del carry rende insostenibile la posizione affollata",
        "origine": "practitioner",
        "fonti": ["trading-os/knowledge/moondev-repos/RISPOSTE_D1-D15.md"],
        "dati_richiesti": ["fundingRate 1h", "OHLCV 1h"],
        "asset_candidati": ["BTCUSDT", "ETHUSDT"],
        "timeframe": ["1h"],
    }
    base.update(kwargs)
    return Hypothesis.model_validate(base)


def _stato(h: Hypothesis) -> str:
    """Read the current state widened to str (transition mutates in place;
    this avoids mypy narrowing on the attribute across calls)."""
    return h.stato


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_hypothesis_minimal_valid() -> None:
    h = _hyp()
    assert h.stato == "da_amplificare"
    assert h.decay_atteso_pct == 30.0
    assert h.dati_posseduti is None
    assert h.evidenza == []


def test_hypothesis_rejects_bad_id() -> None:
    with pytest.raises(ValidationError):
        _hyp(hid="XX-1")


def test_hypothesis_rejects_short_mechanism() -> None:
    with pytest.raises(ValidationError):
        _hyp(meccanismo="corto")


def test_hypothesis_decay_bounds() -> None:
    with pytest.raises(ValidationError):
        _hyp(decay_atteso_pct=150.0)
    with pytest.raises(ValidationError):
        _hyp(decay_atteso_pct=-1.0)


def test_registry_rejects_duplicate_ids() -> None:
    with pytest.raises((RegistryError, ValidationError)):
        DomainRegistry(domain="crypto-microstructure", hypotheses=[_hyp("EF-001"), _hyp("EF-001")])


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def test_transition_happy_path() -> None:
    h = _hyp()
    assert _stato(h) == "da_amplificare"
    h.transition("amplificata", "letteratura conferma su SSRN", ref="https://ssrn.example/x")
    assert _stato(h) == "amplificata"
    assert len(h.evidenza) == 1
    assert "da_amplificare → amplificata" in h.evidenza[0].testo

    h.transition("in_qualifica", "dati posseduti verificati")
    assert _stato(h) == "in_qualifica"
    h.transition("APPROVED", "gauntlet ADR-017 superato")
    assert _stato(h) == "APPROVED"
    assert len(h.evidenza) == 3


def test_transition_illegal_raises() -> None:
    h = _hyp()
    with pytest.raises(RegistryError, match="transizione illegale"):
        h.transition("APPROVED", "skip")  # cannot jump to terminal
    with pytest.raises(RegistryError):
        h.transition("non_esistente", "x")


def test_terminal_states_have_no_exits() -> None:
    for stato in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[stato] == frozenset()


def test_morta_per_dati_can_reopen() -> None:
    h = _hyp()
    h.transition("morta_per_dati", "serve futures 1m storico (BL-097/098)")
    assert _stato(h) == "morta_per_dati"
    h.transition("da_amplificare", "dati sbloccati da BL-098")
    assert _stato(h) == "da_amplificare"


def test_every_state_is_in_transition_table() -> None:
    from typing import get_args

    for stato in get_args(Hypothesis.model_fields["stato"].annotation):
        assert stato in ALLOWED_TRANSITIONS


# ---------------------------------------------------------------------------
# Registry operations
# ---------------------------------------------------------------------------


def test_add_and_get() -> None:
    reg = DomainRegistry(domain="crypto-microstructure")
    h = _hyp()
    reg.add(h)
    assert reg.get("EF-001") is h
    with pytest.raises(RegistryError, match="duplicate"):
        reg.add(_hyp("EF-001"))
    with pytest.raises(RegistryError, match="not found"):
        reg.get("EF-999")


def test_next_id_sequence() -> None:
    reg = DomainRegistry(domain="d")
    assert reg.next_id() == "EF-001"
    reg.add(_hyp("EF-001"))
    assert reg.next_id() == "EF-002"
    reg.add(_hyp("EF-007"))
    assert reg.next_id() == "EF-008"


def test_by_state_filter() -> None:
    reg = DomainRegistry(domain="d")
    reg.add(_hyp("EF-001"))
    reg.add(_hyp("EF-002"))
    reg.get("EF-002").transition("morta", "confutata in letteratura")
    assert [h.id for h in reg.by_state("da_amplificare")] == ["EF-001"]
    assert [h.id for h in reg.by_state("morta")] == ["EF-002"]


# ---------------------------------------------------------------------------
# YAML round-trip
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_path: Path) -> None:
    reg = DomainRegistry(domain="crypto-microstructure")
    h = _hyp()
    h.transition("amplificata", "ok letteratura")
    reg.add(h)

    path = save_registry(tmp_path / "crypto-microstructure.yaml", reg)
    assert path.exists()

    loaded = load_registry(path)
    assert loaded.domain == "crypto-microstructure"
    assert len(loaded.hypotheses) == 1
    assert loaded.hypotheses[0].stato == "amplificata"
    assert loaded.hypotheses[0].evidenza[0].tipo == "report"
    # Content equality (append-only identity survives the round-trip).
    assert loaded.model_dump() == reg.model_dump()


def test_load_registry_rejects_non_mapping(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("- just\n- a list\n")
    with pytest.raises(RegistryError, match="mapping"):
        load_registry(p)


def test_load_registry_rejects_unknown_state(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(
        "schema_version: 1\n"
        "domain: d\n"
        "hypotheses:\n"
        "  - id: EF-001\n"
        "    nome: test-hypothesis\n"
        "    meccanismo: un meccanismo sufficientemente lungo\n"
        "    perche_esiste: una ragione economica sufficientemente lunga\n"
        "    origine: kb\n"
        "    stato: inventato\n"
    )
    with pytest.raises(ValidationError):
        load_registry(p)

"""BL-701/702 — corpus registry invariants (mining output validation)."""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.research.factory.registry import load_registry

REGISTRY_DIR = Path("docs/knowledge-base/edge-factory/registry")

KB_DOMAINS = [
    "01-fundamental",
    "02-macro",
    "03-quant",
    "04-order-flow",
    "05-sentiment",
    "06-positioning",
    "07-news",
    "08-intermarket",
    "09-cyclical",
    "10-seasonal",
    "11-onchain",
    "12-behavioral",
    "13-meta-synthesis",
]
ALL_DOMAINS = [*KB_DOMAINS, "crypto-microstructure"]


def test_registry_files_match_expected_domains() -> None:
    found = sorted(p.stem for p in REGISTRY_DIR.glob("*.yaml"))
    assert found == sorted(ALL_DOMAINS)


VALID_STATES = {
    "da_amplificare",
    "amplificata",
    "in_qualifica",
    "APPROVED",
    "REJECTED",
    "morta",
    "morta_per_dati",
}


@pytest.mark.parametrize("domain", ALL_DOMAINS)
def test_min_one_hypothesis_per_domain(domain: str) -> None:
    reg = load_registry(REGISTRY_DIR / f"{domain}.yaml")
    assert len(reg.hypotheses) >= 1
    for h in reg.hypotheses:
        assert len(h.meccanismo) >= 10
        assert h.dati_richiesti, f"{h.id}: dati_richiesti vuoto"
        # Stage-1 mined state; hypotheses may advance via the state
        # machine (amplification/qualification) — only validity is enforced.
        assert h.stato in VALID_STATES
        assert h.evidenza and h.evidenza[0].tipo == "miner"


def test_kb_total_hypotheses_at_least_26() -> None:
    """AC: ≥1/dominio; target di sessione: media ≥2/dominio sui 13 KB."""
    total = 0
    for d in KB_DOMAINS:
        total += len(load_registry(REGISTRY_DIR / f"{d}.yaml").hypotheses)
    assert total >= 26


MOONDEV_TRIAGED = {
    "funding-extremum-reversal",
    "liquidation-cascade-reversal",
    "bb-squeeze-release",
    "cvd-divergence",
    "session-seasonality",
}


def test_moondev_five_triaged_factors_present() -> None:
    reg = load_registry(REGISTRY_DIR / "crypto-microstructure.yaml")
    names = {h.nome for h in reg.hypotheses}
    assert MOONDEV_TRIAGED <= names  # noqa: SIM300


def test_practitioner_entries_carry_conservative_haircut() -> None:
    reg = load_registry(REGISTRY_DIR / "crypto-microstructure.yaml")
    practitioners = [h for h in reg.hypotheses if h.origine == "practitioner"]
    assert practitioners, "at least one practitioner entry expected"
    for h in practitioners:
        assert h.decay_atteso_pct >= 40.0
        assert any("moondev-repos" in (e.ref or "") for e in h.evidenza)

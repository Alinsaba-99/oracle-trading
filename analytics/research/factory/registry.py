"""BL-700 — Edge Research Factory hypothesis registry.

Append-only YAML registry, one file per domain.  Hypotheses are never
deleted: they only move through a controlled state machine, and every
observation lands in the append-only ``evidenza`` list.  See
``docs/plans/2026-08-21-edge-research-factory-design.md`` §3.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

_REGISTRY_SCHEMA_VERSION = 1

Origine = Literal["kb", "practitioner", "video", "letteratura"]

Stato = Literal[
    "da_amplificare",
    "amplificata",
    "in_qualifica",
    "APPROVED",
    "REJECTED",
    "morta",
    "morta_per_dati",
]

#: Controlled state machine (design spec §3).  ``morta_per_dati`` is the
#: only terminal-ish state that can reopen — data unlocks (BL-097/098)
#: legitimately revive an hypothesis.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "da_amplificare": frozenset({"amplificata", "morta", "morta_per_dati"}),
    "amplificata": frozenset({"in_qualifica", "morta", "morta_per_dati"}),
    "in_qualifica": frozenset({"APPROVED", "REJECTED"}),
    "APPROVED": frozenset(),
    "REJECTED": frozenset(),
    "morta": frozenset(),
    "morta_per_dati": frozenset({"da_amplificare"}),
}

TERMINAL_STATES = frozenset({"APPROVED", "REJECTED", "morta"})


class RegistryError(ValueError):
    """Invalid registry mutation (bad transition, duplicate id, ...)."""


class Evidence(BaseModel):
    """One append-only observation attached to a hypothesis."""

    data: str  # ISO-8601 timestamp of the observation
    tipo: Literal["miner", "amplificazione", "test", "report", "citazione"]
    testo: str
    ref: str | None = None  # URL, file path, report link

    @classmethod
    def now(
        cls,
        tipo: Literal["miner", "amplificazione", "test", "report", "citazione"],
        testo: str,
        ref: str | None = None,
    ) -> Evidence:
        return cls(data=datetime.now(UTC).isoformat(), tipo=tipo, testo=testo, ref=ref)


class Hypothesis(BaseModel):
    """One testable edge hypothesis (design spec §3 schema)."""

    id: str = Field(pattern=r"^EF-\d{3,}$")
    nome: str = Field(min_length=3)
    meccanismo: str = Field(min_length=10)
    perche_esiste: str = Field(min_length=10)
    origine: Origine
    fonti: list[str] = Field(default_factory=list)
    effect_size_dichiarata: str = "non_quantificata"
    decay_atteso_pct: float = Field(default=30.0, ge=0, le=100)
    dati_richiesti: list[str] = Field(default_factory=list)
    dati_posseduti: bool | None = None  # None = non ancora verificato (Stage 3)
    asset_candidati: list[str] = Field(default_factory=list)
    timeframe: list[str] = Field(default_factory=list)
    stato: Stato = "da_amplificare"
    evidenza: list[Evidence] = Field(default_factory=list)

    def transition(self, nuovo_stato: str, motivo: str, ref: str | None = None) -> None:
        """Move to *nuovo_stato* recording evidence; raises on illegal moves."""
        if nuovo_stato not in ALLOWED_TRANSITIONS.get(self.stato, frozenset()):
            raise RegistryError(
                f"transizione illegale {self.id}: {self.stato} → {nuovo_stato} "
                f"(ammesse: {sorted(ALLOWED_TRANSITIONS.get(self.stato, frozenset()))})"
            )
        self.evidenza.append(Evidence.now("report", f"{self.stato} → {nuovo_stato}: {motivo}", ref))
        self.stato = nuovo_stato  # type: ignore[assignment]


class DomainRegistry(BaseModel):
    """Append-only registry for one research domain."""

    schema_version: int = Field(default=_REGISTRY_SCHEMA_VERSION, ge=1)
    domain: str = Field(min_length=1)
    hypotheses: list[Hypothesis] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> DomainRegistry:
        ids = [h.id for h in self.hypotheses]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate hypothesis ids in registry")
        return self

    def next_id(self) -> str:
        nums = [int(h.id.removeprefix("EF-")) for h in self.hypotheses]
        return f"EF-{(max(nums) if nums else 0) + 1:03d}"

    def add(self, hyp: Hypothesis) -> Hypothesis:
        if any(h.id == hyp.id for h in self.hypotheses):
            raise RegistryError(f"duplicate hypothesis id {hyp.id} in domain {self.domain}")
        self.hypotheses.append(hyp)
        return hyp

    def get(self, hid: str) -> Hypothesis:
        for h in self.hypotheses:
            if h.id == hid:
                return h
        raise RegistryError(f"hypothesis {hid} not found in domain {self.domain}")

    def by_state(self, stato: str) -> list[Hypothesis]:
        return [h for h in self.hypotheses if h.stato == stato]


def load_registry(path: str | Path) -> DomainRegistry:
    """Load (and validate) a domain registry YAML file."""
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RegistryError(f"registry root must be a mapping, got {type(raw).__name__}")
    return DomainRegistry.model_validate(raw)


def save_registry(path: str | Path, registry: DomainRegistry) -> Path:
    """Persist a registry (canonical YAML, append-only content rules apply)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(registry.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return p


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATES",
    "DomainRegistry",
    "Evidence",
    "Hypothesis",
    "RegistryError",
    "load_registry",
    "save_registry",
]

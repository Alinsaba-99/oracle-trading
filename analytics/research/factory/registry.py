"""BL-700 — Edge Research Factory hypothesis registry.

Append-only YAML registry, one file per domain.  Hypotheses are never
deleted: they only move through a controlled state machine, and every
observation lands in the append-only ``evidenza`` list.  See
``docs/plans/2026-08-21-edge-research-factory-design.md`` §3.
"""

from __future__ import annotations

from collections.abc import Iterable
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


# ---------------------------------------------------------------------------
# Cross-domain unified registry (BL-700)
# ---------------------------------------------------------------------------


_DEFAULT_REGISTRY_ROOT = Path("docs/knowledge-base/edge-factory/registry")


class HypothesisNotFoundError(RegistryError):
    """Lookup of an hypothesis id failed across all loaded domains."""


class HypothesisRegistry:
    """Unified, read-write view over the per-domain YAML registry.

    Scans a directory of ``<domain>.yaml`` files (one ``DomainRegistry`` each)
    and exposes cross-domain queries plus append-only state transitions.  All
    mutations are routed through :meth:`Hypothesis.transition` so the controlled
    state machine stays the single authority.  Save back is explicit via
    :meth:`save_all` (or per-domain via :meth:`save_domain`) — the registry
    never writes to disk as a side effect of a state change.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self._root = Path(root) if root is not None else _DEFAULT_REGISTRY_ROOT
        self._domains: dict[str, DomainRegistry] = {}
        self._paths: dict[str, Path] = {}
        self._dirty: set[str] = set()

    # -- discovery ---------------------------------------------------------

    @property
    def root(self) -> Path:
        return self._root

    @property
    def domains(self) -> list[str]:
        return sorted(self._domains)

    def scan(self, root: str | Path | None = None) -> HypothesisRegistry:
        """Load every ``*.yaml`` file under *root* (defaults to ``self._root``).

        Already-loaded domains are replaced — call this to re-read from disk
        after external edits.  Returns self so it composes naturally:
        ``HypothesisRegistry().scan()``.
        """
        target = Path(root) if root is not None else self._root
        if not target.exists():
            raise RegistryError(f"registry root does not exist: {target}")

        self._domains = {}
        self._paths = {}
        self._dirty = set()

        for path in sorted(target.glob("*.yaml")):
            domain = load_registry(path)
            self._domains[domain.domain] = domain
            self._paths[domain.domain] = path
        return self

    # -- queries -----------------------------------------------------------

    def get_hypothesis(self, hid: str) -> Hypothesis:
        for domain in self._domains.values():
            try:
                return domain.get(hid)
            except RegistryError:
                continue
        raise HypothesisNotFoundError(f"hypothesis {hid} not found in any domain")

    def get_domain(self, domain: str) -> DomainRegistry:
        if domain not in self._domains:
            raise RegistryError(f"domain {domain!r} not loaded (have: {self.domains})")
        return self._domains[domain]

    def list_hypotheses(
        self, domain: str | None = None, stato: str | None = None
    ) -> list[Hypothesis]:
        """Cross-domain filter.  Both filters are AND-combined; ``None`` = no filter."""
        results: list[Hypothesis] = []
        for d_name, d_reg in self._domains.items():
            if domain is not None and d_name != domain:
                continue
            for h in d_reg.hypotheses:
                if stato is not None and h.stato != stato:
                    continue
                results.append(h)
        return results

    def count_by_status(self) -> dict[str, int]:
        """Status histogram across the whole registry."""
        counts: dict[str, int] = {}
        for h in self.list_hypotheses():
            counts[h.stato] = counts.get(h.stato, 0) + 1
        return counts

    def count_by_domain(self) -> dict[str, int]:
        return {d: len(r.hypotheses) for d, r in sorted(self._domains.items())}

    # -- mutations ---------------------------------------------------------

    def update_status(
        self,
        hid: str,
        nuovo_stato: str,
        motivo: str,
        ref: str | None = None,
        *,
        persist: bool = False,
    ) -> Hypothesis:
        """Transition *hid* → *nuovo_stato* recording evidence.

        The transition is validated by :meth:`Hypothesis.transition` (which
        raises :class:`RegistryError` on illegal moves).  By default the
        registry only marks the owning domain as dirty; pass ``persist=True``
        to also write the YAML back to disk.
        """
        h = self.get_hypothesis(hid)
        domain = self._domain_of(hid)
        h.transition(nuovo_stato, motivo, ref)
        self._dirty.add(domain)
        if persist:
            self.save_domain(domain)
        return h

    def save_domain(self, domain: str) -> Path:
        if domain not in self._paths:
            raise RegistryError(f"domain {domain!r} not loaded")
        save_registry(self._paths[domain], self._domains[domain])
        self._dirty.discard(domain)
        return self._paths[domain]

    def save_all(self) -> list[Path]:
        """Persist every dirty domain; returns the list of written paths."""
        written: list[Path] = []
        for domain in sorted(self._dirty):
            written.append(self.save_domain(domain))
        return written

    @property
    def dirty_domains(self) -> list[str]:
        return sorted(self._dirty)

    # -- invariants --------------------------------------------------------

    def validate_all(self) -> list[str]:
        """Cross-domain structural invariants.

        Returns a list of human-readable issue strings; empty list = OK.
        Cheap enough to run on every CI commit.  Local invariants
        (Pydantic constraints) are already enforced at load time, so this
        focuses on cross-domain and content invariants that need global view.
        """
        issues: list[str] = []

        # 1. id uniqueness across the whole registry (the on-disk schema
        #    enforces uniqueness *within* a domain; cross-domain collisions
        #    would still pass per-domain validation).
        seen: dict[str, str] = {}
        for d_name, d_reg in self._domains.items():
            for h in d_reg.hypotheses:
                if h.id in seen:
                    issues.append(f"duplicate id {h.id}: domains {seen[h.id]!r} and {d_name!r}")
                else:
                    seen[h.id] = d_name

        # 2. per-hypothesis invariants the schema does not enforce
        #    (deeper business rules on top of pydantic constraints).
        for d_name, d_reg in self._domains.items():
            if d_reg.schema_version != _REGISTRY_SCHEMA_VERSION:
                issues.append(
                    f"domain {d_name}: schema_version {d_reg.schema_version} "
                    f"!= expected {_REGISTRY_SCHEMA_VERSION}"
                )
            for h in d_reg.hypotheses:
                if not h.fonti:
                    issues.append(f"{h.id}: no sources in fonti")
                for s in h.dati_richiesti:
                    if not s.strip():
                        issues.append(f"{h.id}: empty entry in dati_richiesti")
                for ev in h.evidenza:
                    try:
                        datetime.fromisoformat(ev.data)
                    except ValueError:
                        issues.append(f"{h.id}: evidence data not ISO-8601: {ev.data!r}")
                    if not ev.testo.strip():
                        issues.append(f"{h.id}: evidence with empty testo")

        # 3. every stato value present in the data must be a known status.
        known_states = set(Stato.__args__)  # type: ignore[attr-defined]
        for h in self.list_hypotheses():
            if h.stato not in known_states:
                issues.append(f"{h.id}: unknown stato {h.stato!r}")

        return issues

    # -- internals ---------------------------------------------------------

    def _domain_of(self, hid: str) -> str:
        for d_name, d_reg in self._domains.items():
            if any(h.id == hid for h in d_reg.hypotheses):
                return d_name
        raise HypothesisNotFoundError(hid)

    # -- dunders -----------------------------------------------------------

    def __len__(self) -> int:
        return sum(len(r.hypotheses) for r in self._domains.values())

    def __iter__(self) -> Iterable[Hypothesis]:  # type: ignore[override]
        return iter(self.list_hypotheses())


__all__ = [
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATES",
    "DomainRegistry",
    "Evidence",
    "Hypothesis",
    "HypothesisNotFoundError",
    "HypothesisRegistry",
    "RegistryError",
    "load_registry",
    "save_registry",
]

#!/usr/bin/env python3
"""BL-743 — CLI generica per transizioni di stato del registry edge-factory.

Lavora sul registry unificato ``docs/knowledge-base/edge-factory/registry/``
(un file YAML per dominio).  Ogni chiamata transiziona una sola ipotesi,
registra evidence e persiste SOLO il dominio toccato (l'intero registry
NON viene riscritto: il builder è deterministico, vedi BL-744).

Sintassi:

    uv run python scripts/set_registry_state.py --hid EF-004@10-seasonal \\
        --stato REJECTED --motivo "..." --ref "docs/reports/..."

Il formato ``<hid>@<domain>`` è obbligatorio quando ``<hid>`` esiste in più
domini (è il bug BL-745 che la CLI corregge: ``HypothesisRegistry.update_status``
risolve al primo match e transiziona l'ipotesi SBAGLIATA cross-domain).
Senza ``@<domain>`` la CLI cerca l'unico dominio che contiene l'hid; se
è ambiguo → errore esplicito con la lista dei candidati (exit ≠ 0).

Exit code:
    0  transizione OK
    1  ipotesi non trovata (HypothesisNotFoundError)
    2  ipotesi ambigua cross-domain o dominio esplicito sconosciuto
    3  transizione illegale (state machine)
    4  errore I/O / registry root mancante / --hid malformato
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.research.factory.registry import (  # noqa: E402
    DomainRegistry,
    Hypothesis,
    HypothesisNotFoundError,
    HypothesisRegistry,
    RegistryError,
)

_DEFAULT_ROOT = ROOT / "docs" / "knowledge-base" / "edge-factory" / "registry"


def _parse_hid(hid: str) -> tuple[str, str | None]:
    """Split ``EF-NNN@<domain>`` into ``(hid, domain|None)``.

    The domain segment is everything after the first ``@``.  Hypothesis
    ids are fixed (``EF-NNN`` with no ``@``), so a single split is safe.
    """
    if "@" in hid:
        h, d = hid.split("@", 1)
        h = h.strip()
        d = d.strip()
        if not h or not d:
            raise ValueError(f"--hid malformato: {hid!r} (atteso EF-NNN[@domain])")
        return h, d
    stripped = hid.strip()
    if not stripped:
        raise ValueError("--hid vuoto")
    return stripped, None


def _resolve_domain(reg: HypothesisRegistry, hid: str, domain: str | None) -> str:
    """Return the unique domain owning *hid*; raise on ambiguity/missing.

    If *domain* is given, it must be a loaded domain and must contain *hid*.
    If *domain* is None, the unique-domain shortcut applies: 0 or >1 matches
    raise (this is the cross-domain guard the CLI exists to enforce, BL-745).
    """
    if domain is not None:
        dom: DomainRegistry = reg.get_domain(domain)  # raises RegistryError if unknown
        try:
            dom.get(hid)
        except RegistryError as exc:
            raise HypothesisNotFoundError(
                f"hypothesis {hid} not found in domain {domain!r}"
            ) from exc
        return domain

    matches = [d for d in reg.domains if any(h.id == hid for h in reg.get_domain(d).hypotheses)]
    if not matches:
        raise HypothesisNotFoundError(f"hypothesis {hid} not found in any domain")
    if len(matches) > 1:
        raise RegistryError(
            f"hypothesis {hid} is ambiguous across domains {matches}; "
            f"pass --hid {hid}@<domain> (e.g. {hid}@{matches[0]})"
        )
    return matches[0]


def _transition_in_domain(
    reg: HypothesisRegistry,
    hid: str,
    domain: str,
    nuovo_stato: str,
    motivo: str,
    ref: str | None,
    persist: bool,
) -> tuple[Hypothesis, Path | None]:
    """Transition *hid* inside the explicitly resolved *domain*.

    This is a deliberate wrapper that does NOT call
    :meth:`HypothesisRegistry.update_status`: that helper scans every domain
    for ``hid`` and returns the *first* match, which is the BL-745 bug.  By
    routing the transition through the resolved domain we guarantee we
    touch the right file.  We persist only the targeted domain (no
    ``save_all``) — the builder regenerates every YAML from a deterministic
    source, so a stray ``save_all`` would silently re-stamp every file's
    evidence timestamps (BL-744).
    """
    h = reg.get_domain(domain).get(hid)
    h.transition(nuovo_stato, motivo, ref)
    if persist:
        return h, reg.save_domain(domain)
    return h, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hid", required=True, help="EF-NNN oppure EF-NNN@<domain>")
    parser.add_argument("--stato", required=True, help="stato target (ALLOWED_TRANSITIONS)")
    parser.add_argument("--motivo", required=True, help="motivo (registrato in evidenza)")
    parser.add_argument("--ref", default=None, help="ref (URL / report path)")
    parser.add_argument(
        "--root",
        default=str(_DEFAULT_ROOT),
        help="registry root (default: docs/knowledge-base/edge-factory/registry)",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="transiziona in memoria senza scrivere YAML (default: persiste)",
    )
    args = parser.parse_args(argv)

    try:
        hid, domain = _parse_hid(args.hid)
    except ValueError as exc:
        print(f"errore: {exc}", file=sys.stderr)
        return 4

    reg = HypothesisRegistry(root=args.root)
    try:
        reg.scan()
    except RegistryError as exc:
        print(f"errore registry root: {exc}", file=sys.stderr)
        return 4

    try:
        resolved = _resolve_domain(reg, hid, domain)
    except HypothesisNotFoundError as exc:
        print(f"errore: {exc}", file=sys.stderr)
        return 1
    except RegistryError as exc:
        # ambiguity OR unknown explicit domain
        print(f"errore: {exc}", file=sys.stderr)
        return 2

    try:
        h, written = _transition_in_domain(
            reg,
            hid,
            resolved,
            args.stato,
            args.motivo,
            args.ref,
            persist=not args.no_persist,
        )
    except RegistryError as exc:
        # illegal transition (state machine) or unknown stato
        print(f"errore: {exc}", file=sys.stderr)
        return 3

    tail = "(in-memory)" if written is None else f"persisted → {written}"
    print(f"OK {h.id} in domain {resolved!r}: → {h.stato} {tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

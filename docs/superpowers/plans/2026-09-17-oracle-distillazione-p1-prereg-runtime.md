# Oracle Distillazione — Piano P1 (Fase 0a / 0c / 0d) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendere il gate di qualifica di Lane B eseguibile e il suo verdetto credibile — riparare la classificazione dell'errore di tree-integrity, riaprire il prereg come v2, rieseguire la qualifica su un albero pulito **senza bypass**, rifare l'IC screen sul fattore vero, e dare a Lane B un runtime EOD che il runner paper possa eseguire.

**Architecture:** Quattro interventi indipendenti sullo stesso percorso. (1) `analytics/research/factory/prereg.py` distingue le due cause di fallimento (`HEAD_MISMATCH` vs `DIRTY_TREE`) invece di riportarle entrambe come "HEAD drift". (2) Il prereg viene riaperto come v2 con un manifest nuovo, perché la §7 di `BL-726-lane-b-composite-variant.md` lo impone quando il verdetto è un fallimento. (3) `LaneBBacktestResult` porta la serie per-rebalance del composite score, così l'IC screen misura il fattore e non l'autocorrelazione dell'equity curve. (4) `execution/` riceve uno `EodSignalSource` e un `RebalanceSchedule` — il loop a 1 minuto su 4 simboli viene riusato come motore, con clock e sorgente di segnale sostituiti.

**Tech Stack:** Python 3.12, polars, numpy, pandas, pytest, uv. Nessuna dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-09-17-oracle-distillation-design.md` (commit `889c108`) — §0.3 D1/D2, §3 Fase 0a/0c/0d, §3.1 P1.

## Global Constraints

- Il fix a `prereg.py` tocca **solo messaggio e classificazione**: `verify_clean_tree` deve continuare a rifiutare sia HEAD diverso sia working tree sporco nei percorsi sorvegliati. Nessuna soglia cambia.
- Nessun parametro di Lane B cambia: `composite_weights=[0.40, 0.40, 0.20]`, `composite_threshold=0.65`, `top_n_holdings=15`, `per_idea_stop_loss_pct=0.05`, `rebalance_months=3`, finestra `2020-01-01 → 2025-08-14`, bear `2022-01-01 → 2022-12-31`. Il manifest v2 cambia `schema_version` e `code_commit`, **nient'altro**.
- Il re-run di Task 4 gira **senza** `--allow-head-mismatch`. Se il gate fallisce, il verdetto resta fallito e si scrive.
- Vietato toccare `policy/prop_firm/fixtures.py` (PROJECT.md, serve un ADR).
- Vietato `git push`, merge su `main`, `git branch -D`, `git worktree remove`.
- Vietato cancellare documenti.
- La allowlist lean-ctx blocca heredoc, `python3 -c`, `$(…)`, `find -exec`, e tronca i comandi contenenti `|` dentro un pattern quotato. **Ogni script di supporto si scrive su file e poi si esegue.**
- Commit message in italiano, formato `tipo(scope): descrizione`, con la riga `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` in coda.

---

## File Structure

| File | Responsabilità | Azione |
|---|---|---|
| `analytics/research/factory/prereg.py` | loader manifest + verifica tree. Aggiunge `PreregErrorKind`, `PreregError.kind`, `describe_tree_failure()`, `verify_prereg_commit()` | Modifica |
| `scripts/run_bl726_prereg_qualification.py` | runner di qualifica. Riporta la causa vera del fallimento e registra `tree_failure_kind` nel report | Modifica |
| `docs/research/prereg/BL-726.manifest.json` | manifest v1 — resta come record storico, non si tocca | Invariato |
| `docs/research/prereg/BL-726-v2.manifest.json` | manifest v2 — riapertura post-verdetto fallito | Crea |
| `docs/research/prereg/BL-726-v2-lane-b-composite-variant.md` | doc di preregistrazione v2, con la clausola anti-HARKing e il motivo della riapertura | Crea |
| `docs/reports/lane-b-composite/<data>-bl727v2-qualification.{md,json}` | verdetto v2 | Crea (generato) |
| `docs/ORACLE_AUTOPILOT_STATUS.md` | la riga Lane B deve riflettere il verdetto reale | Modifica |
| `analytics/strategy/lane_b_backtester.py` | `LaneBBacktestResult` porta `rebalance_dates` e `rebalance_composite_scores` | Modifica |
| `analytics/research/factory/ic_screen.py` | invariato — `screen_factor()` è già quello che serve | Invariato |
| `execution/eod_source.py` | `RebalanceSchedule` + `EodSignalSource`, implementa il protocollo `SignalSource` | Crea |
| `config/paper_lane_b.yaml` | config del runner in modalità rebalance EOD | Crea |
| `scripts/run_paper_lane_b.py` | wiring: adapter Lane B → `EodSignalSource` → `PaperRunner` | Crea |
| `tests/unit/test_prereg.py` | test del gate | Modifica |
| `tests/unit/test_lane_b_rebalance_series.py` | test della serie per-rebalance | Crea |
| `tests/unit/test_prereg_verdict_reasons.py` | test della formattazione del motivo nel report | Crea |
| `tests/unit/test_eod_source.py` | test di schedule + sorgente EOD | Crea |

---

## ⚠️ DECISIONE APERTA — da chiudere prima di Task 3

Il re-run fallirà **di nuovo** se non si risolve questo, ed è esattamente il meccanismo che ha prodotto D1.

`verify_clean_tree` pretende `HEAD == code_commit`. Ma il manifest v2 deve pinnare un commit che **contiene il manifest stesso**: chicken-and-egg. Un prereg che pina un commit non può mai essere committato senza invalidarsi. La volta scorsa è finita con `--allow-head-mismatch`, cioè un verdetto inutilizzabile.

Tre opzioni, e **una è l'unica praticabile**:

| | Come | Problema |
|---|---|---|
| **A** | `verify_prereg_commit`: passa se `HEAD == pinned` **oppure** se `pinned` è antenato di `HEAD` **e** `git diff --name-only pinned..HEAD -- <percorsi sorvegliati>` è vuoto | Nessuno. La proprietà anti-HARKing è preservata esattamente: il codice che calcola il risultato è quello pinnato. Cambia la *logica* del gate, quindi serve il tuo assenso. |
| **B** | Pinnare a mano il commit del manifest dopo averlo creato con `git commit --amend` | **Non funziona.** L'amend riscrive lo SHA del commit che contiene il manifest, quindi `HEAD != pinned` di nuovo. |
| **C** | Continuare con `--allow-head-mismatch` | È ciò che ha prodotto un report con `REJECTED_TREE_INTEGRITY` e un messaggio che si contraddice. Ricrea il problema. |

**Raccomandazione: A.** Restringe il gate a ciò che il gate dichiara di voler garantire — «il codice nei percorsi sorvegliati non è cambiato dal pin» — invece di un proxy (uguaglianza byte a byte di HEAD) che non è soddisfacibile in pratica. Non indebolisce nulla: un commit che tocca `analytics/strategy/`, `analytics/research/`, `analytics/qualification/`, `analytics/metrics/` o `analytics/fundamental/simfin_loader.py` dopo il pin **fa ancora fallire**. E un working tree sporco **fa ancora fallire**.

La spec dice «mai la logica del gate»: la frase era rivolta a non allargare le soglie per far passare Lane B. L'opzione A non tocca una sola soglia. **Ma è una modifica alla logica, quindi la decidi tu, non l'agente notturno.** Se dici no, Task 3 va riscritto e Task 4 si esegue accettando che il verdetto porti la nota di bypass.

---

## Task 1: `prereg.py` — la causa del fallimento diventa esplicita

**Files:**
- Modify: `analytics/research/factory/prereg.py` (classe `PreregError` a riga 67; `_run_git` a riga 193; `verify_clean_tree` a riga 205)
- Test: `tests/unit/test_prereg.py`

**Interfaces:**
- Consumes: niente.
- Produces:
  - `PreregErrorKind` — `StrEnum` con `HEAD_MISMATCH`, `DIRTY_TREE`, `GIT_FAILED`, `SCHEMA`
  - `PreregError(message: str, *, kind: PreregErrorKind = PreregErrorKind.SCHEMA)` con attributo `.kind`
  - `describe_tree_failure(kind, message, head, pinned) -> str`

- [ ] **Step 1: Write the failing test**

Aggiungere in coda a `tests/unit/test_prereg.py`:

```python
# ---------------------------------------------------------------------------
# PreregErrorKind — la causa del fallimento deve essere esplicita.
# Le due cause erano indistinguibili e il runner le riportava entrambe come
# "HEAD drift": un messaggio che si contraddiceva da solo (D1, 2026-09-17).
# ---------------------------------------------------------------------------


def test_head_mismatch_carries_head_mismatch_kind() -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    bogus = ("0" if head[0] != "0" else "1") + head[1:]
    with pytest.raises(PreregError) as exc:
        verify_clean_tree(bogus, repo_root=REPO_ROOT)
    assert exc.value.kind is PreregErrorKind.HEAD_MISMATCH


def test_dirty_tree_carries_dirty_tree_kind() -> None:
    flag = REPO_ROOT / "analytics" / "research" / "_prereg_kind_test_flag.txt"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("test", encoding="utf-8")
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        with pytest.raises(PreregError) as exc:
            verify_clean_tree(head, repo_root=REPO_ROOT)
        assert exc.value.kind is PreregErrorKind.DIRTY_TREE
    finally:
        flag.unlink(missing_ok=True)


def test_load_error_defaults_to_schema_kind(tmp_path: Path) -> None:
    p = _write(tmp_path, _good_manifest({"code_commit": "deadbeef"}))
    with pytest.raises(PreregError) as exc:
        load_prereg(p)
    assert exc.value.kind is PreregErrorKind.SCHEMA


def test_describe_head_mismatch_names_the_hash_drift() -> None:
    msg = describe_tree_failure(
        PreregErrorKind.HEAD_MISMATCH,
        "HEAD 'aaa' does not match pre-registered commit 'bbb'",
        head="aaa",
        pinned="bbb",
    )
    assert "HEAD_MISMATCH" in msg
    assert "aaa" in msg and "bbb" in msg


def test_describe_dirty_tree_does_not_claim_hash_drift() -> None:
    """Il bug D1: HEAD combaciava e il messaggio diceva comunque '!='."""
    msg = describe_tree_failure(
        PreregErrorKind.DIRTY_TREE,
        "working tree not clean in qualification-affecting paths",
        head="aaa",
        pinned="aaa",
    )
    assert "DIRTY_TREE" in msg
    assert "!=" not in msg
    assert "working tree not clean" in msg
```

Aggiornare l'import in testa al file:

```python
from analytics.research.factory.prereg import (
    PreregError,
    PreregErrorKind,
    Preregistration,
    describe_tree_failure,
    load_prereg,
    verify_clean_tree,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_prereg.py -q`
Expected: FAIL — `ImportError: cannot import name 'PreregErrorKind' from 'analytics.research.factory.prereg'`

- [ ] **Step 3: Write minimal implementation**

In `analytics/research/factory/prereg.py`, aggiungere `from enum import StrEnum` al blocco import e sostituire la classe `PreregError` (riga 67-68):

```python
class PreregErrorKind(StrEnum):
    """Perché un controllo di pre-registrazione è fallito.

    Distinguere le cause conta: ``HEAD_MISMATCH`` significa che il codice
    in qualifica non è quello promesso, ``DIRTY_TREE`` che il codice
    promesso c'è ma ha modifiche locali. Riportarle entrambe come "HEAD
    drift" (comportamento fino al 2026-09-17) ha nascosto un rifiuto per
    tree sporco dietro un messaggio che si contraddiceva da solo.
    """

    HEAD_MISMATCH = "HEAD_MISMATCH"
    DIRTY_TREE = "DIRTY_TREE"
    GIT_FAILED = "GIT_FAILED"
    SCHEMA = "SCHEMA"


class PreregError(ValueError):
    """Invalid pre-registration manifest (schema, range, or type error)."""

    def __init__(self, message: str, *, kind: PreregErrorKind = PreregErrorKind.SCHEMA) -> None:
        super().__init__(message)
        self.kind = kind
```

In `_run_git` (riga 197-200), marcare il fallimento git:

```python
    if proc.returncode != 0:
        raise PreregError(
            f"git {' '.join(args)} failed in {repo_root}: "
            f"exit={proc.returncode} stderr={proc.stderr.strip()}",
            kind=PreregErrorKind.GIT_FAILED,
        )
```

In `verify_clean_tree`, marcare i due siti di fallimento. Il primo:

```python
    head = _run_git(root, "rev-parse", "HEAD").strip()
    if head != expected_commit:
        raise PreregError(
            f"HEAD {head!r} does not match pre-registered commit {expected_commit!r}",
            kind=PreregErrorKind.HEAD_MISMATCH,
        )
```

Il secondo, in coda alla funzione:

```python
    if offending:
        raise PreregError(
            "working tree not clean in qualification-affecting paths; "
            "offending entries:\n  " + "\n  ".join(offending),
            kind=PreregErrorKind.DIRTY_TREE,
        )
```

Aggiungere in coda al modulo, prima di `__all__`:

```python
def describe_tree_failure(kind: PreregErrorKind, message: str, head: str, pinned: str) -> str:
    """Motivo in una riga per un fallimento di tree-integrity, con la causa vera.

    Il runner lo incorpora nel report di qualifica. Prima del 2026-09-17
    stampava sempre ``HEAD <head> != pinned <pinned>`` anche quando i due
    hash erano identici, perché entrambe le modalità di fallimento
    producevano lo stesso messaggio: il report finiva per contraddirsi.
    """
    if kind is PreregErrorKind.HEAD_MISMATCH:
        return f"Tree-integrity gate failed (HEAD_MISMATCH): HEAD {head} != pinned {pinned}"
    if kind is PreregErrorKind.DIRTY_TREE:
        return (
            f"Tree-integrity gate failed (DIRTY_TREE): HEAD {head} == pinned {pinned}, "
            f"but the working tree has local changes — {message}"
        )
    return f"Tree-integrity gate failed ({kind}): {message}"
```

Aggiornare `__all__`:

```python
__all__ = [
    "PreregError",
    "PreregErrorKind",
    "Preregistration",
    "describe_tree_failure",
    "load_prereg",
    "verify_clean_tree",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_prereg.py -q`
Expected: PASS — tutti i test preesistenti verdi (i messaggi sollevati non sono cambiati, solo arricchiti con `kind`) più i 5 nuovi.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS — 3681 passed, 7 skipped (nessuna regressione).

- [ ] **Step 6: Commit**

```bash
git add analytics/research/factory/prereg.py tests/unit/test_prereg.py
git commit -m "fix(BL-726): prereg distingue HEAD_MISMATCH da DIRTY_TREE

verify_clean_tree sollevava PreregError per due cause distinte e il
runner le riportava entrambe come 'HEAD drift': il report BL-727
stampava due hash identici con un != in mezzo. Aggiunge
PreregErrorKind, l'attributo .kind, e describe_tree_failure() per la
formattazione nel report. Nessuna soglia cambia; i messaggi sollevati
restano gli stessi."
```

---

## Task 2: Il runner riporta la causa vera

**Files:**
- Modify: `scripts/run_bl726_prereg_qualification.py:411-421` (blocco tree) e la costruzione di `reasons`/payload
- Test: `tests/unit/test_prereg_verdict_reasons.py` (crea)

**Interfaces:**
- Consumes: `PreregErrorKind`, `describe_tree_failure` (Task 1)
- Produces: il report JSON guadagna `.metadata.tree_failure_kind: str | None` e `.metadata.tree_bypass_used: bool`

- [ ] **Step 1: Write the failing test**

Creare `tests/unit/test_prereg_verdict_reasons.py`:

```python
"""Il motivo di un fallimento di tree-integrity nel report di qualifica.

Regressione D1 (2026-09-17): il report BL-727 dichiarava "HEAD 7f4058a… !=
pinned 7f4058a…" — due stringhe identiche. La causa reale era un working
tree sporco, e il campo verdetto era REJECTED_TREE_INTEGRITY mentre
ORACLE_AUTOPILOT_STATUS.md lo dava per QUALIFICATO.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analytics.research.factory.prereg import PreregErrorKind, describe_tree_failure  # noqa: E402
from scripts.run_bl726_prereg_qualification import _tree_reason  # noqa: E402


def test_tree_reason_uses_describe_for_dirty_tree() -> None:
    reason = _tree_reason(
        PreregErrorKind.DIRTY_TREE,
        "working tree not clean in qualification-affecting paths; offending entries:\n   M x.py",
        head="abc",
        pinned="abc",
    )
    assert reason == describe_tree_failure(
        PreregErrorKind.DIRTY_TREE,
        "working tree not clean in qualification-affecting paths; offending entries:\n   M x.py",
        head="abc",
        pinned="abc",
    )
    assert "!=" not in reason


def test_tree_reason_uses_describe_for_head_mismatch() -> None:
    reason = _tree_reason(
        PreregErrorKind.HEAD_MISMATCH,
        "HEAD 'abc' does not match pre-registered commit 'def'",
        head="abc",
        pinned="def",
    )
    assert "HEAD_MISMATCH" in reason


def test_tree_reason_never_emits_identical_hashes_with_ne() -> None:
    """La regressione esatta: hash uguali e un != in mezzo."""
    for kind in (PreregErrorKind.DIRTY_TREE, PreregErrorKind.HEAD_MISMATCH):
        reason = _tree_reason(kind, "msg", head="same", pinned="same")
        if kind is PreregErrorKind.DIRTY_TREE:
            assert "same != same" not in reason
        else:
            pytest.skip("HEAD_MISMATCH con hash uguali è impossibile per costruzione")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_prereg_verdict_reasons.py -q`
Expected: FAIL — `ImportError: cannot import name '_tree_reason' from 'scripts.run_bl726_prereg_qualification'`

- [ ] **Step 3: Write minimal implementation**

In `scripts/run_bl726_prereg_qualification.py`, aggiornare l'import del prereg:

```python
from analytics.research.factory.prereg import (
    PreregError,
    PreregErrorKind,
    describe_tree_failure,
    load_prereg,
    verify_clean_tree,
)
```

Aggiungere, subito sopra `def _verdict(...)` (riga ~254):

```python
def _tree_reason(kind: PreregErrorKind, message: str, head: str, pinned: str) -> str:
    """Motivo del fallimento di tree-integrity, con la causa vera.

    Delega a ``describe_tree_failure``: il runner non deve reimplementare
    la formattazione, perché è esattamente così che il report ha finito
    per dichiarare "HEAD X != pinned X" con X == X.
    """
    return describe_tree_failure(kind, message, head=head, pinned=pinned)
```

Sostituire il blocco del tree check (righe 411-421) con:

```python
    head = subprocess_run("rev-parse", "HEAD", cwd=REPO_ROOT)
    tree_ok = True
    tree_kind: PreregErrorKind | None = None
    tree_message = ""
    try:
        verify_prereg_commit(prereg.code_commit, repo_root=REPO_ROOT)
    except PreregError as exc:
        tree_ok = False
        tree_kind = exc.kind
        tree_message = str(exc)
        print(f"[tree] FAILED ({exc.kind}): {exc}")
        if not args.allow_head_mismatch:
            print("[tree] aborting (use --allow-head-mismatch to proceed despite drift)")
            return 2
        print(
            "[tree] WARNING: proceeding despite a failed tree-integrity gate. "
            "The recorded verdict will carry the bypass."
        )
    print(f"[tree] ok={tree_ok}, kind={tree_kind}, HEAD={head}")
```

> Nota: `verify_prereg_commit` è definito in Task 3. Se la **Decisione Aperta** in testa al piano è stata chiusa con "no", lasciare `verify_clean_tree` e impostare `tree_kind = exc.kind` nello stesso modo.

Dove il payload viene costruito, aggiungere i due campi dentro `metadata`:

```python
            "tree_integrity_ok": tree_ok,
            "tree_failure_kind": tree_kind.value if tree_kind is not None else None,
            "tree_bypass_used": bool(tree_kind is not None and args.allow_head_mismatch),
```

E sostituire la riga che costruisce `reasons` per il tree con:

```python
        reasons.append(
            _tree_reason(tree_kind, tree_message, head=head, pinned=prereg.code_commit)
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_prereg_verdict_reasons.py tests/unit/test_prereg.py -q`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS — 3681 passed, 7 skipped. Se `test_set_registry_state.py` o un test che importa lo script falliscono, è un import mancante: aggiungerlo.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_bl726_prereg_qualification.py tests/unit/test_prereg_verdict_reasons.py
git commit -m "fix(BL-727): il report nomina la causa vera del fallimento tree

Il campo reasons[0] del report BL-727 dichiarava un HEAD drift che non
esisteva (due hash identici). Ora delega a describe_tree_failure e
registra metadata.tree_failure_kind + metadata.tree_bypass_used, cosi'
un verdetto ottenuto con --allow-head-mismatch e' distinguibile da uno
ottenuto con il gate verde."
```

---

## Task 3: Controllo di commit per antenanza + manifest v2

> **Bloccato dalla Decisione Aperta in testa al piano.** Non partire senza la risposta.

**Files:**
- Modify: `analytics/research/factory/prereg.py` (aggiunge `verify_prereg_commit`)
- Create: `docs/research/prereg/BL-726-v2.manifest.json`
- Create: `docs/research/prereg/BL-726-v2-lane-b-composite-variant.md`
- Test: `tests/unit/test_prereg.py` (aggiunge i test dell'antenanza)

**Interfaces:**
- Consumes: `PreregErrorKind` (Task 1)
- Produces: `verify_prereg_commit(expected_commit: str, repo_root: str | Path = ".") -> None` — passa se `HEAD == expected`, oppure se `expected` è antenato di `HEAD` **e** nessun percorso sorvegliato differisce fra i due.

- [ ] **Step 1: Write the failing test**

Aggiungere in coda a `tests/unit/test_prereg.py`:

```python
# ---------------------------------------------------------------------------
# verify_prereg_commit — antenanza con percorsi sorvegliati invariati.
# Il manifest non può pinnare il commit che lo contiene (chicken-and-egg):
# senza questo, ogni re-run finisce con --allow-head-mismatch.
# ---------------------------------------------------------------------------


def test_verify_prereg_commit_accepts_exact_head() -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    verify_prereg_commit(head, repo_root=REPO_ROOT)


def test_verify_prereg_commit_accepts_ancestor_with_clean_watched_paths() -> None:
    """Un antenato i cui percorsi sorvegliati sono invariati deve passare."""
    log = subprocess.run(
        ["git", "log", "--format=%H", "-20"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    for sha in log[1:]:
        diff = subprocess.run(
            ["git", "diff", "--name-only", f"{sha}..HEAD", "--", *WATCHED],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        if not diff:
            verify_prereg_commit(sha, repo_root=REPO_ROOT)
            return
    pytest.skip("nessun antenato recente con percorsi sorvegliati invariati")


def test_verify_prereg_commit_rejects_descendant() -> None:
    """Un commit che è discendente (non antenato) non è il pin."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    bogus = ("0" if head[0] != "0" else "1") + head[1:]
    with pytest.raises(PreregError) as exc:
        verify_prereg_commit(bogus, repo_root=REPO_ROOT)
    assert exc.value.kind is PreregErrorKind.HEAD_MISMATCH


def test_verify_prereg_commit_rejects_non_hex() -> None:
    with pytest.raises(PreregError, match="40-char hex SHA-1"):
        verify_prereg_commit("not-a-sha", repo_root=REPO_ROOT)
```

E in testa al file, dopo `REPO_ROOT = ...`:

```python
WATCHED = (
    "analytics/strategy/",
    "analytics/research/",
    "analytics/qualification/",
    "analytics/metrics/",
    "analytics/fundamental/simfin_loader.py",
)
```

Aggiornare l'import aggiungendo `verify_prereg_commit`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_prereg.py -q -k prereg_commit`
Expected: FAIL — `ImportError: cannot import name 'verify_prereg_commit'`

- [ ] **Step 3: Write minimal implementation**

In `analytics/research/factory/prereg.py`, aggiungere dopo `verify_clean_tree`:

```python
def verify_prereg_commit(expected_commit: str, repo_root: str | Path = ".") -> None:
    """Come :func:`verify_clean_tree`, ma il pin può essere un antenato.

    Un manifest di pre-registrazione non può pinnare il commit che lo
    contiene: al momento di scriverlo quel commit non esiste. Pretendere
    ``HEAD == pinned`` rende il gate insoddisfacibile per costruzione, e
    la via d'uscita praticata è stata ``--allow-head-mismatch`` — cioè un
    verdetto registrato come fallito.

    Questa funzione preserva esattamente la proprietà anti-HARKing: il
    codice nei percorsi sorvegliati è quello pinnato. Passa quando

    * ``HEAD == expected_commit``; oppure
    * ``expected_commit`` è un antenato di ``HEAD`` **e**
      ``git diff --name-only expected..HEAD -- <percorsi sorvegliati>``
      è vuoto.

    Un commit che tocca un percorso sorvegliato dopo il pin **fallisce**,
    con ``kind=HEAD_MISMATCH``. Un working tree sporco **fallisce**, con
    ``kind=DIRTY_TREE``.
    """
    root = Path(repo_root)
    if not _HEX_SHA1.match(expected_commit):
        raise PreregError(f"expected_commit must be a 40-char hex SHA-1, got {expected_commit!r}")

    head = _run_git(root, "rev-parse", "HEAD").strip()
    if head != expected_commit:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", expected_commit, head],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if ancestor.returncode != 0:
            raise PreregError(
                f"HEAD {head!r} does not match pre-registered commit {expected_commit!r} "
                f"and is not a descendant of it",
                kind=PreregErrorKind.HEAD_MISMATCH,
            )
        touched = _run_git(
            root, "diff", "--name-only", f"{expected_commit}..{head}", "--",
            *_QUALIFICATION_AFFECTING_PATHS,
        ).strip()
        if touched:
            raise PreregError(
                f"HEAD {head!r} descends from pre-registered commit {expected_commit!r} "
                f"but changes qualification-affecting paths:\n  "
                + "\n  ".join(touched.splitlines()),
                kind=PreregErrorKind.HEAD_MISMATCH,
            )

    porcelain = _run_git(root, "status", "--porcelain").splitlines()
    offending: list[str] = []
    for line in porcelain:
        if len(line) < 3:
            continue
        xy = line[:2]
        path = line[3:].strip()
        if xy != "??":
            offending.append(line)
            continue
        if any(path.startswith(p) for p in _QUALIFICATION_AFFECTING_PATHS):
            offending.append(line)
    if offending:
        raise PreregError(
            "working tree not clean in qualification-affecting paths; "
            "offending entries:\n  " + "\n  ".join(offending),
            kind=PreregErrorKind.DIRTY_TREE,
        )
```

Aggiungere `verify_prereg_commit` a `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_prereg.py -q`
Expected: PASS

- [ ] **Step 5: Create the v2 prereg documents**

Creare `docs/research/prereg/BL-726-v2-lane-b-composite-variant.md`:

```markdown
# BL-726 v2 — Lane B composite — riapertura della pre-registrazione

> Data: 2026-09-17 · Stato: PRE-REGISTERED
> Manifest: `docs/research/prereg/BL-726-v2.manifest.json`
> Sostituisce: v1 (`BL-726.manifest.json`, `BL-726-lane-b-composite-variant.md`)

## Perché una v2

La v1 è stata eseguita il 2026-09-03 e il suo verdetto registrato è
`REJECTED_TREE_INTEGRITY` (`docs/reports/lane-b-composite/2026-09-03-bl726-qualification.json`):
il gate di tree-integrity è fallito e il run è proseguito con
`--allow-head-mismatch`.

Il fallimento era riportato come «HEAD 7f4058a… != pinned 7f4058a…», con le
due stringhe identiche. La causa reale era un working tree sporco nei
percorsi sorvegliati — `verify_clean_tree` solleva `PreregError` per due
cause distinte e il runner le riportava entrambe come drift di HEAD.

La §7 della v1 prescrive: *«the only acceptable post-result action is to
declare the variant REJECTED and re-open BL-726 with a new manifest
version»*. Questa è quella riapertura.

## Cosa cambia rispetto alla v1

| Campo | v1 | v2 |
|---|---|---|
| `schema_version` | 1 | 2 |
| `code_commit` | `7f4058a…` | il commit che contiene questo manifest (vedi manifest) |
| Tutto il resto | — | **identico** |

Nessun parametro della variante cambia. Nessuna soglia cambia. Cambia solo
il commit di codice in qualifica, perché `prereg.py` e il runner sono stati
corretti: il verdetto v1 non era attribuibile a un codice riproducibile.

## Clausola anti-HARKing (invariata)

Tutte le soglie sono state fissate PRIMA di osservare il risultato di
questa esecuzione. Nessun parametro è stato scelto dopo aver visto un
risultato. Se il verdetto v2 è un fallimento, la variante resta REJECTED.

## Clausola di tree-integrity (aggiornata)

Al momento della qualifica il working tree deve essere pulito in tutti i
percorsi che influenzano la qualifica: `analytics/strategy/`,
`analytics/research/`, `analytics/qualification/`, `analytics/metrics/`,
`analytics/fundamental/simfin_loader.py`. Il commit di HEAD deve essere il
commit pinnato, oppure un suo discendente che non tocca nessuno di quei
percorsi. Il re-run si esegue **senza** `--allow-head-mismatch`.

## Gap dichiarati (invariati dalla v1)

- `target_annual_vol=0.40` è dichiarato in `LaneBBacktestConfig` ma il
  backtester non applica il vol-target sizing: il posizionamento è
  equal-weight. Lavoro BL-505e, da chiudere prima del gate di promozione
  paper (BL-732).
- SimFin `Publish Date` è il marker PIT; le restatement non sono gestite
  (`lane_b_backtester.py:23-24`), gap documentato a BL-619.
```

Creare `docs/research/prereg/BL-726-v2.manifest.json` copiando
`BL-726.manifest.json` e cambiando **solo** questi tre campi:

```json
  "schema_version": 2,
  "pre_registered_at": "2026-09-17",
  "code_commit": "<SHA del commit che contiene questo manifest>",
```

Il `code_commit` non è conoscibile prima del commit. Procedura:

1. Copiare il manifest v1 in `BL-726-v2.manifest.json` con gli altri due
   campi già aggiornati e `code_commit` lasciato a `7f4058a44e63a4c0740d1c6d0006224f503cc332` (v1) **temporaneamente**.
2. `git add` dei tre file nuovi e `git commit` con il messaggio dello Step 7.
3. Leggere lo SHA: `git rev-parse HEAD`.
4. Scrivere quel SHA in `code_commit`, poi `git add` + `git commit --amend --no-edit`.
5. `verify_prereg_commit` accetterà: il pin è ora un **antenato** di HEAD
   (il commit amendato) e il diff fra i due tocca solo
   `docs/research/prereg/`, che non è un percorso sorvegliato.

> Se la Decisione Aperta è stata chiusa con "no", questo passo non funziona
> e Task 4 va eseguito con `--allow-head-mismatch`, accettando che il
> verdetto porti `tree_bypass_used=true`. **Fermarsi e chiedere.**

- [ ] **Step 6: Verify the manifest loads and the gate passes**

```bash
uv run python -c "import sys; sys.path.insert(0,'.'); from analytics.research.factory.prereg import load_prereg, verify_prereg_commit; p=load_prereg('docs/research/prereg/BL-726-v2.manifest.json'); print(p.bl_id, p.extra.get('schema_version')); verify_prereg_commit(p.code_commit); print('gate OK')"
```

> Con la allowlist lean-ctx, `python3 -c` è bloccato: scrivere il comando in
> `.scratch/check_v2_gate.py` e lanciarlo con `uv run python .scratch/check_v2_gate.py`.

Expected: `BL-726 2` e `gate OK`.

- [ ] **Step 7: Commit**

```bash
git add docs/research/prereg/BL-726-v2.manifest.json docs/research/prereg/BL-726-v2-lane-b-composite-variant.md analytics/research/factory/prereg.py tests/unit/test_prereg.py
git commit -m "feat(BL-726v2): riapertura prereg con pin per antenanza

Il verdetto v1 e' REJECTED_TREE_INTEGRITY: la §7 della v1 impone di
dichiarare la variante REJECTED e riaprire con un manifest nuovo.
verify_prereg_commit accetta il pin esatto oppure un antenato i cui
percorsi sorvegliati sono invariati, cosi' il manifest puo' pinnare il
commit che lo contiene. Parametri e soglie identici alla v1."
```

---

## Task 4: Re-run pulito — il verdetto

**Files:**
- Create: `docs/reports/lane-b-composite/<data>-bl727v2-qualification.{md,json}` (generato dal runner)
- Modify: `docs/reports/lane-b-composite/<data>-bl727v2-qualification.json` (solo per il pin del commit)

**Interfaces:**
- Consumes: manifest v2 (Task 3), runner corretto (Task 2)
- Produces: il verdetto — `APPROVED` o `REJECTED` — che Task 5 scrive in STATUS.md

- [ ] **Step 1: Verify the tree is clean**

Run: `git status --porcelain`
Expected: vuoto. Se non lo è, committare o spostare prima di procedere.

- [ ] **Step 2: Verify the gate passes before running**

Run: `uv run python .scratch/check_v2_gate.py`
Expected: `gate OK`. Se fallisce, **non procedere**: il verdetto sarebbe un altro `REJECTED_TREE_INTEGRITY`.

- [ ] **Step 3: Run the qualification**

```bash
uv run python scripts/run_bl726_prereg_qualification.py --manifest docs/research/prereg/BL-726-v2.manifest.json
```

**Senza** `--allow-head-mismatch`. Il run carica SimFin e impiega alcuni minuti.

Expected: exit 0, e `[tree] ok=True, kind=None` in output.

- [ ] **Step 4: Read the verdict**

```bash
uv run python .scratch/jflat.py docs/reports/lane-b-composite/<data>-bl727v2-qualification.json | grep -E "^\.(verdict|reasons|metadata.tree_failure_kind|metadata.tree_bypass_used|qualification_window.observed_sharpe|ic_screen.passes)"
```

Expected:
- `metadata.tree_bypass_used = False`
- `metadata.tree_failure_kind = None`
- `verdict` = `APPROVED` oppure `REJECTED`

**Qualunque sia il verdetto, si accetta e si scrive.** Se è `REJECTED`, la causa più probabile è l'IC screen (§Task 6): annotarla nel report e proseguire — Task 6 esiste proprio per rifarlo sul fattore vero.

- [ ] **Step 5: Commit the report**

```bash
git add docs/reports/lane-b-composite/
git commit -m "docs(BL-727v2): verdetto della qualifica rieseguita senza bypass"
```

---

## Task 5: `LaneBBacktestResult` porta la serie per-rebalance

**Files:**
- Modify: `analytics/strategy/lane_b_backtester.py` (dataclass a riga 93-132; loop a riga 433-460)
- Test: `tests/unit/test_lane_b_rebalance_series.py` (crea)

**Interfaces:**
- Consumes: niente.
- Produces: `LaneBBacktestResult.rebalance_dates: list[datetime]` e `LaneBBacktestResult.rebalance_composite_scores: list[float]`, allineati per indice. Nei rebalance senza holdings il punteggio è `float("nan")`.

- [ ] **Step 1: Write the failing test**

Creare `tests/unit/test_lane_b_rebalance_series.py`:

```python
"""BL-727 v2 — la serie per-rebalance del composite score.

L'IC screen v1 riceveva i rendimenti giornalieri del portafoglio come
proxy del fattore: misurava l'autocorrelazione di una equity curve e la
chiamava Information Coefficient. Questi test pinnano la serie che il
backtester deve esporre perché lo screen possa misurare il fattore vero.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np

from analytics.strategy.lane_b_backtester import LaneBBacktestResult


def _result(**over: object) -> LaneBBacktestResult:
    base: dict[str, object] = {
        "n_rebalances": 3,
        "n_holdings_per_rebalance": [15, 15, 0],
        "equity_curve": np.array([1.0, 1.1, 1.2]),
        "total_return": 0.2,
        "annual_return": 0.1,
        "sharpe": 1.0,
        "max_drawdown": 0.05,
        "n_unique_tickers": 20,
        "hit_rate": 0.6,
        "benchmark_return": 0.1,
        "alpha_vs_benchmark": 0.1,
        "rebalance_dates": [
            datetime(2020, 1, 1),
            datetime(2020, 4, 1),
            datetime(2020, 7, 1),
        ],
        "rebalance_composite_scores": [0.71, 0.68, float("nan")],
    }
    base.update(over)
    return LaneBBacktestResult(**base)  # type: ignore[arg-type]


def test_result_carries_rebalance_series() -> None:
    r = _result()
    assert len(r.rebalance_dates) == 3
    assert len(r.rebalance_composite_scores) == 3
    assert r.rebalance_dates[0] == datetime(2020, 1, 1)


def test_series_are_index_aligned() -> None:
    r = _result()
    assert len(r.rebalance_dates) == len(r.rebalance_composite_scores)


def test_empty_rebalance_holds_nan() -> None:
    """Un rebalance senza holdings non ha un punteggio: NaN, non zero.

    Zero sarebbe una affermazione falsa sul fattore; NaN è l'assenza di
    affermazione, ed e' quello che l'IC screen deve ricevere.
    """
    r = _result()
    assert math.isnan(r.rebalance_composite_scores[2])


def test_series_can_be_zipped_into_a_series() -> None:
    """La forma che serve a screen_factor: due serie allineate."""
    import pandas as pd

    r = _result()
    factor = pd.Series(r.rebalance_composite_scores, index=pd.DatetimeIndex(r.rebalance_dates))
    prices = pd.Series([1.0, 1.1, 1.2], index=pd.DatetimeIndex(r.rebalance_dates))
    joined = pd.concat([factor.rename("factor"), prices.rename("px")], axis=1).dropna()
    assert len(joined) == 2  # il NaN del terzo rebalance e' escluso
    assert list(joined["factor"]) == [0.71, 0.68]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_lane_b_rebalance_series.py -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'rebalance_dates'`

- [ ] **Step 3: Write minimal implementation**

In `analytics/strategy/lane_b_backtester.py`, aggiungere i due campi alla fine di `LaneBBacktestResult` (dopo `alpha_vs_benchmark`, riga ~132) e aggiornare il docstring della classe con:

```
    rebalance_dates : list[datetime]
        Data di ogni rebalance, in ordine cronologico.
    rebalance_composite_scores : list[float]
        Composite score medio dei titoli selezionati a ogni rebalance,
        allineato per indice con ``rebalance_dates``. ``NaN`` quando il
        rebalance non ha selezionato nulla. E' la serie che l'IC screen
        deve ricevere come *fattore*: la serie dei rendimenti del
        portafoglio misura l'autocorrelazione dell'equity curve, non il
        potere predittivo del fattore.
```

```python
    rebalance_dates: list[datetime]
    rebalance_composite_scores: list[float]
```

Aggiungere i campi **con default in coda** per non rompere i costruttori esistenti:

```python
    rebalance_dates: list[datetime] = field(default_factory=list)
    rebalance_composite_scores: list[float] = field(default_factory=list)
```

`field` è già importato? Verificare con `grep -n "^from dataclasses" analytics/strategy/lane_b_backtester.py`. Se manca, aggiungere `field` all'import.

Nel loop `run()`, dentro il ramo `if screened.height == 0:` aggiungere la registrazione del NaN. Sostituire:

```python
        for i, rebal_date in enumerate(rebalances):
            screened = self._screen_at_date(merged, rebal_date)
            if screened.height == 0:
                holdings_per_rebalance.append(set())
                continue
```

con:

```python
        rebalance_dates_out: list[datetime] = []
        rebalance_scores_out: list[float] = []

        for i, rebal_date in enumerate(rebalances):
            rebalance_dates_out.append(rebal_date)
            screened = self._screen_at_date(merged, rebal_date)
            if screened.height == 0:
                holdings_per_rebalance.append(set())
                rebalance_scores_out.append(float("nan"))
                continue
```

E dopo la riga che appende `holdings_per_rebalance`:

```python
            holdings_per_rebalance.append(set(top_holdings["SimFinId"].to_list()))
            if "composite_score" in top_holdings.columns:
                rebalance_scores_out.append(float(top_holdings["composite_score"].mean()))
            else:
                rebalance_scores_out.append(float("nan"))
```

E nel punto in cui si costruisce `LaneBBacktestResult(...)`, aggiungere i due argomenti:

```python
            rebalance_dates=rebalance_dates_out,
            rebalance_composite_scores=rebalance_scores_out,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_lane_b_rebalance_series.py tests/unit/test_composite_lane_b.py -q`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS — 3681 passed, 7 skipped.

- [ ] **Step 6: Commit**

```bash
git add analytics/strategy/lane_b_backtester.py tests/unit/test_lane_b_rebalance_series.py
git commit -m "feat(BL-727v2): LaneBBacktestResult espone la serie per-rebalance

Senza la serie del composite score l'IC screen non ha un fattore da
misurare: la v1 gli passava i rendimenti giornalieri del portafoglio e
misurava l'autocorrelazione dell'equity curve. NaN nei rebalance senza
holdings, non zero: zero sarebbe un'affermazione falsa sul fattore."
```

---

## Task 6: IC screen sul fattore vero

**Files:**
- Modify: `scripts/run_bl726_prereg_qualification.py` (blocco IC, dove chiama `screen_factor`)
- Test: `tests/unit/test_prereg_verdict_reasons.py` (aggiunge i test della costruzione dell'input)

**Interfaces:**
- Consumes: `rebalance_dates` + `rebalance_composite_scores` (Task 5), `screen_factor(factor, prices, ...)` (già esistente)
- Produces: `build_ic_inputs(result: LaneBBacktestResult) -> tuple[pd.Series, pd.Series]`

- [ ] **Step 1: Write the failing test**

Aggiungere a `tests/unit/test_prereg_verdict_reasons.py`:

```python
import numpy as np  # noqa: E402
from datetime import datetime  # noqa: E402

from scripts.run_bl726_prereg_qualification import build_ic_inputs  # noqa: E402


def _fake_result(dates, scores, equity):
    from types import SimpleNamespace

    return SimpleNamespace(
        rebalance_dates=dates,
        rebalance_composite_scores=scores,
        equity_curve=np.asarray(equity, dtype=float),
    )


def test_build_ic_inputs_uses_rebalance_series_not_daily_returns() -> None:
    dates = [datetime(2020, 1, 1), datetime(2020, 4, 1), datetime(2020, 7, 1)]
    r = _fake_result(dates, [0.71, 0.68, 0.65], [1.0, 1.1, 1.2])
    factor, prices = build_ic_inputs(r)
    assert list(factor.index) == list(prices.index)
    assert list(factor) == [0.71, 0.68, 0.65]


def test_build_ic_inputs_drops_nan_rebalances() -> None:
    dates = [datetime(2020, 1, 1), datetime(2020, 4, 1), datetime(2020, 7, 1)]
    r = _fake_result(dates, [0.71, float("nan"), 0.65], [1.0, 1.1, 1.2])
    factor, prices = build_ic_inputs(r)
    assert len(factor) == 2
    assert not factor.isna().any()
    assert len(factor) == len(prices)


def test_build_ic_inputs_matches_series_lengths() -> None:
    dates = [datetime(2020, 1, 1), datetime(2020, 4, 1)]
    r = _fake_result(dates, [0.5, 0.6], [1.0, 1.05])
    factor, prices = build_ic_inputs(r)
    assert len(factor) == len(prices) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_prereg_verdict_reasons.py -q -k ic_inputs`
Expected: FAIL — `ImportError: cannot import name 'build_ic_inputs'`

- [ ] **Step 3: Write minimal implementation**

In `scripts/run_bl726_prereg_qualification.py`, aggiungere sopra `def _tree_reason(...)`:

```python
def build_ic_inputs(result: LaneBBacktestResult) -> tuple[pd.Series, pd.Series]:
    """Fattore e prezzi per l'IC screen, dal risultato del backtest.

    La v1 passava i rendimenti giornalieri del portafoglio come proxy del
    fattore: misurava l'autocorrelazione di una equity curve e la chiamava
    Information Coefficient. Il fattore vero e' il composite score medio
    dei titoli selezionati a ogni rebalance, contro il valore
    dell'equity curve in quel giorno.

    I rebalance senza holdings (score ``NaN``) sono esclusi: non
    esprimono un giudizio sul fattore.
    """
    factor = pd.Series(
        result.rebalance_composite_scores,
        index=pd.DatetimeIndex(result.rebalance_dates),
        dtype=float,
    )
    equity = np.asarray(result.equity_curve, dtype=float)
    if len(equity) != len(factor):
        msg = (
            f"equity_curve ha {len(equity)} punti ma i rebalance sono {len(factor)}: "
            "la serie per-rebalance non e' allineata all'equity curve"
        )
        raise ValueError(msg)
    prices = pd.Series(equity, index=factor.index, dtype=float)
    joined = pd.concat([factor.rename("factor"), prices.rename("px")], axis=1).dropna()
    return joined["factor"], joined["px"]
```

Sostituire la chiamata a `screen_factor` nel blocco IC con:

```python
    ic_factor, ic_prices = build_ic_inputs(result)
    ic = screen_factor(
        ic_factor,
        ic_prices,
        horizon=int(thr.get("ic_horizon", 1)),
        haircut_pct=float(thr["icir_haircut_pct"]),
        icir_threshold=float(thr["icir_threshold"]),
        t_threshold=float(thr["ic_block_t_threshold"]),
    )
```

> Nota: `horizon` per una serie di rebalance trimestrali è **1** (il periodo successivo), non 5 giorni. Se il codice v1 usava un `horizon` diverso, allinearlo a 1 e annotarlo nel report.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_prereg_verdict_reasons.py -q`
Expected: PASS

- [ ] **Step 5: Re-run the qualification with the corrected IC screen**

```bash
git status --porcelain   # deve essere vuoto
git rev-parse HEAD        # annotare lo SHA
```

Se lo SHA è cambiato rispetto al pin del manifest v2, aggiornare `code_commit` nel manifest v2 con lo SHA corrente e `git add` + `git commit --amend --no-edit` (il pin resta un antenato, i percorsi sorvegliati restano invariati).

```bash
uv run python scripts/run_bl726_prereg_qualification.py --manifest docs/research/prereg/BL-726-v2.manifest.json
```

Expected: `[tree] ok=True, kind=None`, exit 0, report aggiornato.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_bl726_prereg_qualification.py tests/unit/test_prereg_verdict_reasons.py docs/reports/lane-b-composite/
git commit -m "fix(BL-727v2): IC screen sul fattore, non sull'equity curve

La v1 passava i rendimenti giornalieri del portafoglio come proxy del
fattore e dichiarava il risultato 'methodology-limited' nel report.
Ora il fattore e' il composite score medio dei titoli selezionati a
ogni rebalance, contro l'equity in quel giorno. Horizon=1 periodo di
rebalance, non 5 giorni."
```

---

## Task 7: `RebalanceSchedule` e `EodSignalSource`

**Files:**
- Create: `execution/eod_source.py`
- Test: `tests/unit/test_eod_source.py` (crea)

**Interfaces:**
- Consumes: `OrderIntent` da `execution.paper_orchestrator`; il protocollo `SignalSource` di `execution/runner.py:184`
- Produces:
  - `RebalanceSchedule(dates: Iterable[date])` con `.is_rebalance_day(d: date) -> bool` e `.next_on_or_after(d: date) -> date | None`
  - `EodSignalSource(schedule, build_target: Callable[[date, dict[str, Decimal], dict[str, Decimal]], list[OrderIntent]], today: Callable[[], date])` con `async generate_intents(*, symbols, prices, positions) -> list[OrderIntent]`
  - `EodSignalSource.cycles_seen: int` e `.rebalances_seen: int` per l'osservabilità

- [ ] **Step 1: Write the failing test**

Creare `tests/unit/test_eod_source.py`:

```python
"""Runtime EOD per Lane B (BL-732, Fase 0d).

Lane B ri-bilancia trimestralmente su dati EOD. Il runner paper gira a 1
minuto su 4 simboli: e' la macchina sbagliata per l'universo (120 ticker)
e per la frequenza. Questi test pinnano lo strato che riconcilia i due:
una schedule di rebalance e una sorgente che emette solo nei giorni di
rebalance.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from execution.eod_source import EodSignalSource, RebalanceSchedule


class _Recorder:
    """build_target fittizio: registra le chiamate e restituisce una lista fissa."""

    def __init__(self, out: list[object] | None = None) -> None:
        self.calls: list[tuple[date, dict[str, Decimal], dict[str, Decimal]]] = []
        self._out = out if out is not None else []

    def __call__(self, as_of, prices, positions):  # type: ignore[no-untyped-def]
        self.calls.append((as_of, prices, positions))
        return list(self._out)


def _run(source: EodSignalSource, symbols, prices, positions):  # type: ignore[no-untyped-def]
    return asyncio.run(
        source.generate_intents(symbols=symbols, prices=prices, positions=positions)
    )


# ---------------------------------------------------------------------------
# RebalanceSchedule
# ---------------------------------------------------------------------------


def test_schedule_recognises_its_own_dates() -> None:
    s = RebalanceSchedule([date(2020, 1, 2), date(2020, 4, 1)])
    assert s.is_rebalance_day(date(2020, 1, 2))
    assert s.is_rebalance_day(date(2020, 4, 1))


def test_schedule_rejects_other_dates() -> None:
    s = RebalanceSchedule([date(2020, 1, 2)])
    assert not s.is_rebalance_day(date(2020, 1, 3))


def test_schedule_next_on_or_after_inclusive() -> None:
    s = RebalanceSchedule([date(2020, 1, 2), date(2020, 4, 1)])
    assert s.next_on_or_after(date(2020, 1, 2)) == date(2020, 1, 2)
    assert s.next_on_or_after(date(2020, 1, 15)) == date(2020, 4, 1)


def test_schedule_next_returns_none_past_the_end() -> None:
    s = RebalanceSchedule([date(2020, 1, 2)])
    assert s.next_on_or_after(date(2020, 2, 1)) is None


def test_schedule_from_monthly_rebalance_dates() -> None:
    from datetime import datetime

    dates = [datetime(2020, 1, 2), datetime(2020, 4, 1), datetime(2020, 7, 1)]
    s = RebalanceSchedule.from_rebalance_dates(dates)
    assert s.is_rebalance_day(date(2020, 4, 1))
    assert s.next_on_or_after(date(2020, 2, 1)) == date(2020, 4, 1)


# ---------------------------------------------------------------------------
# EodSignalSource
# ---------------------------------------------------------------------------


def test_source_emits_nothing_on_a_non_rebalance_day() -> None:
    rec = _Recorder(out=["intent"])
    src = EodSignalSource(
        RebalanceSchedule([date(2020, 1, 2)]),
        build_target=rec,
        today=lambda: date(2020, 1, 3),
    )
    assert _run(src, ["A"], {"A": Decimal("1")}, {"A": Decimal("0")}) == []
    assert rec.calls == []


def test_source_emits_on_a_rebalance_day() -> None:
    rec = _Recorder(out=["intent"])
    src = EodSignalSource(
        RebalanceSchedule([date(2020, 1, 2)]),
        build_target=rec,
        today=lambda: date(2020, 1, 2),
    )
    assert _run(src, ["A"], {"A": Decimal("1")}, {"A": Decimal("0")}) == ["intent"]
    assert len(rec.calls) == 1


def test_source_passes_prices_and_positions_through() -> None:
    rec = _Recorder()
    src = EodSignalSource(
        RebalanceSchedule([date(2020, 1, 2)]),
        build_target=rec,
        today=lambda: date(2020, 1, 2),
    )
    prices = {"A": Decimal("12.5")}
    positions = {"A": Decimal("3")}
    _run(src, ["A"], prices, positions)
    assert rec.calls[0][1] == prices
    assert rec.calls[0][2] == positions


def test_source_counts_cycles_and_rebalances() -> None:
    src = EodSignalSource(
        RebalanceSchedule([date(2020, 1, 2)]),
        build_target=_Recorder(),
        today=lambda: date(2020, 1, 2),
    )
    _run(src, ["A"], {"A": Decimal("1")}, {})
    _run(src, ["A"], {"A": Decimal("1")}, {})
    assert src.cycles_seen == 2
    assert src.rebalances_seen == 2


def test_source_counts_only_rebalance_days() -> None:
    day = {"d": date(2020, 1, 2)}
    src = EodSignalSource(
        RebalanceSchedule([date(2020, 1, 2)]),
        build_target=_Recorder(),
        today=lambda: day["d"],
    )
    _run(src, ["A"], {"A": Decimal("1")}, {})
    day["d"] = date(2020, 1, 3)
    _run(src, ["A"], {"A": Decimal("1")}, {})
    assert src.cycles_seen == 2
    assert src.rebalances_seen == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_eod_source.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution.eod_source'`

- [ ] **Step 3: Write minimal implementation**

Creare `execution/eod_source.py`:

```python
"""Runtime end-of-day per strategie a rebalance (BL-732, Fase 0d).

Lane B ri-bilancia trimestralmente su dati EOD, con 15 posizioni scelte
da un universo di ~120 ticker. Il runner paper gira a 1 minuto su una
lista di simboli: e' la macchina sbagliata per la frequenza e
soprattutto per l'universo, che a 1 minuto non si puo' nemmeno
rappresentare.

Questo modulo riconcilia i due senza riscrivere il runner:

* :class:`RebalanceSchedule` sa quali giorni sono giorni di rebalance;
* :class:`EodSignalSource` implementa il protocollo ``SignalSource`` di
  :mod:`execution.runner` e emette intenti **solo** nei giorni di
  rebalance, restituendo ``[]`` in tutti gli altri.

Il runner continua a fare quello che fa gia' bene — store durevole
idempotente, kill-switch, alerting, heartbeat, SIGTERM graceful — con
``tick_interval_s`` portato a una cadenza giornaliera.

La costruzione del target resta iniettata (``build_target``): e' il
punto di innesto dell'adapter Lane B, e mantiene questo modulo
dipendente dal solo protocollo, senza importare ``analytics``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime
from decimal import Decimal

from execution.paper_orchestrator import OrderIntent

__all__ = ["EodSignalSource", "RebalanceSchedule"]

TargetBuilder = Callable[
    [date, dict[str, Decimal], dict[str, Decimal]],
    list[OrderIntent],
]
"""``(as_of, prices, positions) -> intents``.

``as_of`` e' il giorno di rebalance, ``prices`` il prezzo corrente per
simbolo, ``positions`` la quantita' detenuta per simbolo. Restituire la
lista completa degli intenti che portano il portafoglio al target.
"""


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


class RebalanceSchedule:
    """I giorni in cui il portafoglio viene ri-bilanciato.

    Immutabile dopo la costruzione. I duplicati sono accettati e
    collassati: un giorno di rebalance duplicato non deve far emettere
    due volte lo stesso target.
    """

    def __init__(self, dates: Iterable[date | datetime]) -> None:
        self._dates: frozenset[date] = frozenset(_as_date(d) for d in dates)
        self._sorted: tuple[date, ...] = tuple(sorted(self._dates))

    @classmethod
    def from_rebalance_dates(cls, dates: Iterable[date | datetime]) -> RebalanceSchedule:
        """Costruisce la schedule dalle date di rebalance di un backtest.

        E' il percorso normale: le date sono quelle generate da
        ``LaneBBacktester._generate_rebalance_dates``, cosi' il paper
        replica esattamente la cadenza della qualifica.
        """
        return cls(dates)

    def is_rebalance_day(self, d: date | datetime) -> bool:
        """True se *d* e' un giorno di rebalance."""
        return _as_date(d) in self._dates

    def next_on_or_after(self, d: date | datetime) -> date | None:
        """Primo giorno di rebalance >= *d*, oppure ``None`` se non ce ne sono."""
        target = _as_date(d)
        for candidate in self._sorted:
            if candidate >= target:
                return candidate
        return None

    def __len__(self) -> int:
        return len(self._sorted)

    def __contains__(self, d: object) -> bool:
        if isinstance(d, (date, datetime)):
            return self.is_rebalance_day(d)
        return False


class EodSignalSource:
    """``SignalSource`` che emette solo nei giorni di rebalance.

    Il runner chiama ``generate_intents`` a ogni ciclo; nei giorni
    ordinari questo restituisce ``[]``, che per il protocollo e' il
    comportamento HOLD atteso. Nei giorni di rebalance delega a
    ``build_target``.

    Contatori esposti per l'osservabilita': un runner che gira per un
    trimestre senza mai incrementare ``rebalances_seen`` e' un runner
    che non sta tradando, ed e' un guasto silenzioso.
    """

    def __init__(
        self,
        schedule: RebalanceSchedule,
        *,
        build_target: TargetBuilder,
        today: Callable[[], date],
    ) -> None:
        self._schedule = schedule
        self._build_target = build_target
        self._today = today
        self.cycles_seen = 0
        self.rebalances_seen = 0

    async def generate_intents(
        self,
        *,
        symbols: list[str],  # noqa: ARG002
        prices: dict[str, Decimal],
        positions: dict[str, Decimal],
    ) -> list[OrderIntent]:
        self.cycles_seen += 1
        as_of = self._today()
        if not self._schedule.is_rebalance_day(as_of):
            return []
        self.rebalances_seen += 1
        return self._build_target(as_of, prices, positions)
```

Verificare il percorso di `OrderIntent`: `grep -n "class OrderIntent\|^from\|^import" execution/paper_orchestrator.py | head -20`. Se `OrderIntent` non è definito lì, correggere l'import nel modulo nuovo.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_eod_source.py -q`
Expected: PASS — 12 test.

- [ ] **Step 5: Check the architecture contract**

Run: `uv run lint-imports`
Expected: PASS. `execution/eod_source.py` importa solo da `execution`, quindi il contratto «execution dipende da core e contracts only» resta verde.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS — 3681 passed, 7 skipped, più i nuovi.

- [ ] **Step 7: Commit**

```bash
git add execution/eod_source.py tests/unit/test_eod_source.py
git commit -m "feat(BL-732): RebalanceSchedule + EodSignalSource per il runtime EOD

Lane B ri-bilancia trimestralmente su 120 ticker; il runner gira a 1
minuto su 4 simboli. La sorgente emette solo nei giorni di rebalance e
restituisce [] negli altri (HOLD per il protocollo), cosi' il runner
riusa store, kill-switch, alerting e heartbeat senza modifiche. Il
target resta iniettato: execution non importa analytics."
```

---

## Task 8: `LaneBBacktester` espone una API pubblica per i segnali

**Perché questo task esiste.** `LaneBBacktester` ha **un solo metodo pubblico**, `run()` (riga 381). Tutta la costruzione del frame `merged` — merge dei segnali Piotroski/Greenblatt e del rendimento a 12 mesi — vive in helper privati chiamati dentro `run()`. Ma `LaneBSignalAdapter.screen_universe()` richiede quel frame come argomento `merged`. Senza una API pubblica, il composition root di Task 9 dovrebbe chiamare metodi privati del backtester da uno script: accoppiamento fragile, ed è esattamente la classe di problema che il Contratto A di P2 deve eliminare.

**Files:**
- Modify: `analytics/strategy/lane_b_backtester.py` (estrae `prepare_signal_bundle`; `run()` la chiama)
- Test: `tests/unit/test_lane_b_signal_bundle.py` (crea)

**Interfaces:**
- Consumes: `LaneBBacktestConfig`, `SimFinLoader` (già esistenti)
- Produces: `LaneBBacktester.prepare_signal_bundle(*, start_date: datetime, end_date: datetime) -> pl.DataFrame` — il frame `merged` con colonne `SimFinId`, `publish_date`, `f_score`, `magic_formula_rank`, `return_12m`, esattamente quello che `run()` costruisce oggi prima del loop di rebalance.

- [ ] **Step 1: Write the failing test**

Creare `tests/unit/test_lane_b_signal_bundle.py`:

```python
"""BL-732 — il frame dei segnali come API pubblica.

Il backtester non esponeva alcun modo di ottenere il frame `merged` che
l'adapter real-time (LaneBSignalAdapter.screen_universe) richiede: solo
run() lo costruiva, in helper privati. Senza questo metodo il wiring di
produzione deve chiamare metodi privati da uno script.
"""

from __future__ import annotations

import inspect

import polars as pl

from analytics.strategy.lane_b_backtester import LaneBBacktester

REQUIRED_COLUMNS = {"SimFinId", "publish_date", "f_score", "magic_formula_rank", "return_12m"}


def test_prepare_signal_bundle_is_public() -> None:
    assert hasattr(LaneBBacktester, "prepare_signal_bundle")
    assert not LaneBBacktester.prepare_signal_bundle.__name__.startswith("_")


def test_prepare_signal_bundle_signature_is_keyword_only() -> None:
    sig = inspect.signature(LaneBBacktester.prepare_signal_bundle)
    assert "start_date" in sig.parameters
    assert "end_date" in sig.parameters
    for name in ("start_date", "end_date"):
        assert sig.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_run_uses_prepare_signal_bundle() -> None:
    """run() non deve duplicare la costruzione del frame.

    Se il frame viene costruito due volte, prima o poi le due copie
    divergono e il paper non replica piu' la qualifica.
    """
    src = inspect.getsource(LaneBBacktester.run)
    assert "prepare_signal_bundle" in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_lane_b_signal_bundle.py -q`
Expected: FAIL — `assert hasattr(LaneBBacktester, 'prepare_signal_bundle')` → False

- [ ] **Step 3: Write minimal implementation**

In `analytics/strategy/lane_b_backtester.py`, aggiungere il metodo pubblico subito sopra `def run(`:

```python
    def prepare_signal_bundle(
        self, *, start_date: datetime, end_date: datetime
    ) -> pl.DataFrame:
        """Costruisce il frame dei segnali fondamentali PIT per la finestra.

        E' il frame che :meth:`run` consuma nel proprio loop di rebalance
        e che :meth:`analytics.strategy.lane_b_adapter.LaneBSignalAdapter.screen_universe`
        richiede come argomento ``merged``. Prima del 2026-09-17 esisteva
        solo dentro ``run``, in helper privati: il percorso di produzione
        non aveva modo di ottenere gli stessi segnali del percorso di
        qualifica.

        Averlo pubblico garantisce che la qualifica e il paper usino la
        stessa costruzione, invece di due copie destinate a divergere.

        Returns
        -------
        pl.DataFrame
            Colonne richieste da ``screen_universe``: ``SimFinId``,
            ``publish_date``, ``f_score``, ``magic_formula_rank``,
            ``return_12m``.
        """
        raise NotImplementedError
```

Poi spostare dentro questo metodo il corpo che oggi sta in `run()` fra la costruzione di `merged` e la riga `rebalances = self._generate_rebalance_dates(...)`, e in `run()` sostituirlo con:

```python
        merged = self.prepare_signal_bundle(start_date=start_date, end_date=end_date)
```

Il corpo da spostare è quello che:
1. carica income/balance/cashflow/shareprices via `self.loader`,
2. chiama `self._compute_piotroski_signals(...)` e `self._compute_greenblatt_signals(...)`,
3. fa il join con `return_12m`.

> **Nota di implementazione:** leggere il corpo reale di `run()` (righe 381-420) e spostarlo **verbatim**, senza riscriverlo. Ogni riga cambiata è una possibilità di alterare i segnali e quindi il verdetto. `raise NotImplementedError` nello Step 3 serve solo a far passare dal rosso al verde il test di presenza; il corpo vero va incollato subito dopo, nello stesso step.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_lane_b_signal_bundle.py -q`
Expected: PASS

- [ ] **Step 5: Verify the refactor did not change the backtest**

Run: `uv run pytest tests/unit/test_composite_lane_b.py tests/unit/test_lane_b_rebalance_series.py -q`
Expected: PASS. Il refactor è puramente estrattivo: ogni test che tocca i segnali deve restare verde.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS — 3681 passed, 7 skipped, più i nuovi.

- [ ] **Step 7: Commit**

```bash
git add analytics/strategy/lane_b_backtester.py tests/unit/test_lane_b_signal_bundle.py
git commit -m "refactor(BL-732): prepare_signal_bundle pubblico sul backtester

run() era l'unico metodo pubblico e costruiva il frame merged in helper
privati, mentre LaneBSignalAdapter.screen_universe lo richiede come
argomento. Il percorso di produzione doveva quindi chiamare metodi
privati. Estrazione puramente meccanica: run() ora chiama lo stesso
codice, cosi' qualifica e paper non possono divergere."
```

---

## Task 9: Wiring e smoke del runtime EOD

**Files:**
- Create: `config/paper_lane_b.yaml`
- Create: `scripts/run_paper_lane_b.py`
- Test: `tests/unit/test_eod_source.py` (aggiunge lo smoke)

**Interfaces:**
- Consumes: `EodSignalSource`, `RebalanceSchedule` (Task 7), `LaneBBacktester.prepare_signal_bundle` (Task 8), `LaneBSignalAdapter.screen_universe` + `.generate_rebalance_intents` (esistenti), `PaperRunner`, `PaperRunnerConfig`
- Produces: `scripts/run_paper_lane_b.py` eseguibile con `--config config/paper_lane_b.yaml --max-cycles N [--dry-schedule]`

- [ ] **Step 1: Write the failing test**

Aggiungere a `tests/unit/test_eod_source.py`:

```python
def test_runner_accepts_the_eod_source_unmodified() -> None:
    """Il runner non deve sapere che la sorgente e' EOD.

    E' il punto del Task 7: se il runner richiede modifiche, l'astrazione
    e' sbagliata e va rifatta prima di andare avanti.
    """
    import inspect

    from execution.runner import PaperRunner, PaperRunnerConfig

    cfg = PaperRunnerConfig(symbols=["A"], tick_interval_s=86400.0)
    src = EodSignalSource(
        RebalanceSchedule([date(2020, 1, 2)]),
        build_target=_Recorder(),
        today=lambda: date(2020, 1, 2),
    )
    runner = PaperRunner(cfg, signal_source=src, clock=lambda: 0.0)
    assert runner is not None
    # Il costruttore deve accettare la sorgente via il protocollo, senza
    # un ramo dedicato: nessun isinstance su EodSignalSource in runner.py.
    assert "EodSignalSource" not in inspect.getsource(PaperRunner.__init__)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_eod_source.py -q -k runner_accepts`
Expected: PASS se il runner accetta già il protocollo, FAIL se richiede un ramo dedicato. Se fallisce, **fermarsi**: l'astrazione va corretta in Task 7, non aggirata qui.

- [ ] **Step 3: Create the config**

Creare `config/paper_lane_b.yaml`:

```yaml
# BL-732 — Config del runner paper in modalità Lane B EOD.
#
# A differenza di config/paper.yaml (tick 60s, 4 simboli), questo profilo
# gira a cadenza giornaliera su un universo ampio: la sorgente di segnale
# emette solo nei giorni di rebalance trimestrali, quindi la maggior
# parte dei cicli e' un HOLD.
#
# Avvio:
#   uv run python scripts/run_paper_lane_b.py --config config/paper_lane_b.yaml --max-cycles 5

db_path: data/paper/paper_lane_b.db

# Un ciclo al giorno: il rebalance e' EOD, non intraday.
tick_interval_s: 86400.0

# L'universo viene popolato a runtime dai titoli selezionati dal
# backtester (Lane B: 15 holdings da ~120 ticker). Questa lista e' il
# fallback quando il segnale non e' ancora disponibile, e serve a far
# partire il runner senza errori.
symbols:
  - SPY
  - QQQ

timeframe: 1d
starting_cash: 100000

# Con un ciclo al giorno, un heartbeat ogni ciclo e' settimanale:
# allineare la soglia di allarme di conseguenza.
heartbeat_cycle_s: 1
heartbeat_timeout_s: 200000.0

lake_root: data/lake/normalized
legacy_root: data/ohlcv
```

- [ ] **Step 4: Create the wiring script**

Creare `scripts/run_paper_lane_b.py`:

```python
#!/usr/bin/env python3
"""BL-732 — Runner paper per Lane B in modalità EOD.

Compone i pezzi esistenti:

    RebalanceSchedule          <- date di rebalance del backtester Lane B
    LaneBBacktester.prepare_signal_bundle  <- i segnali fondamentali PIT
    LaneBSignalAdapter         <- screen + costruzione degli OrderIntent
    EodSignalSource            <- emette solo nei giorni di rebalance
    PaperRunner                <- store durevole, kill-switch, alerting, heartbeat

Il runner non viene modificato. Questo script e' l'unico punto che
conosce sia ``analytics`` (i segnali) sia ``execution`` (il runner), ed
e' per questo che vive in ``scripts/``: e' un composition root.

Uso:
    uv run python scripts/run_paper_lane_b.py \
        --config config/paper_lane_b.yaml --max-cycles 5 --dry-schedule
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl  # noqa: E402

from analytics.fundamental.simfin_loader import SimFinLoader  # noqa: E402
from analytics.strategy.lane_b_adapter import LaneBSignalAdapter  # noqa: E402
from analytics.strategy.lane_b_backtester import LaneBBacktestConfig, LaneBBacktester  # noqa: E402
from execution.eod_source import EodSignalSource, RebalanceSchedule  # noqa: E402
from execution.paper_orchestrator import OrderIntent  # noqa: E402
from execution.runner import PaperRunner, PaperRunnerConfig  # noqa: E402

WINDOW_START = datetime(2020, 1, 1)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=ROOT / "config" / "paper_lane_b.yaml")
    p.add_argument("--max-cycles", type=int, default=0, help="0 = nessun limite")
    p.add_argument(
        "--dry-schedule",
        action="store_true",
        help="Schedule di un solo giorno (oggi): smoke del wire end-to-end.",
    )
    return p.parse_args()


def _build_schedule(*, dry: bool) -> RebalanceSchedule:
    """Date di rebalance.

    Modalita' normale: le stesse date che genera il backtester, cosi' il
    paper replica la cadenza della qualifica. In modalita' dry la
    schedule contiene solo oggi, per verificare il wire senza attendere
    un trimestre.
    """
    if dry:
        return RebalanceSchedule([date.today()])
    cfg = LaneBBacktestConfig()
    end = datetime(datetime.now().year + 1, 1, 1)
    dates: list[datetime] = []
    cur = WINDOW_START
    while cur < end:
        dates.append(cur)
        month = cur.month - 1 + cfg.rebalance_months
        cur = datetime(cur.year + month // 12, month % 12 + 1, 1)
    return RebalanceSchedule.from_rebalance_dates(dates)


def _load_price_frame(loader: SimFinLoader) -> pl.DataFrame:
    """Prezzi giornalieri nel contratto richiesto da screen_universe.

    ``screen_universe`` vuole le colonne ``SimFinId``, ``date``,
    ``Close``. Il loader le espone con i nomi della convenzione SimFin;
    la rinomina esplicita tiene il contratto in un punto solo.
    """
    raw = loader.daily_prices()
    rename = {}
    if "Ticker" in raw.columns and "SimFinId" not in raw.columns:
        rename["Ticker"] = "SimFinId"
    if "Date" in raw.columns:
        rename["Date"] = "date"
    if "Close" not in raw.columns and "Adj. Close" in raw.columns:
        rename["Adj. Close"] = "Close"
    if rename:
        raw = raw.rename(rename)
    missing = {"SimFinId", "date", "Close"} - set(raw.columns)
    if missing:
        msg = f"daily_prices() non espone {sorted(missing)}; colonne: {raw.columns}"
        raise ValueError(msg)
    return raw.select(["SimFinId", "date", "Close"])


def main() -> int:
    args = _parse_args()
    cfg = PaperRunnerConfig.from_yaml(args.config)
    schedule = _build_schedule(dry=args.dry_schedule)

    loader = SimFinLoader()
    backtester = LaneBBacktester(loader)
    adapter = LaneBSignalAdapter()

    # Il bundle si costruisce una volta sola: la finestra copre il
    # presente, quindi i segnali pubblicati fino a oggi sono tutti dentro.
    end = datetime.now()
    merged = backtester.prepare_signal_bundle(start_date=WINDOW_START, end_date=end)
    price_frame = _load_price_frame(loader)
    print(
        f"[lane-b] schedule={len(schedule)} rebalance, "
        f"merged={merged.height} righe, prezzi={price_frame.height} righe"
    )

    def build_target(
        as_of: date, prices: dict[str, Decimal], positions: dict[str, Decimal]
    ) -> list[OrderIntent]:
        """Intenti del rebalance, via l'adapter Lane B.

        L'adapter non tocca la rete: seleziona la pubblicazione piu'
        recente con ``publish_date <= as_of`` dal bundle gia' costruito.
        """
        target = adapter.screen_universe(
            as_of_date=datetime.combine(as_of, time.min),
            merged=merged,
            prices=price_frame,
        )
        return adapter.generate_rebalance_intents(
            current_positions=positions,
            current_prices=prices,
            portfolio_nav=Decimal(str(cfg.starting_cash)),
            as_of_date=as_of.isoformat(),
            target_holdings=target,
        )

    source = EodSignalSource(schedule, build_target=build_target, today=date.today)
    runner = PaperRunner(cfg, signal_source=source)

    original_cycle = runner._run_one_cycle  # noqa: SLF001

    async def capped_cycle() -> object:  # type: ignore[no-untyped-def]
        if args.max_cycles and source.cycles_seen >= args.max_cycles:
            runner.request_stop()
        return await original_cycle()

    runner._run_one_cycle = capped_cycle  # type: ignore[method-assign]  # noqa: SLF001

    async def _go() -> int:
        await runner.setup()
        try:
            return await runner.run()
        finally:
            await runner.shutdown()
            print(f"[lane-b] cicli={source.cycles_seen} rebalance={source.rebalances_seen}")

    return asyncio.run(_go())


if __name__ == "__main__":
    raise SystemExit(main())
```

> **Verifica obbligatoria prima di eseguire:** i nomi delle colonne di
> `SimFinLoader.daily_prices()` (riga 120 di `analytics/fundamental/simfin_loader.py`)
> e la tabella di rinomina che l'adapter si aspetta. `_load_price_frame`
> solleva con l'elenco delle colonne trovate invece di fallire in modo
> opaco: leggere quel messaggio e correggere la rinomina. Non indovinare.

- [ ] **Step 5: Run the smoke**

```bash
uv run python scripts/run_paper_lane_b.py --config config/paper_lane_b.yaml --max-cycles 3 --dry-schedule
```

Expected: exit 0, `[lane-b] cicli=3 rebalance=3` (la schedule dry contiene un solo giorno, che è oggi), nessuna eccezione, e il DB `data/paper/paper_lane_b.db` creato.

Se l'adapter richiede dati SimFin non disponibili in locale, lo smoke fallisce su quello: **non aggirarlo con un target fittizio**. Annotare il gap nel report di Task 8 e lasciare il runner cablato — il cablaggio è il deliverable, il segnale reale dipende da `data/simfin/`.

- [ ] **Step 6: Commit**

```bash
git add config/paper_lane_b.yaml scripts/run_paper_lane_b.py tests/unit/test_eod_source.py
git commit -m "feat(BL-732): wiring del runner paper in modalita' Lane B EOD

scripts/run_paper_lane_b.py e' il composition root: conosce analytics
(l'adapter del segnale) e execution (il runner). Il runner resta
invariato. Config dedicata a cadenza giornaliera, distinta da
config/paper.yaml (tick 60s, 4 simboli)."
```

---

## Task 10: `STATUS.md` allineato al verdetto

**Files:**
- Modify: `docs/ORACLE_AUTOPILOT_STATUS.md` (tabella §3.3, riga «B — Composite value»)

**Interfaces:**
- Consumes: il verdetto di Task 4/6
- Produces: nessuna interfaccia di codice.

- [ ] **Step 1: Read the current claim**

Run: `grep -n "Composite value" docs/ORACLE_AUTOPILOT_STATUS.md`
Expected: la riga che oggi dichiara «🟢 **QUALIFICATO (BL-727)**».

- [ ] **Step 2: Replace the row with the truth**

Sostituire il contenuto della cella con, a seconda del verdetto:

Se `APPROVED`:

```markdown
| **B — Composite value (Piotroski 40% + Greenblatt 40% + Lakonishok 20%, thr 0.65)** | 🟢 **QUALIFICATO (BL-727 v2)** — preregistrazione riaperta il 2026-09-17 dopo che il verdetto v1 risultò `REJECTED_TREE_INTEGRITY` (gate di tree-integrity fallito, run proseguito con `--allow-head-mismatch`; il report dichiarava un HEAD drift inesistente). v2 rieseguita su albero pulito **senza bypass**, `tree_bypass_used=false`: Sharpe <X>, Annual <Y>%, MaxDD <Z>%, DSR <D> ✅, PSR <P> ✅, CPCV OOS median <C> ✅, Haircut Sharpe <H> ✅, Bear 2022 Sharpe <B> ✅, IC screen <esito> | `docs/reports/lane-b-composite/<data>-bl727v2-qualification.md` |
```

Se `REJECTED`:

```markdown
| **B — Composite value (Piotroski 40% + Greenblatt 40% + Lakonishok 20%, thr 0.65)** | 🔴 **REJECTED (BL-727 v2)** — preregistrazione riaperta il 2026-09-17 (v1: `REJECTED_TREE_INTEGRITY`). v2 rieseguita su albero pulito **senza bypass**: gate fallito su <gate>. La variante non è promuovibile: BL-732 è bloccata | `docs/reports/lane-b-composite/<data>-bl727v2-qualification.md` |
```

Sostituire i segnaposto `<X>`, `<Y>`, … con i numeri letti dal JSON di Task 4/6. **Nessun numero inventato**: se un valore non c'è nel report, scrivere «non riportato» e aprire un backlog item.

- [ ] **Step 3: Verify no other doc repeats the stale claim**

Run: `grep -rn "QUALIFICATO (BL-727)" docs/ BACKLOG.md ROADMAP.md PROJECT.md`
Expected: nessun risultato oltre a quello appena corretto. Correggere ogni occorrenza residua.

- [ ] **Step 4: Commit**

```bash
git add docs/ORACLE_AUTOPILOT_STATUS.md
git commit -m "docs(status): la riga Lane B riflette il verdetto reale

STATUS.md dichiarava QUALIFICATO un report il cui verdetto registrato e'
REJECTED_TREE_INTEGRITY. Ora la riga cita il verdetto v2, rieseguito
senza bypass, con i numeri letti dal report."
```

---

## Self-Review

**1. Copertura della spec**

| Requisito spec | Task |
|---|---|
| §3 Fase 0a — fix `prereg.py` (messaggio + classificazione, mai la logica) | 1, 2 |
| §3 Fase 0a — manifest riemesso (riapertura v2, §7 della v1) | 3 |
| §3 Fase 0a — re-run senza `--allow-head-mismatch` | 4 |
| §3 Fase 0a — correzione di `STATUS.md` | 10 |
| §3 Fase 0c — estensione `LaneBBacktestResult` con la serie per-rebalance | 5 |
| §3 Fase 0c — IC screen sul fattore vero | 6 |
| §3 Fase 0d — runtime EOD riusando `execution/runner.py` | 7, 8, 9 |
| §3 Fase 0d — sostituire clock e signal source, non il runner | 7 (test `runner_accepts_the_eod_source_unmodified`) |

Nessun requisito di P1 resta senza task. **Non coperti da questo piano** (appartengono a P2/P3, per §3.1): igiene, i due contratti CI, split del CLI, verifica G7-CFD, archivio, ricerca esterna.

**2. Placeholder scan**

Nessun `TBD`/`TODO`. I due punti che a prima vista sembrano segnaposto non lo sono:
- il `<SHA del commit che contiene questo manifest>` in Task 3 ha una procedura in 5 passi che lo risolve;
- i `<X>`, `<Y>` in Task 10 sono istruiti a essere letti dal JSON, con l'istruzione esplicita di scrivere «non riportato» se mancano.

Restano **due** dipendenze da verificare a runtime, entrambe marcate come tali e con un percorso di errore che dice cosa fare invece di fallire in modo opaco: i nomi delle colonne di `SimFinLoader.daily_prices()` in Task 9 (`_load_price_frame` solleva con l'elenco delle colonne trovate), e il corpo da spostare in Task 8 (che va copiato verbatim, non riscritto).

**3. Coerenza dei tipi**

- `PreregErrorKind` — definito in Task 1, usato in Task 2 (`_tree_reason`) e Task 3 (`verify_prereg_commit`). Stesso nome, stessi membri.
- `describe_tree_failure(kind, message, head, pinned)` — Task 1; `_tree_reason` in Task 2 ha la stessa firma e delega. Coerenti.
- `verify_prereg_commit(expected_commit, repo_root)` — Task 3; chiamato in Task 2 (blocco tree) e Task 3 Step 6. Coerenti.
- `rebalance_dates` / `rebalance_composite_scores` — Task 5 (produzione) e Task 6 (`build_ic_inputs`, consumo). Coerenti.
- `prepare_signal_bundle(*, start_date, end_date) -> pl.DataFrame` — definito in Task 8, consumato in Task 9 e chiamato da `run()`. Coerente.
- `EodSignalSource(schedule, *, build_target, today)` — Task 7; usato in Task 9 con argomenti keyword. Coerenti.
- `RebalanceSchedule.from_rebalance_dates` — Task 7 (definizione) e Task 9 (`_build_schedule`). Coerente.
- `TargetBuilder` — `(date, dict[str, Decimal], dict[str, Decimal]) -> list[OrderIntent]` in Task 7; `build_target` in Task 9 ha quella firma e ritorna `list[OrderIntent]`. Coerente.
- `LaneBSignalAdapter.screen_universe(*, as_of_date, merged, prices, companies=None)` e `.generate_rebalance_intents(*, current_positions, current_prices, portfolio_nav, as_of_date, target_holdings)` — firme lette da `analytics/strategy/lane_b_adapter.py:252` e `:380`, riprodotte in Task 9. Coerenti.

**4. Correzione rispetto alla prima stesura**

La prima versione di questo piano aveva due difetti trovati in verifica:

1. **Task 8 non era implementabile.** Il wiring chiamava `adapter.load_signals()` e `adapter.build_rebalance_intents()`, metodi che non esistono (l'API reale è `screen_universe` / `generate_rebalance_intents`), e assumeva che l'adapter sapesse procurarsi i segnali. Non è così: `screen_universe` **richiede** il frame `merged`, e `LaneBBacktester` ha un solo metodo pubblico, `run()`, che lo costruisce internamente in helper privati. Il piano ora include il Task 8 mancante — l'estrazione di `prepare_signal_bundle()` — senza il quale il composition root dovrebbe chiamare metodi privati del backtester.
2. **`from dataclasses import dataclass`** in `lane_b_backtester.py:29` non importa `field`. Il Task 5 lo richiede esplicitamente.

**5. Decomposizione**

10 task, ciascuno con il suo ciclo test e il suo commit. Task 1-2 sono prerequisito di 3-4. Task 5 è prerequisito di 6. Task 7 e 8 sono prerequisiti di 9. Task 10 dipende da 4 e 6. I due rami (1-4, 5-6) e (7-9) sono indipendenti fra loro e possono procedere in parallelo.

**6. Cosa questo piano NON fa**

Non decide se Lane B è qualificato — lo scopre. Se il verdetto di Task 4 o 6 è `REJECTED`, il piano produce comunque un risultato valido: un verdetto credibile, ottenuto senza bypass, e un runtime EOD pronto per quando una strategia lo meriterà. La spec §6 R1 lo prevede.

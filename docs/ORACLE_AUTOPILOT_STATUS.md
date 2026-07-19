# Oracle Autopilot — Execution Status

> Checkpoint operativo. Aggiornare soltanto con evidenza fresca.
> Ultima review: 2026-07-18

## 1. Identità del checkpoint

- Branch: main
- Baseline HEAD: e54ac46dab86094c3579ba1fe05afe400d2de85f
- Working tree: 180 voci (143 tracked, 37 untracked; una deletion già staged)
- Gate attivo: G0 — Baseline veritiera e riproducibile
- Work package attivo: WP-001 — Consolidare la working tree
- Modalità autorizzata: RESEARCH e PAPER_TEST
- Live, evaluation e funded: DISABLED
- Roadmap: [ORACLE_AUTOPILOT_MASTER_ROADMAP.md](ORACLE_AUTOPILOT_MASTER_ROADMAP.md)
- Review: [reviews/2026-07-18-project-review.md](reviews/2026-07-18-project-review.md)

## 2. Baseline verificata

| Comando/prova | Esito |
|---|---|
| uv run --frozen pytest tests/ -q | 1.605 passed, 2 skipped, 319 warning |
| uv run --frozen ruff check . | Pass |
| uv run --frozen ruff format --check . | 397 file conformi |
| uv run --frozen mypy --strict sui package applicativi | 261 source file, 0 issue con override configurati |
| uv lock --check | Pass |
| uv sync --frozen --all-extras --all-groups in venv pulita | Pass |
| pip-audit sull'ambiente `.venv` installato | Nessuna vulnerabilità nota; `uv.lock` non auditato direttamente |
| Dashboard test | 15/15 |
| Dashboard build | Pass con chunk Plotly circa 4,5 MB |
| Dashboard npm audit | 0 vulnerability dopo upgrade Vite 8 |
| Eliza typecheck/test/build | Pass; 2/2 test |
| Eliza npm audit | 5 low, 0 moderate/high/critical |

## 3. Modifiche safety/stack della review

- upgrade dashboard da Vite 5 a Vite 8 e plugin React compatibile;
- Node 24 standardizzato nelle applicazioni Node e in CI;
- audit npm completo aggiunto alla CI per dashboard ed Eliza;
- CI Python convertita a uv sync --frozen sul lockfile;
- Makefile e check ambiente riallineati a uv frozen;
- incompatibilità Ruff isort/formatter corretta;
- stato locale OMX/lean-ctx e `*.tsbuildinfo` esclusi dal versionamento;
- submit CLI verso broker non-paper reso fail-closed;
- documentazione Phase deprecata e archiviata;
- roadmap riscritta come capability gate;
- architettura corrente/target e ADR aggiunti.

## 4. Gate status

| Gate | Stato | Blocker |
|---|---|---|
| G0 | IN_PROGRESS | Working tree non consolidata; run CI remoto e supply-chain gate da completare |
| G1 | BLOCKED | Risk opzionale, API auth fail-open, ambienti non separati |
| G2 | IN_PROGRESS | ContractSpec, calendari e contract roll assenti |
| G3 | NOT_STARTED | OMS, ledger e broker paper in-memory |
| G4 | IN_PROGRESS | Prop governor esiste ma restano bypass |
| G5 | BLOCKED | Motore qualification non certificato |
| G6 | NOT_STARTED | Paper/shadow qualification assente |
| G7 | NOT_STARTED | Nessun programma certificato |
| G8 | NOT_STARTED | Live/funded non autorizzato |
| G9 | NOT_STARTED | Dipende da G8 |

## 5. Blocker P0/P1

### P0

1. OrderManager accetta risk_manager assente.
2. Alcune composition root possono ancora costruire execution senza hard risk.
3. API authentication resta opzionale quando ORACLE_API_KEY è vuota.
4. Nessun ledger/OMS durevole o account source of truth.
5. Nessun ContractSpec futures certificato.

### P1

1. Contratti PortfolioPlan/TradeIntent nel package agents creano dipendenza
   execution → agents.
2. Backtest Nautilus contiene fallback e modelli equity non futures-grade.
3. vectorbt ha portabilità macOS x86 e licenza Commons Clause da governare.
4. Docker/Compose non usa ancora un'immagine locked/non-root production-grade.
5. Warning Python, coverage e mypy override riducono la forza del claim
   “strict/green”.
6. NATS, QuestDB, Qdrant, Redis e PostgreSQL sono descritti oltre il loro uso
   autorevole corrente.

## 6. Prossimo lavoro eseguibile

1. Inventariare e separare le modifiche della working tree.
2. Eseguire la CI aggiornata su checkout pulito.
3. Aggiungere secret scan, dependency review e SBOM.
4. Rendere API production fail-closed.
5. Rendere risk obbligatorio in ogni execution composition root.
6. Definire environment e credential boundary.
7. Spostare i decision contract in un layer inward.
8. Implementare ContractSpec per un micro future.
9. Progettare ledger, OMS, outbox e reconciliation.
10. Certificare il motore di qualification prima di riaprire GA promotion.

## 7. Protocollo di aggiornamento

Ogni checkpoint deve registrare:

~~~text
Gate:
Work package:
Stato:
Branch e commit:
File modificati:
Test mirati:
Regression suite:
Static checks:
Security/dependency scan:
Evidenza esterna:
Rischi residui:
Prossimo work package:
~~~

Non aggiornare un conteggio copiandolo da documenti precedenti. Rieseguire il
comando e registrare l'output.

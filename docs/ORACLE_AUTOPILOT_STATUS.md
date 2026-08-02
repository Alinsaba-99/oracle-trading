# Oracle Autopilot — Execution Status

> Checkpoint operativo. Aggiornato: 2026-08-01 (validazione post-BL-301).
> La gerarchia documentale è: ROADMAP (perché) → STATUS (cosa) → BACKLOG
> (come) → ADR (decisioni) → report (evidenza). Solo STATUS riporta la
> matrice gate/stato.

## 1. Identità del checkpoint

- **Branch**: `feat/bl-301-data-lake` (active development)
- **HEAD**: `07e2d3d` (feat: grana 5m/15m/30m derivata dal 1m + TIER 9 crypto)
- **Working tree**: modificato (metadata lake post-backfill + remediation typing/mypy)
- **Modalità autorizzata**: RESEARCH, REPLAY, PAPER
- **PAPER, SHADOW, EVALUATION, FUNDED**: PAPER parziale (gate rejected). SHADOW/EVALUATION/FUNDED: DISABLED

## 2. Baseline verificata (2026-08-01)

| Comando | Esito |
|---|---|
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 672 files formatted |
| `mypy --strict core/ market/ analytics/ execution/ genetics/ research/ agents/ audit/ policy/ orchestration/` | ✅ Success: no issues found in 335 source files |
| `pytest tests/` | **✅ 2630 passed**, 6 skipped, 42 warnings, 0 failed |
| Postgres path (`--storage=postgres`) | ✅ — schema applicato, OMS/ledger verdi |
| Smoke regime→paper→OMS | ✅ |
| Data lake integrity | 🟡 457 serie / 97 simboli / 316.704.530 righe / 47.190 lineage entries; 0 riferimenti pendenti, ma 20.879 partizioni normalized senza lineage |

## 3. Gate status (unica tabella gate/stato autoritativa)

| Gate | Stato | Evidenza | Limite noto |
|---|---|---|---|
| G0 baseline | ✅ PASSED | ruff/mypy verdi, uv.lock, CI, secret scan, warning budget | budget warning CI = 350; run locale corrente = 42 |
| G1 autorità/ambienti | ✅ PASSED | mode guard, startup fail-closed, credential isolation, CLI guard | `OrderManager` ammette risk=None in path script untracked (BL-040) |
| G2 contract data | 🟡 PARTIAL | ContractSpec, CME calendars, roll, PIT detection; BL-301 lake operativo | 20.879 partizioni normalized senza lineage, 32 record coverage incompleti, 7 refresh falliti al checkpoint (BL-307) |
| G3 ledger/OMS | ✅ PASSED | PostgreSQL path attivo 25-lug; RecoveryService + ReconciliationWorker + idempotency; restart senza perdita/dup | persistenza Postgres solo in `--storage=postgres` |
| G4 hard risk | ✅ PASSED | RiskManager, FirmProgramProfile, 35 property test, bypass audit | adapter PropFirm cablato in CLI ma **escluso dal paper harness** (BL-070 risolto) |
| **G5 research truth** | ❌ **REJECTED** | dataset M31 pinned (`09a22…`) e re-run riproducibile | median Sharpe 0.3424 < 0.5, worst DD 15.94% > 4%, 88 hard breach; BL-023 aperto |
| G6 paper | 🟡 **REJECTED** | M32a originale 23/30; post-fix 30/30 ma con 0 trade, 0 P&L e Sharpe 0 | manca un run qualificante trade-producing; BL-024 aperto |
| G6-I feedback loop | 🟡 PARTIAL | Factor Timing v1 (26 test), Lorentzian causal-fix (6 test), Regime Ensemble (14 test) | nessun gate end-to-end; Lorentzian mai trigger dominante |
| G7 programm prop-firm | ⚪ NOT_STARTED | dipende da G5+G6+poli cert | block su G5/G6 |
| G8 funded limited | ⚪ NOT_STARTED | | |
| G9 continuous ops | ⚪ NOT_STARTED | | |

### 3.1 Risultati M32a WP2 (verifica 25-lug)

Eseguito: `python scripts/run_g6_wp2_paper_sessions.py --sessions 30 --data data/ohlcv/ES_1d.parquet --storage memory`

| Metrica | Target | Risultato |
|---|---|---|
| pass_rate | ≥ 0.90 | **0.77** (23/30) ❌ |
| mean_sharpe | ≥ -0.5 | -0.31 ✅ (borderline) |
| mean_max_dd | ≤ 3.0% | 1.54% ✅ |
| reconcile_clean_rate | = 1.0 | 1.00 ✅ |

**Decisione**: REJECTED. Causa: regime choppy-biased (29/30 mean_rev per default `_sma_regime_heuristic`).

### 3.2 Distribuzione regime (M32a)

| Regime | n sessioni | Specialist attivo | Pass rate |
|---|---|---|---|
| choppy | 29 | mean_rev | 21/29 (72%) |
| volatile | 1 | breakout | 1/1 (100%) |

## 4. Rischi residui

1. **🔴 Lineage lake incompleta.** 20.879 partizioni `normalized/` non hanno
   una voce in `lineage.json`; 32 record coverage hanno schema incompleto.
   Non va ricostruita provenance per inferenza. Backlog: BL-307.
2. **🔴 G5 ancora REJECTED.** Dataset pin e riproducibilità sono risolti, ma
   Sharpe, drawdown e hard breach non raggiungono le soglie. Backlog: BL-023.
3. **🟡 G6 senza evidenza trade-producing.** Il run post-fix passa formalmente
   30/30 ma produce 0 trade e non qualifica la strategia. Backlog: BL-024.
4. **🟡 42 warning pytest** entro il budget CI di 350; debito tecnico residuo.
5. **🟡 NATS / QuestDB / Qdrant / Redis** descritti in Compose oltre l'uso reale.
6. **🟡 CCXT_bridge e uvicorn** in `ps -ef` non sono di Oracle (sono di
   `distill-lab`). Niente da fare qui.

## 5. Stato reale vs dichiarato

| Affermazione | Verificato |
|---|---|
| "M31 APPROVED per historical replay" | ❌ falso — dataset ora pinned e run riproducibile, ma le soglie G5 sono REJECTED |
| "G3 Postgres path attivo" | ✅ vero (commit ffe91b4) |
| "G6-WP2 PASSED 20/20" | ✅ vero **solo per il primo diagnostic M32** (DD 0.21%). M32a paper 23/30 = REJECTED |
| "Regime-ensemble routing OK" | ✅ ribilanciamento e hysteresys implementati; manca ancora evidenza G6 con trade reali |
| "Lorentzian causal fix" | ✅ test verdi, ma Lorentzian mai trigger dominante nel paper run |
| "Live disabilitato finché G7 non è PASSED" | ✅ vero — modalità RESEARCH/PAPER autorizzate, live bloccato |

## 6. Cosa NON è stato risolto

- Completezza del lineage e uniformità dello schema coverage (BL-307).
- G5/M31 resta sotto soglia nonostante pinning e re-run riproducibile (BL-023).
- G6 necessita un run indipendente che produca trade e P&L reali (BL-024).
- `OrderManager` ammette ancora il percorso `risk_manager=None` (BL-040).
- Ensemble edge e cross-asset factor timing restano aperti (BL-201/202).

## 7. Prossimo lavoro eseguibile (single source of truth: BACKLOG.md)

Vedi `BACKLOG.md` per le task atomiche. Sommario:

1. **P1**: BL-307 — audit e ripristino lineage/coverage del data lake
2. **P1**: BL-023 — portare M31 sopra le soglie G5
3. **P1**: BL-024 — G6 100-session re-run con trade e P&L reali
4. **P1**: BL-201 — ensemble multi-segnale v2
5. **P2**: BL-040 — rendere obbligatorio il RiskManager
6. **P2**: BL-092/202 — factor timing cross-asset
7. **P3**: G7 readiness dopo G5 e G6 verdi

## 8. Decisioni chiave recenti (link agli ADR)

- **ADR-008** modular monolith + authority boundaries → ACCEPTED 2026-07-18
- **ADR-009** data/state storage → ACCEPTED 2026-07-18 (PostgreSQL SoT)
- **ADR-010** execution safety boundary → ACCEPTED
- **ADR-011** backtest discovery vs qualification → ACCEPTED
- **ADR-012** capability gate al posto delle Phase → ACCEPTED
- **ADR-013** versioned prop-firm rule catalog → ACCEPTED
- **ADR-014** M31 evidence loss → ACCEPTED 2026-07-23 (G5 REGRESSED)

## 9. Link di lettura

- [`ROADMAP.md`](../ROADMAP.md) — vision, gate G0-G9, principi
- [`BACKLOG.md`](../BACKLOG.md) — task atomiche eseguibili (BL-NNN)
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — architettura corrente e target
- [`docs/AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) — audit secco 2026-07-25
- [`docs/RUNBOOK.md`](RUNBOOK.md) — operatività
- [`docs/ADR/`](ADR/) — decisioni normative immutabili

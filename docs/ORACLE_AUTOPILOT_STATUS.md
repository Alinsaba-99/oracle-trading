# Oracle Autopilot — Execution Status

> Checkpoint operativo. Aggiornato: 2026-08-18 (allineamento post-Opzione C;
> baseline test fresca).
> La gerarchia documentale è: ROADMAP (perché) → STATUS (cosa) → BACKLOG
> (come) → ADR (decisioni) → report (evidenza). Solo STATUS riporta la
> matrice gate/stato.

## 1. Identità del checkpoint

- **Branch**: `main`
- **HEAD**: `d645a3d` (chore(docs): riorganizzazione piani in docs/plans/)
- **Working tree**: modificato — work-in-progress 2026-08-15→18 non ancora
  committato: pivot Opzione C (ADR-017..020, Lane A/B/D results, AI swarm,
  paper orchestrator, IBKR backfill, knowledge base 13 domini, ~80 file nuovi)
- **Modalità autorizzata**: RESEARCH, REPLAY, PAPER
- **PAPER, SHADOW, EVALUATION, FUNDED**: PAPER parziale (gate rejected). SHADOW/EVALUATION/FUNDED: DISABLED

## 2. Baseline verificata (2026-08-18)

| Comando | Esito |
|---|---|
| `pytest tests/` | **✅ 2903 passed**, 7 skipped, 0 failed (3 regressioni 2026-08-18 fissate: pin lake runner 6533/13973 righe, golden MFFU allineato a BL-095) |
| Lake coverage (`coverage.json`) | ✅ 497 serie / ~101 simboli / ~344M righe; refresh perpetuo systemd attivo (ultimo run 2026-08-18 07:13 UTC) |
| IBKR backfill timer | ⚠️ NON installato — `systemd/oracle-ibkr-backfill.timer` è nel repo ma non in `~/.config/systemd/user/` (vedi §4.1) |
| Live-readiness gaps | ✅ 3/3 chiusi il 2026-08-10 (vedi §5) |

> Storico: il run 2026-08-10 contava 2697 passed; il run fresco 2026-08-18
> (post Opzione C: +108 test Lane A/B/D + orchestrator + DSR + finestre
> pipeline) conta 2903 passed.

## 3. Gate status (unica tabella gate/stato autoritativa)

| Gate | Stato | Evidenza | Limite noto |
|---|---|---|---|
| G0 baseline | ✅ PASSED | ruff/mypy verdi, uv.lock, CI, secret scan, warning budget | budget warning CI = 350; run locale corrente = 42 |
| G1 autorità/ambienti | ✅ PASSED | mode guard, startup fail-closed, credential isolation, CLI guard | `OrderManager` ammette risk=None in path script untracked (BL-040) |
| G2 contract data | 🟡 PARTIAL | ContractSpec, CME calendars, roll, PIT detection; BL-301 lake operativo; BL-307 lineage/coverage completo (68.975 partizioni tracciate, 0 dangling) | BL-306: Polygon per equities 1m (opzionale) |
| G3 ledger/OMS | ✅ PASSED | PostgreSQL path attivo 25-lug; RecoveryService + ReconciliationWorker + idempotency; restart senza perdita/dup | persistenza Postgres solo in `--storage=postgres` |
| G4 hard risk | ✅ PASSED | RiskManager, FirmProgramProfile, 35 property test, bypass audit | adapter PropFirm cablato in CLI ma **escluso dal paper harness** (BL-070 risolto) |
| **G5 research truth** | ❌ **REJECTED** | run ufficiale ADR-016 (Fase 5, 48 obs): median Sharpe **-0.251** < 0.5, worst DD 3.98% ✅, **0 hard breach** ✅, luck p=1.0 → nessun edge statistico. Report canonico `m31-rerun-final` (ensemble v2, N onesto): median Sharpe **-2.51**, 0 breach, ma N=8 < 48 ⚠️. 0/9 multi-asset vs buy&hold, 8/8 candidati REJECTED | nessun edge sfruttabile oggi (S0.1/S0.2) |
| G6 paper | 🟡 **REJECTED** | M32a originale 23/30; post-fix 30/30 ma con 0 trade, 0 P&L e Sharpe 0 | manca un run qualificante trade-producing; BL-024 aperto |
| G6-I feedback loop | 🟡 PARTIAL | Factor Timing v1 (26 test), Lorentzian causal-fix (6 test), Regime Ensemble (14 test) | nessun gate end-to-end; Lorentzian mai trigger dominante |
| G7 programm prop-firm | ⚪ NOT_STARTED | dipende da G5+G6+poli cert | block su G5/G6 |
| G8 funded limited | ⚪ NOT_STARTED | | |
| G9 continuous ops | ⚪ NOT_STARTED | | |

> **Nota G5 (aggiornamento S0)**: il verdetto non è più solo "sotto soglia".
> L'autopsia BL-093 e il modello economico BL-094 hanno stabilito che
> **l'alpha misurato è ≈0 netto costi** (beta scambiato per alpha) e che la
> lane daily è **economicamente morta** (€3K/mese richiedono 5-16× il soffitto
> misurato). Prima di G5/G6 serve un cambio di canale (multi-asset, sweep
> candidati, orizzonte >1d), non tuning. Dettagli in §6.

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

### 3.3 Opzione C — stato lane (verifiche 2026-08-15→18)

> Pivot formalizzato in [ROADMAP §13](../ROADMAP.md) + ADR-020. Il blocco
> era l'edge, non l'architettura: 3 lane validate su dati 100% free prima di
> spendere budget. Prima di promozione paper→shadow→eval→funded ogni lane
> deve superare DSR/PBO/CPCV (ADR-017).

| Lane | Verdetto | Evidenza |
|---|---|---|
| **B — Composite value (Piotroski 40% + Greenblatt 40% + Lakonishok 20%, thr 0.65)** | 🟢 **EDGE REALE** — Sharpe 0.93, annual +19.2%, MaxDD 24.7%, alpha +59% vs SPY (185 ticker SimFin, 23 rebalance, 2020→2025). Default `use_composite=True` | `docs/reports/lane-b-composite/2026-08-17-compare.md`; BL-505d aggressivo (stop 5% + vol tgt 40%): Sharpe 1.49; ADR-019: Lane B prioritaria come personal portfolio |
| **D — VRP (variance risk premium)** | 🔴 **NO EDGE** — Sharpe -0.08 su SPY+VIX 2010-2025 reale (vs claim deep-research 7.36 = 95× inflated, stesso bug R5 BL-503). 69/798 tail events abbattono premium. Non deployable senza regime filter + tail cap | `docs/reports/lane-d-vrp/2026-08-17-spy-vix-2010-2025.md` |
| **AI swarm storico** | 🟡 **EDGE CONDIZIONALE** — REDUCE_SIZE 66.7% beat SPY su 2020-2021 (bull bias); Haiku synthesis ~30% vuote. Serve validazione 2022 bear | `docs/reports/ai-swarm/historical-2020-01-01-50tickers.md` |
| Paper orchestrator | 🟡 MVP — `execution/paper_orchestrator.py` (signal→order→fill, slippage ledger, 14 test); manca real-time loop + adapter Lane B/D | BACKLOG BL-OPC-7 |
| IBKR backfill 1m | 🟡 MVP funzionante (SPY/QQQ/AAPL/MSFT, 1m, window 1 mese, going forward) ma **timer systemd NON installato**; futures bloccati su expiry resolution | BACKLOG BL-OPC-6 |

**Infrastruttura abilitante (2026-08-15→18, tutta nel working tree non committato):**
- SimFin loader + cache (557 MB `data/simfin/`, gitignored) + `analytics/fundamental/simfin_loader.py`
- `analytics/qualification/dsr.py` (DSR/PBO, base ADR-017)
- `analytics/ai_analysts/` (5 analysts + Synthesizer + Skeptic + Risk Manager; LLM via OmniRoute 127.0.0.1:20128)
- `market/ingestion/sources.py`: BinanceVisionHistorical + IBKRHistorical paper quirks
- Pipeline `_month_windows` (fetch a finestre mensili resilienti, BL-104)
- FRED vintage PIT (live-readiness gap #1), pessimistic-fill (gap #3)
- Knowledge base 13 domini (68 file, 112 BL-KB items) in `docs/knowledge-base/`
- Dystopian stress, trial ledger + alerts, edge ensemble v2, CTA, value catalog

## 4. Chiusura S0 (piano production-grade, commit `3bdef58`)

| BL | Esito | Evidenza |
|---|---|---|
| BL-093 (S0.1) | ✅ autopsia BL-023 | `docs/reports/s0-1-bl023-autopsy.md` — benchmark = causa principale (beta misurato come alpha); orizzonte incompatibile col canale; 2 difetti registrati |
| BL-094 (S0.2) | ✅ modello economico | `docs/reports/s0-2-economic-model.md` + `eval_economics.json` — lane daily economicamente morta; requisiti pre-registrati riapertura S1.1 |
| BL-096 (S0.3) | ✅ metadata lake | `pipeline._actual_rows()` + audit `--fix`; 203/488 record corretti, re-audit exit 0 |
| BL-023 Fase 1-5c | ✅ chiuso REJECTED | N onesto ADR-016 §6 (17 curve); sweep 8 candidati nel gate (8/8 REJECTED); multi-asset walk-forward 0/9 vs buy&hold |

## 5. Live-readiness gaps (3/3 chiusi 2026-08-10)

| Gap | Verdetto | Fix |
|---|---|---|
| #1 FRED lookahead | **RISOLTO** | `fetch_series`/`fetch_multiple` accettano `vintage=` → `vintage_dates` (ALFRED PIT). Senza vintage non è PIT (solo live). Test dedicati |
| #2 cvxpy morto | **KEEP documentato** | transitiva obbligatoria di `pyportfolioopt` (pyproject:37); rimuoverla romperebbe la lane-A sizing prevista in S1.2 del piano profittevole |
| #3 pessimistic-fill | **RISOLTO** | `paper_limit_penetration_ticks` + `paper_tick_size`: limit/stop si riempiono solo se il mercato sfonda il trigger di N tick. Default 0 = legacy |

Report: `docs/reports/live-readiness-gap-analysis.md` (status aggiornato in §2.2-2.4).

## 6. Stato reale vs dichiarato

| Affermazione | Verificato |
|---|---|
| "M31 APPROVED per historical replay" | ❌ falso — dataset pinned e run riproducibile, ma G5 è REJECTED (Sharpe -0.251, luck p=1.0) |
| "G3 Postgres path attivo" | ✅ vero (commit ffe91b4) |
| "G6-WP2 PASSED 20/20" | ✅ vero **solo per il primo diagnostic M32** (DD 0.21%). M32a paper 23/30 = REJECTED |
| "Regime-ensemble routing OK" | ✅ ribilanciamento e hysteresys implementati; manca ancora evidenza G6 con trade reali |
| "Lorentzian causal fix" | ✅ test verdi, ma Lorentzian mai trigger dominante nel paper run |
| "Edge mean-reversion daily ES" | ❌ falso — S0.1: era beta scambiato per alpha; mean-reversion ES daily archiviata (4/4, luck p=1.0) |
| "Live disabilitato finché G7 non è PASSED" | ✅ vero — modalità RESEARCH/PAPER autorizzate, live bloccato |

## 7. Cosa NON è stato risolto

- **G5**: nessun edge futures/daily sfruttabile. Il problema non è la soglia
  ma l'edge stesso: alpha residuo trend +2-6% lordo → ~0 netto costi
  (BL-093/BL-094). L'edge ora esiste su un altro canale: Lane B composite
  (Sharpe 0.93) — ma **non è ancora qualificato** DSR/PBO/CPCV (ADR-017).
- **G6**: necessita un run indipendente che produca trade e P&L reali (BL-024).
- **Lane daily**: economicamente morta per il canale prop-firm (S0.2). La via
  aperta è il cambio di canale (orizzonti >1d, multi-asset, sweep candidati).
- `OrderManager` ammette ancora il percorso `risk_manager=None` (BL-040).
- **Working tree non committato**: tutto il lavoro 2026-08-15→18 (Opzione C,
  ADR-017..020, Lane A/B/D, AI swarm, knowledge base, ~80 file nuovi) non è
  in git. Ripristino = commit strutturati (vedi §8 punto 0).
- **IBKR cron non attivo**: il timer systemd del backfill 1m non è installato
  → dal 2026-08-17 nessun nuovo dato 1m sta entrando nel lake.
- **BL-095 residuo**: fixture MFFU aggiornate, ma restano stale
  `scripts/simulate_mff_challenge.py` e `data/prop_firm/topstep_tc_50k.json`.

## 8. Prossimo lavoro eseguibile (single source of truth: BACKLOG.md)

Vedi `BACKLOG.md` per le task atomiche. Ordine proposto (allineato 2026-08-18):

0. **Hygiene**: commit strutturati del working tree (prima il resto, poi il
   lavoro nuovo) — il progetto non è riproducibile finché il pivot Opzione C
   non è in git
1. **BL-OPC-6 chiusura**: installare `systemd/oracle-ibkr-backfill.timer` +
   futures expiry resolution
2. **P1**: BL-201 — ensemble multi-segnale v2 (o in alternativa qualificazione
   DSR/PBO della Lane B composite, prerequisito per qualunque promozione)
3. **P1**: BL-024 — G6 re-run qualificante con trade e P&L reali
4. **P2**: BL-OPC-7 — paper orchestrator real-time loop + adapter Lane B/D
5. **P2**: BL-040 — rendere obbligatorio il RiskManager
6. **P2**: BL-095 residuo — fixture stale rimanenti (dentro S0.5)
7. **P2**: BL-052 — intraday futures dataset (requisito canali 5-30m)
8. **P3**: BL-OPC-8/9/10 — validazioni AI swarm bear, VRP regime filter,
   Lane B aggressiva combinata; G7 readiness dopo G5 e G6 verdi

## 9. Decisioni chiave recenti (link agli ADR)

- **ADR-008** modular monolith + authority boundaries → ACCEPTED 2026-07-18
- **ADR-009** data/state storage → ACCEPTED 2026-07-18 (PostgreSQL SoT)
- **ADR-010** execution safety boundary → ACCEPTED
- **ADR-011** backtest discovery vs qualification → ACCEPTED
- **ADR-012** capability gate al posto delle Phase → ACCEPTED
- **ADR-013** versioned prop-firm rule catalog → ACCEPTED
- **ADR-014** M31 evidence loss → ACCEPTED 2026-07-23 (G5 REGRESSED)
- **ADR-015** Topstep automation policy → ACCEPTED
- **ADR-016** G5 re-spec: stop ATR 1.0, qty 1, N onesto → ACCEPTED (anti-beta benchmark)
- **ADR-017** backtest overfitting validation upgrade (DSR/PBO/CPCV gate) → working tree
- **ADR-018** prop-firm structural EV deployment gate → working tree
- **ADR-019** Lane B priority personal portfolio → working tree
- **ADR-020** zero-cost data strategy (fonti free verificate) → ACCEPTED 2026-08-17

## 10. Link di lettura

- [`ROADMAP.md`](../ROADMAP.md) — vision, gate G0-G14, principi, Opzione C §13
- [`BACKLOG.md`](../BACKLOG.md) — task atomiche eseguibili (BL-NNN)
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — architettura corrente e target
- [`docs/AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) — audit secco 2026-07-25
- [`docs/RUNBOOK.md`](RUNBOOK.md) — operatività
- [`docs/ADR/`](ADR/) — decisioni normative immutabili
- [`docs/plan-production-grade.md`](plan-production-grade.md) — piano S0-S6
- [`docs/plan-profitable-system.md`](plan-profitable-system.md) — multi-lane (A/B/C)
- [`docs/knowledge-base/`](knowledge-base/) — 13 domini di studio + 112 BL-KB items
- [`docs/reports/live-readiness-gap-analysis.md`](reports/live-readiness-gap-analysis.md) — 3 gap chiusi

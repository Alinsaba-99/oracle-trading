# Oracle Autopilot — Execution Status

> Checkpoint operativo. Aggiornato: 2026-08-21 (working tree committato;
> BL-OPC-11/12/6, BL-040, BL-095, BL-060, BL-616, BL-024/BL-201 eseguiti
> con verdetto REJECTED; BL-615 in corso; baseline test fresca).
> La gerarchia documentale è: ROADMAP (perché) → STATUS (cosa) → BACKLOG
> (come) → ADR (decisioni) → report (evidenza). Solo STATUS riporta la
> matrice gate/stato.

## 1. Identità del checkpoint

- **Branch**: `feat/p1-metrics-truth` (main = `b1f0ac7`; merge P1-A +
  BL-OPC quando si chiude la fase)
- **HEAD**: `c1d397a` (feat(BL-616): suite integration catena ordini) +
  working tree con BL-615 in corso (`apps/cli/paper_commands.py`,
  comando `oracle paper run --spec`)
- **Working tree**: ✅ il pivot Opzione C è interamente in git
  (BL-OPC-11 chiuso: commit `e5ef5b6`→`1fe33fd`, suite verde, gitleaks
  su hook pre-commit); 11 commit il 2026-08-21
- **Modalità autorizzata**: RESEARCH, REPLAY, PAPER
- **PAPER, SHADOW, EVALUATION, FUNDED**: PAPER parziale (gate rejected). SHADOW/EVALUATION/FUNDED: DISABLED

## 2. Baseline verificata (2026-08-21)

| Comando | Esito |
|---|---|
| `pytest tests/` | **✅ 3089 passed**, 7 skipped, 0 failed (run completo 2026-08-22, 6m32s; +54 test sessione 2026-08-22: BL-711 tearsheet 3, BL-701/702 corpus 18, BL-706 IC screen 7, BL-707 haircut 8, BL-721 fixtures 18) |
| Smoke runner canonico | ✅ `oracle paper run --spec` end-to-end: 3 sessioni edge_v2, manifest con sha256 dati/spec/git-commit (`logs/paper_canonical/bl615-smoke.*`) |
| Lake coverage (`coverage.json`) | ✅ refresh perpetuo systemd attivo (07:00); IBKR 1m cron ora installato (vedi sotto) |
| IBKR backfill timer | ✅ installato e enabled 2026-08-21 (`~/.config/systemd/user/oracle-ibkr-backfill.timer`, run 18:00 UTC); futures ES/NQ/GC/CL via CONTFUT + equities, 1 run verificato exit 0 |
| Live-readiness gaps | ✅ 3/3 chiusi il 2026-08-10 (vedi §5) |

> Storico: il run 2026-08-18 contava 2903 passed; il run 2026-08-21
> contava 2989 passed (post BL-616); il run corrente 3019 passed.

## 3. Gate status (unica tabella gate/stato autoritativa)

| Gate | Stato | Evidenza | Limite noto |
|---|---|---|---|
| G0 baseline | ✅ PASSED | ruff/mypy verdi, uv.lock, CI, secret scan, warning budget | budget warning CI = 350; run locale corrente = 42 |
| G1 autorità/ambienti | ✅ PASSED | mode guard, startup fail-closed, credential isolation, CLI guard | `OrderManager` ammette risk=None in path script untracked (BL-040) |
| G2 contract data | 🟡 PARTIAL | ContractSpec, CME calendars, roll, PIT detection; BL-301 lake operativo; BL-307 lineage/coverage completo (68.975 partizioni tracciate, 0 dangling) | BL-306: Polygon per equities 1m (opzionale) |
| G3 ledger/OMS | ✅ PASSED | PostgreSQL path attivo 25-lug; RecoveryService + ReconciliationWorker + idempotency; restart senza perdita/dup | persistenza Postgres solo in `--storage=postgres` |
| G4 hard risk | ✅ PASSED | RiskManager, FirmProgramProfile, 35 property test, bypass audit | adapter PropFirm cablato in CLI ma **escluso dal paper harness** (BL-070 risolto) |
| **G5 research truth** | ❌ **REJECTED** | run ufficiale ADR-016 (Fase 5, 48 obs): median Sharpe **-0.251** < 0.5, worst DD 3.98% ✅, **0 hard breach** ✅, luck p=1.0 → nessun edge statistico. Report canonico `m31-rerun-final` (ensemble v2, N onesto): median Sharpe **-2.51**, 0 breach, ma N=8 < 48 ⚠️. 0/9 multi-asset vs buy&hold, 8/8 candidati REJECTED | nessun edge sfruttabile oggi (S0.1/S0.2) |
| G6 paper | 🟡 **REJECTED** | BL-024 2026-08-21: 100 sessioni EdgeEnsembleV2, **390 trade reali**, P&L agg +$16.273, reconcile 100% — ma pass rate **0.35** < 0.90 e mean DD **5.53%** > 3% | il failure mode "0 trade" è chiuso; manca l'edge che passi i criteri |
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
| **B — Composite value (Piotroski 40% + Greenblatt 40% + Lakonishok 20%, thr 0.65)** | 🟢 **QUALIFICATO (BL-727)** — Preregistrazione BL-726 con stop-loss 5% su SimFin 2020→2025: Sharpe 1.43, Annual Return +19.7%, Total Return +115.6%, MaxDD 11.73%, DSR 0.999 ✅, PSR 0.999 ✅, CPCV OOS median 1.46 ✅, Haircut Sharpe 0.67 ✅, Bear 2022 Sharpe 1.21 ✅. Adapter `LaneBSignalAdapter` pronto (BL-728). Promozione paper sbloccata verso `oracle-paper` | `docs/reports/lane-b-composite/2026-09-03-bl726-qualification.md` |
| **D — VRP (variance risk premium)** | 🔴 **NO EDGE** — Sharpe -0.08 su SPY+VIX 2010-2025 reale (vs claim deep-research 7.36 = 95× inflated, stesso bug R5 BL-503). 69/798 tail events abbattono premium. Non deployable senza regime filter + tail cap | `docs/reports/lane-d-vrp/2026-08-17-spy-vix-2010-2025.md` |
| **AI swarm storico** | 🟡 **EDGE CONDIZIONALE** — REDUCE_SIZE 66.7% beat SPY su 2020-2021 (bull bias); Haiku synthesis ~30% vuote. Serve validazione 2022 bear | `docs/reports/ai-swarm/historical-2020-01-01-50tickers.md` |
| Paper orchestrator | 🟡 MVP — `execution/paper_orchestrator.py` (signal→order→fill, slippage ledger, 14 test); manca real-time loop + adapter Lane B/D | BACKLOG BL-OPC-7 |
| IBKR backfill 1m | ✅ **OPERATIVO** (2026-08-21, BL-OPC-6 chiuso): timer systemd installato, futures ES/NQ/GC/CL via CONTFUT + equities SPY/QQQ/AAPL/MSFT, 1m going forward; readonly connect; nota: `docker start ib-gateway` dopo reboot | commit `c1e41dc` |

**Infrastruttura abilitante (2026-08-15→21, ora interamente in git — BL-OPC-11 chiuso):**
- SimFin loader + cache (557 MB `data/simfin/`, gitignored) + `analytics/fundamental/simfin_loader.py`
- `analytics/qualification/dsr.py` (DSR/PBO, base ADR-017)
- `analytics/ai_analysts/` (5 analysts + Synthesizer + Skeptic + Risk Manager; LLM via OmniRoute 127.0.0.1:20128)
- `market/ingestion/sources.py`: BinanceVisionHistorical + IBKRHistorical paper quirks
- Pipeline `_month_windows` (fetch a finestre mensili resilienti, BL-104)
- FRED vintage PIT (live-readiness gap #1), pessimistic-fill (gap #3)
- Knowledge base 13 domini (68 file, 112 BL-KB items) in `docs/knowledge-base/`
- Dystopian stress, trial ledger + alerts, edge ensemble v2, CTA, value catalog

### 3.4 Edge Research Factory — Stage 1 popolato + strumenti qualifica (2026-08-22)

| Componente | Stato | Evidenza |
|---|---|---|
| Registry (BL-700/701/702) | ✅ 46 ipotesi (39 KB + 7 practitioner MoonDev) in 14 YAML `docs/knowledge-base/edge-factory/registry/`; builder deterministico `scripts/build_edge_factory_registry.py` (regen = diff review, vedi nota) | commits b03d943, e95cf6c, f321047 |
| IC screen (BL-706) | ✅ `analytics/research/factory/ic_screen.py` — Spearman non-overlapping + block bootstrap, ICIR>0.05/t>2.5 pre-registrati, haircut 30%, direzione fissata (no sign-flip) | commit 68b5126 |
| Haircut Sharpe (BL-707) | ✅ `analytics/research/factory/haircut_sharpe.py` — PSR + offset DSR, riusa canonical ADR-021 | commits 95c938b, b2b687c |
| Tearsheet (BL-711) | ✅ quantstats 0.0.81 (Apache-2.0) + ffn 1.1.5 (MIT), diagnostico-only | commit 45745e5 |
| Fixture prop-firm (BL-721) | 🟡 prima tranche: FTMO/The5ers/Alpha/E8 da snapshot sha256 2026-08-22; +DailyLossAction(PAUSE/TERMINATE), TRAILING_CLOSED, anti-HFT flag; enforcement = BL-722 | commit b143d87 |

> Nota regole: le ipotesi 03-quant DSR/HLZ sono GATE (metodo), non alpha —
> non entrano nell'IC screen come candidati. Gap noti: VPIN/OFI L2 con
> dati_posseduti=false (aggTrades da ingettare, $0); FundedNext/Alpha-6-10/
> E8-numeri → seconda passata BL-720.

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

- **G5**: nessun edge futures/daily sfruttabile (BL-093/BL-094). La Lane B
  composite (Sharpe 0.93) è stata qualificata ADR-017 il 2026-08-20:
  **REJECTED** (PBO 0.635 ≥ 0.5; bear 2022 Sharpe 0.05 = edge bull-only).
  L'edge esiste nel campione ma non è qualificabile così com'è: la prossima
  via è preregistrata (variante unica senza selection post-hoc, oppure
  pivot crypto factors). **BL-OPC-7 resta bloccato.**
- **G6**: BL-024 eseguito 2026-08-21 — 100 sessioni EdgeEnsembleV2 con
  390 trade reali nella catena paper completa (il failure mode "0 trade"
  è chiuso per sempre), ma il gate resta REJECTED: pass rate 0.35 < 0.90,
  mean max DD 5.53% > 3%. Report `docs/reports/g6-wp2-final/bl024-edgev2-2026-08-21.md`.
- **Lane daily**: economicamente morta per il canale prop-firm (S0.2). La via
  aperta è il cambio di canale (orizzonti >1d, multi-asset, sweep candidati).
- **BL-606**: rotazione credenziali METAAPI_TOKEN + LLM_KEY (richiede accesso
  umano ai provider — non eseguibile da script).
- **BL-607**: history rewrite dei blob pesanti (opzionale, distruttivo,
  differito).
- **P1-B**: BL-616 chiuso (suite integration catena ordini, 16 scenari con
  guasti iniettati). BL-615 in corso: runner canonico
  `oracle paper run --spec` operativo con manifest riproducibile; restano
  migrazione dei runner legacy e spec di riferimento.
- **P1-C/D** (BL-617..619): split sources.py, structlog hot path, PIT
  domain type — aperti.

## 8. Prossimo lavoro eseguibile (single source of truth: BACKLOG.md)

Vedi `BACKLOG.md` per le task atomiche. Ordine proposto (allineato 2026-08-21):

0. ✅ **Hygiene**: working tree committato (BL-OPC-11 chiuso 2026-08-21)
1. ✅ **BL-OPC-6 chiusura**: timer IBKR installato + futures CONTFUT (2026-08-21)
2. ✅ **BL-OPC-12**: qualificazione DSR/PBO Lane B eseguita — REJECTED (2026-08-20)
3. **P1**: decisione preregistrata — (a) variante unica Lane B senza selection
   post-hoc + ri-qualificazione ADR-017, oppure (b) pivot crypto factors;
   senza APPROVED, BL-OPC-7 (paper real-time) resta bloccato
4. **P1**: BL-024 — G6 re-run qualificante con trade e P&L reali
5. **P1**: BL-201 — ensemble multi-segnale v2
6. **P1**: BL-615/616 — runner paper canonico + suite integration ordini
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

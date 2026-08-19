# Oracle — Execution Backlog

> Single source of truth per task atomiche. Versione: 2026-08-18 (allineamento
> post-Opzione C). Sostituisce
> `docs/ORACLE_AUTOPILOT_BACKLOG.md` (rimosso il 25-lug) e
> `docs/plans/oracle-autopilot-*-backlog-*.md`.
>
> Ogni task ha un ID stabile **BL-NNN**, una priorità, owner suggerito, AC
> (acceptance criteria) e link al gate di appartenenza. Le task che
> riguardano un singolo gate sono nel blocco del gate; le task trasversali
> in fondo.

## Regole

### Stati

- `[ ]` non iniziata
- `[~]` in corso
- `[x]` completata e verificata
- `[!]` bloccata con blocker documentato
- `[-]` rimossa con ADR

### Definition of Done (DoD)

1. Codice, test, docs aggiunti al repository
2. `pytest`, `ruff check`, `ruff format --check`, `mypy --strict` (sui path toccati) verdi
3. Nessun segreto introdotto (gitleaks verde)
4. Evidenza in `logs/` o in un report in `docs/reports/`
5. Se modifica API/contratto: ADR o riferimento ad ADR esistente
6. Stato aggiornato in `BACKLOG.md` stesso (qui)

### Priorità

- **P1** = blocca uno dei gate attivi (G5, G6)
- **P2** = abilita una capability nuova ma non blocca
- **P3** = nice-to-have, evoluzione futura

## G0 Baseline Veritiera

- [x] G0-001..010 — ruff/mypy/uv.lock/CI/secret scan/.dockerignore (commit `a5ef2dc`, `f87726f`)
- [x] **BL-001** P1 — **Pin ES_1d in `data/pinned/`** + hash in provenance. ✅ completato in `6bbbb70`: file `data/pinned/ES_1d_m31.parquet` con sha256 = `09a22…`; provenance JSON adiacente.
- [x] **BL-002** P1 — **Anti-overwrite guard su `yfinance_futures`**. ✅ completato in `6bbbb70`: `DataFetcher.yfinance_futures` rifiuta sovrascrittura con bypass `allow_overwrite=True`. Test: `tests/unit/test_data_sources_pinning.py` (2 test, verdi).
- [x] **BL-003** P1 — **Test pinning**: ✅ completato in `6bbbb70`: `scripts/check_dataset_pin.py` — exit 0 se match, exit 1 altrimenti.
- [x] **BL-031** P2 — Warning budget CI bloccante. ✅ completato in `658d9ce`/`f514486`.
- [x] **BL-032** P2 — `pyproject.toml` script untrack warning. ✅ completato.

## G1 Autorità/ambienti

- [x] G1-001..008 — OracleMode, startup guard, cred isolation, API auth, CLI guard, contratti
- [ ] **BL-040** P2 — `OrderManager` rifiuta `risk_manager=None` (lancia `RiskRequired`). AC: rimosso path `OrderManager(broker, risk_manager=None)` da tutti gli script untracked; test in `tests/unit/test_order_manager.py::test_no_risk_manager_raises`. ~1h.

## G2 Verità futures e point-in-time

- [x] G2-001..015 — ContractSpec, calendars, roll, PIT detection (eccetto 019/021/022/023/024)
- [ ] **BL-050** P3 — Catalogo ZN/ZB, 6E/M6E. ~3h.
- [ ] **BL-051** P3 — Roll cost model nei backtest. ~6h.
- [ ] **BL-052** P2 — Intraday futures dataset (Polygon key quando disponibile). ~1gg.

## G3 Ledger/OMS durevoli

- [x] G3-001..012 — In-memory ledger/OMS, reconciliation startup, chaos, PG schema
- [x] G3-005..010 — Postgres path attivo 25-lug (commit `ffe91b4`)
- [x] G3-013 PG ledger production ✅
- [x] G3-014 Periodic reconcile ✅
- [~] G3-017 Recovery idempotency dopo restart (in progress; merge commit ffe91b4)
- [ ] **BL-060** P2 — CLI default `--storage=postgres` quando DATABASE_URL presente in .env. AC: `--storage` flag opzionale, default = `postgres` se DSN env altrimenti `memory` con warning. ~30min.

## G4 Hard risk non bypassabile

- [x] G4-001..015 — FirmProgramProfile, SupportMode, RiskManager, property test, bypass audit
- [x] G4-021 — PropFirmOrderRiskAdapter cablato in CLI ✅
- [x] **BL-070** P1 — **Cablaggio PropFirmOrderRiskAdapter in paper sessions**. ✅ `_PropFirmAllow` già wired in `run_g6_wp2_paper_sessions.py` (commit `b4058e5`). Test di integrazione in `tests/integration/test_paper_session_risk.py` (9 test, tutti verdi). **[Paper è prop-firm compliant]**
- [ ] **BL-071** P2 — Automation policy dettaglio per Topstep ToS (vietato VPS/VPN/residential bot). AC: ADR-015 (da scrivere) che documenta la posizione. ~2h.

## G5 Research truth

- [x] G5-001..013 vecchi → **invalidati** da ADR-014
- [x] **BL-010** P1 — **Regime detector hysteresys** ✅ completato in `275dd6d`: `_apply_hysteresis` esposto via RoutingDecision; stesso regime → stesso specialist.
- [x] **BL-011** P1 — **Ricalibrare soglie `_sma_regime_heuristic`** ✅ completato in `275dd6d`: vol ratio 1.6→1.4; trend dual (SMA20/50 short + SMA50/100 long); threshold 0.025; choppy ridotto da ~96% a ~50%.
- [x] **BL-012** P1 — **Hurst/variance ratio detector** ✅ completato in `275dd6d`: trend-following detector integrato nel branch BULL/BEAR.
- [x] **BL-013** P1 — **`min_bars_for_confidence`** ✅ completato in `275dd6d`: confidence scaling con bar count ≥ 120.
- [x] **BL-014** P1 — **Lorentzian-first routing** ✅ completato in `275dd6d`: SE Lorentzian signal > 0, routing Lorentzian prima dei备選 standard.
- [x] **BL-023** P2 — **M31 re-run con codice post-beta fix** (ex BL-022, rinumerato per evitare conflitto con G6-WP2). AC: report `docs/reports/m31-rerun/m31.md` con 6 regimi × 8 varianti = 48 slice, 0 hard breach, parity broker/ledger, dataset hash riportato in header. **Nota**: tentativo in `18a6836` — REJECTED (median Sharpe 0.34 vs 0.5; worst DD 15.9% vs 4%; 88 hard breaches). **Fase 5 completata 2026-08-04**: audit prerequisiti OK (`/home/alin/docs/f5-audit-prerequisiti.md`), pin lake aggiornato 6522→6523 (lake live), re-run ufficiale ADR-016 eseguito (`scripts/run_replay_qualification.py --data-source lake --symbol ES --timeframe 1d --window-bars 1000 --warmup-bars 200 --stop-mode atr --atr-multiple 1.0 --atr-period 14 --require-pass`). **Esito: REJECTED documentato** — 6/6 regimi, 8/8 varianti, 48 osservazioni, **0 hard breach, worst DD 3.98% ≤ 4%** (risk loop riparato regge), ma median Sharpe -0.251 vs ≥0.5, median return -1.22%, luck p-value 1.0 → nessun edge statistico. Il segnale perde in 5/6 regimi (unico positivo: liquidity_shock +0.36%). Gap dichiarato: N onesto = 6 (1 finestra/regime), non 18 (top-3 ADR-016 §6 non implementato); 8 varianti economicamente identiche (artefatti offline). **Verdetto onesto chiude la Fase 5 → prossima decisione strategica** (candidati segnale probe→gate reale, multi-asset walk-forward).
- [x] **BL-023 Fase 5b (N onesto ADR-016 §6)** — implementato `windows_per_regime=3` in `select_replay_periods` (top-3 finestre non sovrapposte per regime) + flag `--signal` nel runner ufficiale per qualificare i candidati del probe (`scripts/run_m31_candidate_sweep.sh`). Rilancio M31 con N onesto 2026-08-04: **REJECTED più severo** — 17 curve uniche (5 regimi × 3 + 2 macro; il regime macro concede 2 finestre indipendenti con window 1000 bar: 13 eventi clusterizzati 2008-09/2019-10, limite dichiarato nel report), 8/8 varianti, **worst DD 5.63% > 4%** (ora viola il tetto), median Sharpe -0.31, median return -1.52%, pooled luck p=1.0 → nessun edge. L'N onesto (17 vs 6) ha mostrato una ricetta ancora peggiore di quanto sembrava: più evidenza, stesso verdetto.
- [x] **BL-023 Fase 5c (sweep candidati nel gate reale)** — 8 candidati del probe (parametri identici a `probe_signal_candidates.py`, derivazione train-pre-2023) qualificati nel gate ADR-016 con N onesto (`docs/reports/candidates/<signal>.{json,md}`): **tutti REJECTED**. Migliori (family trend/breakout, luck p≤0.012 = edge reale ma insufficiente): donchian_breakout net +1.37% Sharpe +0.216 ma 16 hard breach e DD 4.77%>4%; trend_filtered_breakout Sharpe +0.167, 0 breach ma DD 4.81%. Family mean-reversion (bollinger/zscore/keltner/rsi): negative, Sharpe -0.47..-0.64, luck p=1.0. Nessun candidato raggiunge Sharpe ≥0.5 con DD ≤4% e 0 breach. **Bug fix collaterale**: `rsi()`/`ema()`/`atr()` crasavano con IndexError su prefissi < period+1 bar nel replay bar-by-bar → fail-soft con NaN allineato + guardia in `RsiReversion.compute` (test in `test_technical.py`). **Verdetto: nessun edge sfruttabile tra i candidati attuali → multi-asset walk-forward (Fase 2) o nuova derivazione segnali.**
- [x] **BL-023 Fase 2 (opzione B — multi-asset walk-forward)** — `scripts/run_multiasset_walkforward.py`: segnale puro (long/flat, shift(1) no-lookahead, ritorni % scale-free) su ES/SPY/BTCUSDT 1d dal lake (pin 6523/6679/3275), split train<2023 / test≥2023 (proxy walk-forward delle finestre M31), per i 3 vincitori trend di 5c (donchian_breakout, trend_filtered_breakout, ema_trend). **Verdetto: 0/9 asset×segnale confermati — NESSUN segnale batte il buy&hold** (`docs/reports/multiasset/walkforward.{json,md}`). Tutti soddisfano S_test≥0.3 e luck p<0.1 (l'edge esiste, non è rumore) MA S_test (1.03-1.33) < BH_S (1.35-1.40 ES/SPY, 0.86 BTC): Sharpe alto = **beta** (mercato rialzista), non alpha. Alpha residuo annuo solo +2.3%..+6.1%. **Conclusione: la family trend non produce alpha netto out-of-sample su 3 asset — edge reale ma puro beta; i segnali sono long-passivi imperfetti. Resta REJECTED; prossime opzioni: regime filter/exit per estrarre l'alpha residuo, o nuova derivazione segnali (mean-reversion scartata).**

## S0 Diagnosi e governance (piano production-grade, commit `3bdef58`)

- [x] **BL-093** (S0.1) — **Autopsia BL-023**: decomposizione fallimento sui 6 assi del piano. ✅ `docs/reports/s0-1-bl023-autopsy.md`. Verdetto: benchmark = causa principale (misuravamo beta come alpha; anti-beta ADR-016 ha corretto il metro), orizzonte incompatibile col canale prop-firm; dati e implementazione assolti (2 difetti registrati: candidati duplicati bollinger≡zscore = 7 ipotesi non 8; matrice 2×2×2 byte-identica = teatro). Costi = aggravante. Regime = unica via aperta, solo dopo post-mortem classificatore M32a. Mean-reversion ES daily archiviata (4/4, luck p=1.0). Alpha residuo trend +2-6% lordo = input di S0.2.
- [x] **BL-094** (S0.2) — **Modello economico prop-firm one-page** ✅ `docs/reports/s0-2-economic-model.md` + evidenza MC `docs/reports/s0-2/eval_economics.json` (`scripts/run_eval_economics.py`, seed 42, N=10K; test `tests/unit/test_eval_economics.py`). Verdetto: **€3K/mese richiede alpha ≥ 30-120%/anno su un account (o 5-20 account a α=6%): 5-16× il soffitto misurato +2-6% lordo → lane daily economicamente morta (meta-kill scattata per l'orizzonte daily)**. MC: p(pass) eval 6%/4% = 30.1% random-walk vs 33.7% a α=6% (σ=1.2%): l'alpha misurato vale +3.6 punti; la leva vera è σ (53.4% a σ=0.4%). Requisiti pre-registrati riapertura S1.1: p≥0.60, α netto ≥15%/anno, E[giorni a passare]≤60, DD≤4% ADR-016. Obiettivo sostenibile: €1-1.5K/mese con 2-3 account 150-200K (90/10). Fee P90 percorso: ~$400-1.100. **Verifica empirica aggiunta**: `scripts/run_eval_simulation.py` replaya i segnali reali sul lake con le regole eval (6%/4% trailing EOD, consistency 50%, costi $8.4/RT, 1 contratto ES/$50K) — ES 1d (N=99): donchian 26.3%, trend_filtered 30.3%, ema 26.3%, buy_hold 23.2% (CI95 max sup 40%); ES 1h (N=214): 23.4-29.9%. **Nessun candidato supera il base rate senza edge (30.1%) né si avvicina al requisito 0.60 → family trend falsificata anche nel canale prop-firm** (`docs/reports/s0-2/eval_simulation.json`, `eval_simulation_1h.json`; test `tests/unit/test_eval_simulation.py`). Nota dati: lake ha solo ~8 giorni di 1m/5m/15m futures → requisito 5-30m non testabile oggi (BL-052).
- [~] **BL-095** P2 — **Aggiornare i fixture prop-firm stale** (trovati in BL-094).
  ✅ FATTO 2026-08-15/18: `policy/prop_firm/fixtures.py` MFFU_NEWS_RESTRICTED
  allineato regole 2026 (target 6%, daily loss rimosso, consistency rimossa,
  rule_version 2026-08-15) + golden test aggiornati (2903 suite verde).
  ⏳ RESTANTE: `scripts/simulate_mff_challenge.py` (target $5.000=10% →
  $3.000=6% 2026; daily loss 5% → assente) e `data/prop_firm/topstep_tc_50k.json`
  (profit_target $5.000 → $3.000). AC: parametri allineati alle fonti 2026
  (snapshot hash), profilo rinominato con vintage. ~1h. Da fare dentro S0.5.
- [x] **BL-096** P1 — **Accuratezza metadata lake: coverage.json conteggia doppio/divergente**. ✅ Root cause: `pipeline._update_coverage` accumulava `rows += len(bars)` — ogni refresh incrementale che ri-merge barre già presenti gonfiava il contatore (ES|1d: 13.044 dichiarate vs 6.524 reali). Fix in due punti: (1) `pipeline._actual_rows()` conta dalle parquet normalizzate; (2) `scripts/audit_lake_metadata.py` ora verifica `coverage.rows` contro il conteggio reale (`coverage_row_mismatch` nel report, `--fix` riscrive i rows, exit code 1 su mismatch) + nuovo test gate `tests/unit/test_lake_metadata_audit.py::test_coverage_rows_match_actual_partitions`. **Applicato: 203/488 record corretti** (tutte le serie FX/crypto/futures gonfiate dal refresh perpetuo), re-audit pulito exit 0.

## G6 Paper & shadow operations

### G6-WP1 (M32 diagnostic) — closed

- [x] M32-001..024 done (commit `44b632f`, `ae209f7`, `d4bc85e`, `db55cc2`, `4b22347`, `98319e6`, `13e4cf3`, `44b632f`, `ec59149`)

### G6-WP2 (M32a paper sessions) — REJECTED, da rifare

- [x] **BL-020** P1 — **Ricalibrazione regime + run WP2 v2**. ✅ completato (commit `0716e1a`): vol-scaled regime heuristic (timeframe-invariant).
- [x] **BL-021** P1 — **MES-aware sizing per prop-firm**. ✅ completato in `b4058e5`. Script: `scripts/check_mes_sizing.py`.
- [x] **BL-022** P1 — **100 sessioni paper indipendenti**. ✅ completato (commit `3227804`): 100 session × 95-bar windows, pinned dataset, Monte Carlo opzione, gate criteria.
- [ ] **BL-024** P1 — **G6 re-run qualificante con trade reali**. Il run post-fix 30/30 ha prodotto 0 trade, 0 P&L e Sharpe 0, quindi non costituisce evidenza di qualifica. AC: esecuzione indipendente con `scripts/run_g6_wp2_100_sessions.py`, almeno 10 finestre con trade, P&L aggregato > 0, Sharpe non-zero, pass rate ≥ 0.90, mean max DD ≤ 3%, reconcile clean = 100%; report versionato in `docs/reports/g6-wp2-final/`.

## Edge Portfolio (BL-200..202) — NUOVO dopo audit 25-lug

> 4 strategie battono la baseline RSI mean-rev (mc_pass=27.7%). Edge serio
> richiede **ensemble multi-segnale** e/o **cross-asset factor timing**.
> Vedi [`docs/reports/edge-portfolio/edge-portfolio.md`](docs/reports/edge-portfolio/edge-portfolio.md).

- [x] **BL-200** P1 — **Edge Portfolio Sperimentale** ✅ completato 25-lug
  Report: `docs/reports/edge-portfolio/edge-portfolio.md`. Risultato: 4
  edge > baseline: roc_momentum_12 (mc=41%, DD=3.47%), bollinger_20_2
  (mc=35.5%, DD=4.53%), bollinger_30_2.5 (mc=33%, DD=4.53%),
  donchian_breakout_10 (mc=32%, DD=3.57%).
- [ ] **BL-201** P1 — **Ensemble multi-segnale v2** (roc_momentum_12 +
  bollinger_20_2 + donchian_breakout_10) con hysteresys su
  `RegimeAwareEnsemble`. AC: nuovo script `scripts/run_edge_ensemble.py`;
  `mc_pass_rate > 0.45` su 200 sim; DD < 3% (MES sizing). Report in
  `docs/reports/edge-portfolio/ensemble.md`. ~1 sessione.
- [ ] **BL-202** P2 — **Cross-asset factor timing** (factor catalog port
  da ES a BTC/USDT, EURUSD, GC via `DataRegistry`). AC:
  `FactorTimingEngine` con `instrument` parameter, test su almeno 2
  strumenti, edge verificato per ogni strumento con `run_edge_portfolio.py
  --data <path>`. ~3gg.

### G6-WP3 (M33 shadow) — blocca su G6-WP2

- [ ] M33-001..025 da fare
- [ ] **BL-080** P2 — Shadow broker adapter (paper→broker dual feed). ~1 sprint.

## G6-I Intelligence Feedback Loop

### Phase 1 — done

- [x] I-01 Factor Timing v1 (commit `ffe91b4`); 26 test verdi
- [x] I-03b Lorentzian causal fix (commit `ffe91b4`); 6 test verdi
- [x] I-03c Regime Ensemble (commit `ffe91b4`); 14 test verdi

### Phase 2 — research memory + cross-asset factor timing

- [x] **BL-090** P2 — **Research Memory**: `analytics/research/memory.py` — store decisioni con `decision_id, timestamp, regime, confidence, outcome, features`, SQLite-backed. Hook nel decision path del `RegimeAwareEnsemble.compute()`. ✅ completato in `01b61ba`: 302 line, 17 test, integrato in `RegimeAwareEnsemble`. Next: strategy catalog (BL-400+).
- [x] **BL-091** P2 — **Hurst + variance ratio detector** — ✅ assorbito da BL-012 (completato in `275dd6d`).
- [ ] **BL-092** P2 — **Cross-asset factor timing**: port factor catalog da ES 1h a BTC/USDT, EURUSD, GC. AC: `FactorTimingEngine` con `instrument` parameter, test unit su almeno 2 strumenti. ~3gg.

### Phase 3 — evolution loop (LLM scrive strategie)

- [ ] I-04..I-06 da fare (vedi ADR originali, ma vedi anche discussione in AUDIT_FINDINGS §3.3: prima dell'edge c'è solidità del backtest; LLM-driven strategie sono premature finché i 100 sessioni paper non sono verdi)

## G7 Certificazione programma prop-firm

Non iniziato. Dipende da G5 + G6.

- [ ] **BL-100** P3 — Scegliere una singola firm e programma per G7 (candidati:
  Topstep TC 50K RESEACHED_ONLY come fallback, oppure **MyFundedFutures** che
  supporta automation esplicitamente — cfr PROP_FIRM_READINESS_ROADMAP §9).
  AC: ADR con selezione, support mode confermato, fonti fresche salvate in
  `docs/firm_sources/{firm}/`. ~1gg.

## Trasversali / cleanup

- [x] **BL-030** P2 — **Cleanup script untracked**. ✅ completato in `4ce3fb3` (quarantena in `scripts/legacy/` con README).
- [x] **BL-033** P2 — Symlink `data/ohlcv/ES_1d.parquet` → `data/pinned/ES_1d_m31.parquet` + `.gitignore` aggiornato. ✅ BL-001 già completato (pin existente); symlink opzionale per backward compat.

## BL-301 Data Lake (feat/bl-301-data-lake branch)

> Data lake multi-source zero-cost: 7 sorgenti, pipeline incrementale idempotente,
> backfill orchestrator resumable. Branch: `feat/bl-301-data-lake`.
> Vedi [`docs/BL-301-data-lake-audit-and-integration-plan.md`](docs/BL-301-data-lake-audit-and-integration-plan.md)
> per audit + piano integrazione 4 framework.

- [x] **BL-301** P1 — **Data Lake ingestion layer** (`market/ingestion/`): 7 source adapters (BinanceREST, CryptoDataDownload, DatabentoHistorical, YFinance, HistData, Stooq, Dukascopy), pipeline incrementale, quality checks, backfill orchestrator resumable. ✅ completato in `933ee32`, `6ffb540`, `a1a1ebe`.
- [x] **BL-302** P1 — **DataRegistry lake-aware**: DataRegistry integrato con il data lake per lettura multi-asset. ✅ completato in `933ee32`.
- [x] **BL-303** P1 — **Coverage tracking + lineage**: `data/lake/metadata/coverage.json` (44+ assets), `lineage.json` (tracciamento provenienza), `backfill.conf` (piano backfill prioritario). ✅ completato in `933ee32`.
- [x] **BL-304** P2 — **Perpetual backfill execution**: lanciare backfill orchestrator su tutte le configurazioni in `backfill.conf`. AC: coverage > 90% degli asset listati entro 7gg. ✅ completato 31-lug: piano live 152/152 entry (0 failed) — coverage 220 serie (65×1m, 60×1h, 73×1d, 22×4h); refresh perpetuo attivo (timer systemd 07:00 + `scripts/refresh_lake.py`); orchestrator `--incremental` (fetch solo barre mancanti da coverage.latest) + classificatore ok/fresh/failed (niente falsi failed nei weekend); fix API jetta: bucket correnti → HTTP 400, clamp ai bucket chiusi basato su *today* + filtro sul range effettivo (`_clamp_bucket_range`); piano live 152 entry raggiungibili (dukascopy+yahoo+binance; histdata/stooq/ibkr/databento bloccate e commentate — vedi `docs/DATA_SOURCES.md`). Curation 1m completa: 65 serie (aggiunti 5 cross FX: AUDNZD, NZDJPY, CHFJPY, CADJPY, CADCHF).
- [x] **BL-305** P2 — **ES 1h + EURUSD 1m + BTCUSDT 1m backfill prioritario**: asset critici per G6/G10. ✅ completato: EURUSD 1m 8.67M righe 2003→2026 (Dukascopy), BTCUSDT 1m 4.69M righe 2017→2026 (Binance), ES 1h 36.6K righe; curation 1m estesa a FX+crypto+metalli (58 serie curated, `build_curated_contracts.py` ora auto-discover + gap threshold tf-aware).
- [ ] **BL-306** P3 — **Polygon.io integration** (opzionale, $29/mo): per US equities 1m se necessario. ~2gg.
- [x] **BL-307** P1 — **Ripristinare completezza metadata e lineage del lake**. ✅ completato 02-ago: nuovo `scripts/audit_lake_metadata.py` (audit + `--fix` ripetibile, exit code 0/1) ricostruisce provenance **dal dato stesso** (colonna `source` dentro ogni parquet normalizzato, mai per inferenza), normalizza le chiavi lineage al formato canonico lake-root-relative (`normalized/...`) e rimuove i riferimenti pendenti. Risultato: 68.975 partizioni → 0 senza lineage, 0 dangling, 484 record coverage schema completo (0 incompleti). Fix classificazione weekend: `NO_DATA_WEEKEND` → `fresh` (FX/metalli non quotano sab/dom — il refresh perpetuo non avvelena più `failed`); timeout lettura Binance 30s→120s (i fetch 1m dal listing andavano in timeout). Test bloccanti: `tests/unit/test_lake_metadata_audit.py` (3 gate sul lake reale) + `test_orchestrator_classify.py` (weekend range).

### Data lake enrichment program (S0.6 — "TradingView Ultimate" interno, decisioni 2026-08-05: IBKR+Databento, core ETF+indici, universi mancanti principali)

> Target: tutte le asset class del canale (CME futures, equities/ETF, FX, crypto) con
> storia 1m profonda + resample. Infrastruttura BL-301 già pronta; fonti free-first.
> Fasi A (futures intraday, sblocca S1.1) → B (equities intraday) → C (universi) → D (accuratezza).

- [ ] **BL-097** P1 — **Fase A1 — Futures intraday via IBKR Client Portal**: riattivare `IBKRRestSource` (gateway TWS porta 7497 — **setup manuale utente ~1h**: Client Portal login, `start_ibkr_gateway.sh`), estendere la mappa con_id oltre i 6 esistenti (MES MNQ RTY 6E ZN ZB + equities per Fase B), backfill 5m/15m/1m 2010→ per i core (ES NQ GC CL YM), **roll methodology coerente con G2** (`market/roll.py`) per la serie continua intraday. AC: ES|5m ≥ 100K barre, lineage completo, `run_eval_simulation.py --timeframe 5m` testabile. BLOCCO: setup gateway manuale.
- [ ] **BL-098** P1 — **Fase A2 — Futures CME via Databento free tier**: **utente: registrazione gratuita + DATABENTO_API_KEY**, riattivare `DatabentoHistorical`, backfill incrementale 1m/5m (1GB/mese ≈ 2 mesi di 1m ES al mese, 12 mesi di 5m) + cron giornaliero (Tier 4 del free-1m strategy). AC: copertura 1m ES/NQ/GC/CL ≥ 12 mesi entro 6 mesi di calendario; ridondanza con IBKR. BLOCCO: API key.
- [ ] **BL-099** P1 — **Fase B — Equities/ETF/indici intraday** (dopo BL-097): SPY QQQ DIA IWM TLT GLD + 11 settoriali + ^GSPC ^DJI ^NDX ^RUT ^VIX, 1m/5m 2000→ via IBKR (con_id equities da estendere). AC: SPY|5m ≥ 50K barre; coverage equities intraday completo.
- [x] **BL-101** P2 — **Fase C — SOL/BNB 1m via Binance** ✅ 2026-08-06 (con BL-104: finestre mensili resumable — i timeout finali non perdono dato): SOLUSDT 1m 3.101.332 barre (2020-08-11→), BNBUSDT 1m 4.547.680 barre (2017-11-06→). Crypto 1m ora completo su 10+ coin dal listing.
- [ ] **BL-102** P2 — **Fase C — Futures CME mancanti 1d/1h via yahoo**: BZ VX LBS ZR ZQ HE M2K (entry già aggiunte). AC: 7 nuovi simboli in coverage con lineage.
- [ ] **BL-103** P3 — **Fase D — Calendario macro economico**: espandere `data/macro/m31-events.json` (3 eventi) in calendario continuo 2008-2026 (Nasdaq API free, schema con event_time/available_at/source_sha256 già definito) per il regime modeling. AC: ≥ 500 eventi, schema invariato.
- [x] **BL-104** P1 — **Fetch a finestre mensili con persistenza incrementale** (prerequisito backfill profondi: Binance 1m dal listing E futuro IBKR 1m dal 2010). Root cause: `fetch_range` è un generatore ma il pipeline accumulava tutto prima di scrivere → timeout a metà = in=0 e ritenta da zero (SOLUSDT 1m fallito dopo 29 min con 0 barre scritte). Fix: `_month_windows` (slicing mensile) + `_fetch_all_windows`/`_fetch_window` (persistenza per finestra: merge, coverage, lineage e save DOPO ogni mese; finestra fallita marcata e non bloccante — i mesi mancanti vengono ripresi da coverage.latest al ciclo successivo). Test `tests/unit/test_pipeline_windows.py` (slicing, persistenza parziale su fallimento, resume da coverage, weekend-only). ✅ applicato 2026-08-06.

## G10 — Strategy Catalog (100+ strategie)

- [ ] **BL-400** P2 — **Implementare Trend Following (10 strategie)**: Golden/Death Cross,
  Donchian, Supertrend, EMA21 Trend Ride, Elder Triple Screen, Parabolic SAR,
  Linear Regression Channel, Heikin Ashi Trend, Ichimoku Kumo, ADX Trend.
  AC: ogni strategia come signal puro in `analytics/signals/catalog/trend/`,
  test unitari, test su 3 asset via DataRegistry. ~1 sprint.
- [ ] **BL-401** P2 — **Implementare Mean Reversion (10 strategie)**: Bollinger Bounce,
  RSI 30/70, Stochastic, Std Dev from Spanning, Williams %R, CCI, DPO,
  Envelopes, Z-Score Mean Rev, Pivot Point Bounce.
  AC: stessa struttura di BL-400. ~1 sprint.
- [ ] **BL-402** P2 — **Implementare Breakout (10 strategie)**: Previous Day HL, ORB,
  S/R Horizontal, Trendline, Volatility Squeeze, Triangle, Rectangle,
  Cup&Handle, Flag&Pennant, Volume Profile.
  AC: stessa struttura. ~1 sprint.
- [ ] **BL-403** P3 — **Implementare Price Action (10 strategie)**: Pin Bar, Engulfing,
  Inside Bar, Fakey, Morning/Evening Star, Tweezer, 3 Soldiers/Crows,
  Piercing Line, Doji Star, 1-2-3 Pattern. ~1 sprint.
- [ ] **BL-404** P3 — **Implementare Volumetric & Order Flow (10 strategie)**: POC,
  Volume Imbalance, Volume Exhaustion, Order Book Absorption, Liquidity Sweep,
  Delta Divergence, Iceberg Detection, T&S Acceleration, VWAP, Cumulative Delta.
  Nota: molte richiedono dati di order book / tick — stub per paper iniziale. ~2 sprint.
- [ ] **BL-405** P3 — **Implementare Macro & Fundamentali (10 strategie)**: Interest Rate,
  NFP, Earnings Surprise, Carry Trade, EIA Stocks, Insider Tracking, Dividend Arb,
  COT Report, Intermarket Correlation, CPI. ~2 sprint.
- [ ] **BL-406** P3 — **Implementare Quantitative & Algo (10 strategie)**: Pairs Trading,
  Grid, Market Making, Cross-Exchange Arb, Slipped MA, HFT Momentum, PCA,
  Kalman Filter, Sentiment NLP, Monte Carlo. ~2 sprint.
- [ ] **BL-407** P3 — **Implementare Opzioni (10 strategie)**: Covered Call, Iron Condor,
  Protective Put, Long Straddle, Bull Call Spread, Bear Put Spread,
  Calendar Spread, Cash-Secured Put, Iron Butterfly, Gamma Scalping.
  Nota: richiede dati opzioni. ~3 sprint.
- [ ] **BL-408** P3 — **Implementare Portafoglio & Esotiche (10 strategie)**: All Weather,
  Systematic Rebalancing, Currency Hedge, Smart Beta, Seasonal Commodity,
  Crypto DCA Trend, Funding Rate Arb, Value+Technical Exit,
  Futures Calendar Spread, Anti-Martingala. ~2 sprint.

## G11 — Cross-Asset Universal Coverage

- [ ] **BL-410** P2 — **Auto-calibrazione parametri per asset**: ogni strategia del catalogo
  calibra i propri parametri in base alla volatilità dell'asset (vol-scaled).
  AC: test su 10 asset × 10 strategie = 100 combinazioni. ~1 sprint.
- [ ] **BL-411** P2 — **Regime detection multi-asset**: regime classifier funziona su
  qualsiasi asset con dati OHLCV, non solo ES. AC: test su FX, crypto, commodities,
  tassi. ~3gg.
- [ ] **BL-412** P2 — **Coverage matrix dinamica**: report automatico che mostra
  quante strategie funzionano per ogni (asset, timeframe, regime).
  AC: script `scripts/report_coverage.py` produce JSON + Markdown. ~2gg.
- [ ] **BL-413** P3 — **Portfolio allocation cross-asset**: distribuisce il rischio
  tra asset scorrelati con target volatility. ~1 sprint.

## G12 — Meta-Optimizer Real-Time

- [ ] **BL-420** P1 — **Strategy Performance Registry**: database/metric store che
  tiene traccia di Sharpe rolling, win rate, drawdown per ogni (strategia, asset,
  regime) dopo ogni trade. AC: aggiornato in tempo reale via hook nel paper engine.
  ~1 sprint.
- [ ] **BL-421** P1 — **Regime-aware signal blender**: pesa le strategie in base
  alla performance storica per regime corrente. AC: backtest del blender vs
  baseline a strategia singola su 3 regimi. ~1 sprint.
- [ ] **BL-422** P1 — **Decay detection**: se una strategia degrada per N finestre
  consecutive, peso azzerato con escalation. AC: test su degradazione simulata.
  ~3gg.
- [ ] **BL-423** P2 — **Portfolio risk allocation**: rischio distribuito tra strategie
  scorrelate con target volatility. AC: drawdown massimo < target. ~5gg.

## G13 — Strategy Evolution Loop

- [ ] **BL-430** P2 — **GA evolution scheduling**: GA search lancia nuove varianti
  ogni N sessioni paper. AC: integrazione con R4 GA search esistente. ~5gg.
- [ ] **BL-431** P2 — **Automatic qualification pipeline**: nuova strategia →
  walk-forward → stress gauntlet → paper. AC: pipeline end-to-end testata.
  ~1 sprint.
- [ ] **BL-432** P3 — **Strategy淘汰 (eliminazione)**: strategie con fitness negativo
  per X finestre rimosse dal catalogo attivo. AC: test su degradazione simulata.
  ~3gg.
- [ ] **BL-433** P3 — **Human-in-the-loop gate**: nuove strategie richiedono approval
  umano prima di paper live (fino a G14). AC: notifica + comando approve/deny.
  ~3gg.

## G14 — Edge Discovery Autonomo

- [ ] **BL-440** P3 — **Event study engine**: scandisce dati storici per eventi con
  bucket pre/durante/post. ~1 sprint.
- [ ] **BL-441** P3 — **VARRD model**: Variance Analysis of Returns in Regime Dimensions
  per scoprire pattern con edge in regimi specifici. ~2 sprint.
- [ ] **BL-442** P3 — **Auto-qualification per nuovi pattern**: scoperta → qualifica →
  promozione automatica. ~2 sprint.
- [ ] **BL-443** P3 — **Research memory feedback loop**: il sistema cerca pattern
  simili a quelli già funzionati in passato. ~1 sprint.

## ADR backlog

- [x] **ADR-015** proposta — Automation policy per Topstep ToS (vietato VPS) e
  posizione Oracle. ✅ completato in `8f590d8` (ACCEPTED). Owner: lead.
- [x] **ADR-020** proposta — Zero-cost data strategy — verified free sources only.
  ✅ ACCEPTED 2026-08-17. Vedi [ADR-020](docs/ADR/ADR-020-zero-cost-data-strategy.md).
  Codifica l'inventario fonti verificate 2026-08-16: Tiingo/Massive/Alpaca/SimFin/
  FRED/yfinance/Binance Vision/IBKR paper. Gap dichiarati onestamente. Owner: Alin.

## Opzione C — Zero-cost workflow (BL-OPC-1..5, 2026-08-17)

Pivot formalizzato in [ROADMAP §13](ROADMAP.md) + [ADR-020](docs/ADR/ADR-020-zero-cost-data-strategy.md).
Obiettivo: validare 3 lane su dati free prima di spendere budget per architettura.

- [x] **BL-OPC-1** P1 — AI swarm storico 50-ticker (as-of 2020-01-01, 12mo fwd).
  ✅ DONE 2026-08-17. REDUCE_SIZE 66.7% beat SPY (edge real). Haiku synthesis ~30%
  vuote → REJECT default. Output `docs/reports/ai-swarm/historical-2020-01-01-50tickers.md`.
- [x] **BL-OPC-2** P1 — VRP backtest su storico reale SPY+VIX 2010-2025.
  ✅ DONE 2026-08-17. Sharpe -0.08 (vs 7.36 deep-research = 95× inflated). NON tradabile.
  Fix: regime filter VIX>30 + tail cap 3× premium. Output `docs/reports/lane-d-vrp/2026-08-17-spy-vix-2010-2025.md`.
- [x] **BL-OPC-3** P1 — Composite Lane B vs Legacy AND su SimFin real 185 tickers.
  ✅ DONE 2026-08-17. Sharpe 0.93 vs 0.25, alpha +59% vs -32%. Composite adottato default.
  Output `docs/reports/lane-b-composite/2026-08-17-compare.md`.
- [x] **BL-OPC-4** P1 — Paper trading orchestrator MVP (signal→order→fill, slippage ledger).
  ✅ DONE MVP 2026-08-17. `execution/paper_orchestrator.py` + 14 test. Real-time loop +
  Lane B/D adapters deferred a follow-up P2.
- [x] **BL-OPC-5** P2 — Docs update (ADR-020 + ROADMAP §13 + BACKLOG Opzione C).
  ✅ DONE 2026-08-17. Questo ADR-020 + sezione ROADMAP §13 + sezione BACKLOG.
- [~] **BL-OPC-6** P2 — Backfill IBKR paper 1m cron (ES/NQ/GC/CL going forward).
  In progress. `scripts/backfill_1m_ibkr_paper.py` + systemd timer + backfill.conf entry.
  ✅ MVP validato 2026-08-17 (SPY/QQQ/AAPL/MSFT 1m, window 1 mese/run, 19k bars smoke).
  ⚠️ GAP 2026-08-18: timer systemd NON installato in `~/.config/systemd/user/`
  (solo lake-refresh è attivo) → nessun nuovo 1m dal 17-ago. Futures ES/NQ/GC/CL
  bloccati su expiry resolution (`reqContractDetails`). AC chiusura: timer enabled
  + 1 run verificato + futures almeno 1 simbolo.
- [ ] **BL-OPC-7** P2 — Paper orchestrator followup: real-time loop (cron systemd
  `oracle-paper-trader.service`) + yfinance delayed 15min price feed adapter + Lane B
  signal adapter (`LaneBSignalAdapter.from_screen_at_date`) + Lane D signal adapter.
  Sblocca promozione Lane B composite a paper trading live IBKR.
- [ ] **BL-OPC-8** P3 — AI swarm 2022 bear market validation. Refuta/sostiene il
  66.7% hit-rate osservato su 2020-2021 bull. Fix Haiku parsing (SSE fallback).
- [ ] **BL-OPC-9** P3 — Lane D VRP followup: regime filter VIX>30 + term structure
  inverted + tail cap 3× premium. Ri-run backtest su 2010-2025. Target: Sharpe > 0.5.
- [ ] **BL-OPC-10** P3 — Combine Composite Lane B + BL-505d aggressivo (stop-loss 5%
  + vol target 40%) per target Sharpe > 1.5 su base reale SimFin.
- [ ] **BL-OPC-11** P1 — **Hygiene: commit strutturati del working tree 2026-08-15→18**.
  Tutto il pivot Opzione C (ADR-017..020, Lane A/B/D, AI swarm, paper
  orchestrator, IBKR backfill, knowledge base 13 domini, ~80 file nuovi) non è
  in git. AC: commit atomici per area (docs/ADR, code, report, tests), suite
  verde (2903 passed), gitleaks pulito. Blocca qualunque lavoro successivo
  riproducibile.
- [ ] **BL-OPC-12** P1 — **Qualificazione Lane B composite via ADR-017** (DSR/PBO/CPCV,
  `analytics/qualification/dsr.py` già presente). È il prerequisito per promuovere
  la lane da research → paper (BL-OPC-7) e l'unico edge reale del progetto
  (Sharpe 0.93). AC: report in `docs/reports/lane-b-composite/` con DSR, PBO,
  CPCV su 2020→2025 (incluso bear 2022 separato); verdict registrato.

## P0 Architecture Hygiene — BL-600..606 (dossier architetturale 2026-08-19)

> Audit Principal Architect 2026-08-19 (branch
> `chore/p0-architecture-hygiene`): 18 findings (4 critici, 9 alti). La
> fase P0 chiude i fail-open, i cicli di dipendenza e il repo churn; non
> tocca la ricerca edge. Report: `~/oracle-architecture-audit.html`.

- [x] **BL-600** P0 — Fail-closed API auth/bind (C1/C2 del fail-open report).
  ✅ DONE 2026-08-19 (commit b0cd87a). `verify_auth_bind_safety()` in
  `apps/api/config.py`: bind default `127.0.0.1`; API senza chiave su
  interfaccia non-loopback = SystemExit salvo opt-in esplicito
  `ORACLE_ALLOW_OPEN_BIND`. 6 test in `tests/api/test_config.py`.
- [x] **BL-601** P0 — MAS risk node fail-closed (C3). ✅ DONE 2026-08-19
  (commit b0cd87a). `agents/orchestrator/graph.py`: senza risk_manager il
  nodo ritorna `approved=False` + reason + warning structlog (era
  `approved=True, max_position_size=0.25` silenzioso).
- [x] **BL-602** P0 — Rottura cicli core↔execution e market↔analytics.
  ✅ DONE 2026-08-19 (commit b0cd87a). Tipi broker in
  `core/domain/broker.py` (shim in `execution/brokers/types.py`),
  `IngestionError` in `core/errors/data_errors.py`.
- [x] **BL-603** P0 — Enforcement automatico dei confini. ✅ DONE 2026-08-19.
  `tests/unit/test_architecture_boundaries.py` (AST, 14 test) + contratto
  import-linter in pyproject.toml (4 contratti, verificati 4/4 kept) + job
  CI `architecture` blocking.
- [x] **BL-604** P0 — CI security blocking (F-14). ✅ DONE 2026-08-19
  (commit 3ae6fb2). gitleaks senza `continue-on-error`, pip-audit senza
  `|| echo WARNING`.
- [x] **BL-605** P0 — Machine state fuori da git (F-05). ✅ DONE 2026-08-19
  (commit 3ae6fb2). `data/lake/metadata/`, `data/ohlcv/**/*.parquet`,
  `data/intraday/` untracked (baseline M31 resta in `data/pinned/`);
  `.lint_venv/` gitignorato; RUF006 riabilitato (0 violazioni);
  51 branch merged eliminati; `git gc` (garbage 5.2 MB → 0);
  mypy --strict full path pulito (type-ignore puntuale lane_d_vrp).
- [ ] **BL-606** P0 — Rotazione credenziali METAAPI_TOKEN + LLM_KEY
  (`docs/CREDENTIALS.md`, aperte dal 2026-07-19). Richiede accesso umano
  ai provider; nessuna azione eseguibile da script.
- [ ] **BL-607** P0 — History rewrite dei blob pesanti (opzionale,
  ~100 MB+): `experiments/experiments.db` 11.8 MB, `data/lake/normalized`
  BTCUSDT 1m committato in history, modelli `.pth` 1.7 MB. Solo con
  `git-filter-repo` + force-push coordinato (remote = backup locale
  no-mistakes). Differito: non bloccante, distruttivo.

## Knowledge Base — 13 domini (BL-KB-01..115, 2026-08-17)

> 68 file in `docs/knowledge-base/` + audit critico. 98 items originali
> (BL-KB-01..98, uno per paper/metrica studiata) + 14 items da audit
> (BL-KB-99..115, definiti in `docs/knowledge-base/AUDIT-2026-08-17.md`).
> Non duplicati qui — il registro atomico vive nei README dei singoli domini.
> Priorità immediata: **BL-KB-99** (Haircut Sharpe) e **BL-KB-102** (VPIN,
> sblocca order flow L1 US su dati free).

## Note operative

- Esegui ogni task usando il branch `audit-remediation-beta` (o branch
  dedicato per task grandi); commit con messaggio `feat(BL-NNN): ...` o
  `fix(BL-NNN): ...`.
- Ogni PR deve avere `pytest`, `ruff`, `mypy --strict` verdi sul path
  toccato.
- **Priority chain aggiornata (2026-08-18, post-Opzione C):**
  ```
  BL-OPC-11 (committare il working tree) → BL-OPC-6 chiusura (timer IBKR)
  → BL-OPC-12 (DSR/PBO Lane B composite — qualificazione dell'edge reale)
  → BL-OPC-7 (paper real-time loop Lane B) → BL-024 (G6 run qualificante)
  → BL-201 (ensemble v2) → G6-WP3 shadow → G7 → G8
  → poi mutageno: BL-400..408 → G10 → BL-420 → G12 → G13 → G14
  ```
- I task P1 sono sequenziali. I P2/P3 sono paralleli dove indipendenti.
- Una volta passati a G6-WP2 verde, si procede con G6-WP3 shadow → G7
  cert firm → G8 → poi mutageno gates G10→G14.

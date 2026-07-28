# Oracle — Execution Backlog

> Single source of truth per task atomiche. Versione: 2026-07-25 (audit
> remediation beta). Sostituisce `docs/ORACLE_AUTOPILOT_BACKLOG.md` (rimosso
> il 25-lug) e `docs/plans/oracle-autopilot-*-backlog-*.md`.
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
- [ ] **BL-001** P1 — **Pin ES_1d in `data/pinned/`** + hash in provenance. Cfr §3.1 AUDIT_FINDINGS.md. AC: file `data/pinned/ES_1d_m31.parquet` con sha256 = `09a22…`; symlink/copia in `data/ohlcv/ES_1d.parquet`. Owner: data layer. ~1h.
- [ ] **BL-002** P1 — **Anti-overwrite guard su `yfinance_futures`**. AC: `market/data_sources.py:yfinance_futures` rifiuta di sovrascrivere se la provenienza del file esistente è più recente della `last_business_day()` ritornata dal fetch; fail-closed con messaggio `STALE_DATASET_PINNED`. Test: `tests/unit/test_data_sources_pinning.py`. Owner: data layer. ~1h.
- [ ] **BL-003** P1 — **Test pinning**: ogni `run_g6_wp2_paper_sessions.py` legge il dataset e verifica `sha256` all'avvio; fail se diverso. AC: test in `tests/integration/test_paper_session_dataset_pin.py` + script check --require-pin. ~30min.
- [ ] **BL-031** P2 — Warning budget CI bloccante (321 warnings). AC: `ruff check` con `select=W` + `pyproject.toml` warning budget. ~2h.
- [ ] **BL-032** P2 — `pyproject.toml` script untrack warning esplicito. ~30min.

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
- [ ] **BL-070** P1 — **Cablaggio PropFirmOrderRiskAdapter anche in `run_g6_wp2_paper_sessions.py`**. AC: ogni submit() passa attraverso `_AllowAll` rimosso, sostituito da `PropFirmOrderRiskAdapter(TOPSTEP_TC_50K, ledger, balance_getter)`. Test in `tests/integration/test_paper_session_risk.py`. ~3h. **[CRITICA — è ciò che manca per dire che il paper è prop-firm compliant]**
- [ ] **BL-071** P2 — Automation policy dettaglio per Topstep ToS (vietato VPS/VPN/residential bot). AC: ADR-015 (da scrivere) che documenta la posizione. ~2h.

## G5 Research truth

- [x] G5-001..013 vecchi → **invalidati** da ADR-014
- [~] G5-024 — Dataset pinned (coperto da BL-001..003)
- [ ] **BL-022** P2 — **M31 re-run da zero** con codice post-beta fix (post G6 exit). AC: report `docs/reports/m31-rerun/m31.md` con 6 regimi × 8 varianti = 48 slice, 0 hard breach, parity broker/ledger, dataset hash riportato in header. ~1 sprint.

## G6 Paper & shadow operations

### G6-WP1 (M32 diagnostic) — closed

- [x] M32-001..024 done (commit `44b632f`, `ae209f7`, `d4bc85e`, `db55cc2`, `4b22347`, `98319e6`, `13e4cf3`, `44b632f`, `ec59149`)

### G6-WP2 (M32a paper sessions) — REJECTED, da rifare

- [~] **BL-020** P1 — **Ricalibrazione regime + run WP2 v2**. AC: con hysteresys + soglie ricalibrate (BL-010..014) ri-eseguire WP2 30 sessioni; target `pass_rate ≥ 0.90`, `mean_sharpe ≥ 0`, `mean_dd ≤ 3%`. Report in `docs/reports/g6-wp2-v2.md`. ~1 sessione di lavoro.
- [ ] **BL-021** P1 — **MES-aware sizing per prop-firm**. AC: nuovo flag `--instrument=MES` (default su account 50K) e sizing derivato da `account_risk / stop_distance_in_points` con stop 8pt = $80/contract; test che su ES 50K il sizing = 0 contratti (sotto minimo MES) ma su MES = 1 contract. ~2h.
- [ ] **BL-022** P1 — 100 sessioni paper indipendenti (non 30): finestre 95-bar su 10 anni di dati intraday ES 1h. AC: nuovo script `scripts/run_g6_wp2_100_sessions.py` con blocchi 95-bar × 100 ≈ 9.5y di 1h, output in `logs/g6_wp2_100.json`. Gate target stesso di BL-020. ~3h.

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

- [ ] **BL-090** P2 — **Research Memory**: `analytics/research/memory.py` — store decisioni con `decision_id, timestamp, regime, confidence, outcome, features`, SQLite-backed. Hook nel decision path del `RegimeAwareEnsemble.compute()`. ~3-4gg.
- [ ] **BL-091** P2 — **Hurst + variance ratio detector** come备选 trend-following (BL-012). AC: nuovo file `analytics/regime/detectors/hurst.py` con test deterministici; integrazione in `RegimeDetector`. ~2gg.
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

- [ ] **BL-030** P2 — **Cleanup script untracked** (5 script). AC: ognuno viene
  o migrato in `scripts/contrib/` con mypy clean, o rimosso se orfano. Lista:
    - `scripts/run_backtest_evaluation.py` (33 righe, mypy errors)
    - `scripts/run_lorentzian_test.py`
    - `scripts/run_lorentzian_v2.py`
    - `scripts/run_risk_sized_eval.py`
    - `scripts/run_rolling_challenge.py`
  ~1gg. **O** in alternativa vengono spostati in `scripts/legacy/` con README
  che spiega perché sono fuori scope.
- [ ] **BL-033** P2 — Rimuovere `data/ohlcv/ES_1d.parquet` da ".gitignore commentato" e spostare il pinned in `data/pinned/`. AC: `.gitignore` aggiornato, symlink gestito da `scripts/setup_data.sh`. ~30min.

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

- [ ] **ADR-015** proposta — Automation policy per Topstep ToS (vietato VPS) e
  posizione Oracle. Owner: lead.

## Note operative

- Esegui ogni task usando il branch `audit-remediation-beta` (o branch
  dedicato per task grandi); commit con messaggio `feat(BL-NNN): ...` o
  `fix(BL-NNN): ...`.
- Ogni PR deve avere `pytest`, `ruff`, `mypy --strict` verdi sul path
  toccato.
- **Mutageno priority chain:**
  ```
  BL-020 (regime fix) → BL-021 (MES sizing) → BL-022 (100 sessions)
  → BL-070 (risk wiring) → G6 ✅
  → BL-090 (research memory) → BL-400..408 (strategy catalog)
  → BL-420 (meta-optimizer) → G12
  → BL-430 (evolution loop) → G13
  → BL-440 (edge discovery) → G14 ✅
  ```
- I task P1 sono sequenziali. I P2/P3 sono paralleli dove indipendenti.
- Una volta passati a G6-WP2 verde, si procede con G6-WP3 shadow → G7
  cert firm → G8 → poi mutageno gates G10→G14.

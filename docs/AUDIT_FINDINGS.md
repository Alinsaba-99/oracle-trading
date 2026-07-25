# Oracle — 2026-07-25 Audit Remediation Findings

> Stato reale vs stato dichiarato. Verifica eseguita su `audit-remediation-beta`
> @ `ffe91b4` (HEAD corrente). Non sostituisce le project review del 18 e 20
> luglio — le conferma e le aggiorna con fatti verificati in sessione.

## 1. Risultato secco

**Il sistema è research-grade con un percorso paper funzionante. NON è
deployabile, NON è live. La promozione verso una firm reale richiede
risoluzione strutturale di tutti i punti di questa review + nuovo M31.**

| Area | Dichiarato | Verificato |
|---|---|---|
| G0 baseline (lint/type/test) | ✅ PASSED | ✅ PASSED (2116+ test verdi, ruff/mypy puliti) |
| G1 autorità e ambienti | ✅ PASSED | 🟡 parziale — CLI guard attivo, ma `OrderManager` ancora accetta `risk_manager=None` in alcuni costruttori (path `scripts/run_*_sessions.py` lo creano localmente) |
| G2 contract data | ✅ PASSED | 🟡 parziale — intraday futures non ancora disponibile; Polygon richiede key |
| G3 ledger/OMS | ✅ in-memory → postgres | ✅ — Postgres path attivo 25-lug, OMS factory, RecoveryService, ReconciliationWorker tutti verdi |
| G4 risk | ✅ PASSED | 🟡 — adattore PropFirm cablato in CLI ma escluso dal paper harness (vedi §3) |
| **G5 research truth** | ❌ REGRESSED il 25-lug | ❌ **REGRESSED** — il dataset `data/ohlcv/ES_1d.parquet` è stato ripristinato al provenance `09a22…` solo in working tree (non pinned). Qualsiasi refresh lo sovrascrive |
| G6 paper | 🟡 IN PROGRESS | 🟡 — 20/30 sessioni fatte; **gate rejected** per `mean_sharpe = -0.31` (target: -0.5 borderline), e `pass_rate = 77%` (target: 90%) |
| G6-I feedback loop | 🆕 avviato | 🟡 — Factor Timing, Lorentzian causal-fix, Regime Ensemble **esistenti** ma Lorentzian è solo un备选 fra 4 specialist, mai trigger dominante nei WP2 |

## 2. Cosa funziona davvero (verificato eseguendo o leggendo codice)

- `core/ledger.py` + `core/ledger_postgres.py` — doppio-entry double-entry con idempotency key
- `core/oms_postgres.py` — OMS durevole PostgreSQL, ordini, fill, outbox
- `core/recovery.py` — RecoveryService idempotente dopo restart (5 test verdi)
- `core/reconciliation_worker.py` — reconciliation periodico (7 test verdi)
- `analytics/strategy/factor_timing/` — Rank IC, decay state, null-IC benchmark (26 test verdi)
- `analytics/strategy/lorentzian.py` — fix causal su normalizzazione expanding (6 test verdi)
- `analytics/strategy/regime_ensemble.py` — routing per regime (14 test verdi)
- `scripts/run_g6_wp2_paper_sessions.py` — 30 sessioni paper end-to-end
- `scripts/run_regime_paper_smoke.py` — smoke test completo regime→broker→OMS→reconcile
- `analytics/qualification/` — ReplayPeriod, qualification evaluator, multi-regime 2x2x2
- `policy/prop_firm/` — versioned profile, RiskManager, fixtures Topstep 50K
- `policy/prop_firm/order_risk.py` — adapter PropFirm order-risk cablato in CLI

## 3. Cosa NON funziona (verificato)

### 3.1 ES_1d.parquet — la sovrascrittura "misteriosa"

**Stato attuale**: hash `09a22268d2a7fa815beed6788917663771c7af7b347b7b49db6c2a1318f26b42` (M31 provenance, 250 bar, `last_timestamp=2026-07-17`).

**Cosa è successo (analisi forense dei path):**

```
data/ohlcv/   untracked (vedi .gitignore: data/ohlcv/  commented out)
              → qualunque script `yfinance_futures("ES")` lo riscrive

scripts/refresh_data.py — `refresh_all()` scarica ES=F via yfinance (period 1y)
                          e scrive self.DATA_DIR / f"{symbol}_{interval}.parquet"
                          → path = data/ohlcv/ES_1d.parquet
                          → numero di barre dipende da quando gira

I SCRIPT che leggono ES_1d senza riscriverlo (no writer):
- scripts/run_g6_wp2_paper_sessions.py (lettura)
- scripts/run_regime_paper_smoke.py (lettura)
- scripts/run_replay_qualification.py (lettura + provenance check)
- scripts/run_annual_paper_replay.py (lettura)
- scripts/run_backtest_evaluation.py (lettura)
- scripts/run_rolling_challenge.py (lettura)
- scripts/run_risk_sized_eval.py (lettura)
- scripts/run_lorentzian_test.py / _v2.py (lettura)

SCRITTORI che hanno `to_parquet("data/ohlcv/ES_1d.parquet")`:
- market/data_sources.py: yfinance_futures → path = "ES_1d.parquet" [RISCHIO]
- scripts/refresh_data.py --multi-timeframe ES → chiama yfinance_futures

CRON / PROVE di esecuzione automatica (non confermato ma sospetti):
- niente in /home/alin/_repos/oracle-trading/.githooks
- .claude/scheduled_tasks.lock contiene sessionId di un altro progetto, no cron
- nessun `crontab -l` eseguibile in questo ambiente
- ccxt_bridge (PID 1519) e uvicorn (`app.main:app` su 8000) sono processi di UN ALTRO servizio (vedi /app/main.py e /src/adapters/ccxt_bridge in ps -ef — sono container Docker di distill-lab, NON di oracle)
- NESSUN processo locale tocca data/ohlcv/ES_1d
```

**Conclusione**: la sovrascrittura NON è un processo esterno automatico.
Il colpevole è **uno dei 5 script untracked di lavoro precedente**
(`run_backtest_evaluation.py`, `run_lorentzian_test.py`, `run_lorentzian_v2.py`,
`run_risk_sized_eval.py`, `run_rolling_challenge.py`) che esegue un fetch fresco
di `data/ohlcv/ES_1d.parquet` via path di yfinance**. Tutti e 5 hanno
`raw = pl.read_parquet("data/ohlcv/ES_1d.parquet")` ma almeno uno
(`run_backtest_evaluation.py`) chiama `load_es_data()` senza refresh e
potrebbe essere rieseguito dopo un `refresh_data.py --multi-timeframe ES`
lanciato per errore. Inoltre `market/data_sources.py:yfinance_futures()` scrive
**sempre** lo stesso path, anche se il dataset è già presente.

**Fix definitivo (nel nuovo backlog):**
- [BL-001] Aggiungere check `to_datetime(last).date() == today()` prima di
  to_parquet; fail-closed se il dataset pinned è più fresco del fetch
- [BL-002] Spostare dataset pinned in `data/pinned/` con nome versione
  (`es_1d_m31_2026-07-17.parquet`) e `.provenance.json` adiacente
- [BL-003] Aggiungere test `test_dataset_pinning.py` che fallisce se il
  dataset viene sovrascritto durante un run paper

### 3.2 Regime detector choppy-biased

**Il fatto (logico, non numerico)**: 29 sessioni su 30 sono state etichettate
`choppy` con confidence media 0.91 e routing su `mean_rev` → RsiReversion

**Causa root (`analytics/strategy/regime_ensemble.py:_sma_regime_heuristic`):

```python
recent_vol = float(returns[-20:].std())
long_vol = float(returns.std()) or 1e-9
vol_ratio = recent_vol / long_vol

if vol_ratio > 1.6:
    return VOLATILE
if trend_strength > 0.02:
    return BULL/BEAR
return CHOPPY  # ← default
```

Il ramo `volatile` richiede `recent_vol > 1.6 × long_vol`. Il ramo `trend`
richiede `|SMA20 - SMA50|/SMA50 > 0.02`. Tutto il resto è choppy.
Su 250 barre daily di ES (yfinance ES=F continuo) la vol degli ultimi 20 è
*quasi sempre* inferiore a 1.6× la vol dell'intero dataset, e il trend su
EMA20/50 a 250gg è spesso < 2%. Risultato: choppy vince per default.

**3 specialist sono dichiarati, 1 funziona**: il 99% delle sessioni
atterra su `RsiReversion` (specialista per `MEAN_REVERSION`), perché
choppy → mean_rev routing table. Lorentzian ha un备选 (`MEAN_REVERSION,
LORENTZIAN`) ma la prima match wins e `MEAN_REVERSION` esiste.

**Edge realistico emerso dal paper** (dati veri, log sessione G6-WP2):
- Su choppy → RsiReversion, ES daily, 250 bar diviso in 30 finestre:
  - 23/30 passano il DD cap a 3%
  - mean_sharpe = -0.31 (target gate: -0.5 borderline)
  - **payout medio PASSED: +0.78% a sessione** (Win: 14/23 sessioni positive)
  - mean DD sui PASSED = 1.45%
  - 29/30 mean reversion → la strategia **NON ha edge su breakout, NON ha
    edge su trend-following, NON ha edge su Lorentzian**. Ha un piccolo edge
    su RSI mean reversion SOLO in choppy, e SOLO se DD è gestito.

**Implicazione finanziaria**: la prop firm richiede edge con
expectancy positiva dopo costi e slippage, su base continuativa.
L'edge osservato su RSI in choppy daily non è statisticamente significativo
sulle 30 sessioni (mean sharpe negativo, anche se di poco). Non è
sufficientemente robusto per G7.

**Cosa va fatto**:

| Task | Cosa | Perché |
|---|---|---|
| BL-010 | Aggiungere regime detector con hysteresys (already in `ensemble.py` `_apply_hysteresis` ma non esposto) | Riduce flip-flop |
| BL-011 | Ricalibrare soglie `_sma_regime_heuristic` su 250 bar ES daily; verificare frequenza storica | Portare choppy dal 96% a ~50% |
| BL-012 | Aggiungere detector trend-following (Hurst exponent, variance ratio) come备选 nel branch BULL/BEAR | Cattura trend lentamente emergenti |
| BL-013 | Aggiungere `min_bars_for_confidence` alla regime detector | Oggi bastano 60 bar; dovremmo richiederne ≥120 |
| BL-014 | Routing Lorentzian-first quando Lorentzian ha confidence > 0.7 | Sfrutta il meta-signal piuttosto che perderlo |

### 3.3 Esiste un edge? Risposta secca

L'edge è una funzione di regime, non di strategia. Dalle 30 sessioni
G6-WP2, le sole 23 PASSED sono sufficienti per **una sessione prop-firm
Topstep TC 50K** (target $5k, max loss $2k, daily $1k) con sizing
1 contratto ES. **NON** sono sufficienti per 10 sessioni consecutive
richieste dal percorso standard.

| Contratto | Costo per trade ES | Costo per trade MES | Note |
|---|---|---|---|
| ES | round-trip ~$5 (comm + 2× slippage @ 5bps) | n/a | troppo alto per 1-contract |
| MES | round-trip ~$1.30 (comm + 2× slippage @ 5bps) | round-trip ~$1 | sizing coerente con account 50K |

**Regola di sizing da applicare prima di qualsiasi live**:
- sizing = floor(account_risk / stop_distance_in_points)
- account_risk = $250 (max 0.5% di 50K, sotto daily loss $1K)
- stop_distance max = 8 ES points = $400/contract ES, $80/contract MES
- Sizing risultante = 1 MES contract (o 0.5 ES, impossibile)
- su 30 sessioni G6-WP2 con 1 MES equiv: mean DD sale a ~1.4%×$50K = $700,
  ben sotto il daily $1K. PASSED in 23/30 = 77%

**Se l'edge regge su 100+ sessioni indipendenti siamo a livello prop-firm evaluation.**

### 3.4 Ordine di priorità di remediation

1. Pinning ES_1d (BL-001..003) → sblocca G5
2. Regime rebalance (BL-010..014) → sblocca `pass_rate = 0.90`
3. 100+ sessioni paper indipendenti (BL-020) → sblocca G6 formale
4. Vela MES custom (BL-021) → sizing corretto per prop-firm
5. Run M31 post-fix (BL-022) → riapre G5

## 4. Cosa NON serve cambiare

- ARCHITECTURE.md (in gran parte ancora valido)
- La quasi totalità dei ADR (008, 009, 010, 011, 012, 013)
- Prop-firm profile model e fixture Topstep 50K
- I moduli OMS/PostgresLedger/RecoveryService/ReconciliationWorker appena uniti
- Factor Timing + Lorentzian causal fix (test verdi, codice pulito)
- Tutta la catena di test oltre i 5 script untracked

## 5. Cosa serve riscrivere

La ridefinizione della documentazione sostituisce:

- 6 file Phase* plan in root (`phase0-plan.md` … `phase5-plan.md`,
  `phase3.5.1-plan.md`) → **archiviati**
- `docs/phase6-plan.md` (Phase 6 dashboard, già congelato come storico)
- `docs/ORACLE_AUTOPILOT_BACKLOG.md` (sovrascritto da `BACKLOG.md`)
- `docs/plans/oracle-autopilot-atomic-backlog-v1.md` (già in plans/archive)
- `docs/plans/oracle-autopilot-gate-backlog-v2.md` (già in plans/archive)
- `PROJECT.md` (accorciato e reso "nota introduttiva informale")
- `docs/RUNBOOK.md` (aggiornato al 25-lug)
- `docs/ORACLE_AUTOPILOT_STATUS.md` (riscritto come checkpoint operativo,
  non più single source of truth dei task)

I task atomici diventano un unico `BACKLOG.md` in root, ordinato per gate,
con Definition of Done verificabile e ID stabile (BL-NNN). Chi prende in
mano il progetto legge: ARCHITECTURE → ROADMAP → STATUS → BACKLOG →
RUNBOOK → ADR rilevanti.

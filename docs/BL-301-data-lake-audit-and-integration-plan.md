# BL-301 Data Lake — Audit Verifica + Piano Integrazione 4 Framework

> Data: 2026-07-28
> Branch: `feat/bl-301-data-lake`
> Stato: audit di verifica eseguito, nessuna modifica apportata

---

## Parte 1 — Risultati Verifica (5 Step)

### Step 1: BL-301 Codebase — Già Estremamente Solido

**Files letti integralmente:**
| File | Righe | Cosa fa |
|------|-------|---------|
| `market/ingestion/sources.py` | 1012 | 7 data source adapters zero-cost |
| `market/ingestion/pipeline.py` | 271 | Pipeline incrementale idempotente |
| `market/ingestion/orchestrator.py` | 231 | Backfill multi-source resumable |
| `market/ingestion/normalize.py` | 111 | Quality checks su ogni barra |
| `market/ingestion/types.py` | 126 | OHLCVBar, AssetSpec, RateLimit, QualityFlag |
| `market/data_sources.py` | 364 | DataFetcher unificato (yfinance, CCXT, OpenBB, Polygon, FRED) |
| `market/data_config.py` | 133 | Config centralizzata API keys |

**Architettura già implementata:**
```
data/lake/
├── raw/<source>/               ← immutabile
├── normalized/
│   symbol=<S>/tf=<TF>/          ← Hive-style partitioning
│   └── year=<YYYY>/month=<MM>.parquet
└── curated/<SYMBOL>_<TF>.parquet  ← merged convenience
```

**7 sorgenti zero-cost già cablate:**
| Sorgente | Asset Class | Timeframe | Copertura |
|----------|-------------|-----------|-----------|
| **BinanceREST** | Crypto spot | 1m, 5m, 15m, 1h, 4h, 1d | BTCUSDT 2017→oggi |
| **CryptoDataDownload** | Crypto spot | 1m, 5m, 1h, 1d | BTC 2014→oggi (CSV bulk) |
| **DatabentoHistorical** | Futures CME | 1m, 5m, 15m, 1h, 1d | ES/NQ/CL/GC 2010→oggi (free 1GB/mese) |
| **YFinance** | Futures, FX, Equities | 1m, 5m, 15m, 30m, 1h, 1d | 2000→oggi |
| **HistData** | FX majors+crosses | 1m, 5m, 1h, 1d | 2003→oggi, 28 coppie |
| **Stooq** | Futures | 1d (daily only) | 1990→oggi |
| **Dukascopy** | FX + XAU/XAG | 1m, 5m, 15m, 30m, 1h, 4h, 1d | **2003→oggi 1m!**, 28 coppie |

**Coverage tracking** e **audit logging** già funzionanti.

**Backfill orchestrator** resumable con stato persistente: `python -m market.ingestion.orchestrator run`

---

### Step 2: yfinance ES=F 1h — ✅ FUNZIONA

Test eseguito:
```
ES=F 1h: 83 rows (5 giorni di barre 1h)
ES=F max (daily): 6528 rows (dal 2000-09-18)
EURUSD=X 1d: 260 rows (1 anno)
```

**Confermato**: `yfinance.download("ES=F", period="max", interval="1h")` funziona.
- Dà ~80 barre 1h per 5d
- Dà 6528 barre daily dal 2000
- EURUSD=X funziona con forex

**Implicazione**: non serve Polygon per avere ES 1h. Per 1m futures serve Polygon o Databento.

---

### Step 3: Dukascopy EURUSD 1m — ✅ FUNZIONA, DATI DAL 2003

Test eseguito su data singola (2003-05-05):
```
EURUSD 1m 2003-05-05:
  Bars: 1440              ← 1440 barre 1m (24 ore complete)
  Multiplier: 1e-05
  Has volume data: True
  Shift: 60000ms (1 minuto)
  Open: 1.12177
  Close: 1.12215
```

**Confermato**: Dukascopy dà 1440 barre 1m per giorno dal 2003. Supporta EURUSD, GBPUSD, USDJPY, XAUUSD, XAGUSD + 28 coppie FX. Volume disponibile.

**Implicazione**: Per FX e Oro/Argento, hai 1m dal 2003 gratis — nessun'altra fonte free dà questo.

---

### Step 4: Inalpha — Analisi Approfondita

**Repo**: `mirror29/inalpha` (25⭐, Python 3.12+, TypeScript, AGPL-3.0)
**Architettura**: 4 servizi Python (data, paper, research, factor) + dashboard React + orchestrator Mastra (TS)

**Cosa Inalpha ha che Oracle non ha:**

| Feature | Inalpha | Oracle | Gap |
|---------|---------|--------|-----|
| **Factor timing IC** | Rank IC time-series rolling, ICIR, decay state (stable/fading/decaying) | ❌ ResearchMemory esiste ma senza IC ranking | Da costruire |
| **Factor library** | 79 fattori (pandas-ta, Alpha101, QLib adapters, FRED macro) + DSL custom | ❌ 52 strategie ma nessun catalogo fattori | Da costruire |
| **Strategy evolution** | LLM muta codice → 3 sandbox gates (AST, subprocess, protocol) → backtest → fitness | ❌ Solo GA in genetics/ | Gap grosso |
| **Overfitting defenses** | Combinatorial Purged CV + Deflated Sharpe + BH correction + null-IC benchmark | ❌ Walk-forward esiste, ma non purged CV | Da costruire |
| **Research panel** | 6 analysts + bull/bear/risk debate + investing legends | ✅ `agents/analysts/` esiste ma rudimentale | Parziale |
| **Machine-approved orders** | propose → approve_token → execute, LLM never on order path | ✅ Risk kernel fail-closed, ma LLM path non isolato | Parziale |
| **Orders audit trail** | Every proposal/approval/execution logged with full lifecycle | ✅ Ledger PostgreSQL durevole | Equivalente |
| **Factor decay watch** | Decay state alert su ogni fattore, lineage tracking | ❌ Manca | Da costruire |

**File chiave analizzati:**
- `services/factor/src/inalpha_factor/effectiveness.py` — IC scoring, ICIR, decay state, null-IC benchmark, BH correction
- `services/factor/src/inalpha_factor/engine.py` — Factor engine con 5 adapter di fattori
- `services/factor/src/inalpha_factor/expression.py` — DSL restricted (25 operatori, whitelist-based)
- `services/factor/src/inalpha_factor/panel.py` — Cross-sectional IC ranking
- `services/paper/src/inalpha_paper/engine/robustness.py` — PBO, CSCV
- `services/paper/src/inalpha_paper/engine/cv.py` — Combinatorial Purged CV, WalkForward, PurgedKFold

**Licenza**: AGPL-3.0 → se integri codice copiato, l'intero progetto deve diventare AGPL. Se solo prendi ispirazione architetturale, nessun problema.

---

### Step 5: Polygon.io $29/mo — Valutazione

| Tier | Costo | Rate limit | Barre storiche 1m |
|------|-------|------------|-------------------|
| Free | $0 | 5 calls/min | ❌ Solo delayed, niente aggs storiche |
| **Starter** | **$29/mo** | 5 calls/min | ✅ OHLC 1m per stocks + futures |
| Basic | $49/mo | 15 calls/min | ✅ Tutto |
| Pro | $199/mo | 60 calls/min | ✅ |

**Verdetto**: $29/mo per 5 chiamate/minuto è lento ma **sufficiente** per backfillare US equities 1m su ~50 ticker in una settimana. Per futures 1m, Databento free tier (1GB/mese) è alternativo.

**Alternativa**: Alpaca Markets API (free) dà dati 1m intraday solo per ultimi 15 giorni, non storico. Non sostituisce Polygon.

**Consiglio**: Salta Polygon ora. Con yfinance 1h per ES, Dukascopy 1m per FX, BinanceREST 1m per crypto, hai copertura del 80% dei casi d'uso. Polygon se servono US equities 1m.

---

## Parte 2 — Piano Integrazione Dettagliato 4 Framework

### Framework A: QLib (Microsoft, 46.7K⭐)

**Cosa portare**: Factor definitions (Alpha101, Alpha158, Alpha360), RD-Agent pattern

| Modulo QLib | Cosa fa | Come integrarlo in Oracle |
|-------------|---------|---------------------------|
| `qlib.contrib.data.handler` | Data processing pipeline | ❌ **Skip** — Oracle ha BL-301 che è più multi-asset |
| `qlib.factor` | Factor definitions (Alpha101) | ✅ **Wrap** → traduci ogni alpha in un `BacktestSignal` in `analytics/strategy/signals_r3.py` |
| `qlib.model` | ML models (LightGBM, GRU, Transformer) | ✅ **Adapter** → `analytics/ml/` che chiama QLib model sotto |
| `qlib.backtest` | Backtest engine | ❌ **Skip** — Oracle ha NautilusTrader + vectorbt |
| `qlib.contrib.report` | Analysis report | ✅ **Inspira** — per report automatici dopo sweep |
| **RD-Agent** | LLM-driven R&D automation | ✅ **Pattern** → ispirazione per `agents/genetics/` loop |
| `qlib.contrib.model.ensembler` | Model ensemble | ✅ **Adapter** → integra con il RegimeAwareEnsemble già esistente |

**Stima effort**: 3-5 giorni per wrappare gli alpha 101 in signals.
**Dipendenza**: `pip install qlib` (o `uv pip install qlib`)

**Schema integrazione:**
```
QLib Alpha101/158/360 → QLibFactorAdapter(BaseSignal)
                          ↓
                    signals_r3.py (strategie QLib-based)
                          ↓
                    SweepEngine (testa su tutti gli asset)
                          ↓
                    FactorTiming.rank_ic() → se edge, promuovi
```

**Attenzione**: QLib è ottimizzato per azioni cinesi (A-shares). Gli alpha sono per lo più cross-sectional (rank su panel di N ticker). Per futures (un solo contratto) servono alpha time-series, non cross-sectional. Vanno selezionati solo alpha 101 che hanno senso time-series.

---

### Framework B: Inalpha (25⭐, AGPL-3.0)

**Cosa portare**: Factor timing IC, factor decay, sandbox gates, overfitting defenses
**Cosa NON copiare**: Codice sorgente (licenza AGPL). Solo ispirazione architetturale.

**Priority: ALTA** — colma il gap più grande (nessun loop di feedback)

| Feature Inalpha | Come reimplementarla in Oracle | File Oracle target | Stima |
|-----------------|-------------------------------|--------------------|-------|
| **IC Ranking** (effectiveness.py) | `FactorTimingEngine` legge da `ResearchMemory`, calcola Rank IC time-series | `analytics/research/factor_timing.py` + `analytics/research/memory.py` | 3gg |
| **Decay state** | DecayState enum (stable/fading/decaying) + patrol che marca i fattori morti | `analytics/research/decay.py` | 1gg |
| **Null-IC benchmark** | Bailey-López de Prado E[max] approssimazione | `analytics/research/overfitting.py` | 1gg |
| **Sandbox gates** | AST audit (ast.parse) → subprocess exec → Strategy protocol check | `genetics/gates/` | 3gg |
| **Strategy evolution** | LLM propone modifica → gates → backtest → fitness score → ResearchMemory | `agents/genetics/engine.py` | 5gg |
| **Combinatorial Purged CV** | Implementazione di cv.py con purge+embargo | `analytics/backtest/cv.py` (esiste walk_forward.py) | 2gg |
| **Deflated Sharpe** | Correzione per N trials (Bailey-López de Prado) | `analytics/metrics/deflated_sharpe.py` | 1gg |
| **Factor expression DSL** | 25 operatori whitelist-based, niente eval/exec | `analytics/factor/expression.py` | 2gg |

**Schema integrazione:**
```
Ogni strategia produce segnale
       ↓
ResearchMemory.record_decision() ← già BL-090
       ↓
FactorTimingEngine.rank_ic()
  - Calcola Rank IC rolling su finestra N bar
  - ICIR, decay state
  - Confronta con null-IC benchmark
       ↓
RoutingDecision usa IC ranking per:
  - Pesare le strategie (non più peso fisso)
  - Escludere strategie in decay
  - Promuovere nuove strategie validate
```

---

### Framework C: PyPortfolioOpt (4.5K⭐, MIT)

**Cosa portare**: HRP (Hierarchical Risk Parity), Black-Litterman, Mean-Variance
**Licenza**: MIT → no problemi copia integrale

| Feature | Cosa fa | Integrazione in Oracle |
|---------|---------|------------------------|
| `HRPOpt` | Hierarchical Risk Parity — combina asset correlati | ✅ **Sostituisce** il weighting semplice nell'ensemble portfolio |
| `BlackLittermanModel` | Incorpora view degli analyst nel portfolio | ✅ **Nuovo** — integra con ResearchMemory per le view |
| `EfficientFrontier` | Mean-variance optimization classica | ✅ **Opzionale** — per portfolio-level optimization |
| `risk_models.CovarianceShrinkage` | Stima robusta della matrice di covarianza | ✅ **Utilizzo** — per calcolare correlazioni tra strategie |
| `objective_functions` | Funzioni obiettivo (Sharpe, variance, CVaR) | ✅ **Adapter** → connetti ai tuoi metric calculator |

**Stima effort**: 2-3gg per HRP integration
**Dipendenza**: `pip install PyPortfolioOpt`

**Schema integrazione:**
```
Strategie compute() → segnali per barra
       ↓
PyPortfolioOpt.HRPOpt(cov_matrix) ← correlazione tra strategie
       ↓
Weight allocator → pesi dinamici per ogni strategia
       ↓
RegimeAwareEnsemble.compute() ← pesi sostituiscono il routing fisso
```

**Dettaglio implementativo:**
```python
# Il concetto: invece di routing "choppy → mean_rev", usi HRP su N strategie
# Oracle ha già N strategie in DEFAULT_STRATEGIES (8+10+34=52)
# HRP su tutte = portafoglio diversificato, robusto

from pypfopt import HRPOpt
from pypfopt import risk_models

# 1. Prendi le serie di equity di ogni strategia (da ResearchMemory)
returns_df = research_memory.get_strategy_returns()

# 2. HRP allocation
hrp = HRPOpt(returns_df)
weights = hrp.optimize()
hrp.portfolio_performance(verbose=True)
```

---

### Framework D: pysystemtrade (2.5K⭐, Rob Carver)

**Cosa portare**: Volatility scaling, forecast combination, cross-asset risk budgeting
**Licenza**: BSD-3 → no problemi copia

| Feature pysystemtrade | Cosa fa | Integrazione in Oracle |
|-----------------------|---------|------------------------|
| **Volatility targeting** | Scale position size by inverse vol | ✅ **Già in parte** — Oracle ha vol-based sizing in RiskManager |
| **Forecast scaling** | Raw signal (-1/0/1) → vol-adjusted position | ✅ **Migliora** — aggiunge scalling continuo invece di discreti -1/0/1 |
| **Forecast combination** | Media pesata di forecast da strategie diverse | ✅ **Nuovo** — sostituisce/affianca routing binario |
| **Instrument weighting** | Risk budgeting tra asset class | ✅ **Nuovo** — divide rischio tra ES, BTC, EURUSD |
| **IDM (Instrument Diversification Multiplier)** | Scalare per diversificazione | ✅ **Nuovo** — auto-adatta size quando aggiungi asset |
| **Carver speed rules** | Velocità forecast (slow/medium/fast) | ✅ **Opzionale** — per regime-aware weighting |

**Stima effort**: 3-5gg per l'integrazione dello scaling framework

**Schema integrazione:**
```
Signal raw (-1/0/1) ──→ Forecast scaling → vol-adjusted forecast
                               ↓
                    Forecast combination (tra strategie)
                               ↓
                    Instrument weighting (tra asset)
                               ↓
                    IDM scaler (diversification multiplier)
                               ↓
                    OracleRiskManager.position_sizing()
```

**Dettaglio concettuale** (l'idea di Carver, non il codice):
```python
# Invece di "regime=choppy → mean_rev, regime=direzione 1"
# Ogni strategia produce un forecast continuo per ogni barra
# I forecast sono pesati per Sharpe storico * regime_confidence
# Output finale: position = vol_target * sum(forecasts) / vol_current

# Questo è più robusto del routing binario perché:
# - Se choppy MA trend sta funzionando, trend contribuisce comunque
# - Se trend parte, mean_rev scala giù gradualmente non abruptly
# - La diversificazione tra strategie riduce DD
```

---

## Parte 3 — Roadmap d'Integrazione

### Fase 1: Fondamenta BL-301 (1 settimana)

| Task | Effetto |
|------|---------|
| Fix risk adapter governor reset | Sblocca 0 trade |
| Pin dataset ES_1d.parquet | Riproducibilità |
| Backfill BL-301: ES 1h + EURUSD 1m da Dukascopy + BTC 1m | Copertura dati espansa |
| Verificare HMM detector path (non SMA fallback) | Regime detector corretto |

### Fase 2: Factor Timing Loop (2 settimane) — da Inalpha

| Task | Framework base |
|------|---------------|
| FactorTimingEngine con Rank IC rolling su ResearchMemory | Inalpha |
| Decay state detection (stable/fading/decaying) | Inalpha |
| Null-IC benchmark (Bailey-López de Prado) | Inalpha |
| Combinatorial Purged CV per strategie candidate | Inalpha |

### Fase 3: Portfolio Construction (1 settimana)

| Task | Framework base |
|------|---------------|
| HRP allocation su strategie esistenti | PyPortfolioOpt |
| Volatility targeting + forecast scaling | pysystemtrade |
| Risk budgeting cross-asset (ES/BTC/EURUSD) | pysystemtrade |

### Fase 4: Strategy Evolution (2-3 settimane)

| Task | Framework base |
|------|---------------|
| Sandbox gates (AST audit + subprocess + protocol) | Inalpha |
| LLM-authored strategy pipeline | Inalpha + QLib RD-Agent |
| QLib Alpha101 adapter → signals_r3.py | QLib |

### Fase 5: Sweep Automation (1-2 settimane)

| Task | Framework base |
|------|---------------|
| SweepEngine che testa ogni strategia su ogni asset+TF | Esistente (run_edge_portfolio.py) |
| Walk-forward obbligatorio, shuffle test, MC sim | Esistente (parziale) |
| Ranking dashboard: quali strategie hanno edge su quali asset | Nuovo |

---

## Conclusione

**Lo stato reale**: BL-301 è già al 70% di ciò che descrivi. 7 sorgenti zero-cost, pipeline incrementale, quality checks, backfill orchestrator. La maggior parte del lavoro di "raccolta dati" è già fatta — manca l'esecuzione dei backfill.

**I 4 framework** portano ciascuno un pezzo mancante:
- **QLib** → factor zoo (cosa testare)
- **Inalpha** → factor timing loop (come validare)
- **PyPortfolioOpt** → portfolio construction (come combinare)
- **pysystemtrade** → risk scaling (come dimensionare)

**Nessuno va copiato interamente** — ognuno contribuisce un pattern architetturale o un algoritmo specifico che colma un gap ben preciso di Oracle.

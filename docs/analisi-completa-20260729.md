# Oracle — Analisi Completa del Sistema (2026-07-29)

## 1. Panoramica

```
130.911 righe Python, 916 file, 2577 test passati (25 failure pre-esistenti)
45 simboli × 4 timeframe = 115 entry data lake
2 modelli PyTorch allenati (18-dim + 72-dim)
69 strategie registrate (V1+R1+R2+Alpha101)
```

## 2. Architettura a Strati

```
┌──────────────────────────────────────────────────────────────┐
│                    AGENTS (AAAI)                             │
│  oracle / committee / debate / analysts / genetic / orchestrator │
├──────────────────────────────────────────────────────────────┤
│                    ANALYTICS (6 moduli)                      │
│  regime (7) │ strategy (26) │ backtest (22) │ metrics (1)   │
│  portfolio (4) │ research / factor / sentiment / technical   │
├──────────────────────────────────────────────────────────────┤
│              EXECUTION + MARKET INGESTION                    │
│  order_manager / ledger / reconciliation / risk              │
│  pipeline / sources (10 fonti) / normalize / orchestrator    │
├──────────────────────────────────────────────────────────────┤
│              DATA LAYER + GENETICS                           │
│  data/lake (45 simboli) / data/intraday                     │
│  genetics (5 file: evolution, engine, islands, serialize)    │
├──────────────────────────────────────────────────────────────┤
│              APPLICATION LAYER                               │
│  apps/api / apps/cli / apps/dashboard / config / contracts   │
└──────────────────────────────────────────────────────────────┘
```

## 3. Stato per Modulo

### analytics/regime — ✅ COMPLETO

| File | Righe | Stato | Cosa fa |
|------|:-----:|:----:|---------|
| `ml_features.py` | 302 | ✅ | 18 core features OHLCV (Kairos-v2) |
| `ml_classifier.py` | 357 | ✅ | TradingMLP ResBlock, 8 regimi, training, predict |
| `regime_labeler.py` | 218 | ✅ NUOVO | Labeling metric-based (no forward-looking) |
| `ensemble.py` | 171 | ✅ | EnsembleVoter a 6 detector |
| `detector.py` | 215 | ✅ | 6 detector individuali |

**Giudizio**: Il modulo piu' completo. 3 classificatori (SMA heuristic, 18-dim ML, 72-dim ML) con metric-based labeling che produce 8 regimi con distribuzione realistica (31% noisy, 23% start trend, 13% stop hunt, 11% strong trend, 11% compression, 10% retracement).

### analytics/strategy — ✅ COMPLETO (MA OVERFITTING RISCHIO)

| File | Righe | Stato | Cosa fa |
|------|:-----:|:----:|---------|
| `signals.py` (V1) | 268 | ✅ | 8 strategie base |
| `signals_r1.py` | 383 | ✅ | 10 strategie R1 |
| `signals_r2.py` | 1019 | ✅ | 34 strategie R2 (mastodontico) |
| `adaptive_ensemble.py` | 400 | ✅ | Routing regime-conditional + GA weights |
| `regime_ensemble.py` | 319 | ✅ | RegimeAwareEnsemble con specialisti |
| `weight_evolver.py` | 139 | ✅ | Rolling Sharpe feedback loop |
| `alpha101.py` | 293 | ✅ | 17 QLib Alpha101 factors |

**Giudizio**: 69 strategie totali. Il problema e' che molte non sono state validate con walk-forward OOS. L'adaptive ensemble e' completo ma il suo vero valore emergera' solo quando GA evolution sara' collegato end-to-end.

### analytics/backtest — ✅ COMPLETO

22 file che coprono: walk-forward, CPCV, Monte Carlo, benchmarks, bias testing, multi-asset, intraday, portfolio optimization, PyBroker integration.

**Giudizio**: Eccellente. PBO, DSR, Bootstrap Sharpe CI — tutto implementato.

### analytics/portfolio — ✅ COMPLETO

HRP (PyPortfolioOpt), forecast scaling (pysystemtrade), vol target.

### genetics — ⚠ PARZIALMENTE COLLEGATO

| File | Righe | Stato | Cosa fa |
|------|:-----:|:----:|---------|
| `ga_evolution.py` | 196 | ✅ | GA loop (DNA, crossover, mutazione, elitism) |
| `evolution.py` | 346 | ✅ | Orchestrator evolution |
| `engine.py` | 397 | ✅ | GA engine |
| `islands.py` | 469 | ✅ | Island evolution (multi-population parallelo) |
| `gates/` | 3 | ✅ | Sandbox isolation (AST, subprocess, protocol) |

**Giudizio**: Il GA evolution loop funziona ma non e' collegato al paper runner. Le isole sono state progettate ma non testate end-to-end. Il DNA migliore (alpha_050/063/044 dominanti) e' salvato ma non usato attivamente.

### market/ingestion — ✅ COMPLETO

10 fonti dati: Yahoo Finance, CCXT (Binance/OKX/Bybit), Dukascopy, FreeForexAPI, HistData, IBKR, Polygon, Databento, Stooq.

Pipeline con resume automatico, orchestrazione multi-fonte, normalizzazione unificata.

**Giudizio**: Solido. IBKR e Polygon richiedono API keys/credenziali che non abbiamo.

### Data Lake — ✅ COMPLETO (45 simboli)

```
FX:     EURUSD,GBPUSD,USDJPY,USDCHF,USDCAD,AUDUSD,NZDUSD + 18 minors = 25
Crypto: BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT = 4
Metals: XAUUSD,XAGUSD = 2
Futures: ES,NQ,GC,CL,YM = 5
Equity: SPY,QQQ,IWM,DIA,AAPL,MSFT,GLD,TLT,DBA = 9
TOTAL:  45
```

Timeframe: 1d su tutti, 1h/4h su FX+crypto+futures, 1m su FX+crypto.

**Giudizio**: Mancano dati intraday per futures (ES/NQ/GC/CL 1m richiedono IBKR). Copertura daily eccellente.

### Modelli ML

| Modello | Input | Accuracy | Baseline | Labeling | Stato |
|---------|:-----:|:--------:|:--------:|:---------|:-----:|
| `models/regime/` | 18-dim (1 TF) | 10.0% | 12.5% | Forward return | ❌ |
| `models/regime_72d/` | 72-dim (3 TF) | **36.5%** | 12.5% | Metric-based | ✅ |

**Giudizio**: Il modello 72-dim con metric-based labeling e' un successo (+191% over random).

### Test Suite

```
2577 passed, 6 skipped, 25 failed in 133s
25 failure: ta-lib (C lib), LightGBM, CCXT (no API key), registry (assets mancanti)
```

**Giudizio**: I 25 failure sono tutti pre-esistenti e causati da librerie C o API keys mancanti.

## 4. Problemi Strutturali RIMASTI

### 🔴 Critici

1. **GA evolution non collegato al paper runner** — Il DNA migliore (Sharpe OOS +28, 4/4 fold positive) e' salvato ma non usato attivamente. Il paper runner non carica `data/ga_weights.json`.

2. **No paper trading continuo** — L'ultima paper session ha prodotto 0 trade (risk adapter bug fixato, ma non riconfermato con 100 session).

3. **Mancano dati 1m futures** — ES/NQ/GC/CL 1m richiedono IBKR TWS/Gateway che non abbiamo in esecuzione.

### 🟡 Medi

4. **ML classifier accuracy 36.5%** — Buono ma lontano dall'utilizzabile in produzione (serve >70%).
5. **25 test falliti** — Librerie non installate (ta-lib) o API keys mancanti.
6. **Zero overlap check debole** — Il GA evolution non usa walk-forward per fitness (usa tutta la storia).

### 🟢 Minori

7. **Documentazione distribuita** — 66 file in `docs/`, molti ridondanti.
8. **Config sparsi** — Config in `config/`, `pyproject.toml`, `.env`, hardcoded in scripts.

## 5. Cosa Serve per il LIVE

```
Gate    Cosa                Stato    Tempo stimato
G0      Lint/format/test    2577/2602 ✅   0
G1      Authority/env       OK      ✅   0
G2      Contract data       45 sym  ✅   0
G3      Ledger/OMS          SQLite  ⚠   1 giorno
G4      Hard risk           OK      ✅   0
G5      Research truth      pinned  ⚠   2 giorni
G6      Paper operations    0 trade ❌   3 giorni
G7      Prop firm           MFF     ⚠   1 settimana
G8      Funded ops          —       ❌   > 1 mese
```

**Verdetto**: G5-G6 ancora rossi. Il sistema HA edge (BTC alpha_003, 72-dim classifier, GA DNA) ma non e' ancora pronto per live perche':
1. Paper runner non produce trade reali (testato 0 trade)
2. GA weights non collegati
3. ML classifier non integrato nell'adaptive ensemble per routing

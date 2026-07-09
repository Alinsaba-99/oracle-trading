# Project Oracle — Systematic Trading Intelligence Platform

> *"Un Bloomberg Terminal sotto steroidi con autopilot."*
> Multi-agent AI trading system · Genetic strategy evolution · Real-time market oracle

---

## Vision

Sistema di trading end-to-end completamente autonomo che integra:

- **Multi-Agent AI**: agenti specializzati (macro, tecnico, fondamentale, sentiment, rischio) che collaborano come un hedge fund institutionale
- **Evoluzione Genetica**: algoritmi genetici che scoprono e fanno evolvere strategie alpha con walk-forward validation
- **Bloomberg-Grade Analytics**: dashboard onnicomprensiva, analisi multi-timeframe, screening multi-asset
- **Autopilot**: esecuzione autonoma con risk management, adattamento ai cambiamenti di regime
- **Oracolo Real-Time**: opportunità sia di breve (volatilità estrema) che di lungo termine (value investing, nicchie di mercato)

---

## Architettura a 6 Strati

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LAYER 5: MONITORING & UI                                 │
│  Dashboard Terminal · P&L Analytics · Risk Monitor · Alerting · Agent Logs │
├─────────────────────────────────────────────────────────────────────────────┤
│                    LAYER 4: EXECUTION ENGINE                                │
│  Order Manager · Smart Routing · Multi-Broker · Algo Execution (VWAP/TWAP) │
├─────────────────────────────────────────────────────────────────────────────┤
│                    LAYER 3: MULTI-AGENT SYSTEM                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │  Macro   │ │Technical │ │Fundamental│ │ Sentiment│ │  Alpha   │         │
│  │  Analyst │ │ Analyst  │ │  Analyst  │ │ Analyst  │ │Researcher│         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────────┐           │
│  │  Risk    │ │ Portfolio│ │  Genetic │ │   Market Oracle     │           │
│  │  Manager │ │ Manager  │ │Strategist│ │  (Regime Detector)  │           │
│  └──────────┘ └──────────┘ └──────────┘ └─────────────────────┘           │
├─────────────────────────────────────────────────────────────────────────────┤
│                    LAYER 2: STRATEGY GENERATION                             │
│  Genetic Algorithm Engine · Backtesting Pipeline · Walk-Forward Opt        │
│  Factor Mining · Regime Detection · Meta-Learning · Ensemble               │
├─────────────────────────────────────────────────────────────────────────────┤
│                    LAYER 1: ANALYTICS ENGINE                                │
│  Technical Indicators (TA-Lib) · Fundamental Analysis · Sentiment NLP      │
│  Macro Data · Risk Metrics (VaR/CVaR/Greeks) · Factor Models · Features   │
├─────────────────────────────────────────────────────────────────────────────┤
│                    LAYER 0: DATA INFRASTRUCTURE                             │
│  Real-Time Feeds (WebSocket) · Historical Store (QuestDB) · Cache (Redis)  │
│  Message Queue (NATS) · Alternative Data · On-Chain · Normalization        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stato dell'Arte (Ricerca)

| Progetto | Stelle | Lezione per Oracle |
|----------|--------|--------------------|
| **TradingAgents** (91.3k ★) | Multi-agent LLM trading su LangGraph con analyst, researcher, risk e portfolio manager | Architettura agenti + checkpoint + persistenza |
| **QuantAgent** (nuovo) | 4 agenti paralleli per HFT, open-source da CMU/Yale/Stony Brook | Parallelismo agnostico al LLM |
| **ai-hedge-fund** (55k+ ★) | 6 agenti LLM su LangGraph, segnale majority-vote | Pattern disaccordo produttivo + blind spot mapping |
| **nautilus_trader** | Backtesting HFT-grade, core in Rust, IBKR/Binance connector | Base execution engine + backtesting |
| **vectorbt** | Backtesting vettoriale accelerato Numba | Validazione strategie rapida |

### Pattern Architetturali Chiave

1. **Disaccordo Produttivo**: agenti con ciechi complementari — l'analista tecnico non vede i fondamentali e viceversa
2. **Separazione Deterministico/LLM**: calcoli numerici in codice deterministico, LLM solo per sintesi e pattern recognition
3. **Debate Strutturato**: team bull/bear dibattono prima di una decisione
4. **Confidence Calibration**: LLM sono sistematicamente overconfident — necessaria calibrazione esterna
5. **Walk-Forward Validation**: 50% haircut su Sharpe backtestati vs reali

---

## Sistema Multi-Agente: Design

### Agenti di Analisi (paralleli, non vedono output altrui)

| Agente | Input | Output | Blind Spot |
|--------|-------|--------|------------|
| **Macro Analyst** | GDP, CPI, rates, yield curve, PMI | Regime macro, asset rotation | Ignora micro e price action |
| **Technical Analyst** | OHLCV, order book, volume | Trend, S/R, momentum, vol regime | Ignora perché un asset vale X |
| **Fundamental Analyst** | Bilanci, ratios, DCF, insider | Intrinsic value, margin of safety | Ignora timing di mercato |
| **Sentiment Analyst** | News, social, earnings calls | Market mood, contrarian signals | Non distingue saggezza da panico |
| **Alpha Researcher** | Tutti i dati, cross-asset, fattori | Statistical arb, pair trades | Overfitting |

### Agenti di Controllo (in serie, vedono tutto)

| Agente | Funzione |
|--------|----------|
| **Risk Manager** | Position sizing (Kelly), VaR/CVaR, drawdown limits, correlation check |
| **Portfolio Manager** | Decisione finale BUY/SELL/HOLD, allocazione, rebalancing |
| **Market Oracle** | Regime detection (HMM), volatilità, fase mercato, liquidità |
| **Genetic Strategist** | Evolve nuove strategie via GA, backtest, walk-forward |

---

## Genetic Strategy Evolution

### Genoma
```python
entry_conditions: List[Rule]       # Regole tecniche + fondamentali
exit_conditions: List[Rule]        # TP, SL, trailing
position_sizing: SizingRule        # Kelly, fixed, vol-adjusted
filters: List[Filter]              # Market cap, volume, settore
timeframe: Timeframe               # 1m → 1w
asset_universe: Universe           # Asset screenati
risk_params: RiskParams            # Max DD, posizione max
```

### Algoritmo
- **Selezione**: Tournament (size 3) + elitismo (top 5%)
- **Crossover**: Uniforme con swap a livello di regola
- **Mutazione**: Perturbazione gaussiana, add/remove regole
- **Island Model**: Popolazioni parallele con migrazione periodica
- **Fitness Multi-Obiettivo**: Sharpe, Sortino, Calmar, MaxDD (NSGA-II)
- **Walk-Forward**: Rolling window IS/OOS con penalità overfitting

---

## Tech Stack

| Layer | Tecnologia |
|-------|-----------|
| **Core Language** | Python 3.12+ (Rust per hot path) |
| **Agent Framework** | LangGraph + Custom orchestration |
| **Backtesting** | nautilus_trader + vectorbt |
| **Genetic Algorithm** | DEAP + PyGAD |
| **Time-Series DB** | QuestDB / ClickHouse |
| **Cache/Stream** | Redis + NATS |
| **Workflow** | Temporal / Prefect |
| **Broker API** | IBKR + Binance (nautilus_trader), CCXT |
| **Dashboard** | Streamlit / Dash |

### Data Sources
| Tipo | Fonti |
|------|-------|
| **Prezzi US** | Yahoo Finance, Alpha Vantage, Polygon.io |
| **Crypto** | Binance WS, Coinbase WS, Kraken |
| **Macro** | FRED, World Bank, TradingEconomics |
| **News** | NewsAPI, StockTwits, Reddit, X API |
| **Fundamentals** | Financial Modeling Prep, SEC EDGAR |
| **On-Chain** | Glassnode, Dune Analytics |

---

## Fasi Implementazione (26 settimane)

### Phase 0: Foundation (wk 1-2)
Scaffold, data pipeline, QuestDB, domain models, configurazione

### Phase 1: Analytics Engine (wk 3-4)
Technical indicators, fundamental module, sentiment NLP, macro connector, feature pipeline

### Phase 2: Backtesting (wk 5-6)
nautilus_trader integration, metriche, walk-forward, bias correction, benchmark

### Phase 3: Genetic Engine (wk 7-10)
DEAP GA, genome encoding, operatori, NSGA-II, island model, population management

### Phase 4: Multi-Agent System (wk 11-16)
LangGraph, 5 analyst agents, debate team, risk manager, portfolio manager, market oracle, genetic strategist

### Phase 5: Execution (wk 17-18)
Order manager, broker connectors, paper trading, algo execution, position tracking

### Phase 6: UI & Monitoring (wk 19-20)
Dashboard, P&L analytics, risk monitor, agent logs, alerts (Telegram/webhook)

### Phase 7: Autopilot (wk 21-26)
Continual learning, meta-strategy ensemble, adaptive risk, anomaly detection, explainable AI

---

## Prossimo Passo

Conferma della visione e delle scelte tecnologiche, poi partiamo con **Phase 0**.

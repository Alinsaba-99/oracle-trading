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

## Tech Stack (Attuale)

| Layer | Tecnologia |
|-------|-----------|
| **Core Language** | Python 3.12+ |
| **Agent Framework** | LangGraph 1.2.9 |
| **Backtesting** | vectorbt + nautilus_trader (event-driven) |
| **Genetic Algorithm** | DEAP 1.4 (NSGA-II, island model) |
| **Experiment Registry** | SQLite (aiosqlite, pydantic) |
| **Cache** | LRU in-memory + Redis (previsto) |
| **Message Bus** | NATS (core.events) |
| **Broker API** | ib_insync (IBKR), CCXT (100+ crypto) |
| **LLM** | litellm (multi-provider: GPT-4, Claude, locale) |
| **DataFrames** | Polars + NumPy |
| **Indicatori** | TA-Lib + Polars-native |
| **Dashboard** | Streamlit / Dash (Phase 6) |

### Data Sources (Integrati)
| Fonte | Dati | API Key |
|-------|------|---------|
| **Yahoo Finance** | OHLCV US equities/ETF | No |
| **CoinPaprika** | Crypto 7000+ | No |
| **FRED** | Macro (GDP, CPI, rates) | Sì |
| **Binance WS** | Crypto real-time | No |

---

## Roadmap — Stato Attuale

```
Phase 0: Foundation          ✅  2c2b254   Config, errors, logging, plugins, CLI
Phase 1: Analytics Engine    ✅  7b4e23c   Indicatori, regime, sentiment, feature store
Phase 2: Backtesting         ✅  fc853e3   vectorbt, WFA, bias correction, portfolio opt
Phase 3: Genetic Engine      ✅  aca4c75   DEAP, NSGA-II, island model, 50 alpha factors
Phase 3.5: Signal Opt        🔧  IN CORSO  Heikin Ashi, KNN, class balancing, alpha hybrid
Phase 4: Multi-Agent System  ✅  8ed640d   LangGraph, 3 analyst, debate, risk/portfolio mgr
Phase 5: Execution Engine    ✅  f6f8e88   OrderManager, IBKR, CCXT, 3 algos, CLI
Phase 6: UI & Dashboard      ⬜  PROSSIMO  Streamlit, P&L analytics, risk monitor
Phase 7: Autopilot            ⬜           Continual learning, meta-strategy, adaptive risk
```

**9 commit · 21 file doc · 19/19 showcase · ruff+mypy clean**

### Phase 3.5: Signal Optimization (in corso)

Obiettivo: risolvere la convergenza piatta del GA producendo segnali con edge reale.

| Task | Stato | Cosa |
|------|-------|------|
| T1: Heikin Ashi | ✅ | Conversione OHLCV → HA per segnali smooth |
| T2: KNN balancing | ✅ | Class weighting + distance-weighted vote |
| T3: Hybrid signal | ⬜ | KNN + 50 alpha factors combinati |
| T4: GA ottimizzata | ⬜ | pop=20, gen=20, 4 isole, 5-fold WFA |

### Phase 6: UI & Dashboard (planning)

Streamlit dashboard con:
- P&L analytics, equity curve, drawdown
- Risk monitor (VaR/CVaR, exposure)
- Agent logs e decisioni MAS
- Alert Telegram/webhook

### Phase 7: Autopilot (future)

- Continual learning su nuovi dati
- Meta-strategy ensemble (top-N Pareto strategies)
- Adaptive risk (regime-aware position sizing)
- Anomaly detection su execution
- Explainable AI per decisioni agenti

---

## Prossimo Passo

Completare **Phase 3.5** per sbloccare Sharpe > 0.8 in backtest,
poi **Phase 6** (Dashboard Streamlit) per visualizzare risultati in tempo reale.

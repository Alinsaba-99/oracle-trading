# Oracle — Inalpha + VARRD Integration Blueprint

> **Stato**: Proposta   |   **Base**: audit-remediation-beta (HEAD `a5ef2dc`)
> **Riferimenti**: [Inalpha](https://github.com/mirror29/inalpha) · [VARRD](https://github.com/augiemazza/varrd) · [awesome-systematic-trading](https://github.com/wangzhe3224/awesome-systematic-trading)
> **Ultimo aggiornamento**: 2026-07-24

---

## Indice

1. [Executive Summary](#1-executive-summary)
2. [Diagnosi: perché siamo bloccati](#2-diagnosi-perché-siamo-bloccati)
3. [Pilastro 1 — Factor Timing (da Inalpha)](#3-pilastro-1--factor-timing)
4. [Pilastro 2 — Strategy Generation Loop (da Inalpha)](#4-pilastro-2--strategy-generation-loop)
5. [Pilastro 3 — Research Memory & Confidence](#5-pilastro-3--research-memory--confidence)
6. [Pilastro 4 — HMM + Lorenzian Classification](#6-pilastro-4--hmm--lorenzian-classification)
7. [Pilastro 5 — VARRD-style Edge Discovery](#7-pilastro-5--varrd-style-edge-discovery)
8. [Roadmap Integrata](#8-roadmap-integrata)
9. [Cosa abbiamo già (asset inventory)](#9-cosa-abbiamo-già-asset-inventory)

---

## 1. Executive Summary

**Problema**: Oracle ha 37K LOC di infra (Ledger, OMS, 2 backtest engines, GA, agent committee, paper broker, risk kernel) ma **nessun loop che le colleghi**. I pezzi sono isole. Il progetto avanza per gate (G0→G9) ma l'unico "output" sono i paper session report — non c'è un sistema che impari e migliori da solo.

**Soluzione**: Integrare tre pattern da **Inalpha** e uno da **VARRD** per chiudere il loop:

```
  Fattori (statistici) ──→  Rank IC ──→  Agent sceglie strategia
        ↑                                              │
        │                                     Backtest engine
        │                                              │
        │                                   ┌──────────┘
        │                                   ▼
  Decay detection ←── Ledger ←── Paper ←── Promuovi se OK
        │                              ↑
        └── Research memory ───────────┘
```

I 5 pilastri, in ordine di impatto:

| Pilastro | Origine | Impatto | Sforzo |
|:--------:|:-------:|:-------:|:------:|
| **Factor Timing** | Inalpha | 🔴 Alto — sblocca tutto | 3-5gg |
| **Strategy Gen Loop** | Inalpha | 🔴 Alto — chiude il loop | 5-8gg |
| **Research Memory** | Proprio | 🟡 Medio — evita errori | 3-4gg |
| **HMM + Lorenzian** | Proprio + math | 🟡 Medio — classifica regimi | 2-3gg |
| **Edge Discovery** | VARRD | 🟢 Basso — ispirazione | 1-2gg |

---

## 2. Diagnosi: perché siamo bloccati

### Quello che abbiamo (asset da usare, non da riscrivere)

| Cosa | LOC | Dov'è | Perché è bloccato |
|------|:---:|:-----:|:-----------------:|
| 50 fattori alpha | 1028 | `genetics/alpha/factors.py` | **Statici** — nessuno li classifica per IC corrente |
| 2 backtest engine | 925 | `analytics/backtest/engines/` | **Isolati** — nessuno li chiama automaticamente |
| Paper broker | 508 | `execution/brokers/paper.py` | **Usato solo per sessioni manuali** |
| GA engine | 397 | `genetics/engine.py` | **Registry non cablato** — evolve parametri ma non produce strategie |
| Agenti (analysts + committee) | 3.4K | `agents/` | **Nessun feedback** — non sanno se le loro idee hanno funzionato |
| HMM detector | 129 | `analytics/regime/detectors/hmm.py` | **Standalone** — non alimenta le decisioni |
| Strategy signals | 267 | `analytics/strategy/signals.py` | **Usati solo in sweep** — non nel loop live |
| Regime ensemble | 171 | `analytics/regime/ensemble.py` | **Non collegato** al factor timing |

### Pattern vincenti da Inalpha

**Inalpha** è il progetto più simile al nostro con una differenza cruciale: **hanno chiuso il loop**. Ecco cosa fanno che noi no:

| Pattern | Inalpha | Oracle |
|---------|---------|--------|
| Factor timing | 79 fattori, **classificati per Rank IC corrente** in tempo reale | 50 fattori, **statici** |
| Strategy generation | LLM **scrive codice Python**, 3 sandbox, cross-val, promosso | GA **modifica parametri** di template fissi |
| Unified kernel | Stesso codice per backtest, paper e live (swap Clock+Gateway) | Engine separati (Nautilus vs vectorized) |
| Machine-approved orders | `propose → approve → execute` con token usa-e-getta | OMS con idempotency key, ma manca il three-step |
| Research debate | 6 analysts + panel leggende + bull/bear/risk | Committee + debate esistono, ma non producono strategie |
| CV anti-overfitting | WalkForward + PurgedKFold + CPCV + Deflated Sharpe | Solo walk-forward base |
| Skills procedurali | Markdown playbook caricati on-demand | Assente |

---

## 3. Pilastro 1 — Factor Timing

### Concetto

Invece di usare i fattori staticamente (es. "RSI(14) significa X"), **ogni fattore viene valutato per IC (Information Coefficient) corrente** rispetto ai rendimenti forward. I fattori sono ordinati per chi sta funzionando *adesso* — quando il mercato ruota, i fattori ruotano con lui.

### Architettura (da integrare in Oracle)

```
┌─────────────────────────────────────────────────────────────┐
│                    analytics/strategy/factor_timing/         │
│                                                             │
│  factor_rank.py     — Rank IC computation + ranking          │
│  effectiveness.py   — IC/ICIR, decay state, quantile return  │
│  backtest_score.py  — Factor→strategy→backtest→OOS Sharpe    │
│  panel.py           — Cross-sectional Rank IC                │
│  catalog.py         — Registry dei fattori disponibili       │
│  data_client.py     — Bar feed per compute                   │
└─────────────────────────────────────────────────────────────┘
```

### Flusso

```
1. Agent chiede: "quali fattori funzionano per ES ora?"
2. FactorTimingEngine:
   a. Prende N bar di close per ES
   b. Per ogni fattore nel catalogo (50 da factors.py):
      - Calcola serie del fattore su bar
      - Calcola forward return (horizon H)
      - Rank IC = spearman(rank(f_t), rank(r_{t+H}))
      - ICIR = mean(IC) / std(IC)
      - Decay state = stable / fading / decaying
   c. Ordina fattori per |Rank IC| discendente
   d. Ritorna top-10 con IC, direction, decay
3. Oracle usa i top fattori per comporre segnale
```

### Cosa abbiamo già

- `genetics/alpha/factors.py` — **50 fattori già implementati** in Polars (momentum, mean-reversion, volatility, correlation, volume, pattern)
- `analytics/backtest/data.py` — Data loader per bar
- `analytics/strategy/signals.py` — Strategy signals già cablati
- `analytics/regime/detectors/` — Regime detection per contesto

### Cosa serve

| Componente | Codice | Stato |
|-----------|:------:|:-----:|
| `factor_timing/effectiveness.py` | Rank IC, ICIR, decay_state | **Da scrivere** (~200 loc, port da Inalpha) |
| `factor_timing/factor_rank.py` | Scoring engine | **Da scrivere** (~150 loc) |
| `factor_timing/catalog.py` | Registro fattori con metadata | **Da scrivere** (~80 loc) |
| Collegamento a `agents/oracle/` | Agent tool per query fattori | **Da scrivere** (~100 loc) |

### Port dalla codebase Inalpha

I file da cui prendere ispirazione diretta:

| File Inalpha | LOC | Cosa fa | Integrazione |
|:------------|:---:|:--------|:------------|
| `services/factor/.../effectiveness.py` | 378 | Rank IC, ICIR, null_ic_benchmark, decay_state | Port quasi integrale |
| `services/factor/.../engine.py` | 1117 | Factor engine orchestrator | Pattern architetturale |
| `services/factor/.../backtest_score.py` | 431 | Factor→strategy→backtest loop | Adattare ai nostri engine |
| `services/factor/.../expression.py` | 386 | DSL per espressioni fattori | Opzionale, sostituibile con `factors.py` |
| `services/factor/.../panel.py` | 129 | Cross-sectional IC | Per basket ranking |

### Metriche chiave del factor timing (da Inalpha)

| Metrica | Cosa misura | Soglia |
|---------|-------------|--------|
| `rank_ic` | Spearman rank correlation tra fattore e forward return | \|IC\| > 0.02 → segnale |
| `icir` | IC / std(IC) — stabilità del segnale | > 0.5 → interessante |
| `decay_state` | stable / fading / decaying | decaying → weight=0 |
| `null_ic_benchmark` | E[ max \|IC\| \| noise ] con N candidati | IC < benchmark → rumore |
| `quantile_returns` | Return medio per quintile del fattore | Q1 >> Q5 → direzionale |

---

## 4. Pilastro 2 — Strategy Generation Loop

### Concetto

L'agente **non modifica parametri**, ma **scrive intere strategie in Python**. Le strategie passano tre sandbox, vengono cross-validate, e se superiori al baseline (buy-and-hold) vengono **promosse a paper live**. Il loop è:

```
Agent → scrive strategia → AST audit → subprocess check → contract check
    → backtest (WalkForward CV) → fitness > baseline? → promuovi a paper
    → runner live su barre reali → ledger registra → decay? → sostituisci
```

### Architettura (da integrare in Oracle)

```
┌──────────────────────────────────────────────────────────────┐
│                    genetics/evolver/                          │
│                                                              │
│  governor/loop.py       — E1 evolution main loop             │
│  governor/hints.py      — HintGenerator per mutazione        │
│  governor/seed.py       — Seed strategy templates            │
│  mutator/llm.py         — LLM mutation client                │
│  mutator/prompts.py     — Prompt templates per mutation      │
│  sandbox/ast_audit.py   — Static AST security audit          │
│  sandbox/subprocess.py  — Isolated subprocess run            │
│  sandbox/contract.py    — Strategy protocol verification     │
│  evaluator/fitness.py   — Multi-objective fitness function   │
│  evaluator/runner.py    — Backtest runner per candidate      │
│  population/candidate.py— Candidate + EvolutionRun models    │
│                                                              │
│  crossval/walkforward.py — WalkForward splitter              │
│  crossval/purgedkf.py    — Purged K-Fold (López de Prado)    │
│  crossval/cpcv.py        — Combinatorial Purged CV           │
│  crossval/deflated.py    — Deflated Sharpe Ratio             │
└──────────────────────────────────────────────────────────────┘
```

### Flusso di una generazione

```
1. HINT: Agent riceve hint "prova ad aggiungere un filtro RSI"
2. MUTATION: LLM modifica il codice Python della strategia
3. SANDBOX 1 (AST): Controlla che non ci siano eval(), exec(), import pericolosi
4. SANDBOX 2 (subprocess): Esegue in isolamento per verificare non-bloccante
5. SANDBOX 3 (contract): Verifica che rispetti Strategy protocol
6. BACKTEST: Esegue WalkForward CV con gli engine esistenti
7. FITNESS: Sharpe + Calmar - turnover - drawdown (multi-obbiettivo)
8. BASELINE: Confronta con buy-and-hold
9. PROMOZIONE: Se fitness > baseline → candidate pool
10. LIVE RUNNER: Selezionato → promosso a paper runner su barre reali
```

### Cosa abbiamo già

- `analytics/backtest/engines/nautilus.py` (562 loc) — Event-driven backtest engine
- `analytics/backtest/engines/vectorized.py` (363 loc) — Vectorized engine
- `analytics/strategy/signals.py` (267 loc) — 4 strategy template (EmaTrend, RsiReversion, BbandReversion, DonchianBreakout)
- `analytics/strategy/evaluation.py` (254 loc) — Strategy evaluation
- `analytics/strategy/fitness.py` (115 loc) — Fitness function
- `execution/brokers/paper.py` (508 loc) — Paper broker per live runner
- `execution/session_guards.py` (344 loc) — Resilience per live session

### Cosa serve (nuovo)

| Componente | Codice | Ispirazione da Inalpha |
|-----------|:------:|:----------------------|
| `genetics/evolver/governor/loop.py` | ~200 loc | `services/evolver/.../governor/loop.py` (179 loc) |
| `genetics/evolver/mutator/llm_client.py` | ~150 loc | `services/evolver/.../mutator/llm_client.py` (133) |
| `genetics/evolver/mutator/prompt_templates.py` | ~160 loc | `services/evolver/.../mutator/prompt_templates.py` (157) |
| `genetics/evolver/mutator/diff_applier.py` | ~180 loc | `services/evolver/.../mutator/diff_applier.py` (173) |
| `genetics/evolver/sandbox/ast_audit.py` | ~80 loc | `services/evolver/.../sandbox/ast_audit.py` (20) + nostro |
| `genetics/evolver/sandbox/contract_check.py` | ~40 loc | `services/evolver/.../sandbox/contract_check.py` (30) |
| `genetics/evolver/evaluator/fitness.py` | ~80 loc | `services/evolver/.../evaluator/fitness.py` (48) |
| `genetics/evolver/evaluator/runner.py` | ~200 loc | `services/evolver/.../evaluator/runner.py` (167) |
| **Cross-validation** | | |
| `analytics/backtest/cv/walkforward.py` | ~100 loc | `services/paper/.../engine/cv.py` (256 loc, WalkForward + PurgedKFold + CPCV) |
| `analytics/backtest/cv/deflated_sharpe.py` | ~120 loc | `services/paper/.../engine/robustness.py` (216 loc) |
| `analytics/backtest/cv/robustness.py` | ~80 loc | PBO, Bootstrap Sharpe CI |

### Il three-step orders (da Inalpha)

Inalpha usa `propose → approve → execute` con token usa-e-getta. Oracle ha già l'idempotency key nell'OMS, ma manca il three-step esplicito. Da integrare:

```python
# agents/decision/three_step.py  (nuovo)
class ThreeStepOrder:
    plan_id: str
    status: Literal["proposed", "approved", "executed", "rejected"]
    approval_token: str | None  # one-shot, TTL-bound
    risk_check: RiskCheckResult
    ledger_preview: LedgerEntry
```

Questo è a bassa priorità perché l'OMS già garantisce idempotency — il three-step è un miglioramento di audit trail.

---

## 5. Pilastro 3 — Research Memory & Confidence

### Concetto

Ogni decisione dell'agente viene registrata con il suo esito. La prossima volta che l'agente si trova in una situazione simile, può dire: *"l'ultima volta che ho visto questo pattern, avevo ragione il 60% delle volte"*. Inoltre, la confidence del segnale viene **calibrata** usando:
- Accuratezza storica dell'agente in regime simile
- HMM regime corrente
- Rank IC corrente dei fattori usati

### Architettura

```
┌──────────────────────────────────────────────────────────────┐
│                    agents/confidence/                          │
│                                                              │
│  memory.py        — ResearchMemory: salva/carica outcome      │
│  calibrator.py    — ConfidenceCalibrator: calibra probabilità  │
│  tracker.py       — DecisionTracker: traccia ogni decisione   │
│  decay.py         — DecayMonitor: rileva strategie in declino │
└──────────────────────────────────────────────────────────────┘
```

### Flusso

```
1. Oracle decide: "long ES, 2 contract"
2. DecisionTracker registra:
   - timestamp, side, quantity
   - regime corrente (HMM)
   - fattori usati e loro IC
   - confidence stimata
3. Dopo N bar (orizzonte prefissato):
   - Ledger rivela P&L realizzato
   - Memory registra: predetto=true/falso, confidence, risultato
4. Alla prossima decisione simile:
   - Calibrator cerca nel memory: "quando ero in regime bear con fattori momentum,
     avevo accuracy del 40%" → scoraggio la decisione
```

### Cosa abbiamo già

- `agents/confidence.py` (88 loc) — Confidence scoring base
- `core/ledger.py` (202 loc) — Ledger che registra ogni fill
- `analytics/regime/detectors/hmm.py` (129 loc) — Regime detection

### Cosa serve

| Componente | LOC | Note |
|-----------|:---:|------|
| `agents/confidence/memory.py` | ~150 | ResearchMemory — SQLite store di decisioni + esiti |
| `agents/confidence/calibrator.py` | ~120 | Platt scaling / isotonic regression su accuracy storica |
| `agents/confidence/tracker.py` | ~100 | Hook nel decision path per registrare ogni chiamata |
| `agents/confidence/decay.py` | ~80 | DecayMonitor — finestra mobile per rilevare degradazione |

---

## 6. Pilastro 4 — HMM + Lorenzian Classification

### Concetto

**HMM** (già esistente in `analytics/regime/detectors/hmm.py`) modella i regimi di mercato come stati nascosti di una catena di Markov. La **Lorenzian classification** è un metodo di classificazione non-lineare basato sulla metrica dello spazio di Lorenz — utile per rilevare **transizioni di regime** laddove le distribuzioni gaussiane (assunte dall'HMM) falliscono, specialmente in mercati con code pesanti e non-linearità.

### Perché Lorenzian

L'HMM assume che i rendimenti in ogni stato siano distribuiti come gaussiane multivariate. In pratica:
- I rendimenti finanziari hanno **code pesanti** (tailedness) — l'HMM sottostima gli eventi estremi
- Le **transizioni di regime** non sono markoviane lineari — a volte il mercato "salta" da bull a crash senza passare per volatile
- La **Lorenzian classification** non assume gaussianità e cattura meglio la geometria non-lineare dello spazio degli stati

### Architettura

```
┌──────────────────────────────────────────────────────────────┐
│              analytics/regime/classification/                 │
│                                                              │
│  lorenzian.py    — LorenzianClassifier (k-NN su spazio Lorenz)│
│  ensemble.py     — RegimeEnsemble (HMM + Lorenzian + voting) │
│  transition.py   — TransitionDetector (cambia regime in corso)│
│  features.py     — Feature engineering per regime detection   │
└──────────────────────────────────────────────────────────────┘
```

### Integrazione con Factor Timing

```
HMM (Gaussian) + Lorenzian (non-parametric) → ensemble vote
       │                                             │
       ▼                                             ▼
Regime corrente (bull/bear/choppy/volatile)    Confidenza transizione
       │                                             │
       └─────────────┬───────────────────────────────┘
                     ▼
            Pesi fattori aggiustati per regime:
            - bull: momentum + breakout pesati di più
            - bear: mean-reversion + vol pesati di più
            - choppy: mean-reversion + pair trading
            - volatile: vol factors + stop-loss stretti
```

### Cosa abbiamo già

- `analytics/regime/detectors/hmm.py` (129 loc) — HMM detector
- `analytics/regime/detectors/bocd.py` (88 loc) — Bayesian online change point
- `analytics/regime/detectors/vol_cluster.py` (137 loc) — Volatility cluster
- `analytics/regime/ensemble.py` (171 loc) — Ensemble di detector

### Cosa serve

| Componente | LOC | Dettaglio |
|-----------|:---:|----------|
| `analytics/regime/classification/lorenzian.py` | ~180 | Lorenzian classifier: k-NN su embedding Lorenz |
| `analytics/regime/classification/features.py` | ~120 | Feature engineering: rendimenti, vol, skew, kurt, correlation |
| `analytics/regime/classification/transition.py` | ~100 | TransitionDetector: finestra mobile su ensemble vote |
| `analytics/regime/classification/ensemble.py` | ~80 | RegimeEnsemble: HMM + Lorenzian + BOCD voting |

### Lorenzian Classification — Concept

La Lorenzian classification si basa sullo **spazio di Lorenz** (da Lorenz 1963, non il Lorenz di attractor caotico ma la generalizzazione per classification). L'idea:

1. **Embedding**: proietta le serie temporali in uno spazio di feature a N dimensioni usando rendimenti, vol, skewness, kurtosis, autocorrelazione.
2. **Distanza Lorenziana**: metrica non-euclidea che misura la divergenza tra due distribuzioni multivariate considerando le dipendenze di coda:

   $$d_L(x,y) = \sum_{i=1}^n |F_i(x_i) - F_i(y_i)|^\alpha$$

   dove $F_i$ è la CDF empirica della i-esima feature e $\alpha < 1$ enfatizza le code.
3. **k-NN**: classifica il punto corrente nello spazio Lorenz usando i k vicini più prossimi dal training set, dove i vicini sono segmenti storici di regime noto.
4. **Transizione**: quando il punto corrente si allontana dal cluster del regime attuale e si avvicina al cluster di un altro regime, segnala transizione.

Questo è **complementare all'HMM**: l'HMM cattura la dinamica sequenziale (transizioni di Markov), il Lorenzian cattura la **forma della distribuzione** corrente (code pesanti, asimmetria). L'ensemble dei due è più robusto di ciascuno da solo.

---

## 7. Pilastro 5 — VARRD-style Edge Discovery

### Concetto

VARRD permette di **scoprire pattern statisticamente validati** sui dati: l'AI propone un'ipotesi ("se RSI scende sotto 25 su ES, c'è rimbalzo?"), l'engine la testa con event study + Monte Carlo, e se supera il validation gate viene aggiunta all'edge library.

In Oracle, questo si manifesta come un **nuovo tool per l'agente**: `research.discover_edge` che:

1. Prende un'ipotesi in linguaggio naturale
2. La formalizza in un'espressione fattoriale (usando il nostro DSL o factors.py)
3. Esegue event study sul dataset storico
4. Calcola statistical significance (bootstrap p-value)
5. Se significativo, lo aggiunge al factor catalog come nuovo fattore
6. Il nuovo fattore entra nel Factor Timing (Pilastro 1)

### Architettura

```
┌──────────────────────────────────────────────────────────────┐
│              analytics/qualification/discovery/               │
│                                                              │
│  hypothesis.py   — Hypothesis formalization (NL → express.)   │
│  event_study.py  — Event study engine                         │
│  significance.py — Bootstrap p-value, multiple testing corr.  │
│  edge_library.py — Edge registry (nuovi fattori scoperti)     │
└──────────────────────────────────────────────────────────────┘
```

### Cosa abbiamo già

- `analytics/qualification/discovery.py` (120 loc) — Discovery engine esistente
- `analytics/qualification/statistics.py` (92 loc) — Statistical tests
- `analytics/qualification/report.py` (163 loc) — Report generation

### Cosa serve

| Componente | LOC | Note |
|-----------|:---:|------|
| `analytics/qualification/discovery/hypothesis.py` | ~120 | Natural language → formula |
| `analytics/qualification/discovery/event_study.py` | ~200 | Event study computation |
| `analytics/qualification/discovery/significance.py` | ~100 | Bootstrap + FDR correction |
| `analytics/qualification/discovery/edge_library.py` | ~80 | Edge storage e rotazione |

---

## 8. Roadmap Integrata

### Fase 1 — Factor Timing (settimana 1)

```
Obiettivo: i fattori vengono classificati per IC corrente
Output: tool "factor.timing" per l'agente Oracle

Task:
[ ] factor_timing/effectiveness.py    — Port da Inalpha (Rank IC, ICIR, decay)
[ ] factor_timing/catalog.py          — Registro con metadata dei 50 fattori
[ ] factor_timing/factor_rank.py      — Engine che ordina per IC
[ ] Collegamento agent tool           — agents/oracle/ aggiunge tool factor.timing
[ ] Test: factor timing su ES 1h     — Verifica decay detection
```

### Fase 2 — Research Memory (settimana 2)

```
Obiettivo: ogni decisione viene registrata, l'agente impara dagli errori
Output: confidence calibrata, report di accuracy

Task:
[ ] agents/confidence/memory.py       — ResearchMemory store
[ ] agents/confidence/tracker.py      — Hook nel decision path
[ ] agents/confidence/calibrator.py   — Platt scaling su accuracy storica
[ ] agents/confidence/decay.py        — DecayMonitor su strategie attive
[ ] Test: verificare che memory influenzi confidence
```

### Fase 3 — HMM + Lorenzian (settimana 2-3)

```
Obiettivo: regime detection più robusta con multi-modello
Output: RegimeEnsemble che alimenta factor timing

Task:
[ ] regime/classification/lorenzian.py      — Lorenzian classifier
[ ] regime/classification/features.py       — Feature engineering
[ ] regime/classification/ensemble.py       — HMM + Lorenzian + BOCD voto
[ ] regime/classification/transition.py     — Transition detector
[ ] Collegamento: factor timing pesato per regime
[ ] Test: confronto accuracy HMM solo vs ensemble
```

### Fase 4 — Strategy Generation Loop (settimana 3-4)

```
Obiettivo: l'agente genera strategie, le testa, le promuove a paper
Output: evolutor funzionante con almeno 1 strategia promossa

Task:
[ ] genetics/evolver/governor/loop.py     — Evolution main loop
[ ] genetics/evolver/mutator/llm.py       — LLM mutation client
[ ] genetics/evolver/mutator/prompts.py   — Prompt templates
[ ] genetics/evolver/sandbox/*            — 3 sandbox gates
[ ] genetics/evolver/evaluator/*          — Fitness + backtest runner
[ ] analytics/backtest/cv/*              — WalkForward, CPCV, DSR
[ ] Promozione a paper live               — Collegamento con execution/
[ ] Test: end-to-end loop con SMA crossover → mutate → backtest → promote
```

### Fase 5 — Edge Discovery (settimana 4-5)

```
Obiettivo: l'agente scopre nuovi fattori dai dati
Output: edge library con pattern validati

Task:
[ ] discovery/hypothesis.py         — NL → formula
[ ] discovery/event_study.py        — Event study engine
[ ] discovery/significance.py       — Bootstrap + FDR
[ ] discovery/edge_library.py       — Edge registry
[ ] Integrazione con factor timing  — Nuovi edge entrano nel ranking
```

### Fase 6 — Three-step Orders (settimana 5)

```
Obiettivo: audit trail più esplicito per ogni ordine
Output: propose → approve → execute con token

Task:
[ ] agents/decision/three_step.py   — ThreeStepOrder model
[ ] agents/decision/approval.py     — Approval token generator
[ ] Collegamento OMS                 — Bridge three-step → OMS.submit
[ ] Test: end-to-end order flow con three-step
```

---

## 9. Cosa abbiamo già (asset inventory)

### Fattori alpha (da usare subito per Factor Timing)

`genetics/alpha/factors.py` ha 50 fattori in 7 categorie:

| Categoria | Fattori | Esempi |
|-----------|:-------:|--------|
| Momentum | 9 | momentum_1m, momentum_3m, momentum_6m, momentum_12m |
| Mean-reversion | 7 | rsi_reversal, bb_pct_b, williams_r |
| Volatility | 6 | atr_ratio, bollinger_width, volatility_ratio |
| Correlation | 5 | corr_index, corr_bond, corr_vix |
| Volume | 6 | volume_ratio, volume_price_trend, obv_slope |
| Pattern | 8 | inside_bar, engulfing, doji, hammer, morning_star, evening_star, three_white, three_black |
| Combined | 9 | alpha101_001, alpha101_003, alpha101_006, alpha101_012, alpha101_018, alpha101_020, alpha101_024, alpha101_032, alpha101_036 |

Totale: **50 fattori** già implementati, testati, con gestione NaN/Inf e serie corte.

### Backtest engines (da usare per Strategy Generation)

| Engine | LOC | Vantaggio |
|--------|:---:|-----------|
| `analytics/backtest/engines/nautilus.py` | 562 | Event-driven, commissioni, slippage, PIT data |
| `analytics/backtest/engines/vectorized.py` | 363 | Veloce, vettoriale, buono per sweep |

### Regime detection (da combinare con Lorenzian)

| Detector | LOC | Tipo |
|----------|:---:|:----:|
| `hmm.py` | 129 | Gaussian HMM, 4 stati |
| `bocd.py` | 88 | Bayesian online change point detection |
| `pelt.py` | 83 | Pruned Exact Linear Time |
| `vol_cluster.py` | 137 | Volatility clustering |
| `correlation.py` | 92 | Correlation regime |
| `ensemble.py` | 171 | Voting ensemble di tutti i detector |

### Strategy signals (template per evolutor)

| Signal | LOC | Stile |
|--------|:---:|:------|
| `EmaTrend` | — | Trend following (EMA cross) |
| `RsiReversion` | — | Mean reversion (RSI oversold) |
| `BbandReversion` | — | Mean reversion (Bollinger bands) |
| `DonchianBreakout` | — | Breakout (prior N high) |
| `signals_r1.py` | 267 | 10+ additional strategies |

---

## Appendice A — Mappatura Inalpha → Oracle

| Modulo Inalpha | LOC | Equivalente Oracle | Gap |
|:-------------|:---:|:------------------|:----|
| `services/factor` | 3.4K | `genetics/alpha/factors.py` + nuovo `factor_timing/` | Factor timing non esiste |
| `services/paper` | 15K+ | `execution/brokers/paper.py` + `analytics/backtest/` | Unified kernel da costruire |
| `services/paper/engine/cv.py` | 256 | Nessuno | Cross-validation mancante |
| `services/paper/engine/robustness.py` | 216 | Nessuno | PBO/DSR mancanti |
| `services/evolver` | 1.5K | `genetics/engine.py` | LLM mutation invece di GA |
| `services/research` | 4K+ | `agents/` | Panel leggende mancante, debate simile |
| `packages/orchestration` | TS | `agents/orchestrator/` | Skills mancanti |
| `risk engine` | — | `policy/prop_firm/` | Simile, già coperto |

## Appendice B — Mappatura VARRD → Oracle

| Modulo VARRD | LOC | Equivalente Oracle | Gap |
|:------------|:---:|:------------------|:----|
| `client.py` | 600 | Nessuno | Client MCP per edge discovery |
| `skills/*.md` | — | Nessuno | Skills come memoria procedurale |
| Hypothesis → test | — | `analytics/qualification/discovery.py` | Event study + significance |

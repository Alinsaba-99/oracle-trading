# Oracle Trading — Analisi Import Graph e Dipendenze

> Data: 2026-07-30
> Progetto: oracle-trading (74K LOC, modular monolith)
> Riferimento: ARCHITECTURE.md §3.1 (dependency rule), §9 (deviazioni da chiudere)

---

## 1. Estratto delle Regole di Dipendenza (ARCHITECTURE.md §3.1)

```
Dall'esterno verso l'interno:
1. core/domain        — value object, enum, eventi; nessun import da apps, agents, analytics, execution, policy
2. application/contracts — PortfolioPlan, TradeIntent
3. application/services   — use case deterministici
4. adapters               — broker, database, provider dati, NATS, LLM
5. apps                   — composition root CLI/API/worker
```

Divieti espliciti (ARCHITECTURE.md §2.1 + §4):
- **execution** non deve importare contratti da **agents**
- **policy** non deve importare tipi da **execution**
- **analytics** e **market** non devono importarsi in entrambe le direzioni
- **analytics** non deve importare **execution**
- **genetics** non deve dipendere da **analytics** e **agents** non deve dipendere da **genetics**
- **agents** (intelligence plane) non deve importare **analytics** (research plane)

---

## 2. Mappa delle Dipendenze Attuali

```mermaid
flowchart TD
    agents --> core
    agents --> analytics     ❌ VIOLAZIONE
    agents --> genetics      ❌ VIOLAZIONE (TYPE_CHECKING)

    analytics --> core
    analytics --> execution   ❌ VIOLAZIONE
    analytics --> policy      ❌ VIOLAZIONE
    analytics --> market      ❌ VIOLAZIONE
    
    market --> analytics      ❌ VIOLAZIONE (ciclo)
    market --> core
    
    execution --> agents      ❌ VIOLAZIONE (docstring ref, non import reale)
    execution --> core
    
    policy --> execution      ❌ VIOLAZIONE
    policy --> core
    
    genetics --> analytics    ❌ VIOLAZIONE
    genetics --> core

    genetics <--> agents      ❌ VIOLAZIONE CICLO
    
    analytics <--> market     ❌ VIOLAZIONE CICLO
```

---

## 3. Tabella delle Violazioni

### 3.1 agents → analytics (Intelligence → Research — REVERSE)

| # | File | Line | Import | Severità |
|---|------|------|--------|----------|
| V1 | `agents/oracle/oracle.py` | 15-16 | `from analytics.regime.config import RegimeSettings` `from analytics.regime.detector import RegimeDetector` | 🔴 HIGH |

**Problema**: `agents/` (intelligence plane §4.1) importa direttamente `analytics/` (research plane §4.3). L'architettura dice che intelligence deve produrre decision contracts, non importare interni di research.

### 3.2 analytics → execution (Research → Safety Control — LATERALE)

| # | File | Line | Import | Severità |
|---|------|------|--------|----------|
| V2 | `analytics/qualification/execution.py` | 32-39 | `from execution.brokers.paper_engine import ...` `from execution.brokers.types import BrokerOrder, BrokerPosition` `from execution.order_manager.types import OrderRequest` | 🔴 HIGH |
| V3 | `analytics/backtest/providers.py` | 194 | `from execution.brokers.metaapi_client import MetaApiClient` (lazy import) | 🟡 MEDIUM |

**Problema**: Research plane importa safety control plane. Crea dipendenza laterale che rende il path di ricerca dipendente da dettagli implementativi di execution. La qualification engine dovrebbe dipendere da porte (interfacce), non da implementazioni concrete di broker/order_manager.

### 3.3 analytics → policy (Research → Policy)

| # | File | Line | Import | Severità |
|---|------|------|--------|----------|
| V4 | `analytics/strategy/sweep.py` | 27-28 | `from policy.prop_firm import THE5ERS` `from policy.prop_firm.profile import PropFirmProfile` | 🟡 MEDIUM |
| V5 | `analytics/strategy/fitness.py` | 25-26 | `from policy.prop_firm import THE5ERS` `from policy.prop_firm.profile import PropFirmProfile` | 🟡 MEDIUM |
| V6 | `analytics/backtest/challenge.py` | 24-25 | `from policy.prop_firm.governor import ...` `from policy.prop_firm.profile import PropFirmProfile` | 🟡 MEDIUM |
| V7 | `analytics/backtest/challenge_intraday.py` | 24-25 | `from policy.prop_firm.governor import ...` `from policy.prop_firm.profile import PropFirmProfile` | 🟡 MEDIUM |
| V8 | `analytics/qualification/execution.py` | 41-44 | `from policy.prop_firm.fixtures import ...` `from policy.prop_firm.governor import ...` `from policy.prop_firm.order_risk import ...` `from policy.prop_firm.profile import ...` | 🟡 MEDIUM |
| V9 | `analytics/qualification/discovery.py` | (ctx_graph) | `from policy.prop_firm.profile import PropFirmProfile` | 🟡 MEDIUM |
| V10 | `analytics/strategy/evaluation.py` | (ctx_graph) | `from policy.prop_firm.profile import PropFirmProfile` | 🟡 MEDIUM |
| V11 | `analytics/strategy/evaluator.py` | (ctx_graph) | `from policy.prop_firm.profile import PropFirmProfile` | 🟡 MEDIUM |

**Problema**: analytics/ (research) dipende da policy/ per i profili prop-firm. Questi dovrebbero essere passati come parametri, non importati come dipendenze. La policy appartiene al safety control plane.

### 3.4 analytics ↔ market (CICLO BIDIREZIONALE)

| # | File | Line | Import | Severità |
|---|------|------|--------|----------|
| V12 | `analytics/backtest/data.py` | 16 | `from market.store import FeatureStore` | 🔴 HIGH |
| V13 | `analytics/orchestrator.py` | 12 | `from market.store.feature_store import FeatureStore` | 🔴 HIGH |
| V14 | `analytics/qualification/execution.py` | 40 | `from market.contracts import ContractSpec` | 🔴 HIGH |
| V15 | `market/ingestion/__init__.py` | 27 | `from analytics.common.errors import IngestionError` | 🔴 HIGH |

**Problema**: Ciclo bidirezionale analytics ↔ market. analytics importa market per FeatureStore e ContractSpec; market importa analytics per IngestionError. Questo viola la regola architetturale che vieta dipendenze incrociate tra i due pacchetti.

### 3.5 genetics → analytics (Genetics → Research)

| # | File | Line | Import | Severità |
|---|------|------|--------|----------|
| V16 | `genetics/engine.py` | 20 | `from analytics.backtest.config import BacktestConfig` | 🟡 MEDIUM |
| V17 | `genetics/fitness/evaluator.py` | 20-21 | `from analytics.backtest.config import BacktestConfig` `from analytics.backtest.walk_forward import WalkForwardEngine` | 🟡 MEDIUM |
| V18 | `genetics/genome/pair_signal.py` | 10 | `from analytics.technical.pair_trading import compute_cointegration` | 🟡 MEDIUM |

**Problema**: genetics/ (GA engine) importa analytics/ per configurazioni e algoritmi di backtest. Nel target architetturale, genetics dovrebbe dipendere solo da core/ e da interfacce, non da implementazioni di research.

### 3.6 policy → execution (Policy → Safety Control)

| # | File | Line | Import | Severità |
|---|------|------|--------|----------|
| V19 | `policy/prop_firm/order_risk.py` | 8 | `from execution.order_manager.types import OrderRequest` | 🟡 MEDIUM |

**Problema**: policy/ importa un tipo interno di execution/ (OrderRequest). L'architettura dice che policy e execution devono dipendere entrambi da una porta inward (application/contracts), non direttamente l'uno dall'altro.

### 3.7 agents ↔ genetics (CICLO agents ↔ genetics)

| # | File | Line | Import | Severità |
|---|------|------|--------|----------|
| V20 | `agents/genetic/adapter.py` | 11-12, 50 | TYPE_CHECKING: `from genetics.genome.parameters import GenomeParameter` `from genetics.genome.signal import Genome, decode` | 🟢 LOW |
| V21 | `agents/genetic/strategist.py` | 11-12 | TYPE_CHECKING: `from genetics.engine import GAConfig` `from genetics.genome.signal import GenomeConfig` | 🟢 LOW |
| V22 | `genetics/engine.py` | 28-29 | TYPE_CHECKING: `from core.domain.experiment import ExperimentRegistry` | 🟢 LOW |

**Problema**: Sebbene le import siano sotto TYPE_CHECKING (quindi non eseguite a runtime), la dipendenza concettuale tra agents e genetics è bidirezionale. genetics dipende da analytics e agents dipende da genetics, creando un potenziale ciclo agents → genetics → analytics → agents.

---

## 4. Riepilogo per Severità

### 🔴 HIGH (7 violazioni)

| ID | Path | Dipendenza |
|----|------|-----------|
| V1 | `agents/oracle/oracle.py:15-16` | agents → analytics |
| V2 | `analytics/qualification/execution.py:32-39` | analytics → execution |
| V12 | `analytics/backtest/data.py:16` | analytics → market |
| V13 | `analytics/orchestrator.py:12` | analytics → market |
| V14 | `analytics/qualification/execution.py:40` | analytics → market |
| V15 | `market/ingestion/__init__.py:27` | market → analytics (CICLO) |

### 🟡 MEDIUM (12 violazioni)

| ID | Path | Dipendenza |
|----|------|-----------|
| V3 | `analytics/backtest/providers.py:194` | analytics → execution |
| V4 | `analytics/strategy/sweep.py:27-28` | analytics → policy |
| V5 | `analytics/strategy/fitness.py:25-26` | analytics → policy |
| V6 | `analytics/backtest/challenge.py:24-25` | analytics → policy |
| V7 | `analytics/backtest/challenge_intraday.py:24-25` | analytics → policy |
| V8 | `analytics/qualification/execution.py:41-44` | analytics → policy |
| V9 | `analytics/qualification/discovery.py` | analytics → policy |
| V10 | `analytics/strategy/evaluation.py` | analytics → policy |
| V11 | `analytics/strategy/evaluator.py` | analytics → policy |
| V16 | `genetics/engine.py:20` | genetics → analytics |
| V17 | `genetics/fitness/evaluator.py:20-21` | genetics → analytics |
| V18 | `genetics/genome/pair_signal.py:10` | genetics → analytics |
| V19 | `policy/prop_firm/order_risk.py:8` | policy → execution |

### 🟢 LOW (3 violazioni)

| ID | Path | Dipendenza |
|----|------|-----------|
| V20 | `agents/genetic/adapter.py:11,50` | agents → genetics (TYPE_CHECKING) |
| V21 | `agents/genetic/strategist.py:11-12` | agents → genetics (TYPE_CHECKING) |
| V22 | `genetics/engine.py:28-29` | genetics → core (TYPE_CHECKING) |

---

## 5. Cicli di Dipendenza Identificati

### Ciclo C1: analytics ↔ market (CICLO REALE)

```
analytics/backtest/data.py → market.store.FeatureStore
analytics/orchestrator.py → market.store.feature_store.FeatureStore
analytics/qualification/execution.py → market.contracts.ContractSpec
                                                      ↓
market/ingestion/__init__.py → analytics.common.errors.IngestionError
```

**Impatto**: Impossibile testare analytics senza market e viceversa. Refactoring di market.store rompe analytics.

### Ciclo C2: agents → genetics → analytics (CICLO CONCETTUALE)

```
agents/genetic/adapter.py → genetics.genome.parameters.GenomeParameter
agents/genetic/strategist.py → genetics.engine.GAConfig
                                                      ↓
genetics/engine.py → analytics.backtest.config.BacktestConfig
genetics/fitness/evaluator.py → analytics.backtest.config.BacktestConfig
                                                      ↓
agents/oracle/oracle.py → analytics.regime.config.RegimeSettings  (chiude il ciclo)
```

**Impatto**: agents → genetics → analytics → agents (via oracle.py). Sebbene le import agents→genetics siano TYPE_CHECKING, il ciclo è reale a livello concettuale: agents chiama genetics che chiama analytics che viene chiamato da agents.

---

## 6. Compliance con ARCHITECTURE.md §3.1

| Regola | Stato | Violazioni |
|--------|-------|-----------|
| `core/domain` non importa da altri pacchetti | ✅ COMPLIANT | 0 violazioni |
| `application/contracts` non ha dipendenze esterne | ✅ COMPLIANT | 0 violazioni |
| `execution` non importa contratti da `agents` | ✅ COMPLIANT (l'import era solo in docstring) | 0 violazioni reali |
| `policy` non importa tipi da `execution` | ❌ VIOLATO | V19: order_risk.py → OrderRequest |
| `analytics` e `market` non si importano bidirezionalmente | ❌ VIOLATO | V12-V15: ciclo analytics ↔ market |
| `analytics` non importa `execution` | ❌ VIOLATO | V2-V3: analytics → execution |
| `genetics` non dipende da `analytics` | ❌ VIOLATO | V16-V18: genetics → analytics |
| `agents` (intelligence) non importa `analytics` (research) | ❌ VIOLATO | V1: oracle.py → regime |

---

## 7. Remediation Proposta

### Remediation R1 — agents/oracle/oracle.py → analytics (V1)
**Azione**: Estrarre regime detection in un servizio dentro core/ o application/services, oppure passare RegimeDetector come dependency injection a MarketOracle invece di importarlo direttamente.
**Path**: `agents/oracle/oracle.py:15-16`
**Stima**: 2h (estrazione interfaccia + DI)

### Remediation R2 — analytics → execution (V2, V3)
**Azione**: Definire porte (interfacce astratte) in `application/contracts/` per PaperEngine, BrokerOrder. Fare sì che analytics dipenda dalle interfacce, non da execution.brokers.
**Path**: `analytics/qualification/execution.py:32-39`, `analytics/backtest/providers.py:194`
**Stima**: 4h (creazione interfacce, refactor qualification engine)

### Remediation R3 — analytics → policy (V4-V11)
**Azione**: Passare PropFirmProfile come parametro alle funzioni di backtest/challenge, non importarlo staticamente. Oppure spostare i profili in un package `profiles/` separato che analytics e policy condividono.
**Path**: Multipli in `analytics/strategy/`, `analytics/backtest/`, `analytics/qualification/`
**Stima**: 3h (refactor parametri)

### Remediation R4 — Ciclo analytics ↔ market (V12-V15)
**Azione**: Invertire la dipendenza: introdurre un'interfaccia `FeatureStore` in `core/domain/` (o `application/contracts/`), e far sì che sia analytics che market ne dipendano. Per l'IngestionError, spostare l'errore in `core/errors/`.
**Path**: `analytics/backtest/data.py:16`, `analytics/orchestrator.py:12`, `analytics/qualification/execution.py:40`, `market/ingestion/__init__.py:27`
**Stima**: 3h (interfaccia + spostamento errori)

### Remediation R5 — genetics → analytics (V16-V18)
**Azione**: Introdurre `BacktestConfig` come parametro di configurazione passato dall'esterno, non importato. Estrarre `compute_cointegration` in `core/domain/` o tenerla in analytics ma passarla come callable.
**Path**: `genetics/engine.py:20`, `genetics/fitness/evaluator.py:20-21`, `genetics/genome/pair_signal.py:10`
**Stima**: 2h (refactor parametri + interfaccia)

### Remediation R6 — policy → execution (V19)
**Azione**: OrderRequest dovrebbe essere spostato in `application/contracts/` (esiste già `TradeIntent` che è simile). Alternativamente, PropFirmOrderRiskAdapter dovrebbe accettare un tipo più astratto.
**Path**: `policy/prop_firm/order_risk.py:8`
**Stima**: 1h (spostamento tipo in application/contracts)

### Remediation R7 — TYPE_CHECKING imports agents ↔ genetics (V20-V22)
**Azione**: Mantenere TYPE_CHECKING. Il vero fix è eliminare la dipendenza concettuale di genetics da analytics (R5), che spezza il ciclo agents → genetics → analytics.
**Path**: `agents/genetic/adapter.py`, `agents/genetic/strategist.py`
**Stima**: Già gestito con TYPE_CHECKING. Zero remediation necessaria oltre R5.

---

## 8. Piano di Remediation Prioritizzato

| Priorità | Remediation | Impatto | Sforzo | Dipendenza |
|----------|-------------|---------|--------|-----------|
| P0 | R4 — Ciclo analytics ↔ market | 🔴 Alta (blocca test indipendenti) | 3h | Nessuna |
| P0 | R1 — agents → analytics | 🔴 Alta (viola architettura) | 2h | Nessuna |
| P1 | R2 — analytics → execution | 🔴 Alta (lateral dependency) | 4h | R4 (FeatureStore interface) |
| P1 | R5 — genetics → analytics | 🟡 Media (ciclo concettuale) | 2h | R4 (BacktestConfig as param) |
| P2 | R3 — analytics → policy | 🟡 Media (user decision su architettura profili) | 3h | R4 (PropFirmProfile as param) |
| P2 | R6 — policy → execution | 🟡 Media | 1h | R2 (OrderRequest in contracts) |
| P3 | R7 — TYPE_CHECKING agents→genetics | 🟢 Bassa | 0h | R5 risolve |

### Quick Wins (prima sessione)
1. **R1**: Estrarre `RegimeDetector` come DI — 2h
2. **R6**: Spostare `OrderRequest` in `application/contracts/` — 1h
3. **R4 (parte)**: Spostare `IngestionError` in `core/errors/` — 30min

---

## 9. Metriche

| Metrica | Valore |
|---------|--------|
| File Python totali | ~300 |
| Violazioni HIGH | 7 (in 6 file) |
| Violazioni MEDIUM | 12 (in 8 file) |
| Violazioni LOW | 3 (TYPE_CHECKING) |
| Cicli reali | 1 (analytics ↔ market) |
| Cicli concettuali | 1 (agents → genetics → analytics) |
| Pacchetti compliant (0 violazioni) | core/, application/, apps/, execution/ (su contracts) |
| Pacchetto più violato | analytics/ (11 violazioni) |
| Pacchetto più dipendente da altri | analytics/ (dipende da execution, market, policy) |

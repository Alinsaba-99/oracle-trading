# Phase 4 — Team Mode Task Registry

> 9 task · 6 settimane · Esecuzione parallela per wave
> Commit: `da04a9f` (plan v2 con review feedback incorporate)

---

## Wave 1 (Week 1) — T1 + T2 in parallelo

### T1: Foundation (`agents/`)

| Subtask | File | Dipende da | Agente | Tempo |
|---------|------|-----------|--------|-------|
| 1a | `agents/protocol.py` — AgentVote, AnalystInput, AnalystSignal, DebateResult, MarketState, RiskAssessment, PortfolioDecision, MASState (tutti pydantic.BaseModel frozen) | — | T | 0.5g |
| 1b | `agents/errors.py` — AgentError, ModelCallError, DebateTimeoutError, CircuitBreakerOpen | — | T | 0.5g |
| 1c | `agents/config.py` — MASConfig (pydantic-settings): model config, agent list, debate rounds, timeouts | — | T | 0.5g |
| 1d | `agents/llm.py` — LLMClient protocol + LangChainLLMClient + fallback chain (GPT-4→3.5→locale) | 1a | E | 1g |
| 1e | `agents/cache.py` — LLMResponseCache (LRU keyed su prompt_hash+data_hash) | — | T | 0.5g |
| 1f | `agents/confidence.py` — ConfidenceTracker: accuracy storica, calibration weights | 1a | E | 1g |
| 1g | `agents/__init__.py` — re-export | 1a-1f | T | 0.5g |
| 1h | `tests/agents/test_protocol.py` — serializzazione, validazione, frozen, edge cases | 1a | T | 0.5g |
| 1i | `tests/agents/test_llm.py` — LLMClient mock, fallback chain, timeout | 1d | T | 0.5g |
| 1j | `tests/agents/test_cache.py` — LRU eviction, cache hit/miss, key collision | 1e | T | 0.5g |
| 1k | `tests/agents/test_confidence.py` — tracking, calibration, edge cases | 1f | T | 0.5g |

### T2: Market Oracle (`agents/oracle/`)

| Subtask | File | Dipende da | Agente | Tempo |
|---------|------|-----------|--------|-------|
| 2a | `agents/oracle/oracle.py` — MarketOracle: regime detection (da Phase 1) + LLM narrative | T1a | E | 1g |
| 2b | `agents/oracle/synthesizer.py` — LLM synthesis: dati deterministici → contesto testuale | T1d | E | 1g |
| 2c | `agents/oracle/__init__.py` | 2a-2b | T | 0.5g |
| 2d | `tests/agents/test_oracle.py` — mock regime detector, LLM synthesis | 2a-2b | T | 1g |

---

## Wave 2 (Week 2) — T3 (3 sub-agenti paralleli)

### T3: Analyst Agents (`agents/analysts/`)

| Subtask | File | Dipende da | Agente | Tempo |
|---------|------|-----------|--------|-------|
| 3a | `agents/analysts/base.py` — BaseAnalyst ABC con analyze() + blind_spot | T1a | T | 0.5g |
| 3b | `agents/analysts/macro.py` — Macro Analyst: GDP, CPI, rates, macro indicators | 3a, T1d | E | 1.5g |
| 3c | `agents/analysts/technical.py` — Technical Analyst: RSI, MACD, BB, volume, trend | 3a, T1d | E | 1.5g |
| 3d | `agents/analysts/sentiment.py` — Sentiment Analyst: sentiment scores, news | 3a, T1d | E | 1.5g |
| 3e | `agents/analysts/factory.py` — create_analyst(type, llm, config) | 3b-3d | T | 0.5g |
| 3f | `agents/analysts/__init__.py` | 3a-3e | T | 0.5g |
| 3g | `tests/agents/test_macro.py` — mock LLM, prompt flow, edge cases | 3b | T | 1g |
| 3h | `tests/agents/test_technical.py` — mock LLM, indicatori mancanti | 3c | T | 1g |
| 3i | `tests/agents/test_sentiment.py` — mock LLM, sentiment estremo | 3d | T | 1g |

**3b, 3c, 3d eseguibili in parallelo.** 3g, 3h, 3i anche.

---

## Wave 3 (Week 3) — T4 + T5 in parallelo

### T4: Debate Team (`agents/debate/`)

| Subtask | File | Dipende da | Agente | Tempo |
|---------|------|-----------|--------|-------|
| 4a | `agents/debate/team.py` — DebateTeam: 2-round flow (tesi → contra → DA → rebuttal) | T3, T1d | E | 1.5g |
| 4b | `agents/debate/prompts.py` — Prompt template per Bull/Bear/DA/rebuttal | T1a | T | 0.5g |
| 4c | `agents/debate/scorer.py` — DebateScorer: qualità argomenti, copertura, coerenza | T1a | E | 1g |
| 4d | `agents/debate/__init__.py` | 4a-4c | T | 0.5g |
| 4e | `tests/agents/test_debate.py` — flow, rebuttal, timeout, consensus/no-consensus | 4a-4c | T | 1g |

### T5: Decision Layer (`agents/decision/`) — 0% LLM

| Subtask | File | Dipende da | Agente | Tempo |
|---------|------|-----------|--------|-------|
| 5a | `agents/decision/scoring.py` — SignalScorer: weighted vote aggregation per confidence + accuracy | T1a, T1f | E | 1g |
| 5b | `agents/decision/risk.py` — RiskManager: Kelly fraction, VaR/CVaR, drawdown, correlation, max position size | T1a | E | 2g |
| 5c | `agents/decision/portfolio.py` — PortfolioManager: weighted vote, sentenza finale, escalate handler | 5a, 5b | E | 1.5g |
| 5d | `agents/decision/policy.py` — Bridge a PolicyEngine (Phase 0): hard/soft limits | T1a | E | 1g |
| 5e | `agents/decision/__init__.py` | 5a-5d | T | 0.5g |
| 5f | `tests/agents/test_risk.py` — 10+ test: Kelly precisione, VaR edge cases, drawdown limite | 5b | T | 1g |
| 5g | `tests/agents/test_portfolio.py` — vote aggregation, escalate, no-trade | 5c | T | 1g |

---

## Wave 4 (Week 4) — T6

### T6: Genetic Strategist (`agents/genetic/`)

| Subtask | File | Dipende da (Phase 3) | Agente | Tempo |
|---------|------|----------------------|--------|-------|
| 6a | `agents/genetic/strategist.py` — GeneticStrategist: run GA + Pareto filtering | genetics.engine | E | 1.5g |
| 6b | `agents/genetic/adapter.py` — GAResult → StrategySuggestion (per agenti) | genetics.serialize | E | 1g |
| 6c | `agents/genetic/registry.py` — Reader per Experiment Registry (GA runs passati) | core.domain.experiment | E | 1g |
| 6d | `agents/genetic/__init__.py` | 6a-6c | T | 0.5g |
| 6e | `tests/agents/test_genetic.py` — Pareto filtering, adapter roundtrip, registry | 6a-6c | T | 1g |

---

## Wave 5 (Week 5) — T7

### T7: MAS Orchestrator (`agents/orchestrator/`)

| Subtask | File | Dipende da | Agente | Tempo |
|---------|------|-----------|--------|-------|
| 7a | `agents/orchestrator/graph_adapter.py` — WorkflowEngine protocol: isola LangGraph | — | E | 1g |
| 7b | `agents/orchestrator/graph.py` — LangGraph StateGraph: oracle→analysts→debate→risk→portfolio→END | 7a, T2, T3, T4, T5 | E | 2g |
| 7c | `agents/orchestrator/state.py` — MASState manager (init, validate, snapshot) | T1a | T | 0.5g |
| 7d | `agents/orchestrator/orchestrator.py` — MASOrchestrator: lifecycle, signal handler, run loop | 7b, 7c | E | 1.5g |
| 7e | `agents/orchestrator/runner.py` — MASRunner: single-shot vs watch loop | 7d | E | 1g |
| 7f | `agents/orchestrator/__init__.py` | 7a-7e | T | 0.5g |
| 7g | `tests/agents/test_mas.py` — end-to-end con mock LLM, timeout, error recovery | 7b-7e | T | 1.5g |

---

## Wave 6 (Week 6) — T8 + T9 in parallelo

### T8: CLI + Esperimenti

| Subtask | File | Dipende da | Agente | Tempo |
|---------|------|-----------|--------|-------|
| 8a | `apps/cli/agent_commands.py` — agent run/debate/status handlers | T7e | E | 1g |
| 8b | `apps/cli/main.py` — estensione comandi esistenti | 8a | E | 0.5g |
| 8c | `experiments/scripts/run_mas.py` — MAS experiment runner batch | T7e | E | 1.5g |
| 8d | `experiments/scripts/analyze_mas.py` — Analisi decisioni passate, confidence | T1f | E | 1g |
| 8e | `tests/agents/test_cli.py` — comandi, output modes, error handling | 8a-8b | T | 1g |

### T9: Finalizzazione

| Subtask | Dipende da | Agente | Tempo |
|---------|-----------|--------|-------|
| 9a | ruff check agents/ apps/ | T1-T8 | T | 0.5g |
| 9b | mypy --strict agents/ apps/ | T1-T8 | T | 0.5g |
| 9c | pytest tests/agents/ -q — target ≥ 60 test | T1-T8 | T | 0.5g |
| 9d | Aggiornare showcase.py → 18/18 | T7e | T | 0.5g |
| 9e | python showcase.py — verify 18/18 | 9d | T | 0.5g |
| 9f | Commit finale + tag v0.4.0 | 9a-9e | T | — |

---

## Riepilogo Esecuzione

```
W1: [T1a+T1b+T1c+T1e] ———— [T1d+T1f] ———— [T1g+T1h+T1i+T1j+T1k]    4 agenti paralleli
    [T2a+T2b] ——————————————————————————— [T2c+T2d]                    2 agenti paralleli

W2: [T3a] ——— [T3b+T3c+T3d] ——— [T3e+T3f+T3g+T3h+T3i]               3 analyst in parallelo

W3: [T4a+T4b+T4c] ——— [T4d+T4e]                                       2 agenti paralleli
    [T5a+T5b+T5c+T5d] ——— [T5e+T5f+T5g]                              2 agenti paralleli

W4: [T6a+T6b+T6c] ——— [T6d+T6e]                                       2 agenti paralleli

W5: [T7a+T7b+T7c+T7d] ——— [T7e+T7f+T7g]                              2 agenti paralleli

W6: [T8a+T8c+T8d] ——— [T8b+T8e]                                       2 agenti paralleli
    [T9a+T9b+T9c+T9d+T9e+T9f]                                          1 agente
```

**Totali:** 9 task, ~55 subtask, 6 onde di parallelismo.
**Picco parallelo:** Week 1 con 6 agenti simultanei (T1 + T2).
**Dipendenze critiche:** T1a (protocolli) prima di tutto il resto. T3 (analyst) prima di T4 (debate). T7 (orchestrator) ultimo.
**Stima realistica:** 5-6 settimane con 2 ingegneri equivalenti in team mode.

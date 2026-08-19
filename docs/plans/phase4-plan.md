> **ARCHIVIO STORICO.** Documento del modello Phase, deprecato da ADR-012
> e sostituito dai capability gate G0-G9. Roadmap canonica:
> [ROADMAP.md](../../ROADMAP.md). Stato corrente:
> [ORACLE_AUTOPILOT_STATUS.md](../ORACLE_AUTOPILOT_STATUS.md).
> **Non aggiornare** — solo git archaeology.

# Phase 4 — Multi-Agent System (LangGraph)

> 6 settimane · 9 task · Orchestrazione multi-agente LLM con debate, risk management e portfolio decision
> Base: Phase 3 Genetic Engine completato · Dipendenza: LangGraph + litellm
> Review: CEO (8.5KB) + Engineering (19.2KB) + Design (6.6KB) — 3 revisioni incorporate

---

## 1. Visione Architetturale

```
┌─────────────────────────────────────────────────────────────────────────┐
│   MARKET ORACLE (regime-aware)                                          │
│   Determina: regime trend/vol/liquidità, fase mercato, risk-on/off      │
├─────────────────────────────────────────────────────────────────────────┤
│                    ANALYST POOL × 3 (paralleli)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │    MACRO     │  │  TECHNICAL   │  │  SENTIMENT   │                  │
│  │   Analyst    │  │   Analyst    │  │   Analyst    │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
│  Ogni agente: analizza → voto + confidence + reasoning + blind_spot    │
│  Fundamental + Factor Analyst: DEFERRED a Phase 5                      │
├─────────────────────────────────────────────────────────────────────────┤
│                        DEBATE TEAM (2 round)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐             │
│  │  BULL (pro)  │  │ BEAR (con)   │  │ DEVIL'S ADVOCATE │             │
│  └──────────────┘  └──────────────┘  └──────────────────┘             │
│   Round 1: Bull tesi → Bear contra → DA sintesi                        │
│   Round 2: Rebuttal (opzionale se divergenza > 0.3)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                        DECISION LAYER (deterministico)                  │
│  ┌────────────────────┐  ┌────────────────────┐                         │
│  │   RISK MANAGER     │  │ PORTFOLIO MANAGER  │                         │
│  │  Kelly fraction    │  │  Weighted vote agg  │                         │
│  │  VaR/CVaR limits   │  │  Sentenza finale   │                         │
│  │  Drawdown control  │  │  BUY/SELL/HOLD      │                         │
│  │  Corr check        │  │  0% LLM — solo deterministico               │
│  └────────────────────┘  └────────────────────┘                         │
├─────────────────────────────────────────────────────────────────────────┤
│   GENETIC STRATEGIST (ponte con Phase 3)                                │
│   Legge Pareto front da GeneticEngine → suggerisce strategie candidate  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Principi (dalla SPEC, immutabili)

| # | Principio | Conseguenza |
|---|-----------|-------------|
| 1 | **LLM = Consulente** | LLM analizza e dibatte — mai decide un trade |
| 2 | **Separazione Det/LLM** | RiskManager + PortfolioManager = 0% LLM |
| 3 | **Debate Strutturato** | 2 round con rebuttal |
| 4 | **Fail Closed** | Se un agente fallisce → NO TRADE |
| 5 | **Riproducibilità** | Ogni run MAS loggata su Experiment Registry |
| 6 | **Confidence Calibrated** | Voto LLM pesato per accuratezza storica |

---

## 2. Decisioni Architetturali (per Review)

| Review | Issue | Decision |
|--------|-------|----------|
| CEO | 5 analyst = troppo per v1 | **3 analyst**: Macro, Technical, Sentiment. Fundamental + Factor Analyst deferred a Phase 5 |
| CEO | Confidence calibration assente | **Task esplicito**: confidence tracker + historical accuracy weighting |
| CEO | Timeline irrealistica | 6 settimane confermato ma solo 3 analyst + rebuttal ridotto |
| Eng | `@dataclass` vs `BaseModel` | **pydantic.BaseModel** dappertutto — consistenza con codebase |
| Eng | TypedDict MASState fragile | `MASState` come `BaseModel` frozen |
| Eng | LLM accoppiato a langchain | **LLMClient protocol** + adapter |
| Eng | Timeout / retry mancanti | Per-agent timeout + circuit breaker + retry policy |
| Eng | LangGraph lock-in | **Adapter layer** attorno a LangGraph |
| Eng | Cache LLM mancante | Response cache keyed su (prompt_hash + data_hash) |
| Eng | EventBus gap | Market data entra via EventBusClient esistente |
| Eng | AnalystInput indefinito | Protocollo `AnalystInput` con specifica esatta |
| Design | PortfolioManager LLM? | **0% LLM** — determinismo puro |
| Design | 1 round debate = teatro | **2 round** con rebuttal |
| Design | Alpha Researcher vago | Deferito a Phase 5 come Factor Analyst |
| Design | CLI output mancanti | Modalità `--json`, `--table`, `--verbose` |
| Design | Modello fallback assente | Catena di fallback (GPT-4 → GPT-3.5 → locale) |
| Design | Prompt versioning | Hash promemoria in metadata AnalystSignal |
| Design | Cost tracking | Token/run su Experiment Registry |
| Design | Output validator | Schema validator per risposte LLM |

---

## 3. Protocolli (pydantic.BaseModel, non dataclass)

```python
class AgentVote(BaseModel):
    direction: Literal["buy", "sell", "hold"]
    confidence: float  # 0.0-1.0
    reasoning: str
    risk_score: float | None = None  # 0 (safe) - 1 (risky)


class AnalystInput(BaseModel):
    instrument: str
    ohlcv: Any  # pl.DataFrame — type: ignore[valid-type]
    market_state: "MarketState"
    agent_specific_data: dict[str, Any]  # indicatori pre-calcolati


class AnalystSignal(BaseModel):
    source: Literal["macro", "technical", "sentiment"]
    vote: AgentVote
    metadata: dict[str, Any]
    blind_spot: str
    prompt_hash: str = ""  # per tracciabilità versioni prompt
    model: str = ""  # modello LLM usato
    tokens_used: int = 0  # per cost tracking


class DebateResult(BaseModel, frozen=True):
    round_1: dict  # bull + bear + da
    round_2: dict | None = None  # rebuttal se divergenza > 0.3
    consensus: AgentVote | None = None
    disagreements: list[str] = []
    debate_quality: float = 0.0  # 0-1 da DebateScorer


class MarketState(BaseModel, frozen=True):
    regime: str  # bull, bear, choppy
    phase: str  # accumulation, markup, distribution, markdown
    volatility: str  # low, medium, high, panic
    liquidity: str  # normal, tight, crisis
    risk_appetite: str  # risk_on, risk_off
    narrative: str = ""  # LLM narrative (solo testo)


class RiskAssessment(BaseModel, frozen=True):
    approved: bool
    max_position_size: float
    kelly_fraction: float
    var_95: float
    reasons: list[str]


class PortfolioDecision(BaseModel, frozen=True):
    direction: Literal["buy", "sell", "hold", "no_trade"]
    instrument: str
    position_size: float
    confidence: float
    reasoning: str
    agents_contributing: list[str]
    regime_at_decision: str
    risk_approved: bool
    escalated: bool = False


class MASState(BaseModel, frozen=True):
    market_data: Any | None = None  # pl.DataFrame
    market_state: MarketState | None = None
    analyst_signals: list[AnalystSignal] = []
    debate: DebateResult | None = None
    risk_assessment: RiskAssessment | None = None
    decision: PortfolioDecision | None = None
    errors: list[str] = []
    run_id: str = ""
    total_tokens: int = 0
    timing: dict[str, float] = {}
```

---

## 4. LLMClient Protocol

```python
class LLMClient(Protocol):
    """Adapter protocol — isola il MAS da LangChain/litellm."""

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        temperature: float = 0.1,
        timeout_s: float = 30.0,
    ) -> BaseModel: ...

    @property
    def model_name(self) -> str: ...

    async def count_tokens(self, text: str) -> int: ...
```

Implementazione default: `LangChainLLMClient(langchain_openai.ChatOpenAI)`.
Fallback chain: GPT-4 → GPT-3.5 → locale.

---

## 5. Task Breakdown

### Week 1: Foundation + Oracle

**T1: Foundation (`agents/`) — 2 giorni**
| File | Scopo |
|------|-------|
| `agents/__init__.py` | MASOrchestrator, tutti i protocolli |
| `agents/config.py` | `MASConfig` (pydantic): model config, agent list, debate rounds |
| `agents/protocol.py` | Tutti i protocolli sopra (AgentVote, AnalystSignal, PortfolioDecision, ecc.) |
| `agents/errors.py` | AgentError, ModelCallError, DebateTimeoutError, CircuitBreakerOpen |
| `agents/llm.py` | `LLMClient` protocol + `LangChainLLMClient` + fallback chain |
| `agents/cache.py` | `LLMResponseCache`: LRU keyed su (prompt_hash + data_hash) |
| `agents/confidence.py` | `ConfidenceTracker`: accuracy storica per agente, calibration weights |
| `tests/agents/test_protocol.py` | 8+ test: serializzazione, validazione, frozen |

**T2: Market Oracle (`agents/oracle/`) — 3 giorni**
| File | Scopo |
|------|-------|
| `agents/oracle/__init__.py` | MarketOracle |
| `agents/oracle/oracle.py` | `MarketOracle`: regime detection + LLM narrative |
| `agents/oracle/synthesizer.py` | LLM synthesis: dati deterministici → contesto testuale |
| `tests/agents/test_oracle.py` | 6+ test: mock regime detector |

### Week 2: Analyst Agents

**T3: 3 Analyst Agents (`agents/analysts/`) — 4 giorni**
| File | Agente | Input Unico |
|------|--------|-------------|
| `agents/analysts/macro.py` | Macro Analyst | GDP, CPI, rates, yield curve (from `analytics.macro`) |
| `agents/analysts/technical.py` | Technical Analyst | RSI, MACD, BB, volume (from `analytics.technical`) |
| `agents/analysts/sentiment.py` | Sentiment Analyst | Sentiment scores (from `analytics.sentiment`) |
| `agents/analysts/factory.py` | Factory | `create_analyst(type, llm, config) → BaseAnalyst` |
| `agents/analysts/__init__.py` | Re-export | BaseAnalyst, 3 factory functions |

Ogni agente: 10+ test con mock LLM, prompt strutturato, output schema JSON.

### Week 3: Debate + Decision Layer

**T4: Debate Team (`agents/debate/`) — 3 giorni**
| File | Scopo |
|------|-------|
| `agents/debate/__init__.py` | DebateTeam, DebateResult |
| `agents/debate/team.py` | `DebateTeam`: 2-round orchestrazione |
| `agents/debate/prompts.py` | Prompt template per Bull/Bear/DA + rebuttal |
| `agents/debate/scorer.py` | `DebateScorer`: qualità argomenti, coerenza, copertura |
| `tests/agents/test_debate.py` | 8+ test: debate flow, rebuttal, timeout |

**T5: Decision Layer (`agents/decision/`) — 3 giorni**
| File | Scopo |
|------|-------|
| `agents/decision/__init__.py` | RiskManager, PortfolioManager |
| `agents/decision/risk.py` | `RiskManager`: Kelly, VaR/CVaR, drawdown, correlation, max position |
| `agents/decision/portfolio.py` | `PortfolioManager`: weighted vote, sentenza, escalate handler |
| `agents/decision/scoring.py` | `SignalScorer`: weighted vote per confidence + accuracy storica |
| `agents/decision/policy.py` | Bridge a PolicyEngine (Phase 0) |
| `tests/agents/test_risk.py` | 10+ test: Kelly, VaR, edge cases |
| `tests/agents/test_portfolio.py` | 6+ test: vote aggregation, escalate, no-trade |

### Week 4: Genetic Strategist

**T6: Genetic Strategist (`agents/genetic/`) — 4 giorni**
| File | Scopo |
|------|-------|
| `agents/genetic/__init__.py` | GeneticStrategist |
| `agents/genetic/strategist.py` | `GeneticStrategist`: pareto front → suggestions |
| `agents/genetic/adapter.py` | Adatta `GAResult` → agent-readable `StrategySuggestion` |
| `agents/genetic/registry.py` | Legge experiment passati da Experiment Registry |
| `tests/agents/test_genetic.py` | 6+ test: Pareto parsing, filtering, integration |

### Week 5: MAS Orchestrator

**T7: MAS Orchestrator (`agents/orchestrator/`) — 5 giorni**
| File | Scopo |
|------|-------|
| `agents/orchestrator/__init__.py` | MASOrchestrator |
| `agents/orchestrator/orchestrator.py` | `MASOrchestrator`: lifecycle, signal handler, run loop |
| `agents/orchestrator/graph.py` | LangGraph state graph + adapter layer |
| `agents/orchestrator/graph_adapter.py` | Isola LangGraph dietro `WorkflowEngine` protocol |
| `agents/orchestrator/state.py` | `MASState` (da protocolli) |
| `agents/orchestrator/runner.py` | `MASRunner`: CLI bridge, single-shot vs watch loop |
| `tests/agents/test_mas.py` | 6+ test: end-to-end con mock LLM |

### Week 6: CLI + Test + Commit

**T8: CLI + Esperimenti — 3 giorni**
| File | Scopo |
|------|-------|
| `apps/cli/main.py` | Aggiunge `oracle agent run` con `--json`, `--table`, `--verbose` |
| `apps/cli/agent_commands.py` | Implementazione comandi agent |
| `experiments/scripts/run_mas.py` | MAS experiment runner batch |
| `experiments/scripts/analyze_mas.py` | Analisi decisioni passate, confidence calibration |

**T9: Test finale + Commit — 2 giorni**
- `ruff check agents/ apps/` clean
- `mypy --strict agents/ apps/` clean
- `pytest tests/agents/ -q` ≥ 60 test
- `python showcase.py` → 18/18 componenti
- Commit finale

---

## 6. Test Plan

| Categoria | Tests | Copertura |
|-----------|-------|-----------|
| **Unit (deterministico)** | RiskManager, PortfolioManager, SignalScorer | 100% — niente LLM |
| **Unit (mock LLM)** | Analyst agents, Debate team, Market Oracle | Prompt flow, parsing, errori |
| **Integration** | MAS end-to-end (mock LLM), CLI | Flusso completo |
| **Confidence** | ConfidenceTracker, calibration weights | Accuratezza storica |
| **Edge Cases** | Timeout, circuit breaker, consensus failure, risk rejection | Fallimenti graceful |
| **LLM Fallback** | Catena GPT-4→3.5→locale su fallimento | Resilienza |

---

## 7. Success Criteria

1. `oracle agent run --instrument SPY` → PortfolioDecision in <30s
2. `oracle agent run --instrument SPY --json` → JSON strutturato
3. 3 analyst agents producono voti indipendenti (non sempre correlated)
4. Debate team NON raggiunge sempre consensus (disaccordo = feature)
5. RiskManager blocca posizioni che violano hard limits
6. ConfidenceTracker calibra voti LLM per accuratezza storica
7. Se un LLM fallisce, catena di fallback attiva
8. `ruff check agents/` clean + `mypy --strict agents/` clean
9. `pytest tests/agents/` ≥ 60 test
10. LangGraph grafo visualizzabile

---

## 8. Dipendenze Nuove

```toml
agents = [
    "litellm>=1.60",        # multi-provider LLM (OpenAI, Anthropic, locale)
    "langgraph>=0.3",        # orchestratore stato
]
dev = [
    "pytest-asyncio>=0.24",
]
```

LangChain rimosso dalle dipendenze — uso `litellm` direttamente via LLMClient protocol, riducendo dipendenze e complessità.

---

## 9. Rischi e Mitigazioni

| Rischio | Probabilità | Mitigazione |
|---------|-------------|-------------|
| **LLM token cost elevato** | Alta | Cache LLMResponseCache riduce chiamate identiche; 3 agenti (non 5) = 40% meno token |
| **LLM allucina analisi** | Media | Output JSON forzato + schema validator; confidence tracking storico |
| **Debate non converge** | Media | PortfolioManager decide con weighted vote; 2-round garantisce profondità |
| **LangGraph breaking changes** | Bassa | GraphAdapter isola LangGraph; se cambia, si riscrive solo l'adapter |
| **Overconfidence LLM** | Alta | **ConfidenceTracker**: peso voto per accuratezza storica; calibration esplicita |
| **Provider LLM down** | Media | Fallback chain: GPT-4 → GPT-3.5 → locale (Ollama) |
| **Circuit breaker aperto** | Bassa | Retry con backoff esponenziale; dopo N fallimenti, skip agente + log |

---

## 10. Esecuzione Consigliata (Team Mode)

```
Week 1:  T1 (Foundation: protocolli BaseModel, LLMClient, cache, confidence)
         T2 (Market Oracle: oracle + synthesizer)
Week 2:  T3 (3 Analyst Agents: Macro, Technical, Sentiment + factory)
Week 3:  T4 (Debate Team: 2-round + rebuttal + scoring)
         T5 (Decision Layer: RiskManager + PortfolioManager — 0% LLM)
Week 4:  T6 (Genetic Strategist bridge)
Week 5:  T7 (MAS Orchestrator: LangGraph + adapter + runner)
Week 6:  T8 (CLI: --json/--table/--verbose)
         T9 (test + ruff + mypy + commit)
```

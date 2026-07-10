# Phase 4 — Multi-Agent System (LangGraph)

> 6 settimane · 8 task · Orchestrazione multi-agente LLM con debate, risk management e portfolio decision
> Base: Phase 3 Genetic Engine completato · Dipendenza: LangGraph (nuovo) + librerie LLM

---

## 1. Visione Architetturale

```
┌─────────────────────────────────────────────────────────────────────────┐
│   MARKET ORACLE (regime-aware)                                          │
│   Determina: regime trend/vol/liquidità, fase mercato, risk-on/off      │
├─────────────────────────────────────────────────────────────────────────┤
│                        ANALYST POOL (paralleli)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  MACRO   │  │TECHNICAL │  │FUNDAMENT.│  │SENTIMENT │  │  ALPHA   │ │
│  │ Analyst  │  │ Analyst  │  │ Analyst  │  │ Analyst  │  │Researcher│ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│  Ogni agente: analizza → produce voto + confidence + reasoning          │
├─────────────────────────────────────────────────────────────────────────┤
│                        DEBATE TEAM                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐             │
│  │  BULL (pro)  │  │ BEAR (con)   │  │ DEVIL'S ADVOCATE │             │
│  └──────────────┘  └──────────────┘  └──────────────────┘             │
│  1 round: Bull presenta tesi, Bear contesta, DA trova terza via        │
├─────────────────────────────────────────────────────────────────────────┤
│                        DECISION LAYER                                   │
│  ┌────────────────────┐  ┌────────────────────┐                         │
│  │   RISK MANAGER     │  │ PORTFOLIO MANAGER  │                         │
│  │  Position sizing   │  │  Decisione finale  │                         │
│  │  VaR/CVaR limits   │  │  BUY/SELL/HOLD     │                         │
│  │  Drawdown control  │  │  Allocazione       │                         │
│  └────────────────────┘  └────────────────────┘                         │
├─────────────────────────────────────────────────────────────────────────┤
│   GENETIC STRATEGIST (ponte con Phase 3)                                │
│   Legge Pareto front da GeneticEngine → suggerisce strategie candidate   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Principi (dalla SPEC, immutabili)

| # | Principio | Conseguenza |
|---|-----------|-------------|
| 1 | **LLM = Consulente** | LLM analizza e dibatte — mai decide un trade |
| 2 | **Separazione Det/LLM** | Calcoli numerici in codice deterministico, LLM per sintesi |
| 3 | **Debate Strutturato** | Bull/Bear/DA prima di ogni decisione |
| 4 | **Fail Closed** | Se un agente fallisce → NO TRADE, non default all'azione |
| 5 | **Riproducibilità** | Ogni run MAS loggata su Experiment Registry |

---

## 2. Task Breakdown

### Task 1: Foundation & Protocolli (`agents/` — Week 1)

**Files:**
| File | Scopo |
|------|-------|
| `agents/__init__.py` | Esporta: MASOrchestrator, AgentSignal, tutte le factory |
| `agents/config.py` | `MASConfig` (Pydantic): model config, agent list, debate rounds |
| `agents/protocol.py` | `AgentInput`, `AgentOutput`, `AgentVote`, `AnalystSignal` protocolli |
| `agents/errors.py` | `AgentError`, `ModelCallError`, `DebateTimeoutError` |

**Protocolli chiave:**

```python
@dataclass
class AgentVote:
    direction: Literal["buy", "sell", "hold"]
    confidence: float           # 0.0-1.0
    reasoning: str              # LLM output testuale
    risk_score: float | None    # 0 (safe) - 1 (risky)

@dataclass
class AnalystSignal:
    source: str                  # "macro", "technical", "fundamental", "sentiment", "alpha"
    vote: AgentVote
    metadata: dict               # indicatori specifici dell'agente
    model: str                   # modello LLM usato

@dataclass
class DebateResult:
    bull_case: AnalystSignal
    bear_case: AnalystSignal
    da_analysis: str
    consensus: AgentVote | None  # None = no consensus
    disagreements: list[str]

@dataclass
class PortfolioDecision:
    direction: Literal["buy", "sell", "hold"]
    instrument: str
    position_size: float         # % of capital
    confidence: float
    reasoning: str
    agents_contributing: list[str]
    regime_at_decision: str
    risk_approved: bool
```

**Dipendenza:** `pip install langgraph langchain-core langchain-openai` (o litellm)

---

### Task 2: Market Oracle (`agents/oracle/` — Week 1)

**Files:**
| File | Scopo |
|------|-------|
| `agents/oracle/__init__.py` | Esporta: MarketOracle |
| `agents/oracle/oracle.py` | `MarketOracle`: sintesi regime + fase + vol + liquidità |
| `agents/oracle/synthesizer.py` | LLM synthesis: prende dati regime deterministici e produce narrative |
| `agents/oracle/types.py` | `MarketState`: regime, fase, vol, liquidità, risk-on/off, confidence |

**Pattern:**
```python
class MarketOracle:
    """Sintetizza lo stato di mercato combinando regime detection deterministica + LLM narrative."""

    def __init__(self, regime_detector, llm_client):
        self._detector = regime_detector
        self._llm = llm_client

    async def analyze(self, market_data: pl.DataFrame) -> MarketState:
        # 1. Regime detection deterministica (Phase 1) → regime, fase, vol, corr
        regime = self._detector.detect(market_data)
        # 2. LLM narrative context (solo testo, nessuna decisione)
        narrative = await self._llm.synthesize(regime)
        # 3. MarketState completo
        return MarketState(
            regime=regime.regime, phase=regime.phase,
            volatility=regime.volatility, liquidity=regime.liquidity,
            risk_appetite="risk_on" if regime.regime in ("bull",) else "risk_off",
            narrative=narrative,
        )
```

---

### Task 3: Analyst Agents (`agents/analysts/` — Week 2)

**5 agenti paralleli**, ognuno in un file separato. Ogni agente:
1. Riceve input: DataFrame OHLCV + market state + indicatori specifici
2. Chiama LLM con prompt strutturato
3. Produce `AnalystSignal` con voto + confidence + reasoning

| File | Agente | Input Unico |
|------|--------|-------------|
| `agents/analysts/macro.py` | Macro Analyst | GDP, CPI, rates, yield curve, PMI (from `analytics.macro`) |
| `agents/analysts/technical.py` | Technical Analyst | RSI, MACD, BB, SMA, volume (from `analytics.technical`) |
| `agents/analysts/fundamental.py` | Fundamental Analyst | P/E, ROE, D/E, DCF (from `analytics.fundamental`) |
| `agents/analysts/sentiment.py` | Sentiment Analyst | Sentiment scores, news (from `analytics.sentiment`) |
| `agents/analysts/alpha.py` | Alpha Researcher | Factor exposures, alpha signals (from `genetics.alpha`) |
| `agents/analysts/factory.py` | Factory | `create_analyst(type, llm_client) → BaseAnalyst` |

**Protocollo BaseAnalyst:**
```python
class BaseAnalyst(ABC):
    @abstractmethod
    async def analyze(self, data: AnalystInput) -> AnalystSignal:
        """Analizza i dati e produce un voto strutturato."""
        ...

    @property
    @abstractmethod
    def blind_spot(self) -> str:
        """Descrizione del blind spot — per il debate team."""
        ...
```

---

### Task 4: Debate Team (`agents/debate/` — Week 3)

**Files:**
| File | Scopo |
|------|-------|
| `agents/debate/__init__.py` | Esporta: DebateTeam, DebateResult |
| `agents/debate/team.py` | `DebateTeam`: orchestrazione debate a 3 voci |
| `agents/debate/prompts.py` | Prompt template per Bull/Bear/Devil's Advocate |
| `agents/debate/scorer.py` | `DebateScorer`: scoring quantitativo della qualità del debate |

**Flusso Debate:**
```
1. BULL presenta: "Compra SPY perché momentum + macro"
2. BEAR contesta: "RSI in overbought, vol in aumento"
3. DEVIL'S ADVOCATE: "Entrambi ignorano il regime FOMC"
4. Consensus? → se confidence medio > 0.7, produce voto unificato
         no? → PortfolioManager decide con voto pesato
```

---

### Task 5: Decision Layer (`agents/decision/` — Week 3-4)

**Files:**
| File | Scopo |
|------|-------|
| `agents/decision/__init__.py` | Esporta: RiskManager, PortfolioManager |
| `agents/decision/risk.py` | `RiskManager`: position sizing, VaR/CVaR, drawdown, correlation check, Kelly |
| `agents/decision/portfolio.py` | `PortfolioManager`: decisione finale, allocazione, rebalancing |
| `agents/decision/policy.py` | Bridge a PolicyEngine (Phase 0): hard/soft limits |
| `agents/decision/scoring.py` | `SignalScorer`: weighted vote aggregation |

**RiskManager (deterministico puro, nessun LLM):**
```python
class RiskManager:
    """Calcoli deterministici di rischio. MAI un LLM qua dentro."""

    def kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float: ...
    def var(self, returns: pl.Series, alpha: float = 0.05) -> float: ...
    def max_position_size(self, equity: float, volatility: float) -> float: ...
    def correlation_check(self, instrument: str, portfolio: Portfolio) -> bool: ...
    def approve(self, decision: PortfolioDecision) -> PortfolioDecision:
        """Applica hard limits. Se violato → NO TRADE."""
        ...
```

---

### Task 6: Genetic Strategist (`agents/genetic/` — Week 4)

**Files:**
| File | Scopo |
|------|-------|
| `agents/genetic/__init__.py` | Esporta: GeneticStrategist |
| `agents/genetic/strategist.py` | `GeneticStrategist`: bridge Phase 3 → Phase 4 |
| `agents/genetic/adapter.py` | Adatta `GAResult` in formato interpretabile dagli agenti |

**Pattern:**
```python
class GeneticStrategist:
    """Legge il Pareto front dal GeneticEngine e produce suggerimenti strategici."""

    def __init__(self, engine: GeneticEngine, ga_config: GAConfig):
        self._engine = engine
        self._config = ga_config

    async def suggest_strategies(self, market_state: MarketState) -> list[StrategySuggestion]:
        """Carica il Pareto front corrente e filtra per regime di mercato."""
        # 1. Recupera Pareto front
        result = await self._engine.run(...)
        # 2. Filtra per regime corrente (solo strategie appropriate al market state)
        filtered = self._filter_by_regime(result.pareto_front, market_state)
        # 3. Produce suggerimenti strutturati per gli agenti
        return [self._to_suggestion(ind, i) for i, ind in enumerate(filtered[:5])]
```

---

### Task 7: MAS Orchestrator (`agents/orchestrator/` — Week 5)

**Files:**
| File | Scopo |
|------|-------|
| `agents/orchestrator/__init__.py` | Esporta: MASOrchestrator |
| `agents/orchestrator/orchestrator.py` | `MASOrchestrator`: LangGraph workflow, ciclo di vita, signal handler |
| `agents/orchestrator/graph.py` | LangGraph state graph: definisce nodi e archi |
| `agents/orchestrator/state.py` | `MASState`: definizione dello stato condiviso del grafo |
| `agents/orchestrator/runner.py` | `MASRunner`: CLI runner, flusso single-shot vs watch loop |

**LangGraph State:**
```python
class MASState(TypedDict):
    market_data: pl.DataFrame           # OHLCV input
    market_state: MarketState           # Dal Market Oracle
    analyst_signals: list[AnalystSignal]  # Dai 5 analyst
    debate: DebateResult | None          # Dal debate team
    risk_assessment: RiskAssessment | None  # Dal Risk Manager
    decision: PortfolioDecision | None    # Decisione finale
    execution_result: dict | None         # Risultato (Phase 5)
    errors: list[str]                     # Errori raccolti
```

**LangGraph workflow:**
```python
def build_graph() -> StateGraph:
    """Costruisce il grafo del sistema multi-agente."""
    graph = StateGraph(MASState)

    # Nodi
    graph.add_node("oracle", MarketOracleNode())
    graph.add_node("analysts", AnalystPoolNode())      # parallelo
    graph.add_node("debate", DebateTeamNode())
    graph.add_node("risk", RiskManagerNode())
    graph.add_node("portfolio", PortfolioManagerNode())

    # Archi
    graph.set_entry_point("oracle")
    graph.add_edge("oracle", "analysts")
    graph.add_edge("analysts", "debate")
    graph.add_conditional_edges(
        "debate",
        router,  # se consensus → salta risk? No, risk sempre
        {"risk": "risk", "escalate": "portfolio"},
    )
    graph.add_edge("risk", "portfolio")
    graph.add_edge("portfolio", END)
    return graph.compile()
```

---

### Task 8: CLI + Test + Commit (`apps/` + `tests/` — Week 6)

**Files:**
| File | Scopo |
|------|-------|
| `apps/cli/main.py` | Aggiunge `oracle agent run`, `oracle agent debate`, `oracle agent status` |
| `tests/agents/test_protocol.py` | 6+ test: serializzazione, validazione, edge cases |
| `tests/agents/test_oracle.py` | 6+ test: MarketOracle con mock regime detector |
| `tests/agents/test_analysts.py` | 10+ test: ogni agente con mock LLM |
| `tests/agents/test_debate.py` | 6+ test: debate flow, consensus, timeout |
| `tests/agents/test_risk.py` | 8+ test: Kelly, VaR, position sizing, correlation check |
| `tests/agents/test_portfolio.py` | 6+ test: decision aggregation, rebalancing |
| `tests/agents/test_genetic.py` | 4+ test: GeneticStrategist adapter |
| `tests/agents/test_mas.py` | 4+ test: LangGraph end-to-end (mock LLM) |

---

## 3. Test Plan

| Categoria | Tests | Copertura |
|-----------|-------|-----------|
| **Unit (deterministico)** | RiskManager, PortfolioManager, SignalScorer | 100% — niente LLM |
| **Unit (mock LLM)** | Analyst agents, Debate team, Market Oracle | Tutti i percorsi logici |
| **Integration** | LangGraph end-to-end (mock LLM), CLI commands | Flusso completo |
| **Edge Cases** | Tutti gli agenti timeout, consensus failure, risk rejection, empty data | Fallimenti graceful |

---

## 4. Success Criteria

1. `oracle agent run --instrument SPY` produce decisione BUY/SELL/HOLD in <30s
2. 5 analyst agents producono voti indipendenti (non correlated)
3. Debate team non raggiunge sempre consensus — disaccordo produttivo dimostrabile
4. RiskManager blocca posizioni che violano hard limits (testato)
5. GeneticStrategist produce suggerimenti da Pareto front reale
6. `ruff check agents/` + `mypy --strict agents/` clean
7. `pytest tests/agents/` ≥ 50 test
8. LangGraph grafo visualizzabile (`graph.get_graph().draw_mermaid_png()`)

---

## 5. Dipendenze Nuove

```toml
agents = [
    "langgraph>=0.3",
    "langchain-core>=0.3",
    "langchain-openai>=0.3",  # o litellm per multi-provider
]
dev = [
    "pytest-asyncio>=0.24",
]
```

---

## 6. Rischi e Mitigazioni

| Rischio | Probabilità | Mitigazione |
|---------|-------------|-------------|
| **LLM token cost elevato** | Alta | Ogni agente chiama LLM una volta per run; debate 2-3 chiamate totali |
| **LLM allucina analisi finanziaria** | Media | Prompt strutturati + schema di output JSON forzato |
| **Debate non converge mai** | Media | PortfolioManager decide con weighted vote se timeout |
| **LangGraph breaking changes** | Bassa | API stabile v0.3+; isolare in adapter se necessario |
| **Genetic Strategist lento** | Media | GA run asincrona in background; cache Pareto front |
| **Overconfidence LLM** | Alta | Confidence calibration: voto LLM pesato per accuratezza storica |

---

## 7. Esecuzione Consigliata (Team Mode)

```
Week 1:  T1 (Foundation + protocolli) + T2 (Market Oracle) — paralleli
Week 2:  T3 (5 Analyst Agents + factory) — parallelo interno
Week 3:  T4 (Debate Team) + T5 (Decision Layer) — paralleli
Week 4:  T6 (Genetic Strategist bridge)
Week 5:  T7 (MAS Orchestrator + LangGraph graph)
Week 6:  T8 (CLI + test + commit)
```

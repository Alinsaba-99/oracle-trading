# Phase 5 — Execution Engine

> 4 settimane · 6 task · Broker connectors, Order Manager, Execution Algos
> Base: Phase 4 MAS completa · Scaffold `execution/` già esistente (vuoto)
> Dipendenze nuove: `ib_insync`, `ccxt`

---

## 1. Stato Attuale

L'execution layer è già **scaffoldato ma vuoto** (stub Phase 0):

```
execution/                  # Package vuoto
├── __init__.py             # Vuoto
├── algos/__init__.py       # Vuoto
├── brokers/__init__.py     # Vuoto
└── order_manager/__init__.py  # Vuoto
```

**Già esistente (Phase 0-2, FROZEN):**
- `core/domain/order.py` — `Order` model con validazione (pydantic)
- `core/domain/enums.py` — `OrderSide`, `OrderType`, `OrderStatus`, `TimeInForce`
- `core/events/order.py` — `OrderSubmittedEvent`, `OrderFilledEvent`
- `core/events/trade.py` — trade events
- `core/events/portfolio.py` — portfolio events

**Da Phase 4:**
- `agents/decision/portfolio.py` — `PortfolioManager` produce `PortfolioDecision`
- `agents/decision/risk.py` — `RiskManager` approva/rifiuta

---

## 2. Architettura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PORTFOLIO MANAGER (Phase 4)                           │
│  Produce: PortfolioDecision { direction, instrument, size, confidence } │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ PortfolioDecision
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ORDER MANAGER                                    │
│  - Riceve PortfolioDecision → converte in Order                          │
│  - Valida contro RiskManager (sanity check)                             │
│  - Sceglie execution algo (market/VWAP/TWAP/iceberg)                   │
│  - Invia a broker connector                                             │
│  - Aggiorna Order lifecycle: pending → submitted → filled/cancelled     │
│  - Emette eventi NATS per ogni transizione di stato                     │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │ Order (via broker connector)
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BROKER CONNECTORS                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │  IBKR (live) │  │ CCXT (crypto)│  │  PAPER (sim) │                   │
│  │ ib_insync    │  │ 100+ exchange│  │  mock fills  │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Principi

| # | Principio | Conseguenza |
|---|-----------|-------------|
| 1 | **Fail Closed** | Se broker non raggiungibile → NO TRADE, non riprovare all'infinito |
| 2 | **Event-Driven** | Ogni stato order emette evento NATS (Phase 0) |
| 3 | **Paper First** | Tutti i test su paper broker; IBKR/CCXT solo dopo validazione |
| 4 | **Idempotenza** | Ogni ordine ha `order_id` univoco; duplicati = reject silenzioso |
| 5 | **Audit Trail** | Tutti gli ordini su Experiment Registry |
| 6 | **No LLM** | Execution layer = 0% AI. Solo codice deterministico |

---

## 3. Broker APIs (dalla ricerca)

| Broker | Libreria | Asset | Stato |
|--------|----------|-------|-------|
| **Interactive Brokers** | `ib_insync` (Python sync/async) | Stocks, Options, Futures, FX | Pianificato |
| **Binance / 100+ crypto** | `ccxt` (Python/JS) | Crypto spot + futures | Pianificato |
| **Paper Trading** | Broker interno (mock fills) | Tutti | **Primo** |

**Perché queste scelte:**
- `ib_insync` → 25.4K★, gold standard per IBKR, API matura (1995+)
- `ccxt` → 34K★, 100+ exchange, unificato, mantenuto attivamente
- `nautilus_trader` → già in `pyproject.toml` come dipendenza (Phase 2), ha broker connector IBKR. Potenzialmente riutilizzabile in Phase 5.5

---

## 4. Task Breakdown

### Week 1: Order Manager (`execution/order_manager/`)

**T1: Order Manager Core — 3 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/order_manager/manager.py` | `OrderManager`: riceve PortfolioDecision, crea Order, lifecycle management, event emission | E |
| `execution/order_manager/types.py` | `OrderRequest`, `OrderResult`, `FillReport` (pydantic) | T |
| `execution/order_manager/inventory.py` | `InventoryTracker`: posizioni aperte, P&L non realizzato | E |
| `tests/execution/test_order_manager.py` | 8+ test: create order, lifecycle transitions, duplicate reject | T |

**T2: Portfolio Bridge — 2 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/order_manager/bridge.py` | `PortfolioBridge`: adatta PortfolioDecision (Phase 4) → OrderRequest | E |
| `tests/execution/test_bridge.py` | 6+ test: decision mapping, edge cases | T |

---

### Week 2: Paper Broker (`execution/brokers/`)

**T3: Paper Broker + Protocol — 3 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/brokers/protocol.py` | `BrokerProtocol`: submit, cancel, status, connect, disconnect | T |
| `execution/brokers/paper.py` | `PaperBroker`: simulate fills con spread, slippage model, partial fills | E |
| `execution/brokers/types.py` | `BrokerOrder`, `BrokerFill`, `BrokerPosition` | T |
| `tests/execution/test_paper_broker.py` | 10+ test: market fill, partial fill, slippage, reject | T |

**T4: IBKR Connector — 3 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/brokers/ibkr.py` | `IBKRBroker`: ib_insync wrapper, connect, submit, cancel, position sync | E |
| `execution/brokers/ibkr_config.py` | `IBKRConfig`: host, port, client_id, account | T |
| `tests/execution/test_ibkr.py` | 4+ test con mock ib_insync | T |

---

### Week 3: CCXT + Execution Algos

**T5: CCXT Connector — 2 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/brokers/ccxt_broker.py` | `CCXTBroker`: ccxt wrapper, exchange abstraction | E |
| `execution/brokers/ccxt_config.py` | `CCXTConfig`: exchange, api_key, secret, sandbox | T |
| `tests/execution/test_ccxt.py` | 4+ test con ccxt mocked exchange | T |

**T6: Execution Algos (`execution/algos/`) — 3 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/algos/protocol.py` | `ExecutionAlgo` protocol: execute(order, market_data) → list[FillReport] | T |
| `execution/algos/market.py` | `MarketOrderAlgo`: submit immediately at market | T |
| `execution/algos/vwap.py` | `VWAPAlgo`: slice order across N intervals aligned to volume profile | E |
| `execution/algos/twap.py` | `TWAPAlgo`: slice order across N equal time intervals | E |
| `execution/algos/iceberg.py` | `IcebergAlgo`: hidden quantity, show small portion at a time | E |
| `execution/algos/factory.py` | `create_algo(name, config) → ExecutionAlgo` | T |
| `tests/execution/test_algos.py` | 10+ test: market fill, VWAP schedule, TWAP timing, iceberg display | T |

---

### Week 4: CLI + Integrazione + Test

**T7: Broker Registry + CLI — 3 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/brokers/__init__.py` | `BrokerRegistry`: get/set active broker | T |
| `execution/__init__.py` | Re-export: OrderManager, disponi broker factory | T |
| `apps/cli/main.py` | `oracle trade submit --instrument SPY --side buy --qty 100` | E |
| `apps/cli/trade_commands.py` | Trade CLI handlers | E |
| `tests/execution/test_cli.py` | 6+ test: CLI trade commands | T |

**T8: Integrazione con Phase 4 — 2 giorni**

| Task | Cosa |
|------|------|
| Bridge | PortfolioDecision → OrderManager: collegamento diretto |
| Orchestrator update | `MASOrchestrator.run()` esegue trade se decision=BUY/SELL |
| Safety check | RiskManager chiamato DOPO OrderManager come sanity |
| Fire Drill | Paper broker con dati sintetici: MAS decide → ordine eseguito → evento emesso |

**T9: Final — 2 giorni**

| Subtask | Target |
|---------|--------|
| ruff check execution/ | Clean |
| mypy --strict execution/ | Clean |
| pytest tests/execution/ -q | ≥ 50 test |
| Showcase update | 19/19 componenti |
| Commit | `feat: Phase 5 Execution Engine` |

---

## 5. Dipendenze Nuove

```toml
execution = [
    "ib-insync>=0.10",
    "ccxt>=4.4",
]
```

---

## 6. BrokerProtocol (Interfaccia)

```python
class BrokerProtocol(Protocol):
    """Connector astratto per qualsiasi broker."""

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...

    async def submit_order(self, order: Order) -> str:
        """Submit order → broker_order_id."""
        ...

    async def cancel_order(self, broker_order_id: str) -> bool: ...
    async def order_status(self, broker_order_id: str) -> OrderStatus: ...
    async def positions(self) -> list[BrokerPosition]: ...
```

---

## 7. Esecuzione Consigliata (Team Mode)

```
Week 1: T1 (OrderManager) + T2 (PortfolioBridge) — parallelo
Week 2: T3 (PaperBroker) + T4 (IBKR) — paralleli (paper broker mocka ibkr)
Week 3: T5 (CCXT) + T6 (Algos) — paralleli
Week 4: T7 (CLI+Registry) + T8 (Phase 4 Integrazione) + T9 (Final) — in serie
```

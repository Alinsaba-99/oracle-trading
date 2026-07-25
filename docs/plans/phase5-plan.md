# Phase 5 — Execution Engine (v2)

> 5 settimane · 8 task · Broker connectors, Order Manager, Execution Algos, Market Data
> Base: Phase 4 MAS completa · Scaffold `execution/` già esistente (vuoto)
> Review: CEO (5.9KB) + Engineering (4.3KB) + Design (7.0KB) — 3 revisioni incorporate

---

## 1. Decisioni dalla Review

| # | Review | Issue | Decisione |
|---|--------|-------|-----------|
| 1 | **CEO/Eng/Design** | RiskManager dopo OrderManager = invertito | **RiskManager gate PRIMA** della creazione Order. Due gates distinte: (a) pre-decisione Kelly/VaR in Phase 4, (b) pre-submission position/concentration check in Execution |
| 2 | **CEO/Eng** | IBKR 3gg = irrealistico | **Wrap nautilus_trader** (già installato) dietro BrokerProtocol. Risparmia ~2 settimane di debugging API |
| 3 | **Design** | BrokerProtocol no streaming | Aggiungere `stream_orders()`, `stream_positions()`, `amend_order()` al protocollo |
| 4 | **CEO/Design** | CLI troppo minimale | 9 flag: `--algo`, `--price`, `--order-type`, `--time-in-force`, `--broker`, `--dry-run`, `--algo-config`. 5 verbi: `submit`, `list`, `cancel`, `status`, `kill` |
| 5 | **Design** | Algos senza market data = showstopper | Aggiungere `MarketDataFeed` per volume profile (VWAP) e prezzi real-time |
| 6 | **Eng** | float→Decimal nel bridge | `Decimal(str(position_size)).quantize(...)` al confine PortfolioBridge |
| 7 | **Eng** | Eventi lifecycle mancanti | Aggiungere `OrderCancelledEvent`, `OrderRejectedEvent`, `OrderPartiallyFilledEvent`, `OrderAmendedEvent` |
| 8 | **CEO/Eng** | No reconnection strategy | `is_connected()`, `health()`, exponential backoff reconnect in BrokerProtocol |
| 9 | **Eng/Design** | MarketOrderAlgo = no-op | Rimosso. Sostituito da path diretto in OrderManager |
| 10 | **Eng** | Config duplicati | Collassare `ibkr_config.py` + `ccxt_config.py` in singolo `BrokerConfig` |

---

## 2. Architettura (Revisionata)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PORTFOLIO MANAGER (Phase 4)                           │
│  Produce: PortfolioDecision { direction, instrument, size, confidence } │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ PortfolioDecision
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      PORTFOLIO BRIDGE (T2)                               │
│  - Converte PortfolioDecision → OrderRequest                            │
│  - float → Decimal con quantize(0.0001)                                 │
│  - Mappa confidence → execution algo (high=market, low=VWAP)           │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ OrderRequest
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ORDER MANAGER (T1)                               │
│  - Riceve OrderRequest                                                  │
│  ▶ RISK GATE #2: position/concentration check contro posizioni aperte   │
│  - Seleziona ExecutionAlgo                                              │
│  - Crea Order → lifecycle: pending → submitted                          │
│  - Emette OrderSubmittedEvent su NATS                                   │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │ Order → ExecutionAlgo
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     EXECUTION ALGOS (T6)                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │  VWAP    │  │  TWAP    │  │ Iceberg  │  │  Market  │               │
│  │(vol.prof)│  │(time sch)│  │(hidden)  │  │(direct)  │               │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘               │
│  ↑ bisogno di MarketDataFeed per prezzi e volumi                        │
└─────────────┬─────────────────────────────────────┬─────────────────────┘
              │ Order slice                         │ FillReport
              ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BROKER CONNECTORS                                │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌──────────────┐      │
│  │ nautilus_trader IBKR │  │ nautilus_trader  │  │ PAPER (sim)  │      │
│  │ (wrap → BrokerProto) │  │ CCXT (wrap)      │  │ mock fills   │      │
│  └──────────────────────┘  └──────────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Principi (v2)

| # | Principio | Conseguenza |
|---|-----------|-------------|
| 1 | **Risk gate PRIMA** | RiskManager chiamato prima di creare qualsiasi Order. Mai "sanity check" dopo |
| 2 | **nautilus_trader first** | Broker connector wrappa nautilus_trader (già installato), non codice custom |
| 3 | **Streaming nativo** | BrokerProtocol ha stream_orders/stream_positions per fills real-time |
| 4 | **Kill switch** | `oracle trade kill` cancella tutti gli ordini aperti su tutti i broker |
| 5 | **Market Data** | ExecutionAlgos ricevono MarketDataFeed per prezzi e volumi real-time |
| 6 | **Fail Closed** | Se broker non raggiungibile → NO TRADE, con riconnessione esponenziale |
| 7 | **Audit Trail** | Ogni order lifecycle event → Experiment Registry |

---

## 3. Task Breakdown (v2)

### Week 1: Order Manager + Bridge

**T1: Order Manager Core — 3 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/order_manager/manager.py` | `OrderManager`: OrderRequest → lifecycle → algo dispatch → broker | E |
| `execution/order_manager/types.py` | `OrderRequest`, `OrderResult`, `FillReport` (pydantic, Decimal) | T |
| `execution/order_manager/inventory.py` | `InventoryTracker`: posizioni aperte, P&L non realizzato, daily loss limit | E |
| `execution/order_manager/errors.py` | `OrderRejectedError`, `BrokerTimeoutError`, `OrderNotFoundError` | T |
| `tests/execution/test_order_manager.py` | 10+ test: create, lifecycle, risk gate, reject, timeout | T |

**T2: Portfolio Bridge — 2 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/order_manager/bridge.py` | `PortfolioBridge`: PortfolioDecision→OrderRequest, float→Decimal, algo mapping, RiskManager pre-gate | E |
| `tests/execution/test_bridge.py` | 8+ test: decision mapping, Decimal conversion, risk reject | T |

### Week 2: Broker Protocol + Paper + Eventi

**T3: Broker Protocol + Paper — 3 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/brokers/protocol.py` | `BrokerProtocol`: submit, cancel, amend, status, connect, disconnect, is_connected, health, stream_orders, stream_positions | T |
| `execution/brokers/types.py` | `BrokerOrder`, `BrokerFill`, `BrokerPosition` + `namespaced_id` (broker:local_id) | T |
| `execution/brokers/config.py` | `BrokerConfig` unico (ibkr_host, ibkr_port, ccxt_exchange, api_key, sandbox_mode) | T |
| `execution/brokers/base.py` | `BaseBroker`: reconnect con backoff esponenziale, health check, heartbeats | E |
| `execution/brokers/paper.py` | `PaperBroker`: simulate fills, spread 1%, slippage 0.5%, partial fills 50% prob | E |
| `tests/execution/test_paper_broker.py` | 10+ test: fill, slippage, partial, reject, reconnect | T |

**T4: Lifecycle Events — 1 giorno**

| File | Subtask |
|------|---------|
| `core/events/order.py` | Aggiungere: `OrderCancelledEvent`, `OrderRejectedEvent`, `OrderPartiallyFilledEvent`, `OrderAmendedEvent` |

### Week 3: Broker Connectors (nautilus_trader wrap)

**T5: IBKR + CCXT via nautilus_trader — 4 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/brokers/nautilus_ibkr.py` | `NautilusIBKRBroker`: wrappa nautilus_trader IBKR adapter dietro BrokerProtocol | E |
| `execution/brokers/nautilus_ccxt.py` | `NautilusCCXTBroker`: wrappa nautilus_trader CCXT adapter dietro BrokerProtocol | E |
| `execution/brokers/registry.py` | `BrokerRegistry`: get/set active broker, health report | T |
| `tests/execution/test_nautilus.py` | 6+ test con nautilus mocked | T |

### Week 4: Execution Algos + Market Data

**T6: Execution Algos + MarketDataFeed — 4 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `execution/algos/protocol.py` | `ExecutionAlgo` protocol: execute(order, market_data) → AsyncGenerator[FillReport] | T |
| `execution/algos/scheduler.py` | `AlgoScheduler`: shared interval/volume calculation per TWAP/VWAP | E |
| `execution/algos/vwap.py` | `VWAPAlgo`: slice per volume profile (richiede MarketDataFeed) | E |
| `execution/algos/twap.py` | `TWAPAlgo`: slice per intervalli temporali uguali | E |
| `execution/algos/iceberg.py` | `IcebergAlgo`: hidden quantity, display_size, refresh_interval | E |
| `execution/algos/factory.py` | `create_algo(name, config) → ExecutionAlgo` | T |
| `execution/market_data.py` | `MarketDataFeed`: prezzo real-time, volume profile, spread | E |
| `tests/execution/test_algos.py` | 12+ test: VWAP schedule, TWAP timing, Iceberg display_qty, factory | T |

### Week 5: CLI + Integrazione + Final

**T7: CLI estesa — 3 giorni**

| File | Subtask | Agente |
|------|---------|--------|
| `apps/cli/trade_commands.py` | Handler: submit (--algo, --price, --order-type, --time-in-force, --broker, --dry-run, --algo-config), list, cancel <id>, status <id>, kill | E |
| `apps/cli/main.py` | Estensione subparser trade con 5 verbi | E |
| `tests/execution/test_cli.py` | 10+ test: tutti i comandi, flag parsing, --dry-run | T |

**T8: Integrazione Phase 4 + Final — 3 giorni**

| Task | Cosa |
|------|------|
| Bridge vivo | `MASOrchestrator.run()` → se decision=BUY/SELL → `OrderManager.submit()` |
| Risk chain completa | Phase 4 Kelly/VaR (gate #1) + Execution position/concentration (gate #2) |
| Fire Drill | Paper broker: MAS decide → ordine eseguito → fill event → NATS emesso |
| Kill switch test | `oracle trade kill` cancella tutti gli ordini |
| Showcase | 19/19 componenti |
| ruff + mypy + pytest | ≥ 60 test, clean |
| Commit | `feat: Phase 5 Execution Engine` |

---

## 4. Dipendenze

```toml
execution = [
    "ib-insync>=0.10",
    "ccxt>=4.4",
]
```

nautilus_trader è **già installato** (Phase 2 dipendenza).

---

## 5. BrokerProtocol (v2 — con streaming)

```python
class BrokerProtocol(Protocol):
    """Connector astratto per qualsiasi broker, con streaming."""

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def is_connected(self) -> bool: ...
    async def health(self) -> dict[str, Any]: ...

    async def submit_order(self, order: Order) -> str: ...
    async def cancel_order(self, broker_order_id: str) -> bool: ...
    async def amend_order(self, broker_order_id: str, **changes) -> bool: ...
    async def order_status(self, broker_order_id: str) -> OrderStatus: ...

    async def stream_orders(self) -> AsyncGenerator[BrokerOrder, None]: ...
    async def stream_positions(self) -> AsyncGenerator[BrokerPosition, None]: ...
    async def positions(self) -> list[BrokerPosition]: ...
```

---

## 6. CLI Completa

```bash
# Verbi
oracle trade submit --instrument SPY --side buy --qty 100              # Market default
oracle trade submit --instrument SPY --side buy --qty 100 --algo vwap  # VWAP algo
oracle trade submit --instrument SPY --side buy --qty 100 --price 450 --order-type limit --time-in-force day --broker paper
oracle trade submit --instrument SPY --side buy --qty 100 --dry-run    # Valida senza inviare
oracle trade list                           # Ordini aperti
oracle trade cancel <order_id>             # Cancella ordine
oracle trade status <order_id>             # Stato dettagliato
oracle trade kill                          # EMERGENZA: cancella tutti gli ordini
```

---

## 7. Esecuzione (Team Mode)

```
Week 1: T1 (OrderManager) + T2 (PortfolioBridge) — parallelo
Week 2: T3 (BrokerProtocol+Paper+Base+Config) + T4 (Eventi mancanti) — parallelo
Week 3: T5 (nautilus IBKR + CCXT) — 1 agente (4gg)
Week 4: T6 (Algos + MarketDataFeed) — 2 agenti paralleli (algos, market_data)
Week 5: T7 (CLI estesa) + T8 (Integrazione + Final) — in serie
```

# Oracle Domain Model v1.0

> Modello di dominio congelato. Entità, attributi, relazioni, invarianti.
> Ogni modifica sostanziale richiede ADR.

---

## 1. Entità Principali

```
┌─────────────────────────────────────────────────────────────────┐
│                         ASSET CLASS                             │
│  abstract                                                       │
├─────────────────────────────────────────────────────────────────┤
│  asset_id: str              # "AAPL", "BTC-USD", "EUR-USD"      │
│  asset_class: AssetClass    # equity | crypto | fx | option     │
│  exchange: str              # NASDAQ | BINANCE | IDEALPRO       │
│  currency: str              # USD | EUR | BTC                   │
│  active: bool               # Abilitato per trading             │
│  lot_size: Decimal          # Minimo trading unit               │
│  tick_size: Decimal         # Minimo price increment            │
└─────────────────────────────────────────────────────────────────┘
         ▲                  ▲                 ▲             ▲
         │                  │                 │             │
┌────────┴──────┐  ┌────────┴──────┐  ┌──────┴───────┐  ┌──┴────────┐
│    EQUITY     │  │    CRYPTO     │  │      FX      │  │  OPTION   │
├───────────────┤  ├──────────────┤  ├──────────────┤  ├───────────┤
│ sector: str   │  │ token: str   │  │ quote_cur:   │  │ strike:   │
│ market_cap:   │  │ chain: str   │  │ str          │  │ Decimal   │
│ Decimal       │  │ contract:    │  │ pip_value:   │  │ expiry:   │
│ dividend_yield│  │ str          │  │ Decimal      │  │ datetime  │
│ shares_out:   │  │ decimals:    │  │ rollover:    │  │ option:   │
│ int           │  │ int          │  │ Decimal      │  │ call|put  │
│ sector: str   │  │ supply:      │  │              │  │ iv: Dec   │
│ industry: str │  │ Decimal      │  │              │  │ oi: int   │
└───────────────┘  └──────────────┘  └──────────────┘  └───────────┘
```

### Invarianti

- `asset_id` è unico per exchange
- Un option ha sempre come underlying un altro Instrument
- `tick_size` > 0, `lot_size` > 0

---

## 2. Bar e Tick

```
┌──────────────────────────┐      ┌──────────────────────────┐
│          TICK            │      │         BAR              │
├──────────────────────────┤      ├──────────────────────────┤
│ instrument_id: str       │      │ instrument_id: str       │
│ timestamp: datetime      │      │ timestamp: datetime      │
│ price: Decimal           │      │ timeframe: Timeframe     │
│ volume: Decimal          │      │ open: Decimal            │
│ side: buy|sell           │      │ high: Decimal            │
│ exchange: str            │      │ low: Decimal             │
│                          │      │ close: Decimal           │
│                          │      │ volume: Decimal          │
│                          │      │ trades: int              │
│                          │      │ vwap: Decimal            │
│                          │      │ oi: int (futures/options)│
│                          │      │ complete: bool           │
└──────────────────────────┘      └──────────────────────────┘
```

### Invarianti

- `open ≤ high`, `low ≤ close` (per bar bullish)
- `open ≥ high`, `low ≥ close` (per bar bearish)
- `high ≥ low` sempre
- `volume ≥ 0`

---

## 3. Feature

```
┌───────────────────────────────────┐
│            FEATURE                │
├───────────────────────────────────┤
│ feature_id: str                   │
│ instrument_id: str                │
│ timestamp: datetime               │
│ feature_set: str                  │   # "technical_v2"
│ name: str                         │   # "rsi_14"
│ value: float                      │
│ version: str                      │   # "v2.3"
│ computed_at: datetime             │
│ computation_time_ms: float        │
└───────────────────────────────────┘
```

### Feature Store

```
┌───────────────────────────────────┐
│        FEATURE_SET_VERSION        │
├───────────────────────────────────┤
│ feature_set: str                  │
│ version: str                      │
│ created_at: datetime              │
│ git_commit: str                   │
│ features: list[str]               │   # Lista feature incluse
│ description: str                  │
└───────────────────────────────────┘
```

### Invarianti

- Una feature è sempre associata a un feature_set + version
- Ogni feature_set ha una history di versioni immutabili

---

## 4. Signal

```
┌───────────────────────────────────┐
│            SIGNAL                 │
├───────────────────────────────────┤
│ signal_id: str                    │
│ instrument_id: str                │
│ timestamp: datetime               │
│ strategy_id: str                  │
│ direction: long|short|neutral     │
│ confidence: float (0-1)           │
│ timeframe: Timeframe              │
│ source: str                       │   # "genetic_047" | "agent:technical"
│ metadata: dict                    │   # Scoring breakdown, weights
└───────────────────────────────────┘
```

### Invarianti

- `confidence` è sempre in [0, 1]
- Un signal non modificato dopo la creazione (immutabile)
- Un signal filtrato produce un evento `signal.filtered`, non modifica il signal

---

## 5. Order

```
┌───────────────────────────────────┐
│            ORDER                  │
├───────────────────────────────────┤
│ order_id: str                     │
│ instrument_id: str                │
│ portfolio_id: str                 │
│ side: buy|sell                    │
│ order_type: market|limit|stop     │
│ quantity: Decimal                 │
│ price: Decimal | None             │   # None per market orders
│ stop_price: Decimal | None        │   # Per stop orders
│ time_in_force: day|gtc|ioc|fok    │
│ status: pending|submitted|        │
│         partially_filled|filled|  │
│         cancelled|rejected        │
│ strategy_id: str                  │
│ execution_algo: str | None        │
│ broker_order_id: str | None       │
│ filled_quantity: Decimal          │
│ avg_fill_price: Decimal | None    │
│ commission: Decimal               │
│ submitted_at: datetime            │
│ filled_at: datetime | None        │
│ error: str | None                 │
└───────────────────────────────────┘
```

### Invarianti

- market orders NON hanno `price`
- limit orders HANNO `price`
- stop orders HANNO `stop_price`
- `filled_quantity ≤ quantity`
- `filled_quantity = 0` per ordini non eseguiti
- commission ≥ 0

---

## 6. Trade

```
┌───────────────────────────────────┐
│            TRADE                  │
├───────────────────────────────────┤
│ trade_id: str                     │
│ instrument_id: str                │
│ portfolio_id: str                 │
│ direction: long|short             │
│ status: open|closed               │
│ entry_time: datetime              │
│ exit_time: datetime | None        │
│ entry_price: Decimal              │
│ exit_price: Decimal | None        │
│ quantity: Decimal                 │
│ pnl: Decimal | None               │
│ pnl_pct: float | None             │
│ exit_reason: str | None           │
│ strategy_id: str                  │
│ signal_id: str                    │
│ orders: list[str]                 │   # Order IDs
│ initial_stop_loss: Decimal | None │
│ initial_take_profit: Decimal |None│
│ regime_at_entry: str | None       │
│ regime_at_exit: str | None        │
│ agents_involved: list[str]        │
└───────────────────────────────────┘
```

### Invarianti

- Un trade ha `status = open` quando entry_price è impostato
- Un trade ha `status = closed` quando exit_price è impostato
- `pnl = (exit_price - entry_price) * quantity` per long
- `pnl = (entry_price - exit_price) * quantity` per short
- Un trade closed ha exit_time ≥ entry_time

---

## 7. Position

```
┌───────────────────────────────────┐
│          POSITION                 │
├───────────────────────────────────┤
│ instrument_id: str                │
│ portfolio_id: str                 │
│ quantity: Decimal                 │   # Positive = long, Negative = short
│ avg_entry_price: Decimal          │
│ current_price: Decimal            │
│ unrealized_pnl: Decimal           │
│ realized_pnl: Decimal             │
│ weight: float (0-1)               │   # % del portafoglio
│ updated_at: datetime              │
└───────────────────────────────────┘
```

### Invarianti

- `unrealized_pnl = (current_price - avg_entry_price) * quantity` per long
- `quantity = 0` significa posizione chiusa

---

## 8. Portfolio

```
┌───────────────────────────────────┐
│          PORTFOLIO                │
├───────────────────────────────────┤
│ portfolio_id: str                 │
│ name: str                         │
│ type: live|paper|shadow|backtest  │
│ total_value: Decimal              │
│ cash: Decimal                     │
│ exposure: float (0-1)             │
│ leverage: float                   │
│ day_pnl: Decimal                  │
│ total_pnl: Decimal                │
│ total_return: float               │
│ positions: dict[str, Position]    │
│ updated_at: datetime              │
│ risk_metrics: RiskMetrics         │
└───────────────────────────────────┘
```

### Invarianti

- `total_value = cash + Σ position.market_value`
- `exposure = Σ abs(position.weight)` (non può superare leverage)
- Un portfolio tipo `live` non può essere modificato da backtest

---

## 9. RiskMetrics

```
┌───────────────────────────────────┐
│         RISK_METRICS              │
├───────────────────────────────────┤
│ portfolio_id: str                 │
│ timestamp: datetime               │
│ var_95: float                     │
│ var_99: float                     │
│ cvar_95: float                    │
│ max_drawdown: float               │
│ current_drawdown: float           │
│ sharpe_ratio: float               │   # Rolling annualized
│ sortino_ratio: float              │
│ calmar_ratio: float               │
│ volatility: float                 │   # Annualized
│ beta: float                       │
│ correlation_to_benchmark: float   │
│ concentration: float              │   # Herfindahl index
│ updated_at: datetime              │
└───────────────────────────────────┘
```

### Invarianti

- `var_95` e `var_99` sono espressi come valori assoluti in unità base
- `max_drawdown` è un numero positivo (es: 0.15 = 15% drawdown)
- `concentration` è in [0, 1]

---

## 10. Strategy

```
┌───────────────────────────────────┐
│          STRATEGY                 │
├───────────────────────────────────┤
│ strategy_id: str                  │
│ name: str                         │
│ version: str                      │
│ status: developing|backtesting|   │
│         paper|shadow|live|paused  │
│ genome: Genome                    │   # Pipeline modulare
│ metrics: StrategyMetrics          │
│ created_at: datetime              │
│ updated_at: datetime              │
│ experiment_id: str | None         │   # Experiment che l'ha prodotta
└───────────────────────────────────┘
```

---

## 11. Regime

```
┌───────────────────────────────────┐
│           REGIME                  │
├───────────────────────────────────┤
│ instrument_id: str | "global"     │
│ timestamp: datetime               │
│ volatility: low|medium|high|panic │
│ trend: bull|bear|sideways|choppy  │
│ liquidity: normal|tight|crisis    │
│ correlation: risk_on|risk_off|    │
│              mixed                │
│ phase: accumulation|markup|       │
│        distribution|markdown      │
│ scores: dict[str, float]          │   # Confidence per detection method
│ methods: list[str]                │   # "hmm", "bocd", "pelt", "vol_cluster"
└───────────────────────────────────┘
```

---

## 12. Policy

```
┌───────────────────────────────────┐
│           POLICY                  │
├───────────────────────────────────┤
│ policy_id: str                    │
│ name: str                         │
│ type: hard_limit|soft_limit|      │
│       compliance|market_condition|│
│       governance                  │
│ enabled: bool                     │
│ priority: int                     │   # Ordine di valutazione
│ conditions: list[PolicyCondition] │
│ action: block|warn|require_approval
│ config: dict                      │
└───────────────────────────────────┘
```

---

## 13. Experiment

```
┌───────────────────────────────────┐
│          EXPERIMENT               │
├───────────────────────────────────┤
│ experiment_id: str                │
│ type: backtest|ga_run|training    │
│        |paper_trade               │
│ timestamp: datetime               │
│ git_commit: str                   │
│ status: running|completed|failed  │
│ dataset_version: str              │
│ feature_version: str              │
│ genome_hash: str | None           │
│ config_hash: str                  │
│ random_seed: int                  │
│ metrics: dict                     │
│ artifacts: list[str]              │
│ duration_seconds: float           │
│ error: str | None                 │
└───────────────────────────────────┘
```

---

## 14. Enumerazioni

```python
OracleMode = Enum("research", "replay", "paper", "shadow", "evaluation", "funded")
AssetClass = Enum("equity", "crypto", "fx", "option", "future")
Timeframe = Enum("tick", "1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M")
OrderSide = Enum("buy", "sell")
OrderType = Enum("market", "limit", "stop")  # paper broker accetta anche "stop_limit" a runtime
TimeInForce = Enum("day", "gtc", "ioc", "fok")
OrderStatus = Enum("pending", "submitted", "partially_filled", "filled", "cancelled", "rejected")
TradeDirection = Enum("long", "short")
TradeStatus = Enum("open", "closed")
PortfolioType = Enum("live", "paper", "shadow", "backtest")
StrategyStatus = Enum("developing", "backtesting", "paper", "shadow", "live", "paused")
RegimeVolatility = Enum("low", "medium", "high", "panic")
RegimeTrend = Enum("bull", "bear", "sideways", "choppy")
RegimeLiquidity = Enum("normal", "tight", "crisis")
RegimeCorrelation = Enum("risk_on", "risk_off", "mixed")
MarketPhase = Enum("accumulation", "markup", "distribution", "markdown")
PolicyType = Enum("hard_limit", "soft_limit", "compliance", "market_condition", "governance")
```

> Fonti reali: `core/domain/enums.py` (AssetClass..PolicyType) e
> `core/domain/mode.py:17` (OracleMode, transizioni irregressibili
> research→…→funded). `stop_limit` non è nell'enum `OrderType` ma è accettato
> dal paper broker (`execution/brokers/paper.py`).

---

## 15. Relazioni

```
Asset 1──N Bar
Asset 1──N Tick
Asset 1──N Feature
Asset 1──N Signal
Asset 1──N Trade

Portfolio 1──N Position
Portfolio 1──N Trade
Portfolio 1──N Order
Portfolio 1──1 RiskMetrics

Strategy 1──1 Genome
Strategy 1──N Signal
Strategy 1──N Trade
Strategy N──1 Experiment

Trade 1──N Order
Trade 1──1 Signal (source)

Policy N──N Strategy (via Policy Engine evaluation)
```

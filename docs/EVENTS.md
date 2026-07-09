# Oracle Event Contracts

> Tutta la comunicazione tra componenti avviene via eventi NATS.
> Nessun componente chiama direttamente un altro.
> ADR-001: NATS come Event Bus.

---

## 1. Event Envelope

Ogni evento NATS segue questo schema standard:

```json
{
  "id": "uuid-string",
  "type": "market.tick",
  "version": 1,
  "timestamp": "2026-07-06T14:30:00.000Z",
  "source": "service.ingestion",
  "trace_id": "uuid-string",
  "data": {}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID v4 | Identificatore univoco dell'evento |
| `type` | string | Nome del tipo di evento (dot-notation) |
| `version` | int | Versione dello schema dell'evento |
| `timestamp` | ISO8601 | Timestamp di emissione |
| `source` | string | Servizio/plugin che ha emesso l'evento |
| `trace_id` | UUID v4 | Trace ID end-to-end per debugging |
| `data` | object | Payload specifico del tipo di evento |

---

## 2. NATS Subjects

```
market.>          # Dati di mercato
  market.tick
  market.bar
  market.orderbook
  market.trade (realizzato)

feature.>         # Feature calcolate
  feature.updated
  feature.batch

signal.>          # Segnali
  signal.generated
  signal.filtered

regime.>          # Regime di mercato
  regime.updated

risk.>            # Risk metrics
  risk.evaluated
  risk.limit_breached

policy.>          # Policy Engine
  policy.approved
  policy.rejected
  policy.warning

order.>           # Ordini
  order.submitted
  order.cancelled
  order.rejected
  order.filled

trade.>           # Trade
  trade.opened
  trade.closed
  trade.updated

portfolio.>       # Portfolio
  portfolio.updated
  portfolio.rebalanced
  portfolio.risk_updated

strategy.>        # Strategie
  strategy.evolved
  strategy.deployed
  strategy.paused

experiment.>      # Esperimenti
  experiment.started
  experiment.completed
  experiment.failed

agent.>           # Agenti
  agent.analysis.completed
  agent.debate.completed
  agent.decision.proposed

system.>          # Sistema
  system.health
  system.plugin.registered
  system.config.updated
  system.error
```

---

## 3. Event Schemas

### 3.1 market.tick

```json
{
  "type": "market.tick",
  "version": 1,
  "data": {
    "instrument_id": "AAPL",
    "asset_class": "equity",
    "exchange": "NASDAQ",
    "timestamp": "2026-07-06T14:30:00.123456Z",
    "bid": 198.50,
    "ask": 198.52,
    "last": 198.51,
    "volume": 1500,
    "bid_size": 100,
    "ask_size": 200
  }
}
```

### 3.2 market.bar

```json
{
  "type": "market.bar",
  "version": 1,
  "data": {
    "instrument_id": "BTC-USD",
    "asset_class": "crypto",
    "exchange": "BINANCE",
    "timestamp": "2026-07-06T14:30:00Z",
    "timeframe": "1m",
    "open": 62345.0,
    "high": 62400.0,
    "low": 62320.0,
    "close": 62380.0,
    "volume": 125.5,
    "trades": 342
  }
}
```

### 3.3 market.orderbook

```json
{
  "type": "market.orderbook",
  "version": 1,
  "data": {
    "instrument_id": "SPY",
    "asset_class": "equity",
    "exchange": "ARCA",
    "timestamp": "2026-07-06T14:30:00Z",
    "bids": [
      {"price": 543.20, "size": 500},
      {"price": 543.19, "size": 1200}
    ],
    "asks": [
      {"price": 543.21, "size": 800},
      {"price": 543.22, "size": 300}
    ],
    "bid_depth": 5,
    "ask_depth": 5
  }
}
```

### 3.4 feature.updated

```json
{
  "type": "feature.updated",
  "version": 1,
  "data": {
    "instrument_id": "AAPL",
    "timestamp": "2026-07-06T14:30:00Z",
    "feature_set": "technical_v2",
    "features": {
      "sma_20": 195.5,
      "sma_50": 192.3,
      "rsi_14": 62.5,
      "atr_14": 2.34,
      "bb_upper": 201.2,
      "bb_lower": 189.8,
      "volume_sma_20": 45000000
    }
  }
}
```

### 3.5 regime.updated

```json
{
  "type": "regime.updated",
  "version": 1,
  "data": {
    "timestamp": "2026-07-06T14:30:00Z",
    "instrument_id": "SPY",
    "regime": {
      "volatility": "medium",
      "trend": "bull",
      "liquidity": "normal",
      "correlation": "risk_on",
      "phase": "markup"
    },
    "scores": {
      "hmm_regime": 0.82,
      "volatility_cluster": "medium",
      "bocd_change_point": false
    }
  }
}
```

### 3.6 signal.generated

```json
{
  "type": "signal.generated",
  "version": 1,
  "data": {
    "instrument_id": "AAPL",
    "timestamp": "2026-07-06T14:30:00Z",
    "strategy_id": "gen_047",
    "direction": "long",
    "confidence": 0.73,
    "timeframe": "1d",
    "reason": "Bullish breakout on volume above SMA_20 with RSI > 50 and bullish MACD crossover",
    "agents_involved": ["technical_analyst", "sentiment_analyst"]
  }
}
```

### 3.7 signal.filtered

```json
{
  "type": "signal.filtered",
  "version": 1,
  "data": {
    "instrument_id": "AAPL",
    "timestamp": "2026-07-06T14:30:00Z",
    "signal_id": "uuid",
    "filter": "earnings_window",
    "reason": "Earnings release within 24h - filtered out",
    "action": "blocked"
  }
}
```

### 3.8 risk.evaluated

```json
{
  "type": "risk.evaluated",
  "version": 1,
  "data": {
    "portfolio_id": "main",
    "timestamp": "2026-07-06T14:30:00Z",
    "metrics": {
      "portfolio_var_95": 0.023,
      "portfolio_var_99": 0.041,
      "max_drawdown": -0.085,
      "current_exposure": 0.65,
      "leverage": 1.0,
      "concentration": {
        "top_position": 0.12,
        "top_sector": 0.25
      },
      "correlation_to_spy": 0.72
    }
  }
}
```

### 3.9 policy.approved / policy.rejected / policy.warning

```json
{
  "type": "policy.approved",
  "version": 1,
  "data": {
    "policy_id": "max_daily_loss",
    "policy_type": "hard_limit",
    "decision": "approved",
    "context": {
      "signal_id": "uuid",
      "instrument_id": "AAPL",
      "proposed_size": 1000,
      "current_pnl": -1500
    },
    "evaluated_at": "2026-07-06T14:30:00Z",
    "evaluation_time_ms": 0.45
  }
}

// Per rejected:
{
  "type": "policy.rejected",
  "version": 1,
  "data": {
    "policy_id": "max_daily_loss",
    "policy_type": "hard_limit",
    "decision": "rejected",
    "reason": "Daily loss limit of $2000 exceeded (current: -$2500)",
    "context": {
      "signal_id": "uuid",
      "instrument_id": "AAPL",
      "proposed_size": 1000,
      "current_pnl": -2500
    }
  }
}
```

### 3.10 order.submitted

```json
{
  "type": "order.submitted",
  "version": 1,
  "data": {
    "order_id": "uuid",
    "instrument_id": "AAPL",
    "side": "buy",
    "order_type": "limit",
    "quantity": 100,
    "price": 198.50,
    "time_in_force": "day",
    "strategy_id": "gen_047",
    "portfolio_id": "main",
    "submitted_at": "2026-07-06T14:30:00Z",
    "broker": "ibkr",
    "execution_algo": "twap"
  }
}
```

### 3.11 order.filled

```json
{
  "type": "order.filled",
  "version": 1,
  "data": {
    "order_id": "uuid",
    "instrument_id": "AAPL",
    "side": "buy",
    "quantity": 100,
    "fill_price": 198.48,
    "fill_quantity": 100,
    "commission": 0.35,
    "filled_at": "2026-07-06T14:30:05.123Z",
    "broker": "ibkr",
    "venue": "NASDAQ"
  }
}
```

### 3.12 trade.opened / trade.closed

```json
{
  "type": "trade.opened",
  "version": 1,
  "data": {
    "trade_id": "uuid",
    "instrument_id": "AAPL",
    "direction": "long",
    "entry_price": 198.48,
    "quantity": 100,
    "entry_time": "2026-07-06T14:30:05Z",
    "strategy_id": "gen_047",
    "signal_id": "uuid",
    "initial_stop_loss": 193.0,
    "initial_take_profit": 210.0
  }
}

{
  "type": "trade.closed",
  "version": 1,
  "data": {
    "trade_id": "uuid",
    "instrument_id": "AAPL",
    "direction": "long",
    "entry_price": 198.48,
    "exit_price": 205.30,
    "quantity": 100,
    "entry_time": "2026-07-06T14:30:05Z",
    "exit_time": "2026-07-10T15:30:00Z",
    "pnl": 682.0,
    "pnl_pct": 0.034,
    "exit_reason": "take_profit",
    "strategy_id": "gen_047",
    "agents_involved": ["technical_analyst", "sentiment_analyst"],
    "regime_at_entry": "bull_markup",
    "regime_at_exit": "bull_markup"
  }
}
```

### 3.13 portfolio.updated

```json
{
  "type": "portfolio.updated",
  "version": 1,
  "data": {
    "portfolio_id": "main",
    "timestamp": "2026-07-06T14:30:00Z",
    "total_value": 1050000.0,
    "cash": 350000.0,
    "exposure": 0.67,
    "positions": [
      {
        "instrument_id": "AAPL",
        "quantity": 1000,
        "avg_entry": 195.0,
        "current_price": 198.50,
        "unrealized_pnl": 3500.0,
        "weight": 0.19
      }
    ],
    "day_pnl": 1250.0,
    "total_pnl": 50000.0
  }
}
```

### 3.14 experiment.completed

```json
{
  "type": "experiment.completed",
  "version": 1,
  "data": {
    "experiment_id": "exp_20260706_ga_047",
    "type": "ga_run",
    "status": "completed",
    "timestamp": "2026-07-06T14:30:00Z",
    "duration_seconds": 3420.5,
    "metrics": {
      "best_sharpe": 1.87,
      "best_sortino": 2.14,
      "best_calmar": 1.52,
      "avg_sharpe": 0.95,
      "max_drawdown": -0.12,
      "convergence_generation": 42
    },
    "artifact_path": "experiments/exp_20260706_ga_047/"
  }
}
```

### 3.15 agent.analysis.completed

```json
{
  "type": "agent.analysis.completed",
  "version": 1,
  "data": {
    "agent": "fundamental_analyst",
    "instrument_id": "AAPL",
    "timestamp": "2026-07-06T14:30:00Z",
    "signal": "buy",
    "confidence": 0.65,
    "summary": "Strong cash flows, P/E 28x slightly above sector but justified by 15% revenue growth. Piotroski F-Score 7/9.",
    "key_metrics": {
      "pe_ratio": 28.5,
      "pb_ratio": 6.2,
      "roe": 0.34,
      "debt_to_equity": 1.5,
      "revenue_growth": 0.15,
      "f_score": 7
    },
    "risks": ["Valuation premium vs sector", "Supply chain concentration in Asia"]
  }
}
```

### 3.16 agent.debate.completed

```json
{
  "type": "agent.debate.completed",
  "version": 1,
  "data": {
    "instrument_id": "AAPL",
    "timestamp": "2026-07-06T14:30:00Z",
    "round": 1,
    "bull_case": "Strong earnings momentum, services revenue growing 18% YoY, massive buyback program",
    "bear_case": "P/E at 5-year high, smartphone market saturation, regulatory risk in EU",
    "devils_advocate": "Both sides assume linear growth - what if AI capex doesn't deliver ROI?",
    "consensus": "cautious_buy",
    "no_trade_recommended": false
  }
}
```

### 3.17 agent.decision.proposed

```json
{
  "type": "agent.decision.proposed",
  "version": 1,
  "data": {
    "instrument_id": "AAPL",
    "timestamp": "2026-07-06T14:30:00Z",
    "portfolio_manager": "pm_v1",
    "decision": "buy",
    "quantity": 500,
    "order_type": "limit",
    "price_limit": 199.00,
    "confidence": 0.68,
    "timeframe": "1w-1m",
    "rationale": "Bullish technical setup confirmed by fundamental strength and positive sentiment",
    "agents_consulted": [
      "technical_analyst",
      "fundamental_analyst",
      "sentiment_analyst"
    ],
    "regime_at_decision": "bull_markup"
  }
}
```

---

## 4. Event Flow — Ciclo Completo di un Trade

```
market.tick / market.bar  (ingestion → analytics)
        │
        ▼
feature.updated           (analytics → feature store)
regime.updated            (analytics → regime detector)
        │
        ▼
signal.generated          (agent system → signal)
        │
        ▼
signal.filtered           (filter genes → decision)
        │
        ▼
risk.evaluated            (risk engine → metrics)
        │
        ▼
policy.approved/rejected  (policy engine → compliance)
        │
        ▼
order.submitted           (execution → broker)
        │
        ▼
order.filled              (broker → execution)
        │
        ▼
trade.opened              (execution → portfolio)
        │
        ▼
... time passes ...
        │
        ▼
trade.closed              (execution → portfolio, audit)
portfolio.updated         (portfolio → dashboard)
```

---

## 5. Tracing

Ogni evento include un `trace_id` che attraversa l'intero ciclo di vita. Un trade partito da `market.tick` e arrivato a `trade.closed` condivide lo stesso `trace_id`.

Strumenti di tracing:
- OpenTelemetry per spans distribuiti
- Jaeger per visualizzazione trace
- Header `trace_id` in ogni evento NATS

# Policy Engine Design v1.0

> Libreria embeddata per valutazione policy. Separata dalle strategie.
> ADR-003: Policy Engine Embeddato.

---

## 1. Principi

1. **Separazione**: Le policy sono completamente indipendenti dalle strategie. Una strategia non può bypassare le policy.
2. **Fail Closed**: Se una policy non può essere valutata (errore, timeout), il default è `Rejected`.
3. **Componibilità**: Le policy sono valutate in catena. Ogni policy può bloccare o approvare.
4. **Configurabilità a Caldo**: Le policy possono essere ricaricate senza riavviare il sistema.
5. **Auditabilità**: Ogni valutazione è tracciata per audit e debugging.

---

## 2. Architettura

```
Strategy
    │
    ▼
┌───────────────────────────────────────────────┐
│              POLICY ENGINE                     │
│                                               │
│  HardLimit ─→ SoftLimit ─→ Compliance ─→      │
│  MarketCondition ─→ Governance                │
│                                               │
│  Ordine: per priorità (decrescente)           │
└──────────────────┬────────────────────────────┘
                   │ PolicyResult
                   ▼
         Approved → Execution
         Rejected → Blocca (con reason)
         Warning  → Continua con flag alert
```

---

## 3. Policy Type

```python
@dataclass
class Policy:
    policy_id: str
    name: str
    type: PolicyType          # hard_limit | soft_limit | compliance | market_condition | governance
    enabled: bool
    priority: int             # Ordine di valutazione (più alto = prima)
    conditions: list["PolicyCondition"]
    action: str               # "block" | "warn" | "require_approval"
    config: dict
    created_at: str
```

### Policy Types

| Type | Comportamento | Esempi |
|------|---------------|--------|
| **HardLimit** | Blocca l'esecuzione se violato | Max loss giornaliero, max exposure, max leverage |
| **SoftLimit** | Allerta, non blocca | Concentration warning, vol warning |
| **Compliance** | Blocca se violato | SEC/MiFID, broker rules, KYC |
| **MarketCondition** | Blocca o avverte | No trade in certi regimi, spread troppo alto |
| **Governance** | Richiede approvazione umana | Trade sopra soglia $, nuovo asset class |

---

## 4. Policy Evaluation

```python
@dataclass
class PolicyContext:
    portfolio: Portfolio
    signal: Signal
    market_state: MarketState
    order: Order | None = None
    regime: Regime | None = None

@dataclass
class PolicyResult:
    decision: str             # "approved" | "rejected" | "warning"
    policy_id: str
    policy_name: str
    policy_type: str
    reason: str | None = None
    details: dict | None = None
    warning: str | None = None
    evaluated_at: str
    evaluation_time_ms: float

@dataclass
class PolicyChainResult:
    results: list[PolicyResult]
    final_decision: str       # "approved" | "rejected"
    rejected_by: str | None   # Prima policy che ha bloccato
```

### Valutazione

```python
class PolicyEngine:
    """Valutatore di policy embeddato."""

    def __init__(self, policies: list[Policy]):
        self.policies = sorted(policies, key=lambda p: -p.priority)

    def evaluate(self, context: PolicyContext) -> PolicyChainResult:
        """Valuta tutte le policy in ordine di priorità."""
        results = []
        for policy in self.policies:
            if not policy.enabled:
                continue

            result = self._evaluate_one(policy, context)
            results.append(result)

            if result.decision == "rejected":
                return PolicyChainResult(
                    results=results,
                    final_decision="rejected",
                    rejected_by=policy.policy_id
                )

        return PolicyChainResult(
            results=results,
            final_decision="approved",
            rejected_by=None
        )

    def _evaluate_one(self, policy: Policy,
                      context: PolicyContext) -> PolicyResult:
        start = time.perf_counter()
        try:
            for condition in policy.conditions:
                violation = self._check_condition(condition, context)
                if violation:
                    elapsed = (time.perf_counter() - start) * 1000
                    return PolicyResult(
                        decision="rejected" if policy.action == "block"
                                 else "warning",
                        policy_id=policy.policy_id,
                        policy_name=policy.name,
                        policy_type=policy.type,
                        reason=violation,
                        evaluated_at=datetime.utcnow().isoformat(),
                        evaluation_time_ms=elapsed
                    )

            elapsed = (time.perf_counter() - start) * 1000
            return PolicyResult(
                decision="approved",
                policy_id=policy.policy_id,
                policy_name=policy.name,
                policy_type=policy.type,
                evaluated_at=datetime.utcnow().isoformat(),
                evaluation_time_ms=elapsed
            )

        except Exception as e:
            # Fail closed: errore → rejected
            return PolicyResult(
                decision="rejected",
                policy_id=policy.policy_id,
                policy_name=policy.name,
                policy_type=policy.type,
                reason=f"Policy evaluation error: {str(e)}",
                evaluated_at=datetime.utcnow().isoformat(),
                evaluation_time_ms=0.0
            )
```

---

## 5. Policy Definitions (YAML)

Le policy sono definite in file YAML separati e caricate all'avvio:

```yaml
# config/policies/risk_limits.yaml
policies:
  - policy_id: "max_daily_loss"
    name: "Maximum Daily Loss"
    type: hard_limit
    priority: 100
    action: block
    conditions:
      - metric: "portfolio.day_pnl"
        operator: "less_than"
        value: -5000           # -$5,000 max loss
        unit: "absolute"

  - policy_id: "max_portfolio_exposure"
    name: "Maximum Portfolio Exposure"
    type: hard_limit
    priority: 90
    action: block
    conditions:
      - metric: "portfolio.exposure"
        operator: "greater_than"
        value: 0.95            # 95% max exposure

  - policy_id: "max_position_concentration"
    name: "Maximum Single Position"
    type: soft_limit
    priority: 80
    action: warn
    conditions:
      - metric: "position.weight"
        operator: "greater_than"
        value: 0.15            # 15% concentration → warning
```

```yaml
# config/policies/compliance.yaml
policies:
  - policy_id: "no_trade_earnings_24h"
    name: "No Trade 24h Before Earnings"
    type: compliance
    priority: 70
    action: block
    conditions:
      - metric: "market_state.next_earnings_hours"
        operator: "less_than"
        value: 24

  - policy_id: "min_liquidity"
    name: "Minimum Liquidity"
    type: market_condition
    priority: 60
    action: block
    conditions:
      - metric: "market_state.avg_daily_volume"
        operator: "less_than"
        value: 1000000         # 1M shares min volume
```

```yaml
# config/policies/governance.yaml
policies:
  - policy_id: "large_trade_approval"
    name: "Large Trade Requires Approval"
    type: governance
    priority: 10
    action: require_approval
    conditions:
      - metric: "order.notional_value"
        operator: "greater_than"
        value: 100000          # $100k+ requires human approval

  - policy_id: "new_asset_class_approval"
    name: "New Asset Class Requires Approval"
    type: governance
    priority: 5
    action: require_approval
    conditions:
      - metric: "portfolio.first_trade_in_asset_class"
        operator: "is_true"
```

---

## 6. PolicyCondition Metrics

Metriche disponibili per le condizioni:

| Metrica | Descrizione | Unità |
|---------|-------------|-------|
| `portfolio.day_pnl` | P&L giornaliero | absolute (USD) |
| `portfolio.total_pnl` | P&L totale | absolute (USD) |
| `portfolio.exposure` | Esposizione totale | float (0-1) |
| `portfolio.leverage` | Leva attuale | float |
| `portfolio.var_95` | VaR 95% | absolute (USD) |
| `portfolio.var_99` | VaR 99% | absolute (USD) |
| `portfolio.current_drawdown` | Drawdown attuale | float (0-1) |
| `position.weight` | Peso di una posizione | float (0-1) |
| `position.unrealized_pnl` | P&L non realizzato | absolute (USD) |
| `order.notional_value` | Valore nozionale ordine | absolute (USD) |
| `order.quantity` | Quantità ordine | absolute |
| `market_state.next_earnings_hours` | Ore alla prossima earnings | hours |
| `market_state.avg_daily_volume` | Volume medio giornaliero | shares |
| `market_state.spread_bps` | Spread in bps | bps |
| `market_state.volatility` | Volatilità annualizzata | float |
| `regime.volatility` | Regime volatilità | enum |
| `regime.trend` | Regime trend | enum |
| `portfolio.first_trade_in_asset_class` | Primo trade in asset class | bool |

---

## 7. Policy Reload

Le policy possono essere ricaricate a caldo:

```python
engine.reload_policies("config/policies/risk_limits.yaml")
# → log: "Policies reloaded: max_daily_loss, max_portfolio_exposure, ..."
```

Il reload è atomico: se il nuovo file è invalido, le vecchie policy rimangono attive.

---

## 8. Auditing

Ogni valutazione è registrata su PostgreSQL:

```sql
CREATE TABLE policy_evaluations (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    policy_id VARCHAR NOT NULL,
    policy_type VARCHAR NOT NULL,
    decision VARCHAR NOT NULL,       -- approved | rejected | warning
    reason TEXT,
    signal_id UUID,
    portfolio_id VARCHAR,
    instrument_id VARCHAR,
    context_snapshot JSONB,          -- Stato al momento della valutazione
    evaluation_time_ms FLOAT
);

CREATE INDEX idx_policy_eval_timestamp ON policy_evaluations(timestamp);
CREATE INDEX idx_policy_eval_decision ON policy_evaluations(decision);
```

---

## 9. Integrazione nel DOE

Nel Decision Orchestration Engine:

```python
async def orchestrate_decision(signal: Signal, portfolio: Portfolio,
                               market_state: MarketState) -> ExecutionDecision:
    # 1. Risk evaluation
    risk_result = risk_engine.evaluate(portfolio, signal, market_state)

    # 2. Policy evaluation
    policy_context = PolicyContext(portfolio, signal, market_state)
    policy_result = policy_engine.evaluate(policy_context)

    # 3. Decision
    if policy_result.final_decision == "rejected":
        return ExecutionDecision(
            action="rejected",
            reason=policy_result.rejected_by,
            details=policy_result.results
        )

    # 4. Execute (se tutto ok)
    return ExecutionDecision(action="execute", signal=signal)
```

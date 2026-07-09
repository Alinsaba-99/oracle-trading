# Oracle Plugin API v1.0

> Ogni estensione a Oracle è un plugin registrato. Il core non si modifica mai.
> ADR-004: Plugin-First Architecture.

---

## 1. Plugin Lifecycle

```
register() → validate() → initialize() → start() → stop() → dispose()
```

Ogni plugin attraversa queste fasi al caricamento e allo spegnimento.

### Fasi

| Fase | Descrizione | Fail behavior |
|------|-------------|---------------|
| `register()` | Plugin manager scopre il plugin (via entry point o directory) | Plugin non caricato |
| `validate(config)` | Verifica configurazione e dipendenze | Fail fast: errore all'avvio |
| `initialize()` | Alloca risorse, connette API, carica modelli | Plugin disabilitato, sistema continua |
| `start()` | Avvia processing (subscribe a NATS, avvia thread) | Plugin fermato, sistema continua |
| `stop()` | Ferma processing gracefulmente (timeout 5s) | Forza stop dopo timeout |
| `dispose()` | Rilascia risorse (chiudi file, DB, API) | Sempre eseguito |

---

## 2. BasePlugin Interface

```python
from abc import ABC, abstractmethod
from typing import Optional

class BasePlugin(ABC):
    """Classe base per tutti i plugin Oracle."""

    # --- Metadata (dichiarati dal plugin) ---
    name: str                       # Nome univoco
    version: str                    # Semver (es: "1.2.3")
    description: str                # Descrizione testuale
    dependencies: list[str] = []    # Nomi plugin richiesti
    subjects_in: list[str] = []     # NATS subjects consumati
    subjects_out: list[str] = []    # NATS subjects emessi

    # --- Config ---
    config_schema: Optional[dict] = None  # JSON Schema per validazione

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.logger = None          # Assegnato dal plugin manager
        self.event_bus = None       # Assegnato dal plugin manager

    # --- Lifecycle ---
    def validate(self) -> list[str]:
        """Valida configurazione. Ritorna lista di errori (vuota = ok)."""
        return []

    def initialize(self) -> None:
        """Alloca risorse. Solleva eccezione su fallimento."""

    def start(self) -> None:
        """Avvia processing. Solleva eccezione su fallimento."""

    def stop(self) -> None:
        """Ferma processing gracefulmente."""

    def dispose(self) -> None:
        """Rilascia tutte le risorse."""

    # --- Event Helpers ---
    async def publish(self, subject: str, data: dict, version: int = 1):
        """Pubblica un evento su NATS."""
        await self.event_bus.publish(subject, {
            "type": subject,
            "version": version,
            "data": data,
            "source": f"plugin.{self.name}",
        })

    async def subscribe(self, subject: str, handler: callable):
        """Subscribe a un subject NATS."""
        await self.event_bus.subscribe(subject, handler)
```

---

## 3. Plugin Discovery

I plugin sono scoperti in due modi:

### 3.1 Package Entry Points

```python
# pyproject.toml
[project.entry-points."oracle.plugins"]
my_indicator = "my_package:MyIndicatorPlugin"
```

### 3.2 Directory Scanning

```python
# Tutti i plugin in plugins/ sono scoperti automaticamente
oracle/plugins/
├── indicators/
│   ├── ema.py
│   └── rsi.py
├── brokers/
│   ├── ibkr.py
│   └── binance.py
├── agents/
│   ├── macro_analyst.py
│   └── sentiment_analyst.py
└── ...
```

---

## 4. Plugin Types

### 4.1 Indicator Plugin

```python
class BaseIndicator(BasePlugin):
    """Calcola feature tecniche da dati di mercato."""

    subjects_in = ["market.tick", "market.bar"]
    subjects_out = ["feature.updated"]

    @abstractmethod
    async def compute(self, instrument_id: str, data: dict) -> dict:
        """Calcola indicatori. Ritorna dict nome→valore."""
```

### 4.2 Broker Plugin

```python
class BaseBroker(BasePlugin):
    """Connettore a broker/exchange per execution."""

    subjects_in = ["order.submitted", "order.cancelled"]
    subjects_out = ["order.filled", "order.rejected", "market.tick"]

    @abstractmethod
    async def submit_order(self, order: Order) -> str:
        """Invia ordine al broker. Ritorna broker_order_id."""

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool: ...

    @abstractmethod
    async def get_positions(self) -> list[dict]: ...
```

### 4.3 Risk Model Plugin

```python
class BaseRiskModel(BasePlugin):
    """Modello di risk metrics e position sizing."""

    @abstractmethod
    async def evaluate(self, portfolio: Portfolio,
                       signal: Signal,
                       market_state: MarketState) -> RiskEvaluation: ...

    @abstractmethod
    async def position_size(self, portfolio: Portfolio,
                            signal: Signal,
                            risk_budget: float) -> Decimal: ...
```

### 4.4 Execution Algo Plugin

```python
class BaseExecutionAlgo(BasePlugin):
    """Algoritmo di execution (VWAP, TWAP, Iceberg)."""

    @abstractmethod
    async def execute(self, order: Order,
                      market_data: MarketData) -> ExecutionResult: ...
```

### 4.5 Agent Plugin

```python
class BaseAgent(BasePlugin):
    """Agente LLM specializzato."""

    agent_role: str                 # "technical_analyst", "macro_analyst", etc.
    agent_layer: str                # "analyst", "debate", "decision", "meta"

    @abstractmethod
    async def analyze(self, instrument_id: str,
                      context: AgentContext) -> AnalysisResult: ...

    @abstractmethod
    async def debate(self, bull_case: AnalysisResult,
                     bear_case: AnalysisResult) -> DebateResult: ...
```

### 4.6 Feature Plugin

```python
class BaseFeaturePlugin(BasePlugin):
    """Trasformazione/calcolo feature."""

    @abstractmethod
    async def compute(self, features: dict,
                      market_data: MarketData) -> dict: ...
```

---

## 5. Configurazione Plugin

I plugin sono configurati via YAML in `config/plugins/`:

```yaml
# config/plugins/indicators.yaml
plugins:
  ta_lib:
    enabled: true
    config:
      cache_size: 1000
      default_periods:
        sma: [20, 50, 200]
        rsi: 14
        bb: [20, 2]

  custom_momentum:
    enabled: true
    config:
      lookback: 30
      threshold: 0.05
```

---

## 6. Error Handling

I plugin non devono mai crashare il sistema:

```python
class PluginError(Exception):
    """Errore recuperabile del plugin."""

class PluginFatalError(Exception):
    """Errore irreversibile. Plugin disabilitato."""
```

- `PluginError`: log + evento `system.error`, plugin continua
- `PluginFatalError`: log + evento `system.error`, plugin fermato
- Eccezioni non catturate: plugin fermato, traceback loggato

---

## 7. Plugin Registry

```python
class PluginRegistry:
    """Registry centralizzato di tutti i plugin caricati."""

    def get(self, name: str) -> BasePlugin: ...
    def list(self, plugin_type: str = None) -> list[BasePlugin]: ...
    def get_by_type(self, plugin_type: str) -> list[BasePlugin]: ...
    def is_loaded(self, name: str) -> bool: ...
    def load(self, path: str) -> BasePlugin: ...
    def unload(self, name: str) -> None: ...
    def reload(self, name: str) -> None: ...
```

---

## 8. Scrittura di un Plugin — Esempio Completo

```python
"""plugins/indicators/ema.py — Exponential Moving Average Indicator"""

from decimal import Decimal
from libraries.core.plugin import BasePlugin
from libraries.events import event_bus

class EMAPlugin(BasePlugin):
    name = "ema"
    version = "1.0.0"
    description = "Exponential Moving Average indicator"
    subjects_in = ["market.bar"]
    subjects_out = ["feature.updated"]

    config_schema = {
        "type": "object",
        "properties": {
            "periods": {
                "type": "array",
                "items": {"type": "integer"},
                "default": [10, 20, 50, 200]
            }
        }
    }

    def initialize(self):
        self.periods = self.config.get("periods", [10, 20, 50, 200])
        self.cache = {}  # instrument_id → {period: value}

    async def on_bar(self, event: dict):
        data = event["data"]
        instrument_id = data["instrument_id"]
        close = Decimal(str(data["close"]))

        features = {}
        for period in self.periods:
            features[f"ema_{period}"] = self._compute_ema(
                instrument_id, close, period
            )

        await self.publish("feature.updated", {
            "instrument_id": instrument_id,
            "feature_set": "technical_v2",
            "features": features,
        })

    def _compute_ema(self, instrument_id: str,
                     price: Decimal, period: int) -> float:
        key = (instrument_id, period)
        prev = self.cache.get(key)
        k = 2 / (period + 1)
        if prev is None:
            ema = float(price)
        else:
            ema = float(price) * k + prev * (1 - k)
        self.cache[key] = ema
        return ema
```

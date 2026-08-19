> **ARCHIVIO STORICO.** Documento del modello Phase, deprecato da ADR-012
> e sostituito dai capability gate G0-G9. Roadmap canonica:
> [ROADMAP.md](../../ROADMAP.md). Stato corrente:
> [ORACLE_AUTOPILOT_STATUS.md](../ORACLE_AUTOPILOT_STATUS.md).
> **Non aggiornare** — solo git archaeology.

# Oracle Phase 0 — Foundation Implementation Plan

> **Date:** 2026-07-09
> **Status:** REVISED v2 (post-Architect+Critic consensus)
> **Author:** Planner + Architect + Critic
> **Repository:** `~/_repos/oracle-trading/`
> **Phase 0 Budget:** 2 weeks (wk 1-2 per PROJECT.md)

---

## 1. RALPLAN-DR Summary

### Principles (Immutable for Phase 0)

| # | Principle | Rationale |
|---|-----------|-----------|
| P1 | **No code changes to implemented core.** Domain models (16 entities) and event models (11 events) are FROZEN. Phase 0 adds infrastructure around them — never modifies them. | Existing models + tests pass; ADR-000 to ADR-007 assume them stable. Every modification requires a new ADR. |
| P2 | **First commit must be meaningful and coherent.** No half-baked scaffolding. The initial commit must be a single, atomic, testable whole that proves the foundation works end-to-end. | A repo with zero commits but all files staged is an awkward state. The first commit is the project's identity — it must represent a coherent, passing baseline. |
| P3 | **Test before commit.** Every new module must have unit tests before it enters the first commit. ruff strict + mypy strict must pass. | ADR-005 monorepo structure and CI enforce these; we must never lower the bar. |
| P4 | **Fail closed by default.** Config, errors, logging, plugin loader — all default to safe, not silent. | Principle #7 from SPEC.md: no silent failures in foundation components. |
| P5 | **No premature optimization.** Stick to Python 3.12+ pure implementation for Phase 0. Rust/PyO3, QuestDB integration, and LangGraph are Phase 1+. | Phase 0 is about infrastructure foundations, not data path or agent orchestration. |

### Decision Drivers (Top 3)

| Driver | Weight | Description |
|--------|--------|-------------|
| **DD1: Reproducibility** | CRITICAL | Every component must be configurable, versionable, and observable from day 0. Experiment Registry design starts in Phase 0. |
| **DD2: Developer Velocity** | HIGH | Dev tooling must work on `make dev && make test` in under 10 seconds. No manual steps beyond `make fresh`. |
| **DD3: Extensibility** | HIGH | Config, plugin system, and error hierarchy must support future extension without breaking existing code. Plugin discovery must work before any plugin is written. |

### Key Decisions & Options

#### D1: Configuration Module Architecture

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: pydantic-settings (RECOMMENDED)** | Use `pydantic-settings` with layered sources (YAML > env > defaults). | Already a dependency; integrates with existing Pydantic models; validates at load time; supports `.env`, YAML, JSON, env vars. | Heavy for simple key-value config; YAML parsing adds dep (PyYAML already in deps). |
| **B: stdlib configparser + env** | Use `configparser` for INI-style + `os.environ` overrides. | Zero deps; simple; well-understood. | No validation; no typing; no nested config; doesn't scale beyond Phase 0. |
| **C: YAML-only with manual loading** | Load config files via `yaml.safe_load()` with manual validation. | Simple; flexible. | No schema enforcement; manually maintained validation; easy to make brittle. |

**Invalidation:** Option B fails DD3 (no hierarchy, no typing). Option C fails DD1 (no validation, easy to misconfigure). **Option A wins** because it layers cleanly (defaults → YAML → env vars), validates on load via Pydantic models, and is already in the dependency chain.

#### D2: Plugin Discovery Strategy

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Entry-point based (RECOMMENDED)** | Use `importlib.metadata.entry_points` with `oracle.plugins` group + `plugins/` directory scanning. | Standard Python mechanism; works with pip-installed packages; directory scan covers local development. | Slightly more complex than pure directory scan. |
| **B: Pure directory scanning** | Only scan `plugins/` subdirectories for `BasePlugin` subclasses. | Dead simple; no registration ceremony. | Cannot load installed packages; fragile discovery (import side effects). |
| **C: Registry with manual registration** | Every plugin must be explicitly registered in a central YAML. | Total control; explicit ordering. | High friction; violates ADR-004 "plugin discovery automatic." |

**Invalidation:** Option C violates ADR-004 (automatic discovery). Option B fails for pip-installed plugins (community contributions). **Option A wins** — it supports both pip-installed and local plugins, matching the two discovery modes in PLUGIN_API.md §3.

#### D3: NATS Subject Naming Convention

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Dot-notation as defined in EVENTS.md (RECOMMENDED)** | `market.tick`, `signal.generated`, etc. Already documented. | Coherent with existing docs; no migration risk. | None. |
| **B: Domain-prefixed conv: `oracle.market.tick`** | Add repo-level prefix to avoid collisions in multi-repo NATS. | Future-proof if Oracle shares a NATS cluster. | Breaks documented EVENTS.md convention; unnecessary for v1. |
| **C: Namespace-versioned: `v1.market.tick`** | Include version in subject. | Explicit schema version routing. | Bloated subjects; version already in envelope. |

**Invalidation:** Options B and C would require updates to EVENTS.md and all event models. The current convention works and is documented. **Option A wins** — change only when there's evidence of a collision.

#### D4: Logging Architecture

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: structlog (RECOMMENDED)** | `structlog` with JSON output, bound contexts, structured fields. | Already in dependencies; integrates with stdlib logging; ideal for Loki consumption; supports OpenTelemetry bridge. | Learning curve vs stdlib; slightly more ceremony for simple scripts. |
| **B: stdlib logging only** | Standard Python logging with JSON formatter for Loki. | Zero deps; universal. | Manually structured logging is error-prone; no easy context binding. |
| **C: loguru** | Third-gen logging library. | Best DX; automatic context; no boilerplate. | Not in deps; introduces a new dependency that overlaps with structlog. |

**Invalidation:** Option B lacks the structured context binding needed for OpenTelemetry correlation (required per pyproject.toml deps). Option C duplicates structlog without the OTEL integration. **Option A wins** — already in deps, purpose-built for structured logging, integrates with OTLP exporter.

#### D5: Error Hierarchy

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: Domain-driven hierarchy (RECOMMENDED)** | `OracleError(BaseException)` → `ConfigError`, `PluginError`, `EventError`, `NATSConnectionError` — each with `code: str`, `details: dict`. | Self-documenting; machine-readable; aligns with ADR-004 PluginError/PluginFatalError pattern. | More files; more imports. |
| **B: Single `OracleException` with error code enum** | One exception class + enum for error type. | Minimal code; easy to import. | No type-based catching; error codes are strings (brittle). |
| **C: Flat exception module** | All exception classes in one module, no hierarchy. | Simple; flat import. | No categorization; catch clauses are imprecise. |

**Invalidation:** Option B violates P4 (fail closed — string-based error codes are fragile). Option C makes it impossible to catch "all plugin errors" vs "all config errors." **Option A wins** — clear hierarchy, typed catch clauses, future-proof for Phase 1+ extension.

---

Phase 0 is decomposed into **7 milestones + Pre-flight Bootstrap (M0)**:

```
M0: Pre-flight Bootstrap (verify repo, deps, Docker)
│
└──▶ M1: Core Config Module
     │
     └──▶ M2: Error Hierarchy
          │
          └──▶ M3: Logging Infrastructure
               │
               ├──▶ M4: Plugin System
               ├──▶ M5: Event Bus Client
               │    │
               │    └──▶ M6: Wiring + Registry + CLI + First Commit
```

M4 and M5 run in **parallel** after M3. M5 depends on M1 (NATSSettings), M2 (NATSConnectionError), M3 (structlog) — NOT on M4.
Each milestone produces testable, lintable, type-checked code.

---

### M0: Pre-flight Bootstrap

**Goal:** Verify repository state, install dependencies, confirm baseline passes before adding Phase 0 code.

**Verification steps:**
- `pyproject.toml` exists with all declared dependencies
- `pip install -e ".[dev]"` succeeds
- Existing test suite passes (`make test`)
- `make lint && make typecheck` passes on existing code
- `docker compose -f infra/docker/docker-compose.yml up -d` starts NATS + Redis
- `docker compose down` for cleanup

**Dependencies to verify (already in pyproject.toml):**
- `pydantic-settings>=2.2` — declared
- `structlog` — declared
- `nats-py>=2.8` — declared as `nats-py`

**Acceptance Criteria:**
- `pip install -e ".[dev]"` succeeds with zero errors
- Existing test suite passes (baseline)
- Docker services start and are reachable

---
### M1: Core Configuration Module

**Goal:** Implement the config system via `pydantic-settings` with layered sources, plus config serialization (JSON/YAML/TOML).

**Files to create:**
- `core/config/__init__.py` — update from empty to `OracleSettings` exports
- `core/config/settings.py` — `OracleSettings(BaseSettings)` with nested models (`NATSSettings`, `RedisSettings`, `QuestDBSettings`, `PostgresSettings`, `PluginSettings`)
- `core/config/loader.py` — `ConfigLoader` with `load_yaml()`, `merge_configs()`
- `core/config/schema.py` — Config model Pydantic schemas
- `core/config/serializer.py` — `SettingsSerializer` with `to_json()`, `to_yaml()`, `to_toml()` and `write_*()` methods
- `tests/unit/test_config.py` — Config tests

**Key APIs:**
```python
# core/config/settings.py
class OracleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    environment: str = "development"
    log_level: str = "INFO"
    nats: NATSSettings = NATSSettings()
    redis: RedisSettings = RedisSettings()
    questdb: QuestDBSettings = QuestDBSettings()
    postgres: PostgresSettings = PostgresSettings()
    plugins: PluginSettings = PluginSettings()


class NATSSettings(BaseModel):
    url: str = "nats://localhost:4222"
    timeout: float = 5.0
    max_reconnect: int = 10


# core/config/loader.py
class ConfigLoader:
    """Loads and merges config from YAML files with env var override."""

    def __init__(self, config_dir: Path = Path("config")):
        self.config_dir = config_dir

    def load(self, profile: str = "development") -> dict:
        """Load config/development.yaml → override with env → return dict."""


# core/config/serializer.py
class SettingsSerializer:
    """Export OracleSettings to JSON, YAML, or TOML."""

    @staticmethod
    def to_json(settings: OracleSettings) -> str: ...
    @staticmethod
    def to_yaml(settings: OracleSettings) -> str: ...
    @staticmethod
    def to_toml(settings: OracleSettings) -> str:
        """Attempt tomli_w export; raise RuntimeError with clear message if unavailable."""
        try:
            import tomli_w
        except ImportError:
            raise RuntimeError("tomli_w required for TOML export. Install: pip install tomli-w")
```

**Test Strategy:**
- Test defaults match expected values
- Test env var overrides (`ORACLE__NATS__URL`)
- Test YAML loading and merging
- Test missing file behavior (should fail closed)
- Test type validation (wrong type raises `ValidationError`)
- Test SettingsSerializer round-trip (JSON, YAML)
- Test `to_toml()` without tomli_w raises `RuntimeError` (not uncaught `ImportError`)

**Acceptance Criteria:**
- `OracleSettings()` loads with zero config files (all defaults)
- `settings.nats.url` reads from env var
- Invalid config raises `ValidationError` (not silent fallback)
- Settings export round-trips correctly
- `to_toml()` fails gracefully when dependency missing
- All tests pass: `make test-unit`
- ruff + mypy pass on `core/config/`
**Key APIs:**
```python
# core/config/settings.py
class OracleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    environment: str = "development"
    log_level: str = "INFO"
    nats: NATSSettings = NATSSettings()
    redis: RedisSettings = RedisSettings()
    questdb: QuestDBSettings = QuestDBSettings()
    postgres: PostgresSettings = PostgresSettings()
    plugins: PluginSettings = PluginSettings()


class NATSSettings(BaseModel):
    url: str = "nats://localhost:4222"
    timeout: float = 5.0
    max_reconnect: int = 10


# core/config/loader.py
class ConfigLoader:
    """Loads and merges config from YAML files with env var override."""

    def __init__(self, config_dir: Path = Path("config")):
        self.config_dir = config_dir

    def load(self, profile: str = "development") -> dict:
        """Load config/development.yaml → override with env → return dict."""
```

**Test Strategy:**
- Test defaults match expected values
- Test env var overrides (`ORACLE__NATS__URL`)
- Test YAML loading and merging
- Test missing file behavior (should fail closed)
- Test type validation (wrong type raises ValidationError)

**Acceptance Criteria:**
- `OracleSettings()` loads with zero config files (all defaults)
- `settings.nats.url` reads from env var
- Invalid config raises `ValidationError` (not silent fallback)
- All tests pass: `make test-unit`
- ruff + mypy pass on `core/config/`

---

### M2: Error Hierarchy

**Goal:** Implement domain-driven exception hierarchy for all Oracle components.

**Files to create:**
- `core/errors/__init__.py` — update from empty to export all error classes
- `core/errors/base.py` — `OracleError(Exception)` base + `OracleFatalError`
- `core/errors/config_errors.py` — `ConfigError`, `ConfigValidationError`, `ConfigNotFoundError`
- `core/errors/plugin_errors.py` — `PluginError`, `PluginFatalError`, `PluginNotFoundError`, `PluginRegistrationError`
- `core/errors/event_errors.py` — `EventError`, `EventPublishError`, `EventSubscribeError`
- `core/errors/nats_errors.py` — `NATSConnectionError`, `NATSDisconnectedError`, `NATSTimeoutError`
- `core/errors/logging_errors.py` — `LoggingConfigurationError`
- `tests/unit/test_errors.py` — Error hierarchy tests

**Key APIs:**
```python
# core/errors/base.py
class OracleError(Exception):
    """Base exception for all Oracle errors."""

    def __init__(self, message: str, code: str = "UNKNOWN", details: dict | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)


class OracleFatalError(Exception):
    """Non-recoverable. System should stop or skip component."""
```

**Test Strategy:**
- Each error class catches at the right granularity
- Error codes are unique
- `str(err)` includes code + message
- `OracleFatalError` is NOT a subclass of `OracleError` (intentionally separate for `except OracleError` to not catch fatals)
- Inherits from `Exception` correctly

**Acceptance Criteria:**
- `errors/` module has all error classes for Phase 0
- `isinstance(ConfigError("x"), OracleError)` is True
- `isinstance(PluginFatalError("x"), OracleError)` is False
- `str(ConfigError("x", code="CFG001"))` includes "CFG001"
- All tests pass: `make test-unit`

---

### M3: Logging Infrastructure

**Goal:** Configure structlog with JSON output, bound contexts, **stdlib bridging**, and optional OTLP bridge.

**Files to create:**
- `core/logging/` directory (new)
- `core/logging/__init__.py` — export `get_logger()`, `configure_logging()`
- `core/logging/config.py` — structlog configuration, processors, formatters, stdlib routing
- `core/logging/context.py` — context binding helpers, trace_id propagation
- `tests/unit/test_logging.py` — Logging tests

**Key APIs:**
```python
# core/logging/config.py
import structlog
import structlog.stdlib
import logging


def configure_logging(
    environment: str = "development",
    log_level: str = "INFO",
    json_output: bool = False,
    service_name: str = "oracle",
) -> None:
    """Configure structlog with stdlib bridging and optional OTLP."""
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer()
            if environment == "development"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog
    logging.basicConfig(
        format="%(message)s", level=getattr(logging, log_level.upper(), logging.INFO)
    )
    logging.captureWarnings(True)


# core/logging/__init__.py
def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger with caller context."""
    return structlog.get_logger(name or __name__)
```

**Test Strategy:**
- Logger produces JSON in production mode
- Logger produces pretty-printed output in dev mode
- Bound context persists across calls
- `trace_id` is automatically included
- Different log levels filter correctly
- Thread-safety (concurrent loggers don't corrupt)
- **Stdlib bridging**: `logging.getLogger("test").warning("msg")` routes through structlog

**Acceptance Criteria:**
- `get_logger("test").info("hello")` produces valid output
- JSON mode output is valid JSON with `event`, `level`, `timestamp`, `logger` fields
- Trace ID context binding works
- `logging.getLogger("x").warning("check")` captured by structlog (stdlib bridging test)
- All tests pass
---


### M4: Plugin System

**Goal:** Implement `BasePlugin`, `PluginRegistry`, `PluginDiscovery` (entry-point + directory scan), and lifecycle management with error isolation.

**Files to create:**
- `core/plugin/__init__.py` — update from empty to exports
- `core/plugin/base.py` — `BasePlugin` abstract class (matching PLUGIN_API.md). Includes `publish()` that passes bare data to EventBusClient (envelope owned by EventBusClient per ADR-008).
- `core/plugin/registry.py` — `PluginRegistry` with lifecycle management, per-plugin state tracking, `start_all()` with `return_exceptions=True`
- `core/plugin/discovery.py` — `PluginDiscovery` (entry_point via importlib.metadata + directory via pkgutil.iter_modules)
- `core/plugin/lifecycle.py` — Plugin state machine (register→validate→init→start→stop→dispose)
- `tests/unit/test_plugin_system.py` — Plugin tests
- `tests/fixtures/plugins/` — Mock plugin fixtures for testing discovery

**Key APIs:**
```python
# core/plugin/base.py
class BasePlugin(ABC):
    name: str
    version: str
    description: str
    dependencies: list[str] = []
    subjects_in: list[str] = []
    subjects_out: list[str] = []
    config_schema: dict | None = None

    def __init__(self, config: dict | None = None): ...
    def validate(self) -> list[str]: ...
    def initialize(self) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def dispose(self) -> None: ...
    async def publish(self, subject: str, data: dict, **kwargs) -> None:
        """Publish via event bus. Passes BARE data — EventBusClient owns the envelope per ADR-008."""
        await self._event_bus.publish(subject, data, source=f"plugin.{self.name}", **kwargs)


# core/plugin/registry.py
class PluginRegistry:
    """Thread-safe registry with per-plugin state tracking."""

    def register(self, plugin: BasePlugin) -> None: ...
    def get(self, name: str) -> BasePlugin: ...
    def list(self, plugin_type: str | None = None) -> list[BasePlugin]: ...
    def is_loaded(self, name: str) -> bool: ...
    def unload(self, name: str) -> None: ...
    async def start_all(self) -> dict[str, Exception | None]:
        """Start all plugins with return_exceptions=True for isolation."""
        results = await asyncio.gather(
            *(p.start() for p in self._plugins.values()), return_exceptions=True
        )
        errors = {}
        for name, result in zip(self._plugins.keys(), results):
            if isinstance(result, Exception):
                errors[name] = result
                self._states[name] = PluginState.error
        return errors


# core/plugin/discovery.py
class PluginDiscovery:
    def discover_entry_points(self) -> list[type[BasePlugin]]:
        """Scan oracle.plugins entry points via importlib.metadata."""
        eps = entry_points(group="oracle.plugins")
        return [ep.load() for ep in eps]

    def discover_directory(self, path: Path = Path("plugins")) -> list[type[BasePlugin]]:
        """Scan plugins/ subdirs for BasePlugin subclasses via pkgutil."""
        ...

    def discover_all(self) -> list[type[BasePlugin]]:
        """Combine both discovery mechanisms."""
        return self.discover_entry_points() + self.discover_directory()
```

**Test Strategy:**
- `BasePlugin` can be subclassed and instantiated
- Lifecycle state machine transitions correctly (register→valid→init→start→stop→dispose)
- `PluginRegistry` tracks registration, duplicate detection
- Plugin discovery finds entry points and directory plugins (via mock fixtures in tests/fixtures/plugins/)
- Missing dependencies raise `PluginDependencyError`
- Invalid config during `validate()` returns errors
- `PluginFatalError` during `initialize()` disables plugin, other plugins continue
- Registry `get()` raises `PluginNotFoundError` for missing names
- `start_all()` with `return_exceptions=True` isolates single-plugin failures
- `BasePlugin.publish()` passes bare data (envelope test via mock EventBusClient)

**Acceptance Criteria:**
- A minimal test plugin can be registered, validated, initialized, started, stopped, disposed
- Registry correctly returns plugins by name and type
- Discovery finds a mock entry-point plugin
- Discovery finds a mock directory plugin (via fixtures)
- Lifecycle failure handling works — one failing plugin does NOT crash others
- `start_all()` returns errors dict (not raises)
- All tests pass
---

### M5: Event Bus Client (NATS Client Wrapper)

**Goal:** Implement the NATS client wrapper with envelope wrapping (sole owner per ADR-008), None-guarded connection lifecycle, JetStream support, and system events (system.health, system.plugin.registered).

**Files to create:**
- `core/events/client.py` — `EventBusClient` with None-guard on `_nc`, `connect()`/`close()` lifecycle
- `core/events/envelope.py` — `build_envelope()` per EVENTS.md — sole envelope builder, no double-wrapping
- `core/events/subscription.py` — `SubscriptionManager` with handler routing
- `core/events/system.py` — `SystemEventPayload`, `HealthEventPayload`, `PluginRegisteredPayload` with subject constants
- `tests/unit/test_event_bus.py` — NATS client tests (mock-based)
- `tests/integration/test_nats_live.py` — Integration tests (Docker NATS, marked @pytest.mark.integration)

**Key APIs:**
```python
# core/events/client.py
class EventBusClient:
    """NATS event bus client. Sole envelope owner per ADR-008."""

    def __init__(self, settings: NATSSettings):
        self.settings = settings
        self._nc: Nats | None = None  # None until connect()
        self._js: JetStreamContext | None = None

    async def connect(self) -> None:
        """Connect to NATS. Raises NATSConnectionError on failure."""
        try:
            self._nc = await nats.connect(self.settings.url, ...)
            self._js = self._nc.jetstream()
        except Exception as e:
            raise NATSConnectionError(f"Failed to connect: {e}") from e

    async def close(self) -> None: ...

    async def publish(self, subject: str, data: dict, **kwargs) -> None:
        """Publish with envelope. Raises NATSConnectionError if not connected."""
        if self._nc is None:
            raise NATSConnectionError("Not connected. Call connect() first.")
        payload = build_envelope(subject, data, **kwargs)
        await self._nc.publish(subject, json.dumps(payload).encode())

    async def subscribe(self, subject: str, handler: Callable, queue: str | None = None) -> None:
        """Subscribe with optional queue group."""
        if self._nc is None:
            raise NATSConnectionError("Not connected. Call connect() first.")
        ...


# core/events/envelope.py
def build_envelope(
    subject: str, data: dict, source: str, version: int = 1, trace_id: str | None = None
) -> dict:
    """Build standard NATS envelope. Sole owner — no double-wrapping.

    Schema per EVENTS.md: { subject, version, timestamp, source, trace_id, data }
    """
    return {
        "subject": subject,
        "version": version,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": source,
        "trace_id": trace_id or str(uuid4()),
        "data": data,
    }


# core/events/system.py
SYSTEM_HEALTH = "system.health"
SYSTEM_PLUGIN_REGISTERED = "system.plugin.registered"


class SystemEventPayload(BaseModel):
    """Base for system events per EVENTS.md."""

    timestamp: datetime
    service: str = "oracle"


class HealthEventPayload(SystemEventPayload):
    """Published on EventBusClient.connect()."""

    status: Literal["healthy", "degraded", "unhealthy"]
    components: dict[str, str]


class PluginRegisteredPayload(SystemEventPayload):
    """Published on successful plugin registration."""

    plugin_name: str
    plugin_version: str
```

**Test Strategy:**
- Integration tests connect to real NATS (Docker) for pub/sub round-trip
- Unit tests mock `nats.connect` to verify connection management
- Envelope builder produces correct schema per EVENTS.md (asserts shape, no double-wrapping via mock BasePlugin)
- `publish()` before `connect()` raises `NATSConnectionError` (None-guard test)
- `persistent=True` uses JetStream
- Reconnection logic (short timeout + network flap)
- Concurrent publish/subscribe doesn't drop messages
- System events have correct schema

**Acceptance Criteria:**
- `EventBusClient` connects, publishes, receives events in integration test
- Envelope matches EVENTS.md schema exactly
- `publish()` before `connect()` raises `NATSConnectionError` (NOT AttributeError)
- Persistent events survive in JetStream
- Connection failures raise `NATSConnectionError`
- Subscribe with queue group delivers to one subscriber
- `system.health` event published on successful connect
- All unit tests pass; integration tests gated as @pytest.mark.integration
- ruff + mypy pass
---

### M6: Infrastructure Wiring, CLI, Experiment Registry, and First Commit

**Goal:** Wire everything together, implement minimal Experiment Registry (ADR-007), create CLI entry point, and make the **first commit**.

**NOTE:** `pydantic-settings` already in `pyproject.toml`. Docker Compose already has 7 services (NATS, Redis, QuestDB, PostgreSQL, Loki, Prometheus, Qdrant). No dependency changes needed.

**Files to create/modify:**
- `core/domain/experiment.py` — Extend existing model. Add `ExperimentContext(BaseModel)` + `ExperimentRegistry` (thread-safe, JSONL-backed, ~50 lines)
- `apps/cli/main.py` — CLI entry point with argparse: `oracle --version`, `oracle config validate`, `oracle plugins list`, `oracle nats ping`
- `apps/cli/__init__.py` — update from empty
- `apps/cli/commands/` directory
  - `__init__.py`
  - `config_cmd.py`
  - `plugin_cmd.py`
  - `nats_cmd.py`
- `apps/cli/application.py` — `OracleApplication` context manager with signal handlers and graceful shutdown (asyncio)
- `infra/docker/Dockerfile` — verify or create minimal dev Dockerfile
- `config/development.yaml` — default config YAML
- `config/production.yaml` — production config YAML
- `tests/unit/test_experiment.py` — Experiment Registry tests
- `tests/unit/test_cli.py` — CLI tests

**Experiment Registry:**
```python
# core/domain/experiment.py (extend existing model)
import threading
from datetime import datetime, timezone


class ExperimentContext(BaseModel):
    """Immutable experiment context. Created once, never mutated."""

    experiment_id: str = Field(default_factory=lambda: str(uuid4()))
    git_commit: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    random_seed: int = 42
    tags: dict[str, str] = Field(default_factory=dict)


class ExperimentRegistry:
    """Thread-safe experiment registry backed by JSONL. Phase 1: migrate to PG/QuestDB."""

    def __init__(self, path: Path = Path("experiments/_registry.jsonl")):
        self._path = path
        self._lock = threading.Lock()

    def register(self, ctx: ExperimentContext) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a") as f:
                f.write(ctx.model_dump_json() + "\n")

    def list(self) -> list[ExperimentContext]: ...
    def get(self, experiment_id: str) -> ExperimentContext | None: ...


# apps/cli/application.py
class OracleApplication:
    """Context manager with signal handlers and clean shutdown."""

    async def __aenter__(self) -> "OracleApplication": ...
    async def __aexit__(self, *args) -> None: ...
    async def shutdown(self, sig: signal.Signals) -> None: ...
```

**Test Strategy:**
- CLI `--version` prints correct version
- CLI `config validate` with valid/invalid config exits 0/1
- CLI `plugins list` shows registered plugins
- CLI `nats ping` attempts connection (mock NATS)
- Experiment Registry creates, persists, retrieves contexts
- ExperimentContext uses timezone-aware datetime
- Graceful shutdown tested with signal simulation
- All lint/typecheck passes on the full codebase

**Acceptance Criteria:**
- `oracle --version` -> `0.1.0`
- `oracle config validate` passes with `config/development.yaml`
- `oracle config validate --file missing.yaml` exits 1
- `docker compose -f infra/docker/docker-compose.yml up` starts all 7 services
- Experiment Registry creates, stores, and retrieves experiments
- CI workflow passes on the first commit
- `make test` passes (unit tests)
- `make lint && make format && make typecheck` passes
- First commit message: `feat: Phase 0 foundation — config, errors, logging, plugins, event bus, CLI`
---

## 3. Key Design Decisions to Make

### 3.1 Core Config Module Design

**Decision (PENDING APPROVAL):** Use `pydantic-settings` with layered sources.

**Rationale:** Already in dev deps indirectly via pydantic; layered loading (defaults -> YAML -> env vars) matches 12-factor app methodology; validates at load time preventing silent misconfiguration.

### 3.2 Plugin System API

**Decision (PENDING APPROVAL):** Adopt PLUGIN_API.md's `BasePlugin` verbatim.

**Rationale:** Already documented and reviewed in ADR-004. Implementation matches the spec exactly to avoid documentation drift.

### 3.3 NATS Subject Naming Convention

**Decision (PENDING APPROVAL):** Keep as documented in EVENTS.md (dot-notation, no prefix).

**Rationale:** Already documented, already used in event model docstrings. Prefixing can be added later via a wrapper. Versioning is in the envelope, not the subject.

### 3.4 Logging Architecture

**Decision (PENDING APPROVAL):** structlog with JSON output.

**Key configuration chain:**
1. `structlog.stdlib.BoundLogger` as logger class
2. `structlog.processors.TimeStamper(fmt="iso")` for timestamps
3. `structlog.processors.add_log_level` for level field
4. `structlog.dev.ConsoleRenderer` in dev mode
5. `structlog.processors.JSONRenderer` in production
6. OpenTelemetry bridge via `structlog.stdlib.OTELProcessor` (when OTEL is active)

### 3.5 Error Hierarchy Structure

**Decision (PENDING APPROVAL):** Domain-driven hierarchy with error codes.

```
OracleError (Exception)
├── OracleFatalError (Exception)  [separate hierarchy]
├── ConfigError
│   ├── ConfigValidationError
│   └── ConfigNotFoundError
├── PluginError
│   ├── PluginNotFoundError
│   ├── PluginRegistrationError
│   └── PluginDependencyError
├── EventError
│   ├── EventPublishError
│   └── EventSubscribeError
├── NATSConnectionError
│   ├── NATSDisconnectedError
│   └── NATSTimeoutError
└── LoggingConfigurationError
```

**NOTE:** `OracleFatalError` is intentionally NOT a subclass of `OracleError`. This allows `except OracleError` to catch recoverable errors only.

---

## 4. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **R1: NATS flaky in CI** | Medium | High — integration tests fail intermittently | Use `@pytest.mark.integration` to separate unit from integration tests. CI runs unit only. |
| **R2: pydantic-settings version conflict** | Low | Medium — blocks first commit | Pin `pydantic-settings>=2.2,<3.0` in pyproject.toml. Test import before commit. |
| **R3: Plugin discovery doesn't find directory plugins** | Medium | Medium — community contribution path broken | Write integration test with a `plugins/` fixture directory. Test both discovery mechanisms. |
| **R4: structlog OTEL bridge version mismatch** | Medium | Low — OTEL integration deferred to Phase 1 | Mark OTEL bridge import as optional with graceful fallback. |
| **R5: Docker compose port conflicts** | Low | Medium — blocks local development | Document required ports. Override with env vars. |
| **R6: First commit too large** | Medium | Low — foundation is naturally large | Ensure atomicity: one commit, clear message. Scope is bounded. |
| **R7: Event bus client design over-abstracted** | Medium | Low — wasted effort | Keep `EventBusClient` thin: wrap nats-py, add envelope and reconnect. No broker abstraction layer. |
| **R8: Mypy strict blocks valid code** | Medium | Medium — type friction | Add `# type: ignore[XXX]` for known third-party limitations. Document each. |

---

## 5. Verification Strategy

### 5.1 Testing Gates (Pre-Commit)

| Gate | Command | Success Criteria |
|------|---------|------------------|
| **Lint** | `make lint` | Zero warnings (ruff strict) |
| **Format** | `make format` | Format check passes |
| **Type Check** | `make typecheck` | Zero mypy `--strict` errors |
| **Unit Tests** | `make test-unit` | All pass (>=80% coverage on new code) |
| **Pre-commit** | `make precommit` | All hooks pass |

### 5.2 Phase 0 Completion Checklist
- [ ] **M0:** Bootstrap verified — deps install, existing tests pass, Docker starts
- [ ] **M1:** Config module (incl. serialization) implemented, tested, type-checked
- [ ] **M2:** Error hierarchy implemented, tested, type-checked
- [ ] **M3:** Logging infrastructure (incl. stdlib bridging) implemented, tested, type-checked
- [ ] **M4:** Plugin system (BasePlugin + Registry + Discovery + Lifecycle + fixtures) implemented, tested, type-checked
- [ ] **M5:** Event bus client (incl. system events, None-guard) implemented, tested, type-checked
- [ ] **M6:** CLI wiring, Experiment Registry, graceful shutdown, Docker verified, CI passes
- [ ] **Full suite:** `make test` passes (unit tests)
- [ ] **Full suite:** `make lint && make format && make typecheck` passes
- [ ] **Full suite:** `make precommit` passes
- [ ] **Docker:** `docker compose up` starts all 7 services (NATS, Redis, QuestDB, PostgreSQL, Loki, Prometheus, Qdrant)
- [ ] **Coverage:** >=80% coverage on all Phase 0 code
- [ ] **First commit:** `feat: Phase 0 foundation — config, errors, logging, plugins, event bus, CLI`
### 5.3 Post-Commit Validation

After the first commit is made:

1. Clone the repo to a clean directory
2. Run `make fresh && make dev` to install
3. Run `make test` — all pass
4. Run `docker compose -f infra/docker/docker-compose.yml up` — all services start
5. Run `oracle --version` -> `0.1.0`
6. Run `oracle config validate` — exits 0
7. Push to GitHub — CI passes

---

## 6. Open Questions

- [ ] M5 integration tests: run against Docker NATS or mock? Prefer mock for unit tests, mark real NATS tests as `@pytest.mark.integration`.
- [ ] Should `core/logging/` go under `core/` or a new top-level `libraries/`? Per ADR-005, `core/` is foundation — logging belongs there.
- [ ] CLI framework: use `argparse` (stdlib, zero new deps) or `typer` (better DX)? Recommend `argparse` for Phase 0, migrate to `typer` in Phase 1.

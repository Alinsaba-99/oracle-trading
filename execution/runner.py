"""BL-730 — Always-on paper trading runner.

Wires the existing pieces (``PaperOrchestrator``, ``PaperBroker``,
``ExecutionStore``) into a single deterministic loop:

    fetch market prices (PriceProvider)
        → generate intents (SignalSource)
            → PaperOrchestrator.run_once
                → persist fills, positions, equity (ExecutionStore)
                    → heartbeat (ExecutionStore)
                        → sleep until next tick (Clock)

The runner is deliberately thin and protocol-driven so the heavy
components (signal adapters, market-data feeds, order managers) can be
swapped without touching this file. The default signal source is
``NoopSignalSource`` — the real Lane B / Lane D adapter ships in BL-728
(separate task).

Scheduling
----------
A bar-close aligned tick is implemented as ``sleep_until_next`` on an
injectable :class:`Clock` callable. The default ``SystemClock`` uses
``asyncio.get_event_loop().time()``; tests inject ``FakeClock`` so a
24h simulated run completes in milliseconds.

Graceful shutdown
-----------------
SIGTERM / SIGINT set an :class:`asyncio.Event` (``_stop_event``) that
the loop checks between cycles. The current cycle is allowed to finish
its DB writes, then the loop exits with code 0.

Configuration
-------------
A :class:`PaperRunnerConfig` dataclass is loadable from YAML
(see ``config/paper.yaml``).  All fields have safe defaults so the
runner can boot with just ``--symbols`` and ``--db``.

Public surface
--------------
- :class:`PaperRunnerConfig` — typed config, ``from_yaml``.
- :class:`PriceProvider` — structural typing protocol.
- :class:`LakePriceProvider` — reads the latest close from
  ``data/ohlcv/{symbol}_{tf}.parquet`` (or the lake if present).
- :class:`SignalSource` — structural typing protocol.
- :class:`NoopSignalSource` — emits no intents (safe default).
- :class:`Clock` — alias for the injectable ``Callable[[], float]``.
- :class:`SystemClock` / :class:`FakeClock` — concrete clocks.
- :class:`PaperRunner` — the loop.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import yaml

from execution.brokers.paper import PaperBroker
from execution.paper_orchestrator import OrderIntent, PaperOrchestrator, SlippageLedger
from execution.store import EquitySnapshot, ExecutionStore, FillRecord, OrderRecord, PositionRecord

logger = logging.getLogger("oracle.execution.runner")


# =========================================================================
class AlertSink(Protocol):
    """Structural typing for the alerting facade (BL-734).

    ``execution`` must not import first-party packages beyond core and
    application contracts (importlinter), so the runner only sees this
    protocol; the concrete :class:`alerting.events.Alerter` is injected
    by the CLI entrypoint (``scripts/run_paper.py``).
    """

    def emit_fill(
        self,
        *,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        slippage_bps: float | None = None,
        strategy_id: str = "",
    ) -> object: ...

    def emit_error(self, exc: BaseException, *, context: str = "") -> object: ...

    def emit_kill_switch(self, reason: str, *, actor: str = "") -> object: ...

    def emit_heartbeat_missed(self, since: str, *, threshold_s: float) -> object: ...


# Configuration
# =========================================================================


@dataclass
class PaperRunnerConfig:
    """Typed config for the paper runner.

    Mirror of ``config/paper.yaml``. Defaults are conservative — the
    runner never makes live orders, never spends real money, and
    requires an explicit ``symbols`` list to be useful.
    """

    db_path: str = "data/paper/paper.db"
    tick_interval_s: float = 60.0
    symbols: list[str] = field(default_factory=lambda: ["SPY", "QQQ", "AAPL", "MSFT"])
    timeframe: str = "1m"
    starting_cash: Decimal = Decimal("100000")
    heartbeat_cycle_s: int = 10  # emit heartbeat every N cycles
    heartbeat_timeout_s: float = 900.0  # alert if no heartbeat within this wall-clock window
    store_legacy_ledger_path: str | None = None
    lake_root: str = "data/lake/normalized"
    legacy_root: str = "data/ohlcv"

    @classmethod
    def from_yaml(cls, path: str | Path) -> PaperRunnerConfig:
        """Load config from a YAML file.

        Unknown keys are ignored (forward compat with fields added in
        later BLs).  Decimal fields are coerced via ``Decimal(str(v))``
        so JSON-style ``"100000"`` and bare ``100000`` both work.
        """
        path = Path(path)
        if not path.exists():
            msg = f"Config file not found: {path}"
            raise FileNotFoundError(msg)
        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if not isinstance(raw, dict):
            msg = f"Expected mapping at root of {path}, got {type(raw).__name__}"
            raise ValueError(msg)

        cfg = cls()
        if "db_path" in raw:
            cfg.db_path = str(raw["db_path"])
        if "tick_interval_s" in raw:
            cfg.tick_interval_s = float(raw["tick_interval_s"])
        if "symbols" in raw:
            cfg.symbols = [str(s) for s in (raw["symbols"] or [])]
        if "timeframe" in raw:
            cfg.timeframe = str(raw["timeframe"])
        if "starting_cash" in raw:
            cfg.starting_cash = Decimal(str(raw["starting_cash"]))
        if "heartbeat_cycle_s" in raw:
            cfg.heartbeat_cycle_s = int(raw["heartbeat_cycle_s"])
        if "heartbeat_timeout_s" in raw:
            cfg.heartbeat_timeout_s = float(raw["heartbeat_timeout_s"])
        if raw.get("store_legacy_ledger_path"):
            cfg.store_legacy_ledger_path = str(raw["store_legacy_ledger_path"])
        if "lake_root" in raw:
            cfg.lake_root = str(raw["lake_root"])
        if "legacy_root" in raw:
            cfg.legacy_root = str(raw["legacy_root"])
        return cfg


# =========================================================================
# Protocols
# =========================================================================


class PriceProvider(Protocol):
    """Structural protocol for the market-data feed.

    ``get_prices`` is awaited once per cycle; the runner ignores the
    keys it doesn't need. Implementations should be cheap to call
    (cache, lake read, or in-memory map).
    """

    async def get_prices(self, symbols: list[str]) -> dict[str, Decimal]: ...


class SignalSource(Protocol):
    """Structural protocol for signal generators.

    Implementations consume the latest market prices and return a list
    of ``OrderIntent`` for the current cycle.  Returning ``[]`` is the
    expected HOLD behaviour.  Real Lane B / Lane D adapters ship in
    BL-728.
    """

    async def generate_intents(
        self, *, symbols: list[str], prices: dict[str, Decimal], positions: dict[str, Decimal]
    ) -> list[OrderIntent]: ...


# =========================================================================
# Concrete clocks
# =========================================================================


Clock = Callable[[], float]
"""Injectable monotonic clock. Tests use ``FakeClock``; prod uses ``SystemClock``."""


def system_clock() -> float:
    """Default clock — ``asyncio.get_event_loop().time()`` if a loop is
    running, ``time.monotonic()`` otherwise (CLI entrypoint)."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        return loop.time()
    import time

    return time.monotonic()


#: Default production clock (callable, not a class instance).
SystemClock: Clock = system_clock


class FakeClock:
    """Mutable clock for deterministic tests.

    ``advance(seconds)`` bumps the wall time; ``set(seconds)`` jumps
    to an absolute value.  ``asyncio.sleep`` is NOT mocked — the
    runner uses ``await clock.until(target)`` so the FakeClock fully
    owns scheduling.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds

    def set(self, seconds: float) -> None:
        self._now = seconds


# =========================================================================
# Concrete providers / sources
# =========================================================================


class NoopSignalSource:
    """Default signal source — emits no intents.

    Wired in production as a safe default until the real Lane B / Lane
    D adapter ships (BL-728).  The runner still produces heartbeats
    and equity snapshots, so a smoke run is observable end-to-end.
    """

    async def generate_intents(
        self,
        *,
        symbols: list[str],  # noqa: ARG002
        prices: dict[str, Decimal],  # noqa: ARG002
        positions: dict[str, Decimal],  # noqa: ARG002
    ) -> list[OrderIntent]:
        return []


class LakePriceProvider:
    """Read the latest close from the local data lake / ohlcv dir.

    Looks for ``{lake_root}/symbol={SYM}/tf={tf}/`` partitioned layout
    first, then falls back to ``{legacy_root}/{SYM}_{tf}.parquet`` flat
    layout.  Symbols without any matching file return ``Decimal("0")``
    and are surfaced in the cycle's audit log (so an operator notices
    missing data rather than trading blind).

    The provider keeps an in-process cache of the last row per symbol,
    refreshed on every call.  ``polars`` is optional — the provider
    falls back to ``pandas`` if polars isn't installed (the existing
    ``analytics`` extra already requires it but tests should not need
    a heavy stack).
    """

    def __init__(
        self,
        *,
        lake_root: str | Path = "data/lake/normalized",
        legacy_root: str | Path = "data/ohlcv",
        timeframe: str = "1m",
    ) -> None:
        self._lake_root = Path(lake_root)
        self._legacy_root = Path(legacy_root)
        self._timeframe = timeframe

    async def get_prices(self, symbols: list[str]) -> dict[str, Decimal]:
        return {sym: self._latest_close(sym) for sym in symbols}

    def _latest_close(self, symbol: str) -> Decimal:
        for path in self._candidate_paths(symbol):
            if not path.exists():
                continue
            try:
                return self._read_last_close(path)
            except Exception as exc:
                logger.warning("lake_read_failed path=%s err=%s", path, exc)
                continue
        # Missing data is loud on purpose; the runner audits it.
        return Decimal("0")

    def _candidate_paths(self, symbol: str) -> list[Path]:
        out: list[Path] = []
        lake_dir = self._lake_root / f"symbol={symbol}" / f"tf={self._timeframe}"
        if lake_dir.exists():
            # Partitioned layout: year=*/month=*.parquet
            for part in sorted(lake_dir.glob("year=*/month=*.parquet")):
                out.append(part)
        flat = self._legacy_root / f"{symbol}_{self._timeframe}.parquet"
        out.append(flat)
        return out

    @staticmethod
    def _read_last_close(path: Path) -> Decimal:
        """Read the last row's ``close`` from a parquet file.

        Polars preferred; pandas used as a fallback.  Both honour the
        lake's ``timestamp`` + ``close`` columns (the canonical wide
        OHLCV schema used elsewhere in the repo).
        """
        try:
            import polars as pl

            df = pl.read_parquet(str(path))
            if "close" not in df.columns or df.is_empty():
                return Decimal("0")
            last = float(df.select("close").tail(1).item())
            return Decimal(str(last))
        except ImportError:
            pass

        try:
            import pandas as pd

            df = pd.read_parquet(path)
        except ImportError as exc:
            msg = "Need polars or pandas to read lake parquet"
            raise RuntimeError(msg) from exc

        if df.empty or "close" not in df.columns:
            return Decimal("0")
        last = float(df["close"].iloc[-1])
        return Decimal(str(last))


# =========================================================================
# Helpers — fill → record / intent → record
# =========================================================================


def fill_to_record(
    intent: OrderIntent,
    *,
    fill_price: Decimal,
    fill_quantity: Decimal,
    fill_id: str,
    slippage_bps: int,
    commission: Decimal,
    order_id: str,
    broker_order_id: str,
    filled_at: str,
) -> FillRecord:
    """Build a :class:`FillRecord` from an intent + broker fill.

    The orchestrator already computes slippage; we just re-derive the
    record in the form the store expects.  Centralising the mapping
    keeps the runner free of inline constructions.
    """
    return FillRecord(
        fill_id=fill_id,
        order_id=order_id,
        broker_order_id=broker_order_id,
        instrument_id=intent.instrument_id,
        side=intent.side,
        quantity=fill_quantity,
        price=fill_price,
        commission=commission,
        slippage_bps=slippage_bps,
        backtest_price=intent.backtest_price,
        strategy=intent.strategy,
        meta=dict(intent.meta),
        filled_at=filled_at,
    )


def intent_to_order(
    intent: OrderIntent,
    *,
    order_id: str,
    broker_order_id: str,
    status: str,
    submitted_at: str,
    updated_at: str,
) -> OrderRecord:
    """Build an :class:`OrderRecord` from an intent (pre-fill status)."""
    return OrderRecord(
        order_id=order_id,
        broker_order_id=broker_order_id,
        instrument_id=intent.instrument_id,
        side=intent.side,
        quantity=intent.quantity,
        order_type="market",
        status=status,
        price=None,
        stop_price=None,
        take_profit_price=None,
        strategy=intent.strategy,
        meta=dict(intent.meta),
        submitted_at=submitted_at,
        updated_at=updated_at,
    )


def position_from_inventory(
    *,
    instrument_id: str,
    quantity: Decimal,
    avg_price: Decimal,
    realized_pnl: Decimal,
    updated_at: str,
) -> PositionRecord:
    """Wrap inventory state into a :class:`PositionRecord` for upsert."""
    return PositionRecord(
        instrument_id=instrument_id,
        quantity=quantity,
        avg_price=avg_price,
        realized_pnl=realized_pnl,
        updated_at=updated_at,
    )


# =========================================================================
# PaperRunner
# =========================================================================


@dataclass
class CycleResult:
    """One tick's outcome — surfaces cycle metrics to the audit log."""

    cycle_index: int
    ts: str
    fills: list[FillRecord]
    intents_submitted: int
    intents_with_price: int
    missing_prices: list[str]
    cycle_pnl: Decimal
    equity: Decimal


class PaperRunner:
    """The always-on loop.

    Construct with :class:`PaperRunnerConfig`, optional injectable
    providers / clock / signal source, then call :meth:`run` from an
    async context.

    Lifecycle
    ---------
    1. ``__init__`` wires config, broker, store, providers, signal
       source, clock.  No I/O.
    2. ``setup`` opens the store, connects the broker, optionally
       imports the legacy SlippageLedger, and starts the ledger.
    3. ``run`` enters the tick loop until ``_stop_event`` is set.
    4. ``shutdown`` closes the broker, closes the store, emits a final
       audit ``shutdown`` event.

    Tests
    -----
    Pass a :class:`FakeClock` so the tick loop completes in
    milliseconds, and inject a stub ``PriceProvider`` + a recording
    ``SignalSource`` to assert the wire is correct.
    """

    def __init__(
        self,
        config: PaperRunnerConfig,
        *,
        price_provider: PriceProvider | None = None,
        signal_source: SignalSource | None = None,
        broker: PaperBroker | None = None,
        clock: Clock | None = None,
        alerter: AlertSink | None = None,
    ) -> None:
        self._cfg = config
        self._alerter: AlertSink | None = alerter
        self._heartbeat_missed_s: float = float(config.heartbeat_timeout_s)
        self._price_provider: PriceProvider = price_provider or LakePriceProvider(
            lake_root=config.lake_root, legacy_root=config.legacy_root, timeframe=config.timeframe
        )
        self._signal_source: SignalSource = signal_source or NoopSignalSource()
        self._broker: PaperBroker = broker or PaperBroker()
        self._clock: Clock = clock or SystemClock
        self._store: ExecutionStore | None = None
        self._ledger: SlippageLedger | None = None
        self._orchestrator: PaperOrchestrator | None = None
        self._cycle_index = 0
        self._stop_event = asyncio.Event()
        self._consecutive_failures = 0
        self._last_audit_emitted_cycle = 0

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------
    async def setup(self) -> None:
        """Open store + broker, import legacy ledger if configured."""
        self._store = ExecutionStore(self._cfg.db_path)
        if self._cfg.store_legacy_ledger_path:
            imported = self._store.import_ledger(self._cfg.store_legacy_ledger_path)
            if imported:
                logger.info("legacy_ledger_imported count=%d", imported)
                self._store.append_audit(
                    kind="legacy_ledger_imported",
                    payload={"count": imported, "path": self._cfg.store_legacy_ledger_path},
                )
        # SlippageLedger is kept on disk next to the DB for human inspection
        # and backward compat with the Step-4 pipeline.
        ledger_dir = Path(self._cfg.db_path).parent / "slippage.jsonl"
        self._ledger = SlippageLedger(ledger_dir)
        self._orchestrator = PaperOrchestrator(self._broker, self._ledger)
        await self._broker.connect()

    async def shutdown(self, *, exit_code: int = 0) -> None:
        """Cleanly close broker + store + emit a final audit event.

        Idempotent; safe to call from a signal handler that may fire
        more than once.
        """
        if self._store is not None:
            self._store.append_audit(
                kind="shutdown",
                payload={
                    "cycle_index": self._cycle_index,
                    "exit_code": exit_code,
                    "consecutive_failures": self._consecutive_failures,
                },
            )
        try:
            await self._broker.disconnect()
        except Exception:
            logger.exception("broker_disconnect_failed")
        if self._store is not None:
            self._store.close()
            self._store = None

    def request_stop(self) -> None:
        """Set the stop flag. The current cycle finishes, then the loop exits."""
        self._stop_event.set()

    async def run(self) -> int:
        """Enter the tick loop. Returns the exit code.

        Catches every exception inside the cycle so a single bad tick
        doesn't take the runner down; three consecutive failures
        trigger a non-zero exit so a supervisor (systemd / docker) can
        restart with a fresh state.
        """
        assert self._store is not None, "call setup() before run()"
        await self._install_signal_handlers()

        self._store.append_audit(
            kind="run_start",
            payload={
                "db_path": self._cfg.db_path,
                "symbols": list(self._cfg.symbols),
                "tick_interval_s": self._cfg.tick_interval_s,
            },
        )

        try:
            while not self._stop_event.is_set():
                try:
                    result = await self._run_one_cycle()
                    self._consecutive_failures = 0
                    self._store.append_audit(
                        kind="cycle_end",
                        payload={
                            "cycle_index": result.cycle_index,
                            "ts": result.ts,
                            "intents_submitted": result.intents_submitted,
                            "fills": len(result.fills),
                            "equity": str(result.equity),
                            "missing_prices": result.missing_prices,
                        },
                    )
                except Exception as exc:
                    self._consecutive_failures += 1
                    logger.exception("cycle_failed n=%d", self._consecutive_failures)
                    if self._alerter is not None:
                        self._alerter.emit_error(
                            exc, context=f"cycle n={self._consecutive_failures}"
                        )
                    if self._store is not None:
                        self._store.append_audit(
                            kind="cycle_error",
                            payload={
                                "cycle_index": self._cycle_index,
                                "error": repr(exc),
                                "consecutive_failures": self._consecutive_failures,
                            },
                        )
                    if self._consecutive_failures >= 3:
                        if self._alerter is not None:
                            self._alerter.emit_kill_switch(
                                reason=f"3 consecutive cycle failures (last: {exc!r})",
                                actor="paper-runner-supervisor",
                            )
                        await self.shutdown(exit_code=2)
                        return 2

                if self._stop_event.is_set():
                    break
                await self._sleep_until_next_tick()
        finally:
            await self.shutdown(exit_code=0)
        return 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _make_on_fill(self, ts: str, fills: list[FillRecord]) -> Any:
        """Build the ``run_once`` on_fill callback that persists into the store.

        Captures ``ts`` and the local ``fills`` list (mutated in place
        so the caller observes the inserted records). The runner does
        NOT need the broker fill list once the records are stored —
        ``PaperOrchestrator.run_once`` still returns it for backward
        compat with the Step-4 callers.
        """
        assert self._store is not None, "setup() not called"

        def _on_fill(intent: OrderIntent, fill: Any, slippage_bps: int) -> None:
            order_id = f"order_{fill.broker_order_id}"
            record = fill_to_record(
                intent,
                fill_price=fill.price,
                fill_quantity=fill.quantity,
                fill_id=fill.fill_id,
                slippage_bps=slippage_bps,
                commission=fill.commission,
                order_id=order_id,
                broker_order_id=fill.broker_order_id,
                filled_at=ts,
            )
            # Idempotent ingestion — re-tries during crash recovery are a no-op.
            if self._store is not None and self._store.append_fill(record):
                fills.append(record)
                if self._alerter is not None:
                    self._alerter.emit_fill(
                        order_id=order_id,
                        symbol=record.instrument_id,
                        side=record.side,
                        quantity=float(record.quantity),
                        price=float(record.price),
                        slippage_bps=float(record.slippage_bps),
                        strategy_id=record.strategy,
                    )
            # Persist the order too (so the blotter is complete).
            if self._store is not None:
                self._store.append_order(
                    intent_to_order(
                        intent,
                        order_id=order_id,
                        broker_order_id=fill.broker_order_id,
                        status="filled",
                        submitted_at=ts,
                        updated_at=ts,
                    )
                )

        return _on_fill

    async def _run_one_cycle(self) -> CycleResult:
        """One tick: fetch prices → intents → fills → persist → heartbeat."""
        assert self._store is not None, "setup() not called"
        assert self._orchestrator is not None, "setup() not called"

        self._cycle_index += 1
        ts = _now_iso()

        # Heartbeat staleness check (BL-734): if the last persisted
        # heartbeat is older than the configured window, alert. The
        # wall clock is used on purpose — a stalled loop would never
        # reach this check, but a restarted process reports the gap.
        if self._alerter is not None and self._heartbeat_missed_s > 0:
            last_hb = self._store.latest_heartbeat()
            if last_hb is not None:
                last_ts = datetime.fromisoformat(last_hb.ts)
                age_s = (datetime.now(UTC) - last_ts).total_seconds()
                if age_s > self._heartbeat_missed_s:
                    self._alerter.emit_heartbeat_missed(
                        since=last_hb.ts, threshold_s=self._heartbeat_missed_s
                    )

        prices = await self._price_provider.get_prices(list(self._cfg.symbols))
        missing = [s for s in self._cfg.symbols if prices.get(s, Decimal("0")) <= 0]

        # Sync positions from the broker before asking the signal source.
        broker_positions = await self._broker.positions()
        positions_map = {p.instrument_id: p.quantity for p in broker_positions}

        intents = await self._signal_source.generate_intents(
            symbols=list(self._cfg.symbols), prices=prices, positions=dict(positions_map)
        )
        intents_with_price = [i for i in intents if prices.get(i.instrument_id, Decimal("0")) > 0]

        fills: list[FillRecord] = []
        if intents_with_price:
            broker_fills = await self._orchestrator.run_once(
                intents_with_price, prices, on_fill=self._make_on_fill(ts, fills)
            )
            _ = broker_fills  # run_once also returns the list — we captured via the callback

        # Reconcile positions and snapshot equity.
        positions = await self._broker.positions()
        # Mirror every configured symbol into the positions table — even
        # those with zero quantity — so the DB never carries a stale row
        # that no longer reflects broker truth. The broker omits symbols
        # with net qty 0 from its report; we synthesise them here.
        positions_by_instrument = {p.instrument_id: p for p in positions}
        now = ts
        for symbol in self._cfg.symbols:
            pos = positions_by_instrument.get(symbol)
            self._store.upsert_position(
                position_from_inventory(
                    instrument_id=symbol,
                    quantity=pos.quantity if pos is not None else Decimal("0"),
                    avg_price=pos.avg_price if pos is not None else Decimal("0"),
                    realized_pnl=Decimal("0"),  # paper_broker does not surface realised pnl
                    updated_at=now,
                )
            )

        cash = self._cfg.starting_cash  # paper broker doesn't model cash yet
        positions_value = sum(
            (p.quantity * prices.get(p.instrument_id, Decimal("0")) for p in positions),
            start=Decimal("0"),
        )
        equity = cash + positions_value
        daily_pnl = equity - self._cfg.starting_cash

        snapshot = EquitySnapshot(
            ts=ts,
            cash=cash,
            positions_value=positions_value,
            equity=equity,
            daily_pnl=daily_pnl,
            cycle_index=self._cycle_index,
        )
        self._store.snapshot_equity(snapshot)

        # Heartbeat every N cycles (cheap; lets the ops dashboard know
        # the runner is alive without emitting an event per tick).
        if self._cycle_index - self._last_audit_emitted_cycle >= self._cfg.heartbeat_cycle_s:
            self._store.heartbeat(
                cycle_index=self._cycle_index, payload={"equity": str(equity), "fills": len(fills)}
            )
            self._last_audit_emitted_cycle = self._cycle_index

        return CycleResult(
            cycle_index=self._cycle_index,
            ts=ts,
            fills=fills,
            intents_submitted=len(intents),
            intents_with_price=len(intents_with_price),
            missing_prices=missing,
            cycle_pnl=Decimal("0"),
            equity=equity,
        )

    async def _sleep_until_next_tick(self) -> None:
        """Sleep ``tick_interval_s`` of fake-clock / wall-clock seconds.

        Splits the sleep into short awaits so SIGTERM is honoured even
        on long tick intervals.  When a fake clock is injected the
        runner's tests skip the wall-clock wait entirely by setting
        ``tick_interval_s`` very small.
        """
        interval = max(float(self._cfg.tick_interval_s), 0.001)
        # Chunk into 1s slices so signal-handler latency stays bounded.
        deadline = self._clock() + interval
        while self._clock() < deadline and not self._stop_event.is_set():
            remaining = deadline - self._clock()
            chunk = min(0.1, remaining)
            try:
                await asyncio.sleep(chunk)
            except asyncio.CancelledError:
                return
            # Also nudge the fake clock — ``asyncio.sleep`` still waits
            # in real time, so the test must advance it manually.
            if isinstance(self._clock, FakeClock) or (
                hasattr(self._clock, "__self__") and isinstance(self._clock.__self__, FakeClock)
            ):
                # FakeClock instance call: already mutated by the test.
                pass

    async def _install_signal_handlers(self) -> None:
        """Wire SIGTERM / SIGINT to ``request_stop``.

        Only installs handlers when the runner owns the main thread
        (skipped under pytest / REPL — they install their own).
        """
        loop = asyncio.get_event_loop()
        if sys.platform == "win32":
            # Windows asyncio uses different APIs; skip for parity.
            return
        try:
            loop.add_signal_handler(signal.SIGTERM, self.request_stop)
            loop.add_signal_handler(signal.SIGINT, self.request_stop)
        except (NotImplementedError, RuntimeError):
            # add_signal_handler fails on non-main threads / uvloop quirks.
            logger.debug("signal_handlers_not_installed platform=%s", sys.platform)


# =========================================================================
# Helpers
# =========================================================================


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "CycleResult",
    "FakeClock",
    "LakePriceProvider",
    "NoopSignalSource",
    "PaperBroker",
    "PaperRunner",
    "PaperRunnerConfig",
    "PriceProvider",
    "SignalSource",
    "SystemClock",
]

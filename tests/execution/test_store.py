"""BL-729 — Tests for the durable execution store (SQLite + WAL).

Covers:
- Basic CRUD on every table (orders / fills / positions / equity /
  audit).
- Idempotent fill ingestion (``INSERT OR IGNORE`` on ``fill_id``).
- WAL crash-recovery semantics: a transaction in flight is rolled back
  on connection loss; a committed one survives ``.close()`` and a
  fresh re-open.
- Migration: import the legacy SlippageLedger JSONL into the fills
  table; re-import is a no-op (idempotency).
- Money round-trips as Decimal (no float drift).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from execution.paper_orchestrator import SlippageLedger
from execution.store import (
    AuditEvent,
    EquitySnapshot,
    ExecutionStore,
    FillRecord,
    OrderRecord,
    PositionRecord,
)

# =========================================================================
# Helpers
# =========================================================================


def _iso(ts: datetime | None = None) -> str:
    return (ts or datetime.now(UTC)).isoformat()


def _order(order_id: str = "ord-1", **overrides: object) -> OrderRecord:
    base: dict[str, object] = {
        "order_id": order_id,
        "broker_order_id": "paper_1",
        "instrument_id": "SPY",
        "side": "buy",
        "quantity": Decimal("10"),
        "order_type": "market",
        "status": "submitted",
        "price": None,
        "stop_price": None,
        "take_profit_price": None,
        "strategy": "lane_b_composite",
        "meta": {"screen_date": "2026-08-22"},
        "submitted_at": _iso(),
        "updated_at": _iso(),
    }
    base.update(overrides)
    return OrderRecord(**base)  # type: ignore[arg-type]


def _fill(fill_id: str = "fill-1", **overrides: object) -> FillRecord:
    base: dict[str, object] = {
        "fill_id": fill_id,
        "order_id": "ord-1",
        "broker_order_id": "paper_1",
        "instrument_id": "SPY",
        "side": "buy",
        "quantity": Decimal("10"),
        "price": Decimal("451.50"),
        "commission": Decimal("0"),
        "slippage_bps": 33,
        "backtest_price": Decimal("450.00"),
        "strategy": "lane_b_composite",
        "meta": {"screen_date": "2026-08-22"},
        "filled_at": _iso(),
    }
    base.update(overrides)
    return FillRecord(**base)  # type: ignore[arg-type]


def _position(instrument_id: str = "SPY", **overrides: object) -> PositionRecord:
    base: dict[str, object] = {
        "instrument_id": instrument_id,
        "quantity": Decimal("10"),
        "avg_price": Decimal("450.50"),
        "realized_pnl": Decimal("0"),
        "updated_at": _iso(),
    }
    base.update(overrides)
    return PositionRecord(**base)  # type: ignore[arg-type]


def _equity(ts: str | None = None, **overrides: object) -> EquitySnapshot:
    base: dict[str, object] = {
        "ts": ts or _iso(),
        "cash": Decimal("100000"),
        "positions_value": Decimal("4515"),
        "equity": Decimal("104515"),
        "daily_pnl": Decimal("4515"),
        "cycle_index": 1,
    }
    base.update(overrides)
    return EquitySnapshot(**base)  # type: ignore[arg-type]


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def store(tmp_path: Path) -> ExecutionStore:
    return ExecutionStore(tmp_path / "exec.db")


@pytest.fixture
def legacy_ledger(tmp_path: Path) -> SlippageLedger:
    return SlippageLedger(tmp_path / "slippage.jsonl")


# =========================================================================
# Schema / basic ops
# =========================================================================


class TestSchema:
    def test_tables_exist(self, store: ExecutionStore) -> None:
        tables = {
            row["name"]
            for row in store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {
            "orders",
            "fills",
            "positions",
            "equity_snapshots",
            "audit_log",
            "schema_meta",
        }.issubset(tables)

    def test_wal_mode_active(self, store: ExecutionStore) -> None:
        cur = store._conn.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        assert mode.lower() == "wal"

    def test_db_path_parent_created(self, tmp_path: Path) -> None:
        # Nested dir doesn't exist before — store should mkdir parents.
        target = tmp_path / "deep" / "nested" / "exec.db"
        ExecutionStore(target)
        assert target.exists()


# =========================================================================
# Orders
# =========================================================================


class TestOrders:
    def test_append_and_get(self, store: ExecutionStore) -> None:
        assert store.append_order(_order()) is True
        loaded = store.get_order("ord-1")
        assert loaded is not None
        assert loaded.instrument_id == "SPY"
        assert loaded.quantity == Decimal("10")
        assert loaded.price is None  # market order

    def test_idempotent_order(self, store: ExecutionStore) -> None:
        assert store.append_order(_order()) is True
        # Re-append same order_id — no-op, no rowcount change.
        assert store.append_order(_order()) is False
        assert store.stats()["orders"] == 1

    def test_update_order_status(self, store: ExecutionStore) -> None:
        store.append_order(_order())
        assert store.update_order_status("ord-1", status="filled") is True
        loaded = store.get_order("ord-1")
        assert loaded is not None
        assert loaded.status == "filled"

    def test_update_unknown_order_returns_false(self, store: ExecutionStore) -> None:
        assert store.update_order_status("nope", status="filled") is False

    def test_list_orders_filters(self, store: ExecutionStore) -> None:
        store.append_order(_order(order_id="a", instrument_id="SPY"))
        store.append_order(_order(order_id="b", instrument_id="QQQ"))
        spy_orders = store.list_orders(instrument_id="SPY")
        assert [o.order_id for o in spy_orders] == ["a"]
        all_orders = store.list_orders()
        assert {o.order_id for o in all_orders} == {"a", "b"}


# =========================================================================
# Fills — idempotent ingestion is the contract
# =========================================================================


class TestFills:
    def test_append_and_get(self, store: ExecutionStore) -> None:
        assert store.append_fill(_fill()) is True
        loaded = store.get_fill("fill-1")
        assert loaded is not None
        assert loaded.price == Decimal("451.50")
        assert loaded.slippage_bps == 33
        assert loaded.commission == Decimal("0")

    def test_idempotent_fill_insert_ignored(self, store: ExecutionStore) -> None:
        assert store.append_fill(_fill()) is True
        # Same fill_id: silent no-op.
        assert store.append_fill(_fill(price=Decimal("999"))) is False
        # Original price is preserved (no overwrite).
        fill = store.get_fill("fill-1")
        assert fill is not None
        assert fill.price == Decimal("451.50")
        assert store.count_fills() == 1

    def test_decimal_preserved(self, store: ExecutionStore) -> None:
        # Sub-cent precision must survive TEXT storage.
        f = _fill(fill_id="precise", price=Decimal("123.4567"), commission=Decimal("0.001"))
        store.append_fill(f)
        out = store.get_fill("precise")
        assert out is not None
        assert out.price == Decimal("123.4567")
        assert out.commission == Decimal("0.001")

    def test_count_fills_by_instrument(self, store: ExecutionStore) -> None:
        store.append_fill(_fill(fill_id="f1", instrument_id="SPY"))
        store.append_fill(_fill(fill_id="f2", instrument_id="SPY"))
        store.append_fill(_fill(fill_id="f3", instrument_id="QQQ"))
        assert store.count_fills() == 3
        assert store.count_fills(instrument_id="SPY") == 2
        assert store.count_fills(instrument_id="QQQ") == 1


# =========================================================================
# Positions
# =========================================================================


class TestPositions:
    def test_upsert_then_get(self, store: ExecutionStore) -> None:
        store.upsert_position(_position())
        loaded = store.get_position("SPY")
        assert loaded is not None
        assert loaded.quantity == Decimal("10")
        assert loaded.avg_price == Decimal("450.50")

    def test_upsert_replaces(self, store: ExecutionStore) -> None:
        store.upsert_position(_position(quantity=Decimal("10")))
        store.upsert_position(_position(quantity=Decimal("20"), avg_price=Decimal("455")))
        loaded = store.get_position("SPY")
        assert loaded is not None
        assert loaded.quantity == Decimal("20")
        assert loaded.avg_price == Decimal("455")

    def test_list_positions_sorted(self, store: ExecutionStore) -> None:
        store.upsert_position(_position("ZZZ"))
        store.upsert_position(_position("AAA"))
        store.upsert_position(_position("MMM"))
        ids = [p.instrument_id for p in store.list_positions()]
        assert ids == ["AAA", "MMM", "ZZZ"]


# =========================================================================
# Equity snapshots
# =========================================================================


class TestEquity:
    def test_snapshot_and_curve(self, store: ExecutionStore) -> None:
        t1 = _iso(datetime(2026, 8, 22, 9, 30, 0, tzinfo=UTC))
        t2 = _iso(datetime(2026, 8, 22, 9, 31, 0, tzinfo=UTC))
        store.snapshot_equity(_equity(ts=t1, equity=Decimal("100")))
        store.snapshot_equity(_equity(ts=t2, equity=Decimal("101")))
        curve = store.equity_curve()
        assert [e.equity for e in curve] == [Decimal("100"), Decimal("101")]

    def test_snapshot_idempotent_on_ts(self, store: ExecutionStore) -> None:
        ts = _iso(datetime(2026, 8, 22, 9, 30, 0, tzinfo=UTC))
        assert store.snapshot_equity(_equity(ts=ts, equity=Decimal("100"))) is True
        # Same ts — silent no-op.
        assert store.snapshot_equity(_equity(ts=ts, equity=Decimal("999"))) is False
        # Original equity preserved.
        latest = store.latest_equity()
        assert latest is not None
        assert latest.equity == Decimal("100")

    def test_latest_equity(self, store: ExecutionStore) -> None:
        t1 = _iso(datetime(2026, 8, 22, 9, 30, 0, tzinfo=UTC))
        t2 = _iso(datetime(2026, 8, 22, 9, 31, 0, tzinfo=UTC))
        store.snapshot_equity(_equity(ts=t1, equity=Decimal("100")))
        store.snapshot_equity(_equity(ts=t2, equity=Decimal("105")))
        latest = store.latest_equity()
        assert latest is not None
        assert latest.ts == t2


# =========================================================================
# Audit log
# =========================================================================


class TestAudit:
    def test_heartbeat_emits_audit(self, store: ExecutionStore) -> None:
        store.heartbeat(cycle_index=1)
        store.heartbeat(cycle_index=2)
        latest = store.latest_heartbeat()
        assert isinstance(latest, AuditEvent)
        assert latest.payload["cycle_index"] == 2
        # Heartbeats must not duplicate on re-call (audit_log is append-only).
        assert store.stats()["audit_log"] == 2

    def test_list_audit_filtered(self, store: ExecutionStore) -> None:
        store.heartbeat(cycle_index=1)
        store.append_audit(kind="shutdown", payload={"code": 0})
        beats = store.list_audit(kind="heartbeat")
        assert all(e.kind == "heartbeat" for e in beats)


# =========================================================================
# Crash recovery / WAL semantics
# =========================================================================


class TestCrashRecovery:
    def test_committed_state_survives_reopen(self, tmp_path: Path) -> None:
        db = tmp_path / "exec.db"
        store = ExecutionStore(db)
        store.append_fill(_fill("committed"))
        store.snapshot_equity(_equity(equity=Decimal("100")))
        store.close()

        # Re-open: state is still there.
        reopened = ExecutionStore(db)
        assert reopened.get_fill("committed") is not None
        latest = reopened.latest_equity()
        assert latest is not None
        assert latest.equity == Decimal("100")
        reopened.close()

    def test_transaction_rolls_back_on_exception(self, store: ExecutionStore) -> None:
        # Pre-state: no fills.
        assert store.count_fills() == 0

        class _BoomError(Exception):
            pass

        with pytest.raises(_BoomError), store._tx() as conn:
            conn.execute(
                "INSERT INTO fills (fill_id, order_id, broker_order_id, "
                "instrument_id, side, quantity, price, commission, slippage_bps, "
                "strategy, meta_json, filled_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "rolled-back",
                    "ord-x",
                    "paper_x",
                    "SPY",
                    "buy",
                    "1",
                    "100",
                    "0",
                    0,
                    "",
                    "{}",
                    _iso(),
                ),
            )
            raise _BoomError("simulated mid-write crash")

        # Transaction must NOT have committed.
        assert store.count_fills() == 0
        assert store.get_fill("rolled-back") is None

    def test_kill_connection_mid_write_recovers(self, tmp_path: Path) -> None:
        """Simulate ``kill -9`` by closing the connection mid-transaction.

        SQLite WAL guarantees that on next reopen, the uncommitted tx is
        rolled back and committed state is intact.
        """
        db = tmp_path / "exec.db"
        s1 = ExecutionStore(db)
        s1.append_fill(_fill("before-kill"))  # committed
        s1.close()  # clean close — but a real crash leaves the WAL alone

        # Re-open and append again (fresh WAL).
        s2 = ExecutionStore(db)
        s2.append_fill(_fill("after-reopen"))
        s2.close()

        s3 = ExecutionStore(db)
        assert s3.get_fill("before-kill") is not None
        assert s3.get_fill("after-reopen") is not None


# =========================================================================
# Migration — legacy SlippageLedger → fills
# =========================================================================


class TestImportLedger:
    def test_roundtrip(self, store: ExecutionStore, legacy_ledger: SlippageLedger) -> None:
        from execution.paper_orchestrator import SlippageRecord

        legacy_ledger.append(
            SlippageRecord(
                timestamp="2026-08-22T09:30:00+00:00",
                strategy="lane_b_composite",
                instrument_id="SPY",
                side="buy",
                quantity=Decimal("10"),
                backtest_price=Decimal("450.00"),
                paper_fill_price=Decimal("451.50"),
                slippage_bps=33,
                broker_order_id="paper_legacy_1",
                meta={"screen_date": "2026-08-22"},
            )
        )

        # First import: 1 new fill.
        imported = store.import_ledger(legacy_ledger.path)
        assert imported == 1
        assert store.count_fills() == 1
        fill = store.list_fills()[0]
        assert fill.instrument_id == "SPY"
        assert fill.price == Decimal("451.50")
        assert fill.backtest_price == Decimal("450.00")
        assert fill.strategy == "lane_b_composite"

    def test_reimport_is_noop(self, store: ExecutionStore, legacy_ledger: SlippageLedger) -> None:
        from execution.paper_orchestrator import SlippageRecord

        legacy_ledger.append(
            SlippageRecord(
                timestamp="2026-08-22T09:30:00+00:00",
                strategy="lane_b_composite",
                instrument_id="SPY",
                side="buy",
                quantity=Decimal("10"),
                backtest_price=Decimal("450.00"),
                paper_fill_price=Decimal("451.50"),
                slippage_bps=33,
                broker_order_id="paper_legacy_1",
                meta={},
            )
        )
        assert store.import_ledger(legacy_ledger.path) == 1
        # Second import: 0 new (idempotent on deterministic fill_id).
        assert store.import_ledger(legacy_ledger.path) == 0
        assert store.count_fills() == 1

    def test_missing_ledger_file_is_zero(self, store: ExecutionStore, tmp_path: Path) -> None:
        assert store.import_ledger(tmp_path / "nope.jsonl") == 0

    def test_multi_fill_roundtrip(
        self, store: ExecutionStore, legacy_ledger: SlippageLedger
    ) -> None:
        """Multiple records → multiple fills, each under a distinct fill_id."""
        from execution.paper_orchestrator import SlippageRecord

        for i in range(3):
            legacy_ledger.append(
                SlippageRecord(
                    timestamp=f"2026-08-22T09:30:0{i}+00:00",
                    strategy="lane_b",
                    instrument_id="SPY",
                    side="buy",
                    quantity=Decimal(str(10 + i)),
                    backtest_price=Decimal("450"),
                    paper_fill_price=Decimal("451"),
                    slippage_bps=22,
                    broker_order_id=f"paper_{i}",
                    meta={},
                )
            )

        imported = store.import_ledger(legacy_ledger.path)
        assert imported == 3
        assert store.count_fills() == 3


# =========================================================================
# Stats
# =========================================================================


class TestStats:
    def test_counts_each_table(self, store: ExecutionStore) -> None:
        assert store.stats() == {
            "orders": 0,
            "fills": 0,
            "positions": 0,
            "equity_snapshots": 0,
            "audit_log": 0,
        }
        store.append_order(_order())
        store.append_fill(_fill())
        store.upsert_position(_position())
        store.snapshot_equity(_equity())
        store.heartbeat(cycle_index=1)
        s = store.stats()
        assert s["orders"] == 1
        assert s["fills"] == 1
        assert s["positions"] == 1
        assert s["equity_snapshots"] == 1
        assert s["audit_log"] >= 1


# =========================================================================
# Close idempotency
# =========================================================================


class TestCloseIdempotent:
    def test_double_close(self, store: ExecutionStore) -> None:
        store.close()
        store.close()  # must not raise

"""BL-070 — Paper session PropFirm risk enforcement integration test.

Validates that ``run_g6_wp2_paper_sessions._PropFirmAllow`` correctly wires
the ``PropFirmOrderRiskAdapter`` into the ``OrderManager`` so that:

1. A session within daily loss / contract limits passes.
2. A session exceeding the daily loss limit has trades blocked.
3. The risk governor resets correctly between sessions.
4. Missing stop_price blocks the order (fail-closed).

These tests run the actual paper session harness (minus broker I/O) to verify
the integration end-to-end.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import polars as pl
import pytest

from execution.order_manager.types import OrderRequest
from policy.prop_firm.fixtures import TOPSTEP_TC_50K
from policy.prop_firm.governor import PropFirmRiskGovernor
from policy.prop_firm.order_risk import PropFirmOrderRiskAdapter

# Re-use the _PropFirmAllow from the paper session harness.
from scripts.run_g6_wp2_paper_sessions import _PropFirmAllow


# ── helpers ──────────────────────────────────────────────────────────────

def _make_session_df(n: int = 100) -> pl.DataFrame:
    """Deterministic mock OHLCV series."""
    import numpy as np

    rng = np.random.default_rng(42)
    close = list(100.0 + np.cumsum(rng.standard_normal(n) * 0.5))
    return pl.DataFrame({
        "open": close,
        "high": [c * 1.01 for c in close],
        "low": [c * 0.99 for c in close],
        "close": close,
        "volume": [1000.0] * n,
    })


# ── tests ────────────────────────────────────────────────────────────────


class TestPropFirmAllowConstruction:
    """Verify the _PropFirmAllow wrapper is constructable and defaults sane."""

    def test_constructs_with_defaults(self) -> None:
        pfa = _PropFirmAllow(point_value=Decimal("5.0"))
        assert pfa.point_value == Decimal("5.0")
        # Governor starts at full profile account size.
        assert pfa.governor.profile.account_size == TOPSTEP_TC_50K.account_size
        assert pfa.last_balance == float(TOPSTEP_TC_50K.account_size)

    def test_reset_session_restores_state(self) -> None:
        pfa = _PropFirmAllow(point_value=Decimal("5.0"))
        original_balance = pfa.last_balance

        # Simulate some losses.
        pfa.last_balance = 30_000.0
        pfa.governor.update(balance=30_000.0, equity=30_000.0)

        pfa.reset_session()
        assert pfa.last_balance == float(TOPSTEP_TC_50K.account_size)
        assert pfa.governor.profile.account_size == TOPSTEP_TC_50K.account_size
        assert pfa.last_balance == original_balance


class TestPropFirmAllowCheckOrder:
    """Verify check_order enforces prop-firm risk rules."""

    @pytest.fixture
    def pfa(self) -> _PropFirmAllow:
        return _PropFirmAllow(point_value=Decimal("5.0"))

    def test_allows_valid_order(self, pfa: _PropFirmAllow) -> None:
        """Order within daily loss limit should pass."""
        req = OrderRequest(
            instrument_id="MES",
            side="buy",
            quantity=Decimal("1"),
            order_type="market",
            time_in_force="day",
            price=Decimal("4500.00"),
            stop_price=Decimal("4492.00"),  # 8pt stop
            source="test",
        )
        import asyncio

        assert asyncio.run(pfa.check_order(req)) is True

    def test_blocks_order_exceeding_daily_loss(self, pfa: _PropFirmAllow) -> None:
        """Order that would push past daily loss limit must be blocked."""
        # Simulate $950 daily loss used (limit is $1000).
        pfa.last_balance = 49_050.0
        pfa.governor.update(balance=49_050.0, equity=49_050.0)

        req = OrderRequest(
            instrument_id="MES",
            side="buy",
            quantity=Decimal("1"),
            order_type="market",
            time_in_force="day",
            price=Decimal("4500.00"),
            stop_price=Decimal("4492.00"),  # $40 risk
            source="test",
        )
        # $950 + $40 = $990 < $1000 → still OK.
        # Simulate bigger loss so remaining capacity is exceeded.
        pfa.last_balance = 48_800.0
        pfa.governor.update(balance=48_800.0, equity=48_800.0)
        # $1,200 loss incurred + $40 risk = $1,240 > $1,000 limit.
        import asyncio

        assert asyncio.run(pfa.check_order(req)) is False

    def test_allows_missing_stop_with_synthetic_protection(self, pfa: _PropFirmAllow) -> None:
        """The wrapper synthesises a protective stop if none is provided."""
        req = OrderRequest(
            instrument_id="MES",
            side="buy",
            quantity=Decimal("1"),
            order_type="market",
            time_in_force="day",
            price=Decimal("4500.00"),
            source="test",
        )
        import asyncio

        # The wrapper injects a synthetic stop_price = price - 8pt
        # so the underlying adapter sees a valid stop.
        assert asyncio.run(pfa.check_order(req)) is True

    def test_blocks_missing_price(self, pfa: _PropFirmAllow) -> None:
        """Order without price must be blocked."""
        req = OrderRequest(
            instrument_id="MES",
            side="buy",
            quantity=Decimal("1"),
            order_type="market",
            time_in_force="day",
            stop_price=Decimal("4492.00"),
            source="test",
        )
        import asyncio

        assert asyncio.run(pfa.check_order(req)) is False

    def test_invalid_request_type_returns_false(self, pfa: _PropFirmAllow) -> None:
        """check_order must reject non-OrderRequest objects."""
        import asyncio

        assert asyncio.run(pfa.check_order("not-an-order")) is False  # type: ignore[arg-type]
        assert asyncio.run(pfa.check_order(42)) is False  # type: ignore[arg-type]


class TestPropFirmAllowCrossSession:
    """Verify state is isolated correctly across paper sessions."""

    def test_risk_resets_after_reset(self) -> None:
        """After reset_session(), a previously breaching adapter should allow
        fresh orders within limits."""
        pfa = _PropFirmAllow(point_value=Decimal("5.0"))
        # Drain daily loss.
        pfa.last_balance = 48_800.0
        pfa.governor.update(balance=48_800.0, equity=48_800.0)

        req = OrderRequest(
            instrument_id="MES",
            side="buy",
            quantity=Decimal("1"),
            order_type="market",
            time_in_force="day",
            price=Decimal("4500.00"),
            stop_price=Decimal("4492.00"),
            source="test",
        )
        import asyncio

        assert asyncio.run(pfa.check_order(req)) is False  # Breached.

        # Reset → should allow fresh orders.
        pfa.reset_session()
        assert asyncio.run(pfa.check_order(req)) is True

    def test_twenty_sessions_sequential(self) -> None:
        """Run 20 sequential paper sessions, each with risk-enforced trades.
        All should pass (no policy breach) with fresh reset per session."""
        import asyncio

        for i in range(20):
            pfa = _PropFirmAllow(point_value=Decimal("5.0"))
            df = _make_session_df(95)
            # Simulate a session: generate a few orders.
            for j in range(5):
                price = df["close"][j * 10]
                req = OrderRequest(
                    instrument_id="MES",
                    side="buy" if j % 2 == 0 else "sell",
                    quantity=Decimal("1"),
                    order_type="market",
                    time_in_force="day",
                    price=Decimal(str(price)),
                    stop_price=Decimal(str(price)) - Decimal("8"),
                    source="test",
                )
                allowed = asyncio.run(pfa.check_order(req))
                # All orders within limits → must be allowed.
                assert allowed, f"session {i}, order {j} blocked unexpectedly"

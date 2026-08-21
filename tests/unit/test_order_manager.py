"""BL-040 — OrderManager must refuse a missing risk gate (fail-closed).

The order path can only exist behind a risk manager; constructing an
``OrderManager`` without one is a safety violation and must raise,
never silently create a fail-open manager.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from execution.order_manager.errors import RiskRequiredError
from execution.order_manager.manager import OrderManager


def test_no_risk_manager_raises() -> None:
    """``OrderManager(broker, risk_manager=None)`` raises RiskRequiredError."""
    broker = MagicMock()
    with pytest.raises(RiskRequiredError):
        OrderManager(broker, risk_manager=None)


def test_risk_manager_present_is_accepted() -> None:
    """A real risk manager object constructs fine (no regression)."""
    broker = MagicMock()
    risk = MagicMock()
    manager = OrderManager(broker, risk_manager=risk)
    assert manager is not None

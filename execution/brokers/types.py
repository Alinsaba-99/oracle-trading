"""Backward-compatible re-export of canonical broker types.

The canonical models now live in ``core.domain.broker`` (P0 cycle-break:
``core.kill`` imports broker types, and core may not import execution).
This shim keeps every existing ``from execution.brokers.types import …``
call site working and will be removed once import-linter contracts
prohibit the direction entirely.
"""

from core.domain.broker import BrokerFill, BrokerOrder, BrokerPosition

__all__ = ["BrokerFill", "BrokerOrder", "BrokerPosition"]

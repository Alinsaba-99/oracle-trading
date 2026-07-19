"""MASState lifecycle: init, validate, snapshot."""

from __future__ import annotations

from uuid import uuid4


class StateManager:
    """Manages MASState lifecycle: init, validate, snapshot."""

    @staticmethod
    def initial(instrument: str = "SPY") -> dict[str, object]:
        """Create initial state dict suitable for LangGraph TypedDict."""
        return {
            "instrument": instrument,
            "market_data": None,
            "market_state": None,
            "analyst_signals": [],
            "debate": None,
            "risk_assessment": None,
            "decision": None,
            "errors": [],
            "run_id": str(uuid4()),
            "total_tokens": 0,
            "timing": {},
        }

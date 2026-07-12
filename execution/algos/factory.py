"""Algo factory — creates execution algo instances by name."""

from __future__ import annotations

from typing import Any

from execution.algos.iceberg import IcebergAlgo
from execution.algos.twap import TWAPAlgo
from execution.algos.vwap import VWAPAlgo

ALGO_REGISTRY: dict[str, type[Any]] = {"vwap": VWAPAlgo, "twap": TWAPAlgo, "iceberg": IcebergAlgo}


def create_algo(name: str, config: dict[str, Any] | None = None) -> Any:
    """Create an execution algo by name with optional config overrides."""
    if name == "market":
        return None  # direct path in OrderManager
    if name not in ALGO_REGISTRY:
        msg = f"Unknown algo: {name}, choices: {list(ALGO_REGISTRY)}"
        raise ValueError(msg)
    cfg = config or {}
    return ALGO_REGISTRY[name](**cfg)

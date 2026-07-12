"""Analyst factory — registry and factory function for all analyst types."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.analysts.base import BaseAnalyst

if TYPE_CHECKING:
    from agents.config import MASConfig
    from agents.llm import LLMClient


# ---------------------------------------------------------------------------
# Registry — maps analyst type strings to concrete BaseAnalyst subclasses
# ---------------------------------------------------------------------------
ANALYST_REGISTRY: dict[str, type[BaseAnalyst]] = {}

# Late imports to avoid circular dependencies
# Registry is populated at module level after class definitions are loaded


def _populate_registry() -> None:
    """Lazy-populate the analyst registry on first use.

    Importing the concrete analyst modules inside this function avoids
    circular-import issues when ``agents.analysts.__init__`` re-exports
    the factory and the concrete classes together.
    """
    if ANALYST_REGISTRY:
        return

    from agents.analysts.macro import MacroAnalyst
    from agents.analysts.sentiment import SentimentAnalyst
    from agents.analysts.technical import TechnicalAnalyst

    ANALYST_REGISTRY["macro"] = MacroAnalyst
    ANALYST_REGISTRY["technical"] = TechnicalAnalyst
    ANALYST_REGISTRY["sentiment"] = SentimentAnalyst


def create_analyst(
    analyst_type: str, llm_client: LLMClient, config: MASConfig | None = None
) -> BaseAnalyst:
    """Create an analyst instance by type name.

    Parameters
    ----------
    analyst_type:
        One of ``"macro"``, ``"technical"``, ``"sentiment"``.
    llm_client:
        LLM client the analyst uses for inference.
    config:
        MAS configuration; uses a default config when ``None``.

    Returns
    -------
    A fully initialised :class:`BaseAnalyst` subclass instance.
    """
    _populate_registry()

    cls = ANALYST_REGISTRY.get(analyst_type)
    if cls is None:
        msg = f"Unknown analyst type: {analyst_type}, choices: {list(ANALYST_REGISTRY)}"
        raise ValueError(msg)

    if config is None:
        from agents.config import MASConfig

        config = MASConfig()

    return cls(llm_client=llm_client, config=config)


def list_analysts() -> list[str]:
    """Return all registered analyst type names."""
    _populate_registry()
    return list(ANALYST_REGISTRY)

"""LLM client abstraction — protocol, litellm implementation, and fallback chain."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic import BaseModel

import litellm

from core.errors.base import OracleError
from core.logging import get_logger

logger = get_logger("oracle.agents")

__all__ = ["FallbackLLMClient", "LLMClient", "LitellmLLMClient", "ModelCallError"]


class ModelCallError(OracleError):
    """Raised when an LLM call fails (all providers exhausted)."""


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM clients providing structured extraction.

    Implementations must support multi-provider LLM calls with JSON-mode
    parsing into Pydantic models.
    """

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        temperature: float = 0.1,
        timeout_s: float = 30.0,
    ) -> BaseModel:
        """Send a structured LLM call and parse the response into a Pydantic model."""
        ...

    @property
    def model_name(self) -> str:
        """Human-readable model identifier (e.g. 'gpt-4', 'claude-3-opus')."""
        ...

    async def count_tokens(self, text: str) -> int:
        """Count tokens in the given text using the model's tokenizer."""
        ...


class LitellmLLMClient:
    """LLM client using litellm for multi-provider support.

    Supports GPT-4, Claude 3, local models, and any provider litellm
    supports. Uses JSON mode for structured extraction.
    """

    def __init__(
        self, model: str = "gpt-4", temperature: float = 0.1, timeout_s: float = 30.0
    ) -> None:
        self._model = model
        self._default_temperature = temperature
        self._default_timeout_s = timeout_s

    @property
    def model_name(self) -> str:
        return self._model

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        temperature: float = 0.1,
        timeout_s: float = 30.0,
    ) -> BaseModel:
        """Send a structured LLM call via litellm and parse JSON response.

        Steps:
        1. Build system+user messages
        2. Call litellm.acompletion with response_format={"type": "json_object"}
        3. Parse JSON into the provided Pydantic model
        4. Return validated model
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = await litellm.acompletion(
                model=self._model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                timeout=timeout_s,
            )
        except Exception as e:
            raise ModelCallError(f"LLM call failed: {e}") from e

        if not response.choices:
            raise ModelCallError("Empty response from LLM — no choices returned")

        content = response.choices[0].message.content
        if not content:
            raise ModelCallError("Empty response from LLM — no content in message")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ModelCallError(f"Malformed JSON from LLM: {e}") from e

        return response_model.model_validate(data)

    async def count_tokens(self, text: str) -> int:
        """Count tokens using litellm's token counter, falling back to estimate."""
        try:
            count = litellm.token_counter(model=self._model, text=text)
            return int(count)
        except Exception:
            # Approximate: ~4 chars per token
            return len(text) // 4


class FallbackLLMClient:
    """Wraps multiple LLM clients with fallback logic.

    On ModelCallError (or any exception), tries the next client in chain.
    Logs each fallback event.
    """

    def __init__(self, clients: list[LLMClient]) -> None:
        self._clients = clients
        self._model_name = "|".join(c.model_name for c in clients)

    @property
    def model_name(self) -> str:
        return self._model_name

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        temperature: float = 0.1,
        timeout_s: float = 30.0,
    ) -> BaseModel:
        """Try each client in order until one succeeds."""
        errors: list[Exception] = []
        for client in self._clients:
            try:
                return await client.structured_call(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=response_model,
                    temperature=temperature,
                    timeout_s=timeout_s,
                )
            except Exception as e:
                logger.warning("llm.fallback", model=client.model_name, error=str(e))
                errors.append(e)
        raise ModelCallError("All LLM clients failed") from errors[-1] if errors else None

    async def count_tokens(self, text: str) -> int:
        """Count tokens using the primary client."""
        return await self._clients[0].count_tokens(text)

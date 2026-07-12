"""Tests for LLM client protocol, LitellmLLMClient, and FallbackLLMClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from agents.llm import FallbackLLMClient, LitellmLLMClient, LLMClient, ModelCallError

# ── Fixtures ─────────────────────────────────────────────────────────────────


class _TestModel(BaseModel):
    value: int
    label: str


class _DummyClient:
    """Minimal concrete LLMClient for protocol testing.

    Does NOT inherit from LLMClient to test structural subtyping.
    """

    def __init__(self, *, succeed: bool = True) -> None:
        self._succeed = succeed

    @property
    def model_name(self) -> str:
        return "dummy"

    async def structured_call(
        self,
        system_prompt: str = "",  # noqa: ARG002
        user_prompt: str = "",  # noqa: ARG002
        response_model: type[BaseModel] | None = None,  # noqa: ARG002
        temperature: float = 0.1,  # noqa: ARG002
        timeout_s: float = 30.0,  # noqa: ARG002
    ) -> BaseModel:
        if self._succeed:
            return _TestModel(value=1, label="ok")
        msg = "Dummy client failed"
        raise ModelCallError(msg)

    async def count_tokens(self, text: str) -> int:
        return len(text) // 4


# ── LLMClient protocol ──────────────────────────────────────────────────────


class TestLLMClientProtocol:
    """Verify that LLMClient behaves as a structural Protocol."""

    def test_protocol_is_structural(self) -> None:
        """A class with matching methods should satisfy the Protocol."""
        assert isinstance(_DummyClient(succeed=True), LLMClient)

    def test_protocol_checking(self) -> None:
        """Verify isinstance checks work with Protocol."""
        client = _DummyClient(succeed=True)
        assert isinstance(client, LLMClient)


# ── LitellmLLMClient ────────────────────────────────────────────────────────


class TestLitellmLLMClient:
    """Tests for LitellmLLMClient with mocked litellm."""

    @patch("litellm.acompletion")
    async def test_structured_call_success(self, mock_acompletion: AsyncMock) -> None:
        """Successful LLM call returns a validated Pydantic model."""
        mock_response = MagicMock()
        mock_content = '{"value": 42, "label": "test"}'
        mock_response.choices = [MagicMock(message=MagicMock(content=mock_content))]
        mock_acompletion.return_value = mock_response

        client = LitellmLLMClient(model="gpt-4")
        result = await client.structured_call(
            system_prompt="Be helpful", user_prompt="What is 42?", response_model=_TestModel
        )

        assert isinstance(result, _TestModel)
        assert result.value == 42
        assert result.label == "test"
        mock_acompletion.assert_awaited_once()

    @patch("litellm.acompletion")
    async def test_structured_call_malformed_json(self, mock_acompletion: AsyncMock) -> None:
        """Malformed JSON from LLM raises ModelCallError."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="not json"))]
        mock_acompletion.return_value = mock_response

        client = LitellmLLMClient()
        with pytest.raises(ModelCallError, match="Malformed JSON"):
            await client.structured_call(
                system_prompt="", user_prompt="", response_model=_TestModel
            )

    @patch("litellm.acompletion")
    async def test_structured_call_empty_content(self, mock_acompletion: AsyncMock) -> None:
        """Empty content from LLM raises ModelCallError."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]
        mock_acompletion.return_value = mock_response

        client = LitellmLLMClient()
        with pytest.raises(ModelCallError, match="Empty response"):
            await client.structured_call(
                system_prompt="", user_prompt="", response_model=_TestModel
            )

    @patch("litellm.acompletion")
    async def test_structured_call_empty_choices(self, mock_acompletion: AsyncMock) -> None:
        """No choices from LLM raises ModelCallError."""
        mock_response = MagicMock()
        mock_response.choices = []
        mock_acompletion.return_value = mock_response

        client = LitellmLLMClient()
        with pytest.raises(ModelCallError, match="Empty response"):
            await client.structured_call(
                system_prompt="", user_prompt="", response_model=_TestModel
            )

    @patch("litellm.acompletion")
    async def test_structured_call_api_error(self, mock_acompletion: AsyncMock) -> None:
        """litellm API error raises ModelCallError."""
        mock_acompletion.side_effect = ConnectionError("API timeout")

        client = LitellmLLMClient()
        with pytest.raises(ModelCallError, match="LLM call failed"):
            await client.structured_call(
                system_prompt="", user_prompt="", response_model=_TestModel
            )

    def test_model_name(self) -> None:
        """model_name returns the configured model."""
        client = LitellmLLMClient(model="claude-3-opus")
        assert client.model_name == "claude-3-opus"

    @patch("litellm.token_counter")
    async def test_count_tokens(self, mock_token_counter: MagicMock) -> None:
        """count_tokens delegates to litellm.token_counter."""
        mock_token_counter.return_value = 42
        client = LitellmLLMClient()
        count = await client.count_tokens("hello world")
        assert count == 42
        mock_token_counter.assert_called_once_with(model="gpt-4", text="hello world")

    @patch("litellm.token_counter")
    async def test_count_tokens_fallback(self, mock_token_counter: MagicMock) -> None:
        """count_tokens falls back to estimate when token_counter fails."""
        mock_token_counter.side_effect = ValueError("no tokenizer")
        client = LitellmLLMClient()
        count = await client.count_tokens("hello")
        assert count == 1  # len("hello") // 4 = 1


# ── FallbackLLMClient ───────────────────────────────────────────────────────


class TestFallbackLLMClient:
    """Tests for FallbackLLMClient's chain-of-responsibility pattern."""

    async def test_primary_succeeds(self) -> None:
        """Primary client succeeds — no fallback needed."""
        primary = _DummyClient(succeed=True)
        fallback = _DummyClient(succeed=False)
        client = FallbackLLMClient([primary, fallback])

        result = await client.structured_call(
            system_prompt="", user_prompt="", response_model=_TestModel
        )
        assert isinstance(result, _TestModel)
        assert result.value == 1

    async def test_fallback_called_on_failure(self) -> None:
        """Primary fails — fallback is called and returns result."""
        primary = _DummyClient(succeed=False)
        fallback = _DummyClient(succeed=True)
        client = FallbackLLMClient([primary, fallback])

        result = await client.structured_call(
            system_prompt="", user_prompt="", response_model=_TestModel
        )
        assert isinstance(result, _TestModel)
        assert result.value == 1

    async def test_all_clients_fail(self) -> None:
        """All clients fail — ModelCallError is raised."""
        primary = _DummyClient(succeed=False)
        fallback = _DummyClient(succeed=False)
        client = FallbackLLMClient([primary, fallback])

        with pytest.raises(ModelCallError, match="All LLM clients failed"):
            await client.structured_call(
                system_prompt="", user_prompt="", response_model=_TestModel
            )

    def test_model_name_joins_with_pipe(self) -> None:
        """model_name concatenates all client names."""
        a = _DummyClient()
        b = _DummyClient()
        client = FallbackLLMClient([a, b])
        assert client.model_name == "dummy|dummy"

    async def test_count_tokens_uses_primary(self) -> None:
        """count_tokens delegates to the primary client."""
        primary = _DummyClient()
        fallback = _DummyClient()
        client = FallbackLLMClient([primary, fallback])

        count = await client.count_tokens("hello world")
        assert count == 2  # len("hello world") // 4 = 2

    async def test_single_client_works(self) -> None:
        """Single client list works fine."""
        client = FallbackLLMClient([_DummyClient(succeed=True)])
        result = await client.structured_call(
            system_prompt="", user_prompt="", response_model=_TestModel
        )
        assert isinstance(result, _TestModel)

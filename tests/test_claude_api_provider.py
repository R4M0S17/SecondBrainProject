"""Tests for Claude API chat provider (mocked Anthropic SDK — no live calls)."""

from __future__ import annotations

import importlib.util
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# Allow tests to run when `anthropic` is not installed (CI / minimal venv).
if importlib.util.find_spec("anthropic") is None:
    _anthropic_stub = types.ModuleType("anthropic")

    class _AuthenticationError(Exception):
        pass

    class _APIConnectionError(Exception):
        pass

    _anthropic_stub.AuthenticationError = _AuthenticationError
    _anthropic_stub.APIConnectionError = _APIConnectionError
    _anthropic_stub.AsyncAnthropic = MagicMock
    sys.modules["anthropic"] = _anthropic_stub

import anthropic  # noqa: E402

from core.inference.providers.claude_api_provider import (  # noqa: E402
    ClaudeApiChatProvider,
    ClaudeApiUnavailableError,
    _split_system,
)


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")


def test_init_raises_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ClaudeApiUnavailableError, match="ANTHROPIC_API_KEY"):
        ClaudeApiChatProvider()


def test_is_available_false_after_key_removed(
    monkeypatch: pytest.MonkeyPatch, api_key: None
) -> None:
    provider = ClaudeApiChatProvider()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert provider.is_available() is False


def test_is_available_true_when_key_set(api_key: None) -> None:
    provider = ClaudeApiChatProvider()
    assert provider.is_available() is True


def test_model_id_returns_configured_model(api_key: None) -> None:
    provider = ClaudeApiChatProvider(model="claude-opus-4-7")
    assert provider.model_id() == "claude-opus-4-7"


def test_context_window_1m(api_key: None) -> None:
    provider = ClaudeApiChatProvider(model="claude-sonnet-4-6")
    assert provider.context_window() == 1_000_000


def test_context_window_default_for_unknown_model(api_key: None) -> None:
    provider = ClaudeApiChatProvider(model="custom-model-id")
    assert provider.context_window() == 200_000


@pytest.mark.asyncio
async def test_complete_returns_text(mocker: pytest.MockFixture, api_key: None) -> None:
    mock_client = MagicMock()
    mocker.patch(
        "core.inference.providers.claude_api_provider.anthropic.AsyncAnthropic",
        return_value=mock_client,
    )
    mock_client.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text="  hello  ")])
    )
    provider = ClaudeApiChatProvider()
    result = await provider.complete([{"role": "user", "content": "hi"}])
    assert result == "hello"
    mock_client.messages.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_raises_on_auth_error(mocker: pytest.MockFixture, api_key: None) -> None:
    mock_client = MagicMock()
    mocker.patch(
        "core.inference.providers.claude_api_provider.anthropic.AsyncAnthropic",
        return_value=mock_client,
    )
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_client.messages.create = AsyncMock(
        side_effect=anthropic.AuthenticationError("bad", response=mock_response, body=None)
    )
    provider = ClaudeApiChatProvider()
    with pytest.raises(ClaudeApiUnavailableError, match="Invalid"):
        await provider.complete([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_complete_raises_on_connection_error(
    mocker: pytest.MockFixture, api_key: None
) -> None:
    mock_client = MagicMock()
    mocker.patch(
        "core.inference.providers.claude_api_provider.anthropic.AsyncAnthropic",
        return_value=mock_client,
    )
    mock_client.messages.create = AsyncMock(
        side_effect=anthropic.APIConnectionError(request=MagicMock())
    )
    provider = ClaudeApiChatProvider()
    with pytest.raises(ClaudeApiUnavailableError, match="Cannot reach"):
        await provider.complete([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_stream_yields_tokens(mocker: pytest.MockFixture, api_key: None) -> None:
    mock_client = MagicMock()
    mocker.patch(
        "core.inference.providers.claude_api_provider.anthropic.AsyncAnthropic",
        return_value=mock_client,
    )

    async def text_stream() -> str:
        yield "a"
        yield "b"

    inner = MagicMock()
    inner.text_stream = text_stream()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    mock_client.messages.stream = MagicMock(return_value=cm)

    provider = ClaudeApiChatProvider()
    parts: list[str] = []
    async for chunk in provider.stream([{"role": "user", "content": "x"}]):
        parts.append(chunk)
    assert parts == ["a", "b"]


@pytest.mark.asyncio
async def test_stream_raises_on_connection_error(mocker: pytest.MockFixture, api_key: None) -> None:
    mock_client = MagicMock()
    mocker.patch(
        "core.inference.providers.claude_api_provider.anthropic.AsyncAnthropic",
        return_value=mock_client,
    )
    mock_client.messages.stream = MagicMock(
        side_effect=anthropic.APIConnectionError(request=MagicMock())
    )
    provider = ClaudeApiChatProvider()
    with pytest.raises(ClaudeApiUnavailableError, match="Cannot reach"):
        async for _ in provider.stream([{"role": "user", "content": "x"}]):
            break


def test_split_system_separates_system_message() -> None:
    system, rest = _split_system(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ]
    )
    assert system == "You are helpful."
    assert rest == [{"role": "user", "content": "Hi"}]


def test_split_system_keeps_only_first_system_message() -> None:
    system, rest = _split_system(
        [
            {"role": "system", "content": "First"},
            {"role": "system", "content": "Second"},
            {"role": "user", "content": "Hi"},
        ]
    )
    assert system == "First"
    assert rest == [
        {"role": "system", "content": "Second"},
        {"role": "user", "content": "Hi"},
    ]


def test_split_system_no_system_message() -> None:
    system, rest = _split_system([{"role": "user", "content": "Hi"}])
    assert system == ""
    assert rest == [{"role": "user", "content": "Hi"}]

"""Verify n_ctx and cache_prompt are passed per-request to llama.cpp."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.inference.providers.llamacpp_provider import LlamaCppChatProvider


def _provider() -> LlamaCppChatProvider:
    return LlamaCppChatProvider(
        model="test-model",
        base_url="http://localhost:8080",
    )


def _chat_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


@pytest.mark.asyncio
async def test_complete_passes_n_ctx(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: _chat_response("ok"),
            raise_for_status=lambda: None,
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    await provider.complete([{"role": "user", "content": "hi"}], n_ctx=2048)

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload.get("n_ctx") == 2048


@pytest.mark.asyncio
async def test_complete_default_no_n_ctx(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: _chat_response("ok"),
            raise_for_status=lambda: None,
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    await provider.complete([{"role": "user", "content": "hi"}])

    payload = mock_client.post.call_args.kwargs["json"]
    assert "n_ctx" not in payload


@pytest.mark.asyncio
async def test_complete_passes_cache_prompt(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=lambda: _chat_response("ok"),
            raise_for_status=lambda: None,
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    await provider.complete([{"role": "user", "content": "hi"}], cache_prompt=False)

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload.get("cache_prompt") is False


@pytest.mark.asyncio
async def test_stream_passes_n_ctx(mocker):
    provider = _provider()

    async def _lines():
        yield 'data: {"choices":[{"delta":{"content":"x"}}]}'
        yield "data: [DONE]"

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = _lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    tokens = []
    async for token in provider.stream([{"role": "user", "content": "hi"}], n_ctx=1024):
        tokens.append(token)

    assert tokens == ["x"]
    payload = mock_client.stream.call_args.kwargs["json"]
    assert payload.get("n_ctx") == 1024


@pytest.mark.asyncio
async def test_stream_default_no_n_ctx(mocker):
    provider = _provider()

    async def _lines():
        yield 'data: {"choices":[{"delta":{"content":"x"}}]}'
        yield "data: [DONE]"

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = _lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    tokens = []
    async for token in provider.stream([{"role": "user", "content": "hi"}]):
        tokens.append(token)

    assert tokens == ["x"]
    payload = mock_client.stream.call_args.kwargs["json"]
    assert "n_ctx" not in payload

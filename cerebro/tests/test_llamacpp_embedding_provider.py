from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.inference.providers.llamacpp_embedding_provider import LlamaCppEmbeddingProvider


def _make_mock_client(json_return: dict) -> AsyncMock:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = json_return

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


@pytest.mark.asyncio
async def test_embed_returns_vector():
    provider = LlamaCppEmbeddingProvider()
    fake_vec = [0.1, 0.2, 0.3]
    mock_client = _make_mock_client({"data": [{"embedding": fake_vec}]})

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await provider.embed("hello world")

    assert result == fake_vec
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["input"] == ["hello world"]


@pytest.mark.asyncio
async def test_embed_sends_correct_endpoint():
    provider = LlamaCppEmbeddingProvider(base_url="http://127.0.0.1:8082")
    mock_client = _make_mock_client({"data": [{"embedding": [0.5]}]})

    with patch("httpx.AsyncClient", return_value=mock_client):
        await provider.embed("test")

    url = mock_client.post.call_args.args[0]
    assert url == "http://127.0.0.1:8082/v1/embeddings"


@pytest.mark.asyncio
async def test_embed_raises_runtime_error_on_http_error():
    provider = LlamaCppEmbeddingProvider()

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    http_err = httpx.HTTPStatusError("error", request=MagicMock(), response=mock_resp)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=http_err)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="500"):
            await provider.embed("hello")


@pytest.mark.asyncio
async def test_embed_raises_runtime_error_on_connect_error():
    provider = LlamaCppEmbeddingProvider()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Cannot connect"):
            await provider.embed("hello")


def test_dimensions_returns_1024():
    assert LlamaCppEmbeddingProvider().dimensions() == 1024


def test_name_property():
    assert LlamaCppEmbeddingProvider().name == "llamacpp-embed"

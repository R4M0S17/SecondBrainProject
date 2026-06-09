import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from core.inference.engine import InferenceEngine, InferenceTimeoutError


@pytest.mark.asyncio
async def test_complete_returns_string(mocker):
    engine = InferenceEngine(model="phi3:mini")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "  Hello world  ", "done": True}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    result = await engine.complete("Say hello")
    assert isinstance(result, str)
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_embed_returns_768_floats(mocker):
    engine = InferenceEngine(model="phi3:mini")

    fake_embedding = [0.1] * 768
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"embedding": fake_embedding}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    result = await engine.embed("Test text")
    assert isinstance(result, list)
    assert len(result) == 768
    assert all(isinstance(v, float) for v in result)


@pytest.mark.asyncio
async def test_timeout_raises(mocker):
    engine = InferenceEngine(model="phi3:mini")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    with pytest.raises(InferenceTimeoutError):
        await engine.complete("Any prompt")


def test_unavailable_returns_false(mocker):
    engine = InferenceEngine(model="phi3:mini")

    mock_client = MagicMock()
    mock_client.get = MagicMock(side_effect=httpx.ConnectError("connection refused"))
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)

    mocker.patch("httpx.Client", return_value=mock_client)

    assert engine.is_available() is False


@pytest.mark.asyncio
async def test_embedding_cache_sqlite_persistence(tmp_path):
    """Two CachedEmbeddingProvider instances sharing SQLite: inner provider called only once."""
    from core.cache.embedding_cache import CachedEmbeddingProvider, EmbeddingCache

    db_path = tmp_path / "test_embed_cache.sqlite"
    fake_vec = [0.1] * 384

    # First provider — call embed, expects underlying provider to be called
    mock_underlying = MagicMock()
    mock_underlying.embed = AsyncMock(return_value=fake_vec)
    mock_underlying.dimensions.return_value = 384

    cache1 = EmbeddingCache(max_size=200, persist_db_path=str(db_path), ttl_seconds=3600)
    provider1 = CachedEmbeddingProvider(mock_underlying, cache1)
    result1 = await provider1.embed("test text")
    assert result1 == fake_vec
    assert mock_underlying.embed.call_count == 1

    # Let fire-and-forget SQLite write complete
    await asyncio.sleep(0.1)

    # Second provider — same text, same db, should hit SQLite cache
    mock_underlying2 = MagicMock()
    mock_underlying2.embed = AsyncMock(return_value=fake_vec)
    mock_underlying2.dimensions.return_value = 384

    cache2 = EmbeddingCache(max_size=200, persist_db_path=str(db_path), ttl_seconds=3600)
    provider2 = CachedEmbeddingProvider(mock_underlying2, cache2)
    result2 = await provider2.embed("test text")
    assert result2 == fake_vec
    assert mock_underlying2.embed.call_count == 0  # Should not call provider

    assert result2 == result1

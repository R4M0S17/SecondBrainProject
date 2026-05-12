from __future__ import annotations

import pytest

from core.cache.embedding_cache import CachedEmbeddingProvider, EmbeddingCache


class MockEmbeddingProvider:
    def __init__(self) -> None:
        self.embed_calls = 0

    async def embed(self, text: str) -> list[float]:
        self.embed_calls += 1
        return [float(ord(c)) for c in text[:768].ljust(768)]

    def model_id(self) -> str:
        return "mock-embed-model"


@pytest.mark.asyncio
async def test_embedding_cache_hit() -> None:
    cache = EmbeddingCache(max_size=10)
    mock_provider = MockEmbeddingProvider()
    cached_provider = CachedEmbeddingProvider(mock_provider, cache)

    text = "test query"
    result1 = await cached_provider.embed(text)
    result2 = await cached_provider.embed(text)

    assert result1 == result2
    assert mock_provider.embed_calls == 1
    assert cache.hit_rate() == 50.0


@pytest.mark.asyncio
async def test_embedding_cache_miss() -> None:
    cache = EmbeddingCache(max_size=10)
    mock_provider = MockEmbeddingProvider()
    cached_provider = CachedEmbeddingProvider(mock_provider, cache)

    result1 = await cached_provider.embed("query 1")
    result2 = await cached_provider.embed("query 2")

    assert result1 != result2
    assert mock_provider.embed_calls == 2
    assert cache.hit_rate() == 0.0


@pytest.mark.asyncio
async def test_embedding_cache_lru_eviction() -> None:
    cache = EmbeddingCache(max_size=3)
    mock_provider = MockEmbeddingProvider()
    cached_provider = CachedEmbeddingProvider(mock_provider, cache)

    await cached_provider.embed("query 1")
    await cached_provider.embed("query 2")
    await cached_provider.embed("query 3")

    assert len(cache._cache) == 3

    await cached_provider.embed("query 4")

    assert len(cache._cache) == 3
    assert mock_provider.embed_calls == 4


@pytest.mark.asyncio
async def test_embedding_cache_stats() -> None:
    cache = EmbeddingCache(max_size=10)
    mock_provider = MockEmbeddingProvider()
    cached_provider = CachedEmbeddingProvider(mock_provider, cache)

    await cached_provider.embed("query 1")
    await cached_provider.embed("query 1")
    await cached_provider.embed("query 2")

    stats = cached_provider.get_cache_stats()

    assert stats["hits"] == 1
    assert stats["misses"] == 2
    assert stats["size"] == 2
    assert stats["max_size"] == 10


@pytest.mark.asyncio
async def test_cached_embedding_provider_delegates_model_id() -> None:
    mock_provider = MockEmbeddingProvider()
    cached_provider = CachedEmbeddingProvider(mock_provider)

    assert cached_provider.model_id() == "mock-embed-model"

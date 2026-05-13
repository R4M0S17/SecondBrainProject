from __future__ import annotations

import asyncio

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


@pytest.mark.asyncio
async def test_embedding_cache_concurrent_access() -> None:
    cache = EmbeddingCache(max_size=100)
    mock_provider = MockEmbeddingProvider()
    cached_provider = CachedEmbeddingProvider(mock_provider, cache)

    async def access_cache(query: str) -> list[float]:
        return await cached_provider.embed(query)

    tasks = [access_cache(f"query {i % 10}") for i in range(50)]
    results = await asyncio.gather(*tasks)

    assert all(isinstance(r, list) for r in results)
    assert len(results) == 50
    assert mock_provider.embed_calls == 10
    stats = cache.stats()
    assert stats["hits"] == 40
    assert stats["misses"] == 10


@pytest.mark.asyncio
async def test_embedding_cache_concurrent_put_and_get() -> None:
    cache = EmbeddingCache(max_size=50)

    async def concurrent_ops(idx: int) -> None:
        for i in range(10):
            text = f"query {(idx + i) % 20}"
            await cache.put(text, [float(i)] * 768)
            await cache.get(text)

    tasks = [concurrent_ops(i) for i in range(5)]
    await asyncio.gather(*tasks)

    stats = cache.stats()
    assert stats["size"] <= 50
    assert stats["hits"] + stats["misses"] > 0


@pytest.mark.asyncio
async def test_embedding_cache_clear() -> None:
    cache = EmbeddingCache(max_size=10)
    await cache.put("query 1", [1.0] * 768)
    await cache.put("query 2", [2.0] * 768)

    assert len(cache._cache) == 2

    await cache.clear()

    assert len(cache._cache) == 0
    assert cache.hit_rate() == 0.0

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


@pytest.mark.asyncio
async def test_embedding_cache_performance_metrics() -> None:
    """Verify cache tracks latency metrics correctly."""
    cache = EmbeddingCache(max_size=10)

    await cache.put("query 1", [1.0] * 768)
    await cache.put("query 2", [2.0] * 768)
    await cache.get("query 1")  # hit
    await cache.get("query 3")  # miss

    stats = cache.stats()
    assert stats["avg_get_latency_ms"] >= 0
    assert stats["avg_put_latency_ms"] >= 0
    assert stats["evictions"] == 0
    assert "ttl_seconds" in stats


@pytest.mark.asyncio
async def test_embedding_cache_ttl_expiry() -> None:
    """Expired entries should be treated as cache misses."""
    cache = EmbeddingCache(max_size=10, ttl_seconds=1)
    mock_provider = MockEmbeddingProvider()
    cached_provider = CachedEmbeddingProvider(mock_provider, cache)

    result1 = await cached_provider.embed("query 1")

    # Wait for TTL to expire
    await asyncio.sleep(1.1)

    # Should get a new embedding (cache miss due to expiry)
    result2 = await cached_provider.embed("query 1")

    assert result1 == result2
    assert mock_provider.embed_calls == 2


@pytest.mark.asyncio
async def test_embedding_cache_tracks_evictions() -> None:
    """Cache should track eviction count."""
    cache = EmbeddingCache(max_size=2)
    mock_provider = MockEmbeddingProvider()
    cached_provider = CachedEmbeddingProvider(mock_provider, cache)

    await cached_provider.embed("query 1")
    await cached_provider.embed("query 2")
    await cached_provider.embed("query 3")  # Triggers eviction
    await cached_provider.embed("query 4")  # Triggers eviction

    stats = cache.stats()
    assert stats["evictions"] == 2


@pytest.mark.asyncio
async def test_cached_embedding_provider_timeout_error() -> None:
    """Provider timeout should be retried."""

    class SlowProvider:
        def __init__(self) -> None:
            self.call_count = 0

        async def embed(self, text: str) -> list[float]:
            self.call_count += 1
            # Only timeout on first call
            if self.call_count == 1:
                await asyncio.sleep(20)  # Longer than timeout
            return [1.0] * 768

        def model_id(self) -> str:
            return "slow"

    provider = SlowProvider()
    cache = EmbeddingCache(max_size=10)
    cached_provider = CachedEmbeddingProvider(provider, cache)

    # Should eventually succeed after retries
    result = await cached_provider.embed("query 1")
    assert result == [1.0] * 768
    assert provider.call_count > 1  # At least one timeout + one success


@pytest.mark.asyncio
async def test_cached_embedding_provider_provider_error_not_cached() -> None:
    """Failed embeddings should not be cached."""

    class FailingProvider:
        def __init__(self) -> None:
            self.embed_calls = 0

        async def embed(self, text: str) -> list[float]:
            self.embed_calls += 1
            raise RuntimeError("Provider failure")

        def model_id(self) -> str:
            return "failing"

    provider = FailingProvider()
    cache = EmbeddingCache(max_size=10)
    cached_provider = CachedEmbeddingProvider(provider, cache)

    # Should raise after all retries exhausted
    with pytest.raises(RuntimeError, match="Failed to embed text"):
        await cached_provider.embed("query 1")

    # Cache should still be empty (no failed embedding cached)
    assert cache.stats()["size"] == 0


@pytest.mark.asyncio
async def test_cached_embedding_provider_partial_retry_success() -> None:
    """Provider should eventually succeed if errors are transient."""

    class TransientFailProvider:
        def __init__(self) -> None:
            self.call_count = 0

        async def embed(self, text: str) -> list[float]:
            self.call_count += 1
            if self.call_count < 3:
                raise ConnectionError("Temporary network error")
            return [1.0] * 768

        def model_id(self) -> str:
            return "transient"

    provider = TransientFailProvider()
    cache = EmbeddingCache(max_size=10)
    cached_provider = CachedEmbeddingProvider(provider, cache)

    result = await cached_provider.embed("query 1")

    assert result == [1.0] * 768
    assert provider.call_count == 3  # 2 failures + 1 success
    # Should be cached now
    cache_stats = cache.stats()
    assert cache_stats["size"] == 1

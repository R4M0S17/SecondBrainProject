from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from core.cache.embedding_cache import CachedEmbeddingProvider, EmbeddingCache
from core.cache.stores import InMemoryCacheStore, SQLiteCacheStore


class MockEmbeddingProvider:
    def __init__(self) -> None:
        self.embed_calls = 0

    async def embed(self, text: str) -> list[float]:
        self.embed_calls += 1
        return [float(ord(c)) for c in text[:768].ljust(768)]

    def dimensions(self) -> int:
        return 768


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

        def dimensions(self) -> int:
            return 768

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

        def dimensions(self) -> int:
            return 768

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

        def dimensions(self) -> int:
            return 768

    provider = TransientFailProvider()
    cache = EmbeddingCache(max_size=10)
    cached_provider = CachedEmbeddingProvider(provider, cache)

    result = await cached_provider.embed("query 1")

    assert result == [1.0] * 768
    assert provider.call_count == 3  # 2 failures + 1 success
    # Should be cached now
    cache_stats = cache.stats()
    assert cache_stats["size"] == 1


@pytest.mark.asyncio
async def test_embedding_cache_persistence_checkpoint() -> None:
    """Cache should checkpoint to store periodically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "cache.db"
        cache = EmbeddingCache(max_size=10, persist_db_path=db_path)

        # Add entries
        await cache.put("query 1", [1.0] * 768)
        await cache.put("query 2", [2.0] * 768)

        # Trigger checkpoint manually
        await cache.checkpoint()

        # Verify store was updated
        store = cache._store
        assert isinstance(store, SQLiteCacheStore)

        # Load from store and verify
        loaded = await store.load_all()
        assert len(loaded) == 2


@pytest.mark.asyncio
async def test_embedding_cache_load_from_store() -> None:
    """Cache should load entries from persistent store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "cache.db"

        # Create cache and add entries
        cache1 = EmbeddingCache(max_size=10, persist_db_path=db_path)
        await cache1.put("query 1", [1.0] * 768)
        await cache1.put("query 2", [2.0] * 768)
        await cache1.checkpoint()

        # Create new cache instance from same DB
        cache2 = EmbeddingCache(max_size=10, persist_db_path=db_path)
        await cache2.load_from_store()

        # Verify entries were loaded
        assert len(cache2._cache) == 2
        retrieved = await cache2.get("query 1")
        assert retrieved == [1.0] * 768


@pytest.mark.asyncio
async def test_embedding_cache_persistence_across_restarts() -> None:
    """Cache persistence should survive cache instance restarts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "cache.db"

        # First instance: add data
        cache1 = EmbeddingCache(max_size=10, persist_db_path=db_path)
        mock_provider = MockEmbeddingProvider()
        cached_provider1 = CachedEmbeddingProvider(mock_provider, cache1)

        await cached_provider1.embed("query 1")
        await cached_provider1.embed("query 2")
        await cache1.checkpoint()

        assert mock_provider.embed_calls == 2

        # Second instance: load from store, no provider calls needed
        cache2 = EmbeddingCache(max_size=10, persist_db_path=db_path)
        mock_provider2 = MockEmbeddingProvider()
        cached_provider2 = CachedEmbeddingProvider(mock_provider2, cache2)

        await cache2.load_from_store()

        # Should get from cache without calling provider
        result1 = await cached_provider2.embed("query 1")
        result2 = await cached_provider2.embed("query 2")

        assert mock_provider2.embed_calls == 0  # No provider calls needed!
        assert result1 is not None
        assert result2 is not None


@pytest.mark.asyncio
async def test_embedding_cache_sqlite_store_direct() -> None:
    """SQLiteCacheStore should persist and retrieve entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteCacheStore(db_path)

        # Save entries
        await store.save_entry("key1", [1.0, 2.0, 3.0], 123.456)
        await store.save_entry("key2", [4.0, 5.0, 6.0], 789.012)

        # Load all
        loaded = await store.load_all()
        assert len(loaded) == 2
        assert loaded["key1"] == ([1.0, 2.0, 3.0], 123.456)
        assert loaded["key2"] == ([4.0, 5.0, 6.0], 789.012)

        # Load single
        entry = await store.load_entry("key1")
        assert entry == ([1.0, 2.0, 3.0], 123.456)

        # Delete
        await store.delete_entry("key1")
        loaded = await store.load_all()
        assert len(loaded) == 1
        assert "key1" not in loaded

        # Clear
        await store.clear()
        loaded = await store.load_all()
        assert len(loaded) == 0


@pytest.mark.asyncio
async def test_embedding_cache_in_memory_store() -> None:
    """InMemoryCacheStore should work without persistence."""
    store = InMemoryCacheStore()
    cache = EmbeddingCache(max_size=10, store=store)

    await cache.put("query 1", [1.0] * 768)
    await cache.put("query 2", [2.0] * 768)

    stats = cache.stats()
    assert stats["persistence_store"] == "InMemoryCacheStore"
    assert stats["size"] == 2

    # Clear
    await cache.clear()
    assert stats["size"] == 2  # Stats unchanged after clear
    loaded = await store.load_all()
    assert len(loaded) == 0

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Final

from loguru import logger

if TYPE_CHECKING:
    from core.inference.registry import EmbeddingProvider

EMBED_TIMEOUT_SEC: Final = 10
EMBED_MAX_RETRIES: Final = 3
EMBED_RETRY_BACKOFF_SEC: Final = 0.5


class EmbeddingCache:
    """Thread-safe LRU cache with performance metrics and optional TTL."""

    def __init__(self, max_size: int = 200, ttl_seconds: int | None = None) -> None:
        """Initialize cache.

        Args:
            max_size: Maximum number of embeddings to cache
            ttl_seconds: Time-to-live for entries in seconds (None = no expiry)
        """
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._timestamps: dict[str, float] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._total_get_latency_ms = 0.0
        self._total_put_latency_ms = 0.0
        self._lock = asyncio.Lock()

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def _is_expired(self, key: str) -> bool:
        """Check if cache entry has expired."""
        if self._ttl_seconds is None:
            return False
        timestamp = self._timestamps.get(key, 0)
        return (time.time() - timestamp) > self._ttl_seconds

    async def get(self, text: str) -> list[float] | None:
        key = self._hash_text(text)
        start_time = time.time()
        async with self._lock:
            if key in self._cache and not self._is_expired(key):
                self._hits += 1
                self._cache.move_to_end(key)
                embedding = self._cache[key]
            else:
                self._misses += 1
                embedding = None
                # Clean up expired entry
                if key in self._cache:
                    del self._cache[key]
                    if key in self._timestamps:
                        del self._timestamps[key]

        latency_ms = (time.time() - start_time) * 1000
        self._total_get_latency_ms += latency_ms
        return embedding

    async def put(self, text: str, embedding: list[float]) -> None:
        key = self._hash_text(text)
        start_time = time.time()
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = embedding
            self._timestamps[key] = time.time()

            if len(self._cache) > self._max_size:
                lru_key = next(iter(self._cache))
                del self._cache[lru_key]
                if lru_key in self._timestamps:
                    del self._timestamps[lru_key]
                self._evictions += 1

        latency_ms = (time.time() - start_time) * 1000
        self._total_put_latency_ms += latency_ms

    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return (self._hits / total * 100) if total > 0 else 0.0

    def avg_get_latency_ms(self) -> float:
        return (self._total_get_latency_ms / self._hits) if self._hits > 0 else 0.0

    def avg_put_latency_ms(self) -> float:
        total_puts = max(1, len(self._cache) + self._evictions)
        return self._total_put_latency_ms / total_puts

    def stats(self) -> dict:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": self.hit_rate(),
            "size": len(self._cache),
            "max_size": self._max_size,
            "evictions": self._evictions,
            "avg_get_latency_ms": self.avg_get_latency_ms(),
            "avg_put_latency_ms": self.avg_put_latency_ms(),
            "ttl_seconds": self._ttl_seconds,
        }

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._total_get_latency_ms = 0.0
            self._total_put_latency_ms = 0.0


class CachedEmbeddingProvider:
    """Embedding provider with caching, timeout, and retry logic."""

    def __init__(self, provider: EmbeddingProvider, cache: EmbeddingCache | None = None) -> None:
        self._provider = provider
        self._cache = cache or EmbeddingCache(max_size=200)

    async def embed(self, text: str) -> list[float]:
        """Get embedding with cache-first approach and error handling.

        Tries cache first, then calls provider with timeout and retry logic.
        Does not cache failed embeddings.
        """
        cached = await self._cache.get(text)
        if cached is not None:
            logger.debug("Embedding cache hit for text: {}", text[:50])
            return cached

        # Try provider with retries and timeout
        embedding = await self._embed_with_retry(text)
        if embedding is not None:
            await self._cache.put(text, embedding)
            return embedding
        else:
            raise RuntimeError(f"Failed to embed text after {EMBED_MAX_RETRIES} retries")

    async def _embed_with_retry(self, text: str) -> list[float] | None:
        """Call provider with timeout and exponential backoff retry."""
        last_error = None
        for attempt in range(EMBED_MAX_RETRIES):
            try:
                embedding = await asyncio.wait_for(
                    self._provider.embed(text), timeout=EMBED_TIMEOUT_SEC
                )
                if attempt > 0:
                    logger.info("Embedding provider recovered after {} retries", attempt)
                return embedding
            except asyncio.TimeoutError as e:
                last_error = e
                wait_time = EMBED_RETRY_BACKOFF_SEC * (2 ** attempt)
                logger.warning(
                    "Embedding timeout on attempt {} (waited {}s), retrying in {}s",
                    attempt + 1,
                    EMBED_TIMEOUT_SEC,
                    wait_time,
                )
                if attempt < EMBED_MAX_RETRIES - 1:
                    await asyncio.sleep(wait_time)
            except Exception as e:
                last_error = e
                wait_time = EMBED_RETRY_BACKOFF_SEC * (2 ** attempt)
                logger.warning(
                    "Embedding provider error on attempt {}: {}, retrying in {}s",
                    attempt + 1,
                    type(e).__name__,
                    wait_time,
                )
                if attempt < EMBED_MAX_RETRIES - 1:
                    await asyncio.sleep(wait_time)

        logger.error("Embedding provider failed after {} retries: {}", EMBED_MAX_RETRIES, last_error)
        return None

    def model_id(self) -> str:
        return self._provider.model_id()

    def get_cache_stats(self) -> dict:
        return self._cache.stats()

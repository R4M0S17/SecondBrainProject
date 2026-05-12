from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from core.inference.registry import EmbeddingProvider


class EmbeddingCache:
    def __init__(self, max_size: int = 200) -> None:
        self._max_size = max_size
        self._cache: dict[str, list[float]] = {}
        self._access_order: list[str] = []
        self._hits = 0
        self._misses = 0

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def get(self, text: str) -> list[float] | None:
        key = self._hash_text(text)
        if key in self._cache:
            self._hits += 1
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, text: str, embedding: list[float]) -> None:
        key = self._hash_text(text)
        if key in self._cache:
            self._access_order.remove(key)
        self._cache[key] = embedding
        self._access_order.append(key)

        if len(self._cache) > self._max_size:
            lru_key = self._access_order.pop(0)
            del self._cache[lru_key]

    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return (self._hits / total * 100) if total > 0 else 0.0

    def stats(self) -> dict:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": self.hit_rate(),
            "size": len(self._cache),
            "max_size": self._max_size,
        }

    def clear(self) -> None:
        self._cache.clear()
        self._access_order.clear()
        self._hits = 0
        self._misses = 0


class CachedEmbeddingProvider:
    def __init__(self, provider: EmbeddingProvider, cache: EmbeddingCache | None = None) -> None:
        self._provider = provider
        self._cache = cache or EmbeddingCache(max_size=200)

    async def embed(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            logger.debug("Embedding cache hit for text: {}", text[:50])
            return cached

        embedding = await self._provider.embed(text)
        self._cache.put(text, embedding)
        return embedding

    def model_id(self) -> str:
        return self._provider.model_id()

    def get_cache_stats(self) -> dict:
        return self._cache.stats()

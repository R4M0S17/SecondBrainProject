"""Cache persistence layer with in-memory and SQLite backends.

This module provides pluggable storage backends for embedding cache persistence.
The interface is abstract to allow multiple implementations:

- InMemoryCacheStore: Default, no persistence (embeddings lost on restart)
- SQLiteCacheStore: Persistent storage using SQLite3 with JSON serialization

Embeddings are stored as JSON-serialized lists of floats with timestamps for TTL support.

Example usage:
    # In-memory (default)
    store = InMemoryCacheStore()

    # With SQLite persistence
    store = SQLiteCacheStore("~/.cerebro/cache.db")
    await store.save_entry("key1", [1.0, 2.0], 123.456)
    entry = await store.load_entry("key1")  # (embedding, timestamp)
"""

from __future__ import annotations

import json
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path

from loguru import logger


class CacheStore(ABC):
    """Abstract base class for cache persistence backends."""

    @abstractmethod
    async def save_entry(self, key: str, embedding: list[float], timestamp: float) -> None:
        """Save a cache entry."""

    @abstractmethod
    async def load_entry(self, key: str) -> tuple[list[float], float] | None:
        """Load a cache entry. Returns (embedding, timestamp) or None."""

    @abstractmethod
    async def load_all(self) -> dict[str, tuple[list[float], float]]:
        """Load all cache entries."""

    @abstractmethod
    async def delete_entry(self, key: str) -> None:
        """Delete a cache entry."""

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""

    @abstractmethod
    async def delete_expired_entries(self, ttl_seconds: int) -> int:
        """Delete entries older than ttl_seconds. Returns count of deleted entries."""


class InMemoryCacheStore(CacheStore):
    """In-memory cache store (no persistence)."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[list[float], float]] = {}

    async def save_entry(self, key: str, embedding: list[float], timestamp: float) -> None:
        self._store[key] = (embedding, timestamp)

    async def load_entry(self, key: str) -> tuple[list[float], float] | None:
        return self._store.get(key)

    async def load_all(self) -> dict[str, tuple[list[float], float]]:
        return self._store.copy()

    async def delete_entry(self, key: str) -> None:
        self._store.pop(key, None)

    async def clear(self) -> None:
        self._store.clear()

    async def delete_expired_entries(self, ttl_seconds: int) -> int:
        return 0


class SQLiteCacheStore(CacheStore):
    """SQLite-backed persistent cache store."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize SQLite cache store.

        Args:
            db_path: Path to SQLite database file
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS embeddings (
                        key TEXT PRIMARY KEY,
                        embedding TEXT NOT NULL,
                        timestamp REAL NOT NULL
                    )
                    """
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to initialize SQLite cache: {}", e)
            raise

    async def save_entry(self, key: str, embedding: list[float], timestamp: float) -> None:
        """Save embedding entry to database."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                embedding_json = json.dumps(embedding)
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (key, embedding, timestamp) VALUES (?, ?, ?)",
                    (key, embedding_json, timestamp),
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to save cache entry: {}", e)

    async def load_entry(self, key: str) -> tuple[list[float], float] | None:
        """Load a single embedding entry."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute(
                    "SELECT embedding, timestamp FROM embeddings WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                if row:
                    embedding = json.loads(row[0])
                    timestamp = row[1]
                    return (embedding, timestamp)
        except sqlite3.Error as e:
            logger.error("Failed to load cache entry: {}", e)
        return None

    async def load_all(self) -> dict[str, tuple[list[float], float]]:
        """Load all embeddings from database."""
        result: dict[str, tuple[list[float], float]] = {}
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.execute("SELECT key, embedding, timestamp FROM embeddings")
                for key, embedding_json, timestamp in cursor:
                    embedding = json.loads(embedding_json)
                    result[key] = (embedding, timestamp)
        except sqlite3.Error as e:
            logger.error("Failed to load all cache entries: {}", e)
        return result

    async def delete_entry(self, key: str) -> None:
        """Delete a cache entry."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute("DELETE FROM embeddings WHERE key = ?", (key,))
                conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to delete cache entry: {}", e)

    async def clear(self) -> None:
        """Clear all entries from database."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute("DELETE FROM embeddings")
                conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to clear cache: {}", e)

    async def delete_expired_entries(self, ttl_seconds: int) -> int:
        """Delete entries older than ttl_seconds."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                cutoff = time.time() - ttl_seconds
                cursor = conn.execute("DELETE FROM embeddings WHERE timestamp < ?", (cutoff,))
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as e:
            logger.error("Failed to delete expired cache entries: {}", e)
            return 0

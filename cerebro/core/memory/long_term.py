from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import lancedb
import pyarrow as pa
from loguru import logger

if TYPE_CHECKING:
    from core.inference.registry import EmbeddingProvider
    from core.memory.vector_store import VectorStore

VECTOR_DIM = 768

_AGENT_MEMORY_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("agent_id", pa.string()),
        pa.field("content", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
        pa.field("tags", pa.string()),  # JSON-encoded list[str]
        pa.field("created_at", pa.float64()),
        pa.field("confidence", pa.float64()),
        pa.field("source", pa.string()),
    ]
)


@dataclass
class MemoryChunk:
    id: str
    agent_id: str
    content: str
    tags: list[str]
    created_at: float
    confidence: float
    source: str
    score: float = 0.0


@dataclass
class RetrievalContext:
    query: str
    task_tags: list[str]
    date_range: tuple[float, float] | None
    source_filter: list[str]
    min_confidence: float = 0.5


class LongTermStore:
    TABLE_NAME = "agent_memory"

    def __init__(
        self,
        vector_store: VectorStore,
        agent_id: str,
        embed: EmbeddingProvider,
    ) -> None:
        self._db = lancedb.connect(vector_store.db_path)
        self._agent_id = agent_id
        self._embed = embed
        self._table = self._get_or_create_table()

    def _get_or_create_table(self):
        # exist_ok=True handles concurrent connections to the same DB path
        return self._db.create_table(self.TABLE_NAME, schema=_AGENT_MEMORY_SCHEMA, exist_ok=True)

    async def search(self, query: str, context: RetrievalContext) -> list[MemoryChunk]:
        try:
            vector = await self._embed.embed(query)
        except Exception as e:
            logger.warning("Embedding unavailable, skipping long-term memory search: {}", e)
            return []

        filters = [f"agent_id = '{self._agent_id}'"]
        if context.min_confidence > 0:
            filters.append(f"confidence >= {context.min_confidence}")
        if context.source_filter:
            sources = ", ".join(f"'{s}'" for s in context.source_filter)
            filters.append(f"source IN ({sources})")
        if context.date_range:
            start, end = context.date_range
            filters.append(f"created_at >= {start} AND created_at <= {end}")

        where_clause = " AND ".join(filters)

        try:
            rows = await asyncio.to_thread(
                lambda: self._table.search(vector).where(where_clause).limit(20).to_list()
            )
        except Exception as e:
            logger.warning("LongTermStore.search failed: {}", e)
            return []

        results = []
        for row in rows:
            tags = json.loads(row.get("tags", "[]"))
            if context.task_tags and not any(t in tags for t in context.task_tags):
                continue
            results.append(
                MemoryChunk(
                    id=row["id"],
                    agent_id=row["agent_id"],
                    content=row["content"],
                    tags=tags,
                    created_at=float(row["created_at"]),
                    confidence=float(row["confidence"]),
                    source=row["source"],
                    score=float(row.get("_distance", 0.0)),
                )
            )
        return results

    async def store_episode(self, summary: str, tags: list[str]) -> str:
        chunk_id = str(uuid.uuid4())
        vector = await self._embed.embed(summary)
        row = {
            "id": chunk_id,
            "agent_id": self._agent_id,
            "content": summary,
            "vector": vector,
            "tags": json.dumps(tags),
            "created_at": datetime.now(UTC).timestamp(),
            "confidence": 1.0,
            "source": "episode",
        }
        await asyncio.to_thread(self._table.add, [row])
        logger.debug("Stored episode {} for agent {}", chunk_id, self._agent_id)
        return chunk_id

    def get_agent_episodes(self, agent_id: str, limit: int = 20) -> list[MemoryChunk]:
        try:
            arrow_table = self._table.to_arrow()
            results: list[MemoryChunk] = []
            for i in range(len(arrow_table)):
                row = {col: arrow_table[col][i].as_py() for col in arrow_table.column_names}
                if row["agent_id"] != agent_id:
                    continue
                results.append(
                    MemoryChunk(
                        id=row["id"],
                        agent_id=row["agent_id"],
                        content=row["content"],
                        tags=json.loads(row.get("tags", "[]")),
                        created_at=float(row["created_at"]),
                        confidence=float(row["confidence"]),
                        source=row["source"],
                    )
                )
            results.sort(key=lambda c: c.created_at, reverse=True)
            return results[:limit]
        except Exception as e:
            logger.warning("get_agent_episodes failed: {}", e)
            return []

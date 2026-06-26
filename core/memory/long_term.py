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

from core.memory.vector_store import EmbeddingDimensionMismatchError, _check_vector_dim

VECTOR_DIM = 768


def agent_memory_schema(embedding_dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("agent_id", pa.string()),
            pa.field("content", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), embedding_dim)),
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


def _row_to_chunk(row: dict, score: float = 0.0) -> MemoryChunk:
    return MemoryChunk(
        id=row["id"],
        agent_id=row["agent_id"],
        content=row["content"],
        tags=json.loads(row.get("tags", "[]")),
        created_at=float(row["created_at"]),
        confidence=float(row["confidence"]),
        source=row.get("source", "episode"),
        score=score,
    )


def infer_episode_ui_source(chunk: MemoryChunk) -> str:
    """Map stored row to UI source label (episode | consolidation | archived | manual)."""
    if chunk.source == "manual" or "manual" in chunk.tags:
        return "manual"
    if "archived" in chunk.tags:
        return "archived"
    if "consolidation" in chunk.tags or chunk.content.startswith("[Consolidación"):
        return "consolidation"
    return chunk.source or "episode"


def chunk_to_episode_dict(chunk: MemoryChunk) -> dict:
    tags = list(chunk.tags)
    pinned = "pinned" in tags
    return {
        "id": chunk.id,
        "content": chunk.content,
        "tags": [t for t in tags if t != "pinned"],
        "created_at": chunk.created_at,
        "confidence": chunk.confidence,
        "source": infer_episode_ui_source(chunk),
        "pinned": pinned,
        "agent_id": chunk.agent_id,
    }


def distance_to_relevance(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 / (1.0 + max(0.0, distance))))


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
        self._embedding_dim = embed.dimensions()
        self._table = self._get_or_create_table()

    def _get_or_create_table(self):
        schema = agent_memory_schema(self._embedding_dim)
        try:
            return self._db.create_table(self.TABLE_NAME, schema=schema)
        except ValueError:
            table = self._db.open_table(self.TABLE_NAME)
            try:
                sample = table.to_arrow().select(["vector"]).slice(0, 1)
                if sample.num_rows > 0:
                    first = sample["vector"][0].as_py()
                    if first is not None:
                        _check_vector_dim([float(x) for x in first], self._embedding_dim)
            except EmbeddingDimensionMismatchError:
                raise
            except Exception as e:
                logger.debug("Could not validate agent_memory dimensions: {}", e)
            return table

    async def search(self, query: str, context: RetrievalContext) -> list[MemoryChunk]:
        try:
            vector = await self._embed.embed(query)
            _check_vector_dim(vector, self._embedding_dim)
        except EmbeddingDimensionMismatchError:
            raise
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
            distance = float(row.get("_distance", 0.0))
            results.append(_row_to_chunk(row, score=distance_to_relevance(distance)))
        return results

    async def store_episode(
        self,
        summary: str,
        tags: list[str],
        *,
        source: str = "episode",
    ) -> str:
        chunk_id = str(uuid.uuid4())
        vector = await self._embed.embed(summary)
        _check_vector_dim(vector, self._embedding_dim)
        row = {
            "id": chunk_id,
            "agent_id": self._agent_id,
            "content": summary,
            "vector": vector,
            "tags": json.dumps(tags),
            "created_at": datetime.now(UTC).timestamp(),
            "confidence": 1.0,
            "source": source,
        }
        await asyncio.to_thread(self._table.add, [row])
        logger.debug("Stored episode {} for agent {}", chunk_id, self._agent_id)
        return chunk_id

    def _find_row(self, episode_id: str, agent_id: str | None = None) -> dict | None:
        aid = agent_id or self._agent_id
        try:
            arrow_table = self._table.to_arrow()
            for i in range(len(arrow_table)):
                row = {col: arrow_table[col][i].as_py() for col in arrow_table.column_names}
                if row["id"] == episode_id and row["agent_id"] == aid:
                    return row
        except Exception as e:
            logger.warning("_find_row failed: {}", e)
        return None

    async def delete_episode(self, episode_id: str, agent_id: str | None = None) -> bool:
        aid = agent_id or self._agent_id
        if self._find_row(episode_id, aid) is None:
            return False
        try:
            await asyncio.to_thread(
                lambda: self._table.delete(f"id = '{episode_id}' AND agent_id = '{aid}'")
            )
            return True
        except Exception as e:
            logger.warning("delete_episode failed: {}", e)
            return False

    async def set_episode_pinned(
        self, episode_id: str, pinned: bool, agent_id: str | None = None
    ) -> bool:
        aid = agent_id or self._agent_id
        row = self._find_row(episode_id, aid)
        if row is None:
            return False
        tags = json.loads(row.get("tags", "[]"))
        if pinned:
            if "pinned" not in tags:
                tags.append("pinned")
        else:
            tags = [t for t in tags if t != "pinned"]
        return await self._replace_row(episode_id, aid, row, tags=tags)

    async def update_episode(
        self,
        episode_id: str,
        *,
        content: str | None = None,
        tags: list[str] | None = None,
        agent_id: str | None = None,
    ) -> bool:
        aid = agent_id or self._agent_id
        row = self._find_row(episode_id, aid)
        if row is None:
            return False
        new_content = content.strip() if content is not None else row["content"]
        new_tags = tags if tags is not None else json.loads(row.get("tags", "[]"))
        row = dict(row)
        row["content"] = new_content
        if content is not None:
            vector = await self._embed.embed(new_content)
            _check_vector_dim(vector, self._embedding_dim)
            row["vector"] = vector
        return await self._replace_row(episode_id, aid, row, tags=new_tags)

    async def _replace_row(
        self,
        episode_id: str,
        agent_id: str,
        row: dict,
        *,
        tags: list[str],
    ) -> bool:
        row = dict(row)
        row["tags"] = json.dumps(tags)
        try:
            await asyncio.to_thread(
                lambda: self._table.delete(f"id = '{episode_id}' AND agent_id = '{agent_id}'")
            )
            await asyncio.to_thread(self._table.add, [row])
            return True
        except Exception as e:
            logger.warning("_replace_row failed: {}", e)
            return False

    def get_agent_episodes(self, agent_id: str, limit: int = 100) -> list[MemoryChunk]:
        try:
            arrow_table = self._table.to_arrow()
            results: list[MemoryChunk] = []
            for i in range(len(arrow_table)):
                row = {col: arrow_table[col][i].as_py() for col in arrow_table.column_names}
                if row["agent_id"] != agent_id:
                    continue
                results.append(_row_to_chunk(row))
            results.sort(key=lambda c: c.created_at, reverse=True)
            return results[:limit]
        except Exception as e:
            logger.warning("get_agent_episodes failed: {}", e)
            return []

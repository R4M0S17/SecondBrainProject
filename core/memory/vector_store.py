from __future__ import annotations

import asyncio
import collections.abc
import json
from dataclasses import dataclass
from typing import Any, cast

import lancedb
import pyarrow as pa
import pyarrow.compute as pc
from loguru import logger

from core.inference.engine import InferenceEngine
from core.ingestion.pipeline import Document

# Legacy default for tests; production uses embed provider dimensions (384 local, 1024 llamacpp).
VECTOR_DIM = 768


def vector_schema(embedding_dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("content", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), embedding_dim)),
            pa.field("source_path", pa.string()),
            pa.field("chunk_index", pa.int32()),
            pa.field("file_modified", pa.float64()),
            pa.field("metadata", pa.string()),
        ]
    )


class EmbeddingDimensionMismatchError(ValueError):
    """Raised when stored vectors do not match the active embedding provider."""


def _check_vector_dim(vector: list[float], expected: int) -> None:
    if len(vector) != expected:
        raise EmbeddingDimensionMismatchError(
            f"Vector length {len(vector)} != expected {expected}. "
            "Run: python scripts/reindex_embeddings.py after changing CEREBRO_EMBEDDINGS_BACKEND."
        )


@dataclass
class SearchResult:
    id: str
    content: str
    source_path: str
    chunk_index: int
    score: float
    metadata: dict


class VectorStore:
    def __init__(
        self,
        db_path: str,
        table_name: str = "documents",
        embedding_dim: int = VECTOR_DIM,
    ) -> None:
        self.db_path = db_path
        self.table_name = table_name
        self.embedding_dim = embedding_dim
        self._db = lancedb.connect(db_path)
        self._table = self._get_or_create_table()

    def _get_or_create_table(self):
        schema = vector_schema(self.embedding_dim)
        try:
            return self._db.create_table(self.table_name, schema=schema)
        except ValueError:
            table = self._db.open_table(self.table_name)
            self._validate_existing_table(table)
            return table

    def _validate_existing_table(self, table: Any) -> None:
        try:
            sample = table.to_arrow().select(["vector"]).slice(0, 1)
            if sample.num_rows == 0:
                return
            first = sample["vector"][0].as_py()
            if first is not None:
                _check_vector_dim([float(x) for x in first], self.embedding_dim)
        except EmbeddingDimensionMismatchError:
            raise
        except Exception as e:
            logger.debug("Could not validate vector table dimensions: {}", e)

    async def upsert(self, documents: list[Document], engine: InferenceEngine) -> int:
        if not documents:
            return 0

        indexed = self.get_indexed_files()

        # Group docs by source_path to apply anti-duplication logic per file
        by_source: dict[str, list[Document]] = {}
        for doc in documents:
            by_source.setdefault(doc.source_path, []).append(doc)

        to_insert: list[Document] = []
        for source_path, docs in by_source.items():
            mtime = docs[0].file_modified
            if source_path in indexed:
                if indexed[source_path] == mtime:
                    logger.debug("Skipping unchanged file: {}", source_path)
                    continue
                logger.info("File changed, re-indexing: {}", source_path)
                self.delete_by_source(source_path)
            to_insert.extend(docs)

        if not to_insert:
            return 0

        rows = []
        for doc in to_insert:
            vector = await engine.embed(doc.content)
            _check_vector_dim(vector, self.embedding_dim)
            rows.append(
                {
                    "id": doc.id,
                    "content": doc.content,
                    "vector": vector,
                    "source_path": doc.source_path,
                    "chunk_index": doc.chunk_index,
                    "file_modified": doc.file_modified,
                    "metadata": json.dumps(doc.metadata),
                }
            )

        await asyncio.to_thread(self._table.add, rows)
        logger.info("Inserted {} chunks into vector store", len(rows))
        return len(rows)

    async def search(
        self,
        query: str,
        engine: InferenceEngine | None = None,
        top_k: int = 5,
        embed_fn: (
            collections.abc.Callable[[str], collections.abc.Awaitable[list[float]]] | None
        ) = None,
    ) -> list[SearchResult]:
        if embed_fn:
            vector = await embed_fn(query)
        elif engine:
            vector = await engine.embed(query)
        else:
            raise ValueError("Need engine or embed_fn")
        return await self.search_by_vector(vector, top_k)

    async def search_by_vector(self, vector: list[float], top_k: int = 5) -> list[SearchResult]:
        _check_vector_dim(vector, self.embedding_dim)
        rows = await asyncio.to_thread(lambda: self._table.search(vector).limit(top_k).to_list())
        return [
            SearchResult(
                id=row["id"],
                content=row["content"],
                source_path=row["source_path"],
                chunk_index=int(row["chunk_index"]),
                score=float(row.get("_distance", 0.0)),
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]

    def delete_by_source(self, source_path: str) -> int:
        escaped = source_path.replace("'", "''")
        filter_expr = f"source_path = '{escaped}'"
        try:
            col = self._table.to_arrow().select(["source_path"])["source_path"]
            pc_mod = cast(Any, pc)
            count = int(pc_mod.sum(pc_mod.equal(col, source_path)).as_py() or 0)
            if count > 0:
                self._table.delete(filter_expr)
            return count
        except Exception as e:
            logger.warning("Failed to delete source '{}': {}", source_path, e)
            return 0

    def get_indexed_files(self) -> dict[str, float]:
        try:
            tbl = self._table.to_arrow().select(["source_path", "file_modified"])
            result: dict[str, float] = {}
            for sp, fm in zip(
                tbl["source_path"].to_pylist(),
                tbl["file_modified"].to_pylist(),
            ):
                result[sp] = float(fm)
            return result
        except Exception:
            return {}

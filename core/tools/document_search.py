"""Pure document search — no FastAPI or LLM dependencies.

Provides chunk-level vector search over indexed documents.
Used by POST /api/documents/search (chunks mode).
"""

from __future__ import annotations

import collections.abc
from dataclasses import dataclass
from pathlib import Path

from core.memory.vector_store import SearchResult, VectorStore


@dataclass
class DocumentChunkHit:
    id: str
    source_path: str
    filename: str
    chunk_index: int
    content: str
    score: float
    snippet: str


def make_snippet(content: str, max_len: int = 300) -> str:
    if len(content) <= max_len:
        return content
    truncated = content[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "…"


def filter_by_source_prefix(hits: list[SearchResult], prefix: str | None) -> list[SearchResult]:
    if not prefix:
        return hits
    return [h for h in hits if h.source_path.startswith(prefix)]


async def search_document_chunks(
    *,
    query: str,
    vector_store: VectorStore,
    embed_fn: collections.abc.Callable[[str], collections.abc.Awaitable[list[float]]],
    top_k: int = 8,
    source_prefix: str | None = None,
) -> list[DocumentChunkHit]:
    fetch_k = top_k * 3 if source_prefix else top_k
    results = await vector_store.search(query, top_k=fetch_k, embed_fn=embed_fn)
    if source_prefix:
        results = filter_by_source_prefix(results, source_prefix)
        results = results[:top_k]
    return [
        DocumentChunkHit(
            id=r.id,
            source_path=r.source_path,
            filename=Path(r.source_path).name,
            chunk_index=r.chunk_index,
            content=r.content,
            score=r.score,
            snippet=make_snippet(r.content),
        )
        for r in results
    ]

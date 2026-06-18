from __future__ import annotations

import hashlib

from core.ingestion.pipeline import Document
from core.knowledge_sync.models import FetchedItem


class ChunkingEngine:
    def __init__(self, chunk_size: int = 768, chunk_overlap: int = 96, min_chunk: int = 15) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._min_chunk = min_chunk

    def chunk(self, item: FetchedItem) -> list[Document]:
        words = item.content.split()
        if not words:
            return []

        # For very short content, create a single document
        if len(words) < self._min_chunk:
            return [
                Document(
                    id=hashlib.sha256(item.content.encode()).hexdigest(),
                    content=item.content,
                    source_path=item.url,
                    chunk_index=0,
                    file_modified=item.published_at or 0.0,
                    metadata={
                        "source_type": "knowledge_sync",
                        "url": item.url,
                        "title": item.title,
                        "author": item.author,
                        "published_at": item.published_at,
                        **item.metadata,
                    },
                )
            ]

        docs: list[Document] = []
        step = self._chunk_size - self._chunk_overlap
        i = 0
        while i < len(words):
            end = min(i + self._chunk_size, len(words))
            chunk_text = " ".join(words[i:end])
            if len(chunk_text.split()) < self._min_chunk and docs:
                prev = docs[-1]
                merged = prev.content + "\n" + chunk_text
                docs[-1] = Document(
                    id=hashlib.sha256(merged.encode()).hexdigest(),
                    content=merged,
                    source_path=prev.source_path,
                    chunk_index=prev.chunk_index,
                    file_modified=prev.file_modified,
                    metadata=prev.metadata,
                )
            else:
                docs.append(
                    Document(
                        id=hashlib.sha256(chunk_text.encode()).hexdigest(),
                        content=chunk_text,
                        source_path=item.url,
                        chunk_index=len(docs),
                        file_modified=item.published_at or 0.0,
                        metadata={
                            "source_type": "knowledge_sync",
                            "url": item.url,
                            "title": item.title,
                            "author": item.author,
                            "published_at": item.published_at,
                            **item.metadata,
                        },
                    )
                )
            i += step

        return docs

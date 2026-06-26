from __future__ import annotations

import collections.abc
import time
from dataclasses import dataclass
from pathlib import Path

from core.i18n.messages import _L
from core.inference.engine import InferenceEngine
from core.memory.vector_store import SearchResult, VectorStore
from core.utils.compressor import SemanticCompressor

NO_INFO_RESPONSE = _L("rag.no_info")

SYSTEM_PROMPT = (
    "Eres un asistente personal que responde ÚNICAMENTE basándose en el contexto\n"
    "provisto. Si la información no está en el contexto, responde exactamente:\n"
    '"No encontré información sobre eso en tus documentos."\n'
    "No inventes datos. No uses conocimiento externo."
)

# Token budget — 1 token ≈ 4 chars
_CHARS_PER_TOKEN = 4
_CONTEXT_WINDOW = 4096
_RESERVED_SYSTEM = 512  # system prompt + question overhead
_RESERVED_RESPONSE = 1024
_AVAILABLE_CHARS = (_CONTEXT_WINDOW - _RESERVED_SYSTEM - _RESERVED_RESPONSE) * _CHARS_PER_TOKEN


@dataclass
class RAGResponse:
    answer: str
    sources: list[str]
    chunks_used: int
    latency_ms: float
    compressed: bool = False


class RAGQueryEngine:
    def __init__(
        self,
        store: VectorStore,
        engine: InferenceEngine,
        compressor: SemanticCompressor | None = None,
        embed_fn: (
            collections.abc.Callable[[str], collections.abc.Awaitable[list[float]]] | None
        ) = None,
    ) -> None:
        self.store = store
        self.engine = engine
        self.compressor = compressor
        self._embed_fn = embed_fn

    async def query(self, question: str, top_k: int = 5) -> RAGResponse:
        start = time.monotonic()

        chunks = await self.store.search(
            question, engine=self.engine, top_k=top_k, embed_fn=self._embed_fn
        )
        before = len(chunks)
        if self.compressor is not None:
            chunks = self.compressor.compress(question, chunks)
        compressed = self.compressor is not None and len(chunks) < before
        prompt = self.build_prompt(question, chunks)
        answer = await self.engine.complete(prompt, system=SYSTEM_PROMPT)

        latency_ms = (time.monotonic() - start) * 1000
        # Deduplicated, insertion-order sources
        sources = list(dict.fromkeys(c.source_path for c in chunks))

        return RAGResponse(
            answer=answer,
            sources=sources,
            chunks_used=len(chunks),
            latency_ms=latency_ms,
            compressed=compressed,
        )

    def build_prompt(self, question: str, chunks: list[SearchResult]) -> str:
        context_parts: list[str] = []
        used_chars = 0

        for chunk in chunks:
            source_name = Path(chunk.source_path).name
            header = f"[Fuente: {source_name}, chunk {chunk.chunk_index}]\n"
            entry = header + chunk.content

            remaining = _AVAILABLE_CHARS - used_chars
            if len(entry) > remaining:
                truncate_at = remaining - len(header) - len(" [truncado]")
                if truncate_at <= 0:
                    break
                entry = header + chunk.content[:truncate_at] + " [truncado]"

            context_parts.append(entry)
            used_chars += len(entry)

            if used_chars >= _AVAILABLE_CHARS:
                break

        context_block = "\n---\n".join(context_parts)
        return f"Contexto de tus documentos:\n---\n{context_block}\n---\n" f"Pregunta: {question}"

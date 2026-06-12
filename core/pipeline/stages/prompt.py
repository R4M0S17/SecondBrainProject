"""Stage 4 — Prompt Assembly."""

from __future__ import annotations

from core.pipeline.pipeline import PipelineContext

_MAX_CHUNK_CHARS = 1500  # truncate individual chunks to this length


class PromptAssemblyStage:
    """Builds the final prompt from assembled context (RAG chunks + memory).

    Falls back to normalized_input when no context was retrieved.
    """

    def name(self) -> str:
        return "prompt_assembly"

    def can_skip(self) -> bool:
        return False

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        question = ctx.normalized_input or ctx.raw_input
        assembled = ctx.assembled_context

        if assembled is None or (
            not assembled.retrieved_documents and not assembled.retrieved_memory
        ):
            ctx.prompt = question
            return ctx

        parts: list[str] = []

        for doc in assembled.retrieved_documents:
            snippet = doc.content[:_MAX_CHUNK_CHARS]
            if len(doc.content) > _MAX_CHUNK_CHARS:
                snippet += " [truncado]"
            parts.append(f"[Fuente: {doc.source_path}, chunk {doc.chunk_index}]\n{snippet}")

        for mem in assembled.retrieved_memory:
            snippet = mem.content[:_MAX_CHUNK_CHARS]
            parts.append(f"[Memoria: {mem.id}]\n{snippet}")

        context_block = "\n---\n".join(parts)
        ctx.prompt = f"Contexto:\n---\n{context_block}\n---\n\nPregunta: {question}"
        return ctx

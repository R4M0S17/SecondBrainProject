"""Stage 7 — Post-Processing.

Formats the raw LLM/agent response for delivery: trims whitespace,
extracts source references from context metadata, and sets final_response.
"""

from __future__ import annotations

from core.pipeline.pipeline import PipelineContext


class PostProcessingStage:
    def name(self) -> str:
        return "post_processing"

    def can_skip(self) -> bool:
        return False

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        raw = ctx.raw_response or ""
        ctx.final_response = raw.strip()

        # Collect source paths from whichever retrieval path ran
        sources: list[str] = []
        if ctx.assembled_context:
            sources.extend(ctx.assembled_context.sources_used)
        if "rag_sources" in ctx.metadata:
            for s in ctx.metadata["rag_sources"]:
                if s not in sources:
                    sources.append(s)

        ctx.metadata["sources"] = sources
        return ctx

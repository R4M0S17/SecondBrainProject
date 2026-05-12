"""Stage 3 — Context Retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from core.pipeline.pipeline import PipelineContext

if TYPE_CHECKING:
    from core.agents.state_store import AgentState, AgentStateStore
    from core.memory.context_builder import ContextBuilder


class ContextRetrievalStage:
    """Calls ContextBuilder.build() to assemble semantic + episodic context.

    Dependencies are optional: if not supplied the stage is a no-op
    (it has can_skip=True so a build failure also won't abort the pipeline).
    """

    def __init__(
        self,
        context_builder: ContextBuilder | None = None,
        state_store: AgentStateStore | None = None,
    ) -> None:
        self._builder = context_builder
        self._state_store = state_store

    def name(self) -> str:
        return "context_retrieval"

    def can_skip(self) -> bool:
        return True

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        if self._builder is None:
            return ctx

        agent_state: AgentState | None = ctx.metadata.get("agent_state")
        if agent_state is None and self._state_store is not None:
            agent_id = ctx.metadata.get("agent_id", "default")
            agent_state = self._state_store.load(agent_id)

        if agent_state is None:
            logger.debug("ContextRetrievalStage: no agent_state available, skipping.")
            return ctx

        query = ctx.normalized_input or ctx.raw_input
        ctx.assembled_context = await self._builder.build(query, agent_state)
        if ctx.assembled_context:
            ctx.metadata["context_sources"] = ctx.assembled_context.sources_used

        return ctx

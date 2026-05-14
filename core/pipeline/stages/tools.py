"""Stage 6 — Tool / Agent Execution.

Runs the appropriate execution engine based on detected intent:
  - RAG_QUERY  → RAGQueryEngine (fast path, no full agent loop)
  - All others → AgentRuntime (full ReAct loop)
  - Fallback   → direct ChatProvider call with the assembled prompt

If policy_result is not approved, short-circuits with the policy reason.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from core.inference.registry import Message
from core.pipeline.pipeline import Intent, PipelineContext

if TYPE_CHECKING:
    from core.agents.runtime import AgentRuntime
    from core.inference.registry import ChatProvider
    from core.rag.query_engine import RAGQueryEngine


class ToolExecutionStage:
    def __init__(
        self,
        agent_runtime: AgentRuntime | None = None,
        rag_engine: RAGQueryEngine | None = None,
        chat_provider: ChatProvider | None = None,
        agent_id: str = "default",
    ) -> None:
        self._runtime = agent_runtime
        self._rag = rag_engine
        self._chat = chat_provider
        self._agent_id = agent_id

    def name(self) -> str:
        return "tool_execution"

    def can_skip(self) -> bool:
        return False

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        # Policy gate — short-circuit before any inference
        if ctx.policy_result is not None and not ctx.policy_result.approved:
            ctx.raw_response = ctx.policy_result.reason or "Solicitud bloqueada por política."
            logger.info("ToolExecutionStage: blocked by policy — {}", ctx.policy_result.reason)
            return ctx

        query = ctx.normalized_input or ctx.raw_input

        if ctx.detected_intent == Intent.RAG_QUERY and self._rag is not None:
            response = await self._rag.query(query)
            ctx.raw_response = response.answer
            ctx.metadata["rag_sources"] = response.sources
            ctx.metadata["rag_chunks_used"] = response.chunks_used
            logger.debug("ToolExecutionStage: RAG path, answer length={}", len(ctx.raw_response))

        elif self._runtime is not None:
            agent_id = ctx.metadata.get("agent_id", self._agent_id)
            answer, _ = await self._runtime.run(query, agent_id)
            ctx.raw_response = answer
            logger.debug(
                "ToolExecutionStage: AgentRuntime path, answer length={}", len(ctx.raw_response)
            )

        elif self._chat is not None:
            prompt = ctx.prompt or query
            messages: list[Message] = [{"role": "user", "content": prompt}]
            ctx.raw_response = await self._chat.complete(messages)
            logger.debug("ToolExecutionStage: direct chat path")

        else:
            ctx.raw_response = "(No se configuró motor de ejecución para esta solicitud.)"
            ctx.audit_record.warnings.append("no_execution_engine")
            logger.warning("ToolExecutionStage: no execution engine configured.")

        return ctx

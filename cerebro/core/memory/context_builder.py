from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.memory.long_term import LongTermStore, MemoryChunk, RetrievalContext

if TYPE_CHECKING:
    from core.agents.state_store import AgentState
    from core.inference.registry import Message
    from core.memory.short_term import ShortTermStore
    from core.memory.vector_store import SearchResult

# 1 token ≈ 4 characters (rough universal estimate)
_CHARS_PER_TOKEN = 4
# Leave headroom for system prompt and model response
DEFAULT_TOKEN_BUDGET = 3500


@dataclass
class AssembledContext:
    session_history: list[Message]
    retrieved_memory: list[MemoryChunk]
    retrieved_documents: list[SearchResult]
    agent_summary: str
    total_tokens_estimated: int
    sources_used: list[str]


class ContextBuilder:
    def __init__(
        self,
        short_term: ShortTermStore,
        long_term: LongTermStore,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
    ) -> None:
        self._short_term = short_term
        self._long_term = long_term
        self._token_budget = token_budget

    def _tokens(self, text: str) -> int:
        return max(1, len(text) // _CHARS_PER_TOKEN)

    async def build(self, query: str, agent_state: AgentState) -> AssembledContext:
        remaining = self._token_budget
        sources: list[str] = []

        # Priority 1: instructions + working_memory (always included, deducted upfront)
        instructions = agent_state.profile.preferences.get("instructions", "")
        working_text = " ".join(str(v) for v in agent_state.working_memory.values())
        remaining -= self._tokens(instructions + working_text)

        # Priority 2: session summary
        summary = agent_state.session_summary
        remaining -= self._tokens(summary)

        # Priority 3: retrieved memory episodes (filtered by domain tags + similarity)
        retrieval_ctx = RetrievalContext(
            query=query,
            task_tags=agent_state.profile.domain_tags,
            date_range=None,
            source_filter=[],
            min_confidence=0.5,
        )
        candidate_chunks = await self._long_term.search(query, retrieval_ctx)

        kept_memory: list[MemoryChunk] = []
        for chunk in candidate_chunks:
            cost = self._tokens(chunk.content)
            if remaining - cost >= 0:
                kept_memory.append(chunk)
                remaining -= cost
                sources.append(f"memory:{chunk.id}")
            else:
                break

        # Priority 4 (lowest): recent session messages, newest-first, trim to fit
        ctx = self._short_term.get_context()
        kept_messages: list[Message] = []
        for msg in reversed(ctx.active_messages):
            cost = self._tokens(msg["content"])
            if remaining - cost >= 0:
                kept_messages.insert(0, msg)
                remaining -= cost
            else:
                break

        total_used = self._token_budget - remaining
        return AssembledContext(
            session_history=kept_messages,
            retrieved_memory=kept_memory,
            retrieved_documents=[],  # populated by RAG layer when integrated
            agent_summary=summary,
            total_tokens_estimated=total_used,
            sources_used=sources,
        )

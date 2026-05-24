"""Per-conversation session boundaries for 8 GB hardware.

``conversation_id`` (API / ``ConversationStore``) is the durable session key —
the same UUID the UI sends on every turn in a chat surface.
"""

from __future__ import annotations

import os

from core.agents.conversation_store import ConversationRecord
from core.agents.state_store import AgentState
from core.inference.registry import Message
from core.memory.short_term import ShortTermStore

SESSION_RESUME_MAX_TURNS = int(os.getenv("CEREBRO_SESSION_RESUME_MAX_TURNS", "8"))


def resume_messages(
    record: ConversationRecord | None, max_turns: int | None = None
) -> list[Message]:
    """Return the tail of persisted turns as chat messages (role + content)."""
    if record is None or not record.turns:
        return []
    cap = max_turns if max_turns is not None else SESSION_RESUME_MAX_TURNS
    tail = record.turns[-cap:]
    return [{"role": t.role, "content": t.content} for t in tail]


def hydrate_short_term(short_term: ShortTermStore, record: ConversationRecord | None) -> None:
    """Replace in-memory short-term history with the capped conversation tail."""
    short_term.clear()
    for msg in resume_messages(record):
        short_term.push_message(msg)


def apply_conversation_to_agent_state(
    agent_state: AgentState, record: ConversationRecord | None
) -> None:
    """Load per-conversation summary and isolate tool trace from other chats."""
    if record is None:
        return
    agent_state.session_summary = record.session_summary or ""
    agent_state.tool_trace = []


def persist_session_summary(
    record: ConversationRecord, agent_state: AgentState
) -> ConversationRecord:
    record.session_summary = agent_state.session_summary or ""
    return record

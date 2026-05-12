from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.inference.registry import ChatProvider, Message
    from core.memory.long_term import LongTermStore

_CHARS_PER_TOKEN = 4


@dataclass
class ToolResult:
    tool_name: str
    result: str
    success: bool


@dataclass
class ShortTermMemory:
    active_messages: list[Message]
    last_tool_results: list[ToolResult]
    current_instructions: str
    temporal_goals: list[str]


class ShortTermStore:
    def __init__(self, max_messages: int = 30) -> None:
        self._max_messages = max_messages
        self._messages: list[Message] = []
        self._tool_results: list[ToolResult] = []
        self._current_instructions: str = ""
        self._temporal_goals: list[str] = []

    def push_message(self, msg: Message) -> None:
        self._messages.append(msg)
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages :]

    def push_tool_result(self, result: ToolResult) -> None:
        self._tool_results.append(result)

    def set_instructions(self, instructions: str) -> None:
        self._current_instructions = instructions

    def add_goal(self, goal: str) -> None:
        self._temporal_goals.append(goal)

    def get_context(self) -> ShortTermMemory:
        return ShortTermMemory(
            active_messages=list(self._messages),
            last_tool_results=list(self._tool_results),
            current_instructions=self._current_instructions,
            temporal_goals=list(self._temporal_goals),
        )

    def clear(self) -> None:
        self._messages = []
        self._tool_results = []
        self._current_instructions = ""
        self._temporal_goals = []

    def _token_count(self) -> int:
        return sum(len(m["content"]) // _CHARS_PER_TOKEN for m in self._messages)

    async def distill_if_needed(self, provider: ChatProvider, ctx_size: int) -> bool:
        """Summarize and collapse messages when token usage exceeds 75% of ctx_size.

        Returns True if distillation was performed.
        """
        if self._token_count() < (ctx_size * 3 // 4):
            return False
        summary = await self.to_summary(provider)
        self._messages = [{"role": "system", "content": f"[Contexto previo resumido]: {summary}"}]
        return True

    async def slide_to_long_term(self, long_term: LongTermStore, keep_last_n: int = 10) -> int:
        """Archive oldest messages to long-term vector store, keep last N in memory.

        Returns the number of messages archived.
        """
        if len(self._messages) <= keep_last_n:
            return 0
        to_archive = self._messages[:-keep_last_n]
        self._messages = self._messages[-keep_last_n:]
        text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in to_archive)
        await long_term.store_episode(text, tags=["session", "archived"])
        return len(to_archive)

    async def to_summary(self, provider: ChatProvider) -> str:
        if not self._messages:
            return ""

        conversation_text = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}" for msg in self._messages
        )

        summary_prompt: list[Message] = [
            {
                "role": "system",
                "content": (
                    "Eres un asistente que crea resúmenes concisos de conversaciones. "
                    "El resumen debe capturar los puntos clave, decisiones y contexto importante "
                    "en menos de 500 tokens."
                ),
            },
            {
                "role": "user",
                "content": f"Resume esta conversación de forma concisa:\n\n{conversation_text}",
            },
        ]

        return await provider.complete(summary_prompt)

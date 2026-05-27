"""Dedicated router for deterministic fast-path selection.

Keeps the selection order in one place so AgentRuntime can focus on applying
the already-chosen fast-path result.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from loguru import logger

from core.agents.calendar_fast_path import try_calendar_fast_path
from core.agents.file_content_generator import generate_file_content
from core.agents.file_search_fast_path import try_file_search_fast_path
from core.agents.file_write_calendar_fusion import (
    is_calendar_backed_file_content,
    try_file_write_calendar_fusion,
)
from core.agents.file_write_fast_path import FileWriteIntent, try_file_write_fast_path
from core.agents.math_fast_path import try_pure_math_fast_path
from core.agents.reminder_intent_resolver import (
    extract_reminder_intent,
    heuristic_parse_reminder,
    is_reminder_write_query,
    resolve_reminder_intent,
)
from core.agents.state_store import AgentState
from core.i18n.messages import _L
from core.inference.registry import ProviderRegistry, TaskHint

FastPathKind = Literal["math", "file_write", "reminder", "calendar_read", "file_search"]


@dataclass(frozen=True)
class FastPathResult:
    kind: FastPathKind
    answer: str | None = None
    file_write_intent: FileWriteIntent | None = None
    pending_tool_name: str | None = None
    pending_tool_args: dict[str, Any] | None = None
    warnings: tuple[str, ...] = ()


class FastPathRouter:
    """Resolve the first applicable deterministic fast path."""

    def __init__(
        self,
        registry: ProviderRegistry,
        tool_registry: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        self._registry = registry
        self._tool_registry = tool_registry or {}

    async def try_all(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        """Return the first matching fast-path result, in the canonical order."""
        result = self._try_math(query, agent_state)
        if result is not None:
            return result

        result = await self._try_file_write(query, agent_state)
        if result is not None:
            return result

        result = await self._try_reminder(query, agent_state)
        if result is not None:
            return result

        result = self._try_calendar(query, agent_state)
        if result is not None:
            return result

        return self._try_file_search(query, agent_state)

    def _authorized_tools(self, agent_state: AgentState) -> list[str]:
        return list(agent_state.profile.authorized_tools or [])

    def _tools_for_file_write(self, agent_state: AgentState) -> list[str]:
        tools = self._authorized_tools(agent_state)
        if (
            self._tool_registry
            and "write_file" in self._tool_registry
            and "write_file" not in tools
        ):
            tools.append("write_file")
        return tools

    def _try_math(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        answer = try_pure_math_fast_path(query, self._authorized_tools(agent_state))
        if answer is None:
            return None
        return FastPathResult(kind="math", answer=answer)

    async def _try_file_write(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        if self._tool_registry and "write_file" not in self._tool_registry:
            return None

        tools = self._tools_for_file_write(agent_state)
        fused = try_file_write_calendar_fusion(query, tools)
        if fused is not None:
            return FastPathResult(
                kind="file_write",
                file_write_intent=fused,
                warnings=("file_write_calendar_fusion",),
            )

        intent = try_file_write_fast_path(query, tools, write_roots=None)
        if intent is None:
            return None

        blob = (getattr(intent, "content_spec", None) or intent.content or "").strip()
        if is_calendar_backed_file_content(blob):
            logger.warning(
                "calendar file-export fusion failed; refusing literal description as file body"
            )
            return None

        content_source = getattr(intent, "content_source", "literal")
        if content_source != "spec":
            return FastPathResult(kind="file_write", file_write_intent=intent)

        provider_name = self._registry.select_for_task(TaskHint.CHAT)
        chat = self._registry.get_chat(provider_name)
        try:
            generated = await generate_file_content(
                user_query=query,
                filename=intent.filename,
                content_spec=getattr(intent, "content_spec", None) or intent.content,
                chat=chat,
            )
        except Exception as exc:
            logger.warning("file content generation failed: {}", exc)
            return None

        return FastPathResult(
            kind="file_write",
            file_write_intent=intent.with_content(generated, source="literal"),
            warnings=("file_write_content_generated",),
        )

    async def _try_reminder(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        authorized = self._authorized_tools(agent_state)
        write_tools = {"add_reminder", "delete_reminder"}
        if authorized and not set(authorized) & write_tools:
            return None
        if not is_reminder_write_query(query):
            return None

        provider_name = self._registry.select_for_task(TaskHint.CHAT)
        chat = self._registry.get_chat(provider_name)
        from core.agents.runtime import _now_human

        temporal = _now_human()
        llm_intent = None
        try:
            llm_intent = await extract_reminder_intent(
                query, chat, current_date=temporal["current_date"]
            )
        except Exception as exc:
            logger.warning("reminder LLM extract failed: {}", exc)

        intent = resolve_reminder_intent(query, llm_intent=llm_intent)
        if intent is None:
            intent = heuristic_parse_reminder(query)
        if intent is None or intent.action == "none":
            return None

        if intent.action == "add":
            if authorized and "add_reminder" not in authorized:
                return None
            tool_name = "add_reminder"
            tool_args: dict[str, Any] = {
                "title": intent.title,
                "datetime_str": intent.datetime_str,
            }
        elif intent.action == "delete":
            if authorized and "delete_reminder" not in authorized:
                return None
            tool_name = "delete_reminder"
            tool_args = {"title": intent.title}
            if intent.datetime_str:
                tool_args["datetime_str"] = intent.datetime_str
        else:
            return None

        answer = _L("confirm.tool_pause", tool_name=tool_name)
        answer += f"\n\n**{intent.title}**"
        if intent.datetime_str and intent.action == "add":
            answer += f"\nCuándo: {intent.datetime_str}"
        elif intent.datetime_str and intent.action == "delete":
            answer += f"\nDía: {intent.datetime_str}"

        return FastPathResult(
            kind="reminder",
            answer=answer,
            pending_tool_name=tool_name,
            pending_tool_args=tool_args,
            warnings=("reminder_llm_intent",),
        )

    def _try_calendar(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        answer = try_calendar_fast_path(query, self._authorized_tools(agent_state))
        if answer is None:
            return None
        return FastPathResult(kind="calendar_read", answer=answer)

    def _try_file_search(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        answer = try_file_search_fast_path(query, self._authorized_tools(agent_state))
        if answer is None:
            return None
        return FastPathResult(kind="file_search", answer=answer)

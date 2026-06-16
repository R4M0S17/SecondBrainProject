"""Dedicated router for deterministic fast-path selection.

Keeps the selection order in one place so AgentRuntime can focus on applying
the already-chosen fast-path result.

Canonical order: Time/Date → Config Read → URL Open → Math → File write → Reminder → Calendar read → Calendar write → File search
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from loguru import logger

from core.agents.calendar_fast_path import try_calendar_fast_path
from core.agents.dictionary_fast_path import try_dictionary_fast_path
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
from core.agents.system_info_fast_path import try_system_info_fast_path
from core.agents.unit_conversion_fast_path import try_unit_conversion_fast_path
from core.agents.weather_fast_path import try_weather_fast_path
from core.i18n.messages import _L
from core.inference.registry import ProviderRegistry, TaskHint

_WEEKDAYS_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
_MONTHS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

FastPathKind = Literal[
    "math",
    "file_write",
    "reminder",
    "calendar_read",
    "file_search",
    "time_date",
    "config_read",
    "calendar_write",
    "url_open",
    "web_search",
    "weather",
    "dictionary",
    "unit_conversion",
    "system_info",
]


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
        config_getter: Callable[[], dict[str, Any]] | None = None,
        authorized_read_paths_getter: Callable[[], list[str]] | None = None,
    ) -> None:
        self._registry = registry
        self._tool_registry = tool_registry or {}
        self._config_getter = config_getter
        self._authorized_read_paths_getter = authorized_read_paths_getter

    async def try_all(
        self, query: str, agent_state: AgentState, intent: str | None = None
    ) -> FastPathResult | None:
        """Return the first matching fast-path result, in the canonical order.

        Args:
            query: The user query.
            agent_state: Current agent state.
            intent: Optional intent classification hint (CONFIG, AGENT_ACTION, RAG_QUERY, DIRECT_ACTION).
                   When provided, incompatible routes are skipped as an optimization.
        """
        if intent == "RAG_QUERY":
            return self._try_file_search(query, agent_state)

        if intent == "AGENT_ACTION":
            result = self._try_url_open(query, agent_state)
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
            result = self._try_calendar_write(query, agent_state)
            if result is not None:
                return result
            return self._try_file_search(query, agent_state)

        if intent == "CONFIG":
            return self._try_config_read(query, agent_state)

        result = self._try_time_date(query, agent_state)
        if result is not None:
            return result

        result = self._try_weather(query, agent_state)
        if result is not None:
            return result

        result = self._try_dictionary(query, agent_state)
        if result is not None:
            return result

        result = self._try_config_read(query, agent_state)
        if result is not None:
            return result

        result = self._try_system_info(query, agent_state)
        if result is not None:
            return result

        result = self._try_url_open(query, agent_state)
        if result is not None:
            return result

        result = await self._try_web_search(query, agent_state)
        if result is not None:
            return result

        result = self._try_math(query, agent_state)
        if result is not None:
            return result

        result = self._try_unit_conversion(query, agent_state)
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

        result = self._try_calendar_write(query, agent_state)
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

    def _try_time_date(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        _ = agent_state
        q = query.lower().strip()
        if not re.search(
            r"^(what('s| is)( the)?|tell me the|do you know the)\s*(current\s+)?"
            r"(time|date|day|month|year|hour)\b",
            q,
        ):
            return None
        if re.search(r"\b(time to|it's time|about time)\b", q):
            return None
        now = datetime.now().astimezone()
        date_str = (
            f"{_WEEKDAYS_EN[now.weekday()]}, {_MONTHS_EN[now.month - 1]} {now.day}, {now.year}"
        )
        time_12h = now.strftime("%I:%M %p").lstrip("0")
        tz = now.strftime("%Z") or (now.tzname() or "UTC")
        answer = f"{date_str} — {time_12h} {tz}"
        return FastPathResult(kind="time_date", answer=answer)

    def _try_config_read(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        if self._config_getter is None:
            return None
        q = query.lower().strip()
        if not re.search(
            r"\b(what('s| is)( my)?|show|current|which)\s*(config|model|backend|setting|provider)\b",
            q,
        ):
            return None
        if re.search(r"\b(change|set|update|modify)\b", q):
            return None
        cfg = self._config_getter()
        lines = ["**Current Configuration:**"]
        for key in ("model", "inference_backend", "provider", "embedding_model"):
            val = cfg.get(key)
            if val is not None:
                lines.append(f"- **{key}**: {val}")
        if "model" not in cfg and "inference" in cfg:
            for key in ("model", "base_url"):
                val = cfg.get("inference", {}).get(key)
                if val is not None and str(val).strip():
                    lines.append(f"- **inference.{key}**: {val}")
        memory_vals = []
        for key in (
            "short_term_max_messages",
            "long_term_episode_limit",
            "embedding_cache_ttl_days",
        ):
            val = cfg.get(key) or cfg.get("memory", {}).get(key)
            if val is not None:
                memory_vals.append(f"{key}={val}")
        if memory_vals:
            lines.append(f"- **memory**: {', '.join(memory_vals)}")
        return FastPathResult(kind="config_read", answer="\n".join(lines))

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

    def _try_calendar_write(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        authorized = self._authorized_tools(agent_state)
        if authorized and "create_calendar_event" not in authorized:
            return None

        q = query.lower().strip()
        if not re.search(
            r"\b(schedule|create\s+event|add\s+meeting|book\s+appointment|"
            r"set\s+up\s+a\s+call|plan\s+meeting|organize\s+meeting)\b",
            q,
        ):
            return None
        if not re.search(
            r"\b(today|tomorrow|next|this|at\s|a las|\d{1,2}(:|\.)\d{2}|"
            r"noon|midnight|morning|afternoon|evening|tonight|"
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            q,
        ):
            return None
        if re.search(
            r"\b(schedule|create|add|book|plan|organize)\s+(something|a|an)\s*"
            r"(meeting|event|appointment|call)?\s*(soon|later|someday|eventually)?$",
            q,
        ):
            return None

        raw_title = re.sub(
            r"^(schedule|create|add|book|set up|plan|organize)\s+(a|an|the|one)?\s*",
            "",
            query,
            flags=re.IGNORECASE,
        ).strip()
        title = re.split(
            r"\s+(today|tomorrow|next\s+\w+|this\s+\w+|on\s+\w+|at\s+|a las)",
            raw_title,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
        title = re.sub(
            r"^(meeting|event|appointment|call)\s+", "", title, flags=re.IGNORECASE
        ).strip()
        if not title or len(title) < 2:
            title = "Evento"

        description = ""
        with_match = re.search(r"\bwith\s+(\w[\w\s]*)", query, re.IGNORECASE)
        if with_match:
            description = f"Con {with_match.group(1).strip()}"

        answer = _L("confirm.tool_pause", tool_name="create_calendar_event")
        answer += f"\n\n**{title}**"
        if description:
            answer += f"\n{description}"

        return FastPathResult(
            kind="calendar_write",
            answer=answer,
            pending_tool_name="create_calendar_event",
            pending_tool_args={
                "title": title,
                "datetime_str": query,
                "duration_mins": 60,
                "description": description,
            },
            warnings=("calendar_write_fast_path",),
        )

    def _try_url_open(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        _ = agent_state
        q = query.lower().strip()
        url_match = re.search(r"https?://[^\s]+", q)
        if not url_match:
            return None
        if not re.search(r"^(open|go to|navigate to|visit|launch|show me)\b", q):
            return None
        url = url_match.group(0)
        return FastPathResult(
            kind="url_open",
            answer=url,
        )

    # ── Exclusion patterns: queries that should NOT trigger web search ──
    _WEB_EXCLUDE_CALENDAR_RE = re.compile(r"\b(calendario|agenda|recordatorio)\b", re.IGNORECASE)
    # Queries with calendar entity words (reunión, cita, evento) in personal context
    _WEB_CALENDAR_ENTITY_RE = re.compile(
        r"\b(reuni[oó]n(es)?|cita(s)?|evento(s)?)\b", re.IGNORECASE
    )
    _WEB_CALENDAR_CONTEXT_RE = re.compile(
        r"\b(mi|my|tengo|have|pr[oó]xim[oa](s)?|next|programad[oa]|scheduled)\b",
        re.IGNORECASE,
    )
    _WEB_EXCLUDE_FILE_RE = re.compile(r"\b(archivo|fichero|documento)\b", re.IGNORECASE)

    # ── Explicit search intent (highest confidence — always triggers web search) ──
    _WEB_SEARCH_EXPLICIT_RE = re.compile(
        r"\b(search|web\s*search|look\s+up|find\s+out|"
        r"busca(r)?\s+en\s+(la\s+)?(web|internet)|"
        r"b[uú]scame|b[uú]squeda\s+en\s+la\s+web)\b",
        re.IGNORECASE,
    )

    # ── News / current events (always triggers web search) ──
    _WEB_NEWS_RE = re.compile(
        r"\b(noticias?|news|actualidad|"
        r"últimas?\s+(noticias|hora|actualidad)|"
        r"latest\s+(news|headlines|updates)|"
        r"current\s+(events?|news|affairs|situation)|"
        r"qu[eé]\s+(pas[oó]|ocurri[oó]|hay\s+de\s+nuevo|est[aá]"
        r"\s+pasando|suced[ioó])|"
        r"what'?s\s+(new|happening|going\s+on)|"
        r"breaking\s+news|headlines)\b",
        re.IGNORECASE,
    )

    # ── Weather (always triggers web search) ──
    _WEB_WEATHER_RE = re.compile(
        r"\b(weather|climate|clima|temperatura|"
        r"pron[oó]stico\s+(del\s+)?tiempo|"
        r"c[oó]mo\s+est[aá]\s+el\s+(clima|tiempo|weather)|"
        r"qu[eé]\s+tal\s+(el\s+)?(clima|tiempo|weather))\b",
        re.IGNORECASE,
    )

    async def _try_web_search(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        """Web search fast path with hybrid classification + follow-up summary.

        Flow:
        1. Check if query is a follow-up requesting summary of previous web search
        2. Check explicit triggers (busca en la web, news, weather) → immediate search
        3. Check exclusions (calendar, files, math) → skip
        4. Use LLM classifier for informational queries → search if yes
        5. Store result in working_memory for potential follow-up
        """
        from core.agents.web_search_classifier import (
            classify_needs_web_search,
            is_follow_up_query,
        )

        # Check frontend toggle — only allow web_search when explicitly enabled
        if self._config_getter is not None:
            config = self._config_getter()
            web_search_enabled = config.get("tool_permissions", {}).get("search_web", False)
            if not web_search_enabled:
                return None

        authorized = self._authorized_tools(agent_state)
        if "web_search" not in authorized:
            return None

        q = query.strip()
        if not q:
            return None
        q_lower = q.lower()

        # ── 1. Follow-up detection: summarize previous web search result ──
        if is_follow_up_query(q):
            last_result = agent_state.working_memory.get("last_web_search_result")
            if last_result:
                # Return a special result that signals the runtime to summarize
                return FastPathResult(
                    kind="web_search",
                    answer=None,  # Will be filled by runtime with LLM summary
                    warnings=("web_search_follow_up",),
                )
            # No previous result — fall through to normal search

        # ── 2. Explicit triggers (always match) ──
        explicit_match = (
            self._WEB_SEARCH_EXPLICIT_RE.search(q_lower)
            or self._WEB_NEWS_RE.search(q_lower)
            or self._WEB_WEATHER_RE.search(q_lower)
        )

        # ── 3. Exclusions (skip if matched, unless explicit trigger) ──
        if not explicit_match:
            if self._WEB_EXCLUDE_CALENDAR_RE.search(q_lower):
                return None
            if self._WEB_CALENDAR_ENTITY_RE.search(
                q_lower
            ) and self._WEB_CALENDAR_CONTEXT_RE.search(q_lower):
                return None
            if self._WEB_EXCLUDE_FILE_RE.search(q_lower):
                return None
            if re.search(r"\d+\s*[+\-*×x/]\s*\d+", q_lower):
                return None

            # ── 4. LLM classifier for informational queries ──
            needs_search = await classify_needs_web_search(q, self._registry)
            if not needs_search:
                return None

        # ── 5. Execute web search ──
        try:
            from core.tools.handlers.web import web_search

            result = web_search(q)
        except Exception as exc:
            logger.warning("web_search fast path failed: {}", exc)
            return None

        # Store result in working_memory for potential follow-up
        # (This will be persisted by the runtime when applying the result)
        agent_state.working_memory["last_web_search_result"] = result
        agent_state.working_memory["last_web_search_query"] = q

        return FastPathResult(
            kind="web_search",
            answer=result,
        )

    def _try_weather(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        _ = agent_state
        answer = try_weather_fast_path(query)
        if answer is None:
            return None
        return FastPathResult(kind="weather", answer=answer)

    def _try_dictionary(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        _ = agent_state
        answer = try_dictionary_fast_path(query)
        if answer is None:
            return None
        return FastPathResult(kind="dictionary", answer=answer)

    def _try_system_info(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        _ = agent_state
        answer = try_system_info_fast_path(query)
        if answer is None:
            return None
        return FastPathResult(kind="system_info", answer=answer)

    def _try_unit_conversion(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        _ = agent_state
        answer = try_unit_conversion_fast_path(query)
        if answer is None:
            return None
        return FastPathResult(kind="unit_conversion", answer=answer)

    def _try_file_search(self, query: str, agent_state: AgentState) -> FastPathResult | None:
        paths = self._authorized_read_paths_getter() if self._authorized_read_paths_getter else None
        answer = try_file_search_fast_path(
            query, self._authorized_tools(agent_state), authorized_paths=paths
        )
        if answer is None:
            return None
        return FastPathResult(kind="file_search", answer=answer)

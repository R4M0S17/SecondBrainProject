from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import time
import uuid as _uuid
from collections.abc import AsyncIterable, AsyncIterator, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypedDict, cast

from langgraph.graph import END, StateGraph
from loguru import logger

from core.agents.calendar_fast_path import try_calendar_fast_path
from core.agents.conversation_store import ConversationStore
from core.agents.fast_path_router import FastPathResult, FastPathRouter
from core.agents.file_content_generator import generate_file_content
from core.agents.file_search_fast_path import try_file_search_fast_path
from core.agents.file_write_calendar_fusion import (
    is_calendar_backed_file_content,
    try_file_write_calendar_fusion,
)
from core.agents.file_write_fast_path import FileWriteIntent, try_file_write_fast_path
from core.agents.llm_parse_utils import extract_json_object, repair_tool_json, strip_markdown_fences
from core.agents.math_fast_path import try_pure_math_fast_path
from core.agents.reminder_intent_resolver import (
    ReminderIntent,
    extract_reminder_intent,
    heuristic_parse_reminder,
    is_reminder_write_query,
    resolve_reminder_intent,
)
from core.agents.session_policy import (
    apply_conversation_to_agent_state,
    hydrate_short_term,
    persist_session_summary,
)
from core.agents.state_store import (
    AgentState,
    AgentStateStore,
    ToolCall,
    _state_from_dict,
    _state_to_dict,
)
from core.i18n.messages import _L
from core.inference.agent_answer_stream import AgentAnswerStreamParser
from core.inference.agent_grammar import build_agent_response_grammar
from core.inference.inference_warnings import (
    append_inference_warnings,
    mark_skip_context_enricher,
    should_skip_context_enricher,
)
from core.inference.prompt_cache import sync_prompt_cache
from core.inference.registry import Message, ProviderRegistry
from core.memory.context_builder import AssembledContext, ContextBuilder
from core.observability.ram_monitor import refresh_ram_pressure
from core.observability.time_travel import TimeTravelRecorder
from core.reflection.reflector import Reflector
from core.tools.handlers.filesystem import PathNotAuthorizedError
from core.tools.registry import ToolDefinition

if TYPE_CHECKING:
    from core.agents.context_enricher import ContextEnricher

# --------------------------------------------------------------------------- #
# Hard limits (from spec)
# --------------------------------------------------------------------------- #
MAX_ITERATIONS = 10
MAX_TOOL_CALLS = 5
TIMEOUT_SECONDS = 120

# Tools that must pause execution and wait for explicit user approval.
#
# Two layers:
#   * ``CONFIRMATION_REQUIRED_TOOLS`` — hard fallback when a tool is dispatched
#     by name but is not present in ``tool_definitions`` (defence-in-depth).
#   * ``AgentRuntime._requires_confirmation`` — authoritative check that consults
#     the ``ToolDefinition.requires_confirmation`` flag from the registry.
#
# The two MUST stay aligned: any tool whose ``requires_confirmation=True`` is
# treated as confirmation-required, regardless of whether its name is in the
# fallback set. This unifies the runtime pause with PolicyEngine validation.
CONFIRMATION_REQUIRED_TOOLS: frozenset[str] = frozenset(
    {
        "write_file",
        "execute_python",
        "delete_file",
        "run_script",
        "create_calendar_event",
        "add_reminder",
    }
)

# --------------------------------------------------------------------------- #
# LangGraph state (plain dict — no checkpointing needed for local runtime)
# --------------------------------------------------------------------------- #


class _RunState(TypedDict):
    agent_state: dict  # serialized AgentState
    query: str
    context: dict | None  # serialized AssembledContext
    messages: list[dict]  # Message dicts for the LLM
    iterations: int
    tool_calls_count: int
    final_answer: str | None
    next_tool_name: str | None
    next_tool_args: dict | None
    seen_tool_calls: list[str]  # dedup key = "tool_name:args_json"
    needs_confirmation: bool
    pending_tool_name: str | None
    pending_tool_args: dict | None
    ambient_context: str  # A8 proactive context injection
    image_attachments: list[dict] | None  # [{filename, mime_type, content(base64)}]


# --------------------------------------------------------------------------- #
# Prompt builder
# --------------------------------------------------------------------------- #

_SYSTEM_TEMPLATE = """\
Eres {agent_name}, un agente de IA personal local.
{instructions}

FECHA Y HORA ACTUAL: {current_date} — AÑO ACTUAL: {current_year}

REGLA TEMPORAL: La línea FECHA Y HORA ACTUAL contiene la verdad del momento
presente. Si el usuario pregunta por la fecha, hora, día o año, responde
SIEMPRE con esos valores. NUNCA respondas con una fecha de tu entrenamiento.

HISTORIAL COMPRIMIDO DE SESIÓN:
{session_summary}

MEMORIA RECUPERADA:
{memory_context}

{ambient_context}

INSTRUCCIONES DE RESPUESTA:
Responde SIEMPRE en JSON válido con exactamente uno de estos formatos:

Si necesitas usar una herramienta:
{{"action": "tool", "tool": "<nombre>", "args": {{<argumentos>}}}}

Si puedes responder directamente:
{{"action": "answer", "answer": "<respuesta completa y detallada en el idioma del usuario>"}}

REGLA CRÍTICA SOBRE RESULTADOS DE HERRAMIENTAS:
Cuando veas un mensaje que empiece con "Observación de herramienta:", el resultado es REAL y ya fue ejecutado.
- Si dice "Sin eventos", responde que no hay eventos. No inventes errores.
- NUNCA digas que una herramienta "no está disponible" si ya recibiste su resultado.
- Usa el resultado directamente para responder al usuario.

HERRAMIENTAS DISPONIBLES:
{available_tools_detail}
Si no necesitas herramientas, usa el formato "answer" directamente.\
"""

_STREAM_SYSTEM_TEMPLATE = """\
Eres {agent_name}, un agente de IA personal local.
{instructions}

FECHA Y HORA ACTUAL: {current_date} — AÑO ACTUAL: {current_year}

REGLA TEMPORAL: La línea FECHA Y HORA ACTUAL contiene la verdad del momento
presente. Si el usuario pregunta por la fecha, hora, día o año, responde
SIEMPRE con esos valores. NUNCA respondas con una fecha de tu entrenamiento.

HISTORIAL COMPRIMIDO DE SESIÓN:
{session_summary}

MEMORIA RECUPERADA:
{memory_context}

{ambient_context}

Responde de forma natural y directa en texto plano. No uses JSON ni ningún formato especial.
NO crees archivos a menos que el usuario explícitamente pida crear, escribir o guardar un archivo. Si pide código o contenido, muéstralo directamente en el chat.\
"""

# English weekday/month names — avoids LC_TIME locale drift on small models.
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


def _now_human(now: datetime | None = None) -> dict[str, str]:
    """Locale-independent current date/time fields for prompts (single source of truth)."""
    dt = now if now is not None else datetime.now().astimezone()
    date = f"{_WEEKDAYS_EN[dt.weekday()]}, {_MONTHS_EN[dt.month - 1]} {dt.day}, {dt.year}"
    time_24h = dt.strftime("%H:%M")
    time_12h = dt.strftime("%I:%M %p")
    tz = dt.strftime("%Z") or (dt.tzname() or "UTC")
    current_date = f"{date} — {time_12h} ({time_24h}) {tz}"
    return {
        "date": date,
        "time_12h": time_12h,
        "time_24h": time_24h,
        "tz": tz,
        "year": str(dt.year),
        "current_date": current_date,
    }


def _date_preamble() -> str:
    """One-line dateline for the LLM user turn only (not persisted in the UI log)."""
    t = _now_human()
    return (
        "[System context: Today is "
        f"{t['date']}. Current time is {t['time_12h']} ({t['time_24h']}) {t['tz']}. "
        "If the user asks for the date or time, repeat this exact time — do not invent another.] "
    )


def _reminder_write_prompt_extra(query: str, tool_defs: list[ToolDefinition]) -> str:
    names = {td.name for td in tool_defs}
    if "add_reminder" not in names or not is_reminder_write_query(query):
        return ""
    return (
        "\n\nRECORDATORIO (petición detectada):\n"
        "El usuario quiere crear o borrar un recordatorio en Calendario (evento corto, no app Recordatorios).\n"
        "Para CREAR usa add_reminder con JSON exacto:\n"
        '{"action": "tool", "tool": "add_reminder", "args": {"title": "<nombre>", '
        '"datetime_str": "<día y hora en lenguaje natural, ej. mañana a las 3pm>"}}\n'
        "Para BORRAR usa delete_reminder con title exacto y datetime_str si menciona el día (ej. mañana).\n"
        "datetime_str debe incluir día Y hora. No inventes fechas: usa la petición del usuario.\n"
    )


def _normalize_tool_args(tool_name: str | None, args: dict) -> dict:
    if not tool_name or not args:
        return args
    out = dict(args)
    if tool_name == "add_reminder":
        alias_map = {
            "name": "title",
            "nombre": "title",
            "titulo": "title",
            "título": "title",
            "when": "datetime_str",
            "fecha": "datetime_str",
            "date": "datetime_str",
            "time": "datetime_str",
            "hora": "datetime_str",
            "datetime": "datetime_str",
        }
        for src, dst in alias_map.items():
            if src in out and dst not in out:
                out[dst] = out.pop(src)
    elif tool_name == "delete_reminder":
        for src in ("name", "nombre", "titulo", "título"):
            if src in out and "title" not in out:
                out["title"] = out.pop(src)
        for src in ("when", "fecha", "date", "day", "día"):
            if src in out and "datetime_str" not in out:
                out["datetime_str"] = out.pop(src)
    return out


def _build_system_prompt(
    agent_state: AgentState,
    context: AssembledContext,
    tool_defs: list[ToolDefinition],
    ambient_context: str = "",
    query: str = "",
) -> str:
    memory_lines = [f"- {c.content[:200]}" for c in context.retrieved_memory]
    memory_context = "\n".join(memory_lines) if memory_lines else "(sin episodios previos)"
    instructions = agent_state.profile.preferences.get("instructions", "")
    instructions += _reminder_write_prompt_extra(query, tool_defs)

    if tool_defs:
        detail_lines = []
        for td in tool_defs:
            if td.parameters:
                params = ", ".join(f"{k}: {v}" for k, v in td.parameters.items())
            else:
                params = "sin argumentos"
            detail_lines.append(f"- {td.name}({params}): {td.description}")
        tools_detail = "\n".join(detail_lines)
        # Add clarification about write_file usage
        if any(td.name == "write_file" for td in tool_defs):
            tools_detail += (
                "\n\nNOTA IMPORTANTE SOBRE write_file: SOLO usa write_file cuando el usuario "
                "explícitamente pida crear, escribir o guardar un archivo. Si el usuario solo "
                "pide código, explicación o contenido, respóndelo directamente en el chat SIN "
                "usar write_file."
            )
    else:
        tools_detail = "ninguna"

    temporal = _now_human()
    return _SYSTEM_TEMPLATE.format(
        agent_name=agent_state.profile.name,
        instructions=instructions,
        current_date=temporal["current_date"],
        current_year=temporal["year"],
        session_summary=agent_state.session_summary or "(sesión nueva)",
        memory_context=memory_context,
        ambient_context=ambient_context,
        available_tools_detail=tools_detail,
    )


def _build_stream_system_prompt(
    agent_state: AgentState, context: AssembledContext, ambient_context: str = ""
) -> str:
    memory_lines = [f"- {c.content[:200]}" for c in context.retrieved_memory]
    memory_context = "\n".join(memory_lines) if memory_lines else "(sin episodios previos)"
    instructions = agent_state.profile.preferences.get("instructions", "")
    temporal = _now_human()
    return _STREAM_SYSTEM_TEMPLATE.format(
        agent_name=agent_state.profile.name,
        instructions=instructions,
        current_date=temporal["current_date"],
        current_year=temporal["year"],
        session_summary=agent_state.session_summary or "(sesión nueva)",
        memory_context=memory_context,
        ambient_context=ambient_context,
    )


def _strip_markdown_fences(text: str) -> str:
    return strip_markdown_fences(text)


def _extract_json_object(text: str) -> str | None:
    return extract_json_object(text)


def _repair_tool_json(text: str) -> str:
    return repair_tool_json(text)


def _looks_like_failed_json(text: str) -> bool:
    candidate = text.strip()
    if candidate.startswith(("{", "```")):
        return True
    return '"action"' in candidate or "'action'" in candidate


def _parse_fallback_answer() -> dict[str, str]:
    return {"answer": _L("parse.llm_fallback")}


def _parse_llm_response(
    raw: str,
    known_tools: frozenset[str] | None = None,
) -> tuple[str, str | None, dict]:
    """Return (action, tool_name, args). action is 'answer' or 'tool'.

    Handles:
    - Qwen3 <think>…</think> blocks before the JSON
    - Markdown code fences
    - JSON embedded in surrounding prose
    - Non-standard format where action field holds the tool name directly:
        {"action": "get_upcoming_events", "hours_ahead": 24}
    """
    original = raw.strip()
    text = re.sub(r"<think>.*?</think>", "", original, flags=re.DOTALL).strip()
    text = _strip_markdown_fences(text)

    json_text = _extract_json_object(text)
    if json_text is None:
        if _looks_like_failed_json(text):
            logger.warning("LLM response looked like JSON but no object found: {}", text[:500])
            return "answer", None, _parse_fallback_answer()
        return "answer", None, {"answer": text}

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        repaired = repair_tool_json(json_text)
        try:
            data = json.loads(repaired)
            logger.debug("LLM JSON repaired successfully")
        except json.JSONDecodeError:
            logger.warning("LLM JSON parse failed: {}", text[:500])
            return "answer", None, _parse_fallback_answer()

    if not isinstance(data, dict):
        logger.warning("LLM JSON root is not an object: {}", type(data).__name__)
        return "answer", None, _parse_fallback_answer()

    action = data.get("action", "answer")

    if action == "tool":
        tool_name = data.get("tool")
        if not tool_name or not isinstance(tool_name, str):
            logger.warning("LLM tool response missing tool name: {}", data)
            return "answer", None, _parse_fallback_answer()
        if known_tools is not None and tool_name not in known_tools:
            logger.warning("LLM referenced unknown tool '{}'", tool_name)
            return "answer", None, {"answer": _L("parse.tool_unknown", tool_name=tool_name)}
        args = data.get("args", {})
        if not isinstance(args, dict):
            args = {}
        return "tool", tool_name, args

    if action == "answer":
        answer_text = _stringify_answer(data.get("answer", ""))
        if not answer_text.strip():
            logger.warning("LLM answer action with empty answer field")
            return "answer", None, _parse_fallback_answer()
        return "answer", None, {"answer": answer_text}

    # Shortcut: small models put the tool name directly in "action".
    if known_tools is not None and action not in known_tools:
        logger.warning("LLM action shortcut '{}' is not a registered tool", action)
        return "answer", None, _parse_fallback_answer()

    shortcut_args = {k: v for k, v in data.items() if k != "action"}
    return "tool", str(action), shortcut_args


def _stringify_answer(value: object) -> str:
    """Render a model ``answer`` field as natural text regardless of JSON shape."""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```"):
            text = _strip_markdown_fences(text)
        return text
    if isinstance(value, list):
        return "\n".join(f"- {str(item).strip()}" for item in value if item is not None)
    if isinstance(value, dict):
        keys = list(value.keys())
        if keys == ["error"]:
            err = value["error"]
            return str(err)
        if set(keys) == {"error", "code"}:
            err = value.get("error", "")
            code = value.get("code")
            if code is not None and str(code) != "":
                return f"{err} ({code})"
            return str(err)
        return "\n".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def _chat_supports_grammar_stream(chat: object) -> bool:
    stream_fn = getattr(chat, "stream", None)
    if stream_fn is None:
        return False
    try:
        sig = inspect.signature(stream_fn)
    except (TypeError, ValueError):
        return False
    return "grammar" in sig.parameters


# --------------------------------------------------------------------------- #
# AgentRuntime
# --------------------------------------------------------------------------- #


def _context_to_preview(context: dict | None) -> str | None:
    """Extract a text preview from the assembled context dict."""
    if not context or not isinstance(context, dict):
        return None
    sources = context.get("sources_used") or []
    preview = ""
    if sources:
        preview += "Fuentes: " + ", ".join(str(s) for s in sources[:3])
    tokens = context.get("total_tokens_estimated")
    if tokens:
        preview += f" | ~{tokens} tokens" if preview else f"~{tokens} tokens"
    return preview or None


class StreamRunComplete:
    """Sentinel yielded after all answer tokens when ``run_streaming`` finishes."""

    __slots__ = ("answer", "final_state")

    def __init__(self, answer: str, final_state: AgentState) -> None:
        self.answer = answer
        self.final_state = final_state


class ContextSourcesEvent:
    """Yielded before the first token when context assembly found sources."""

    __slots__ = ("sources", "episode_count")

    def __init__(self, sources: list[str], episode_count: int) -> None:
        self.sources = sources
        self.episode_count = episode_count


class AgentRuntime:
    def __init__(
        self,
        registry: ProviderRegistry,
        state_store: AgentStateStore,
        context_builder: ContextBuilder,
        tool_registry: dict[str, Callable[..., Any]] | None = None,
        tool_definitions: dict[str, ToolDefinition] | None = None,
        enricher: ContextEnricher | None = None,
        conversation_store: ConversationStore | None = None,
        config_getter: Callable[[], dict[str, Any]] | None = None,
        time_travel_recorder: TimeTravelRecorder | None = None,
        reflector: Reflector | None = None,
    ) -> None:
        self._registry = registry
        self._state_store = state_store
        self._context_builder = context_builder
        self._tool_registry = tool_registry or {}
        self._tool_definitions = tool_definitions or {}
        self._enricher = enricher
        self._conv_store = conversation_store
        self._active_conversation_id: str | None = None
        self._config_getter = config_getter
        self._fast_path_router = FastPathRouter(
            self._registry, self._tool_registry, config_getter=config_getter
        )
        self._graph = self._build_graph()
        self._time_travel = time_travel_recorder
        self._reflector = reflector

    def prepare_conversation(self, conversation_id: str | None, agent_id: str) -> None:
        """Hydrate short-term history and per-conversation summary before a run."""
        self._active_conversation_id = conversation_id
        record = (
            self._conv_store.get(conversation_id) if conversation_id and self._conv_store else None
        )
        hydrate_short_term(self._context_builder._short_term, record)
        agent_state = self._state_store.load(agent_id)
        apply_conversation_to_agent_state(agent_state, record)
        self._state_store.save(agent_state)

    def save_conversation_session(
        self, conversation_id: str | None, agent_state: AgentState
    ) -> None:
        """Persist session summary onto the conversation record after a turn."""
        if not conversation_id or self._conv_store is None:
            return
        record = self._conv_store.get(conversation_id)
        if record is None:
            return
        persist_session_summary(record, agent_state)
        self._conv_store.update_session_summary(conversation_id, record.session_summary)

    def _web_search_enabled(self) -> bool:
        """Return True if web_search is enabled via frontend toggle."""
        if self._config_getter is None:
            return False
        config = self._config_getter()
        return config.get("tool_permissions", {}).get("search_web", False)

    def _authorized_tools_for_grammar(self, agent_state: AgentState) -> tuple[str, ...]:
        if agent_state.profile.authorized_tools:
            tools = tuple(sorted(agent_state.profile.authorized_tools))
        else:
            tools = tuple(sorted(self._tool_registry.keys()))
        if not self._web_search_enabled():
            return tuple(t for t in tools if t != "web_search")
        return tools

    def _finish_math_fast_path(
        self,
        query: str,
        conversation_id: str | None,
        answer: str,
        agent_state: AgentState,
    ) -> AgentState:
        """Persist a zero-token arithmetic answer and skip enricher for this request."""
        mark_skip_context_enricher()
        append_inference_warnings(["math_fast_path"])
        self._state_store.save(agent_state)
        short_term = self._context_builder._short_term
        short_term.push_message({"role": "user", "content": query})
        short_term.push_message({"role": "assistant", "content": answer})
        self.save_conversation_session(conversation_id, agent_state)
        return agent_state

    def _finish_calendar_fast_path(
        self,
        query: str,
        conversation_id: str | None,
        answer: str,
        agent_state: AgentState,
        *,
        warning: str = "calendar_fast_path",
    ) -> AgentState:
        """Persist a calendar tool answer without calling the LLM."""
        mark_skip_context_enricher()
        append_inference_warnings([warning])
        self._state_store.save(agent_state)
        short_term = self._context_builder._short_term
        short_term.push_message({"role": "user", "content": query})
        short_term.push_message({"role": "assistant", "content": answer})
        self.save_conversation_session(conversation_id, agent_state)
        return agent_state

    def _try_math_fast_path(self, query: str, agent_state: AgentState) -> str | None:
        return try_pure_math_fast_path(query, list(agent_state.profile.authorized_tools or []))

    def _tools_for_file_write(self, agent_state: AgentState) -> list[str]:
        """Agent tools plus write_file when registered (export-to-file fusion)."""
        tools = list(agent_state.profile.authorized_tools or [])
        if (
            self._tool_registry
            and "write_file" in self._tool_registry
            and "write_file" not in tools
        ):
            tools.append("write_file")
        return tools

    async def _resolve_file_write_intent(
        self, query: str, agent_state: AgentState
    ) -> FileWriteIntent | None:
        """Parse file-write intent; calendar fusion or LLM generation when needed."""
        if self._tool_registry and "write_file" not in self._tool_registry:
            return None
        tools = self._tools_for_file_write(agent_state)
        fused = try_file_write_calendar_fusion(query, tools)
        if fused is not None:
            append_inference_warnings(["file_write_calendar_fusion"])
            return fused

        intent = try_file_write_fast_path(query, tools, write_roots=None)
        if intent is not None:
            blob = (getattr(intent, "content_spec", None) or intent.content or "").strip()
            if is_calendar_backed_file_content(blob):
                logger.warning(
                    "calendar file-export fusion failed; refusing literal description as file body"
                )
                return None

        content_source = getattr(intent, "content_source", "literal") if intent else None
        if intent is None or content_source != "spec":
            return intent

        from core.inference.registry import TaskHint

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

        append_inference_warnings(["file_write_content_generated"])
        return intent.with_content(generated, source="literal")

    def _finish_file_write_fast_path(
        self,
        query: str,
        conversation_id: str | None,
        intent: FileWriteIntent,
        agent_state: AgentState,
    ) -> tuple[str, AgentState]:
        """Queue ``write_file`` for user confirmation without calling the LLM."""
        mark_skip_context_enricher()
        append_inference_warnings(["file_write_fast_path"])
        agent_state.pending_tool_name = "write_file"
        agent_state.pending_tool_args = {"path": intent.path, "content": intent.content}
        answer = _L("confirm.tool_pause", tool_name="write_file")
        if getattr(intent, "filled_from", "") == "calendar":
            generated_note = "\n(Contenido obtenido del calendario.)"
        elif getattr(intent, "generated", False):
            generated_note = "\n(Contenido generado a partir de tu descripción.)"
        else:
            generated_note = ""
        answer += (
            f"\n\nArchivo: `{intent.filename}`\n"
            f"Ruta: `{intent.path}`\n"
            f"Contenido ({len(intent.content)} caracteres): "
            f"{intent.content[:120]}{'…' if len(intent.content) > 120 else ''}"
            f"{generated_note}"
        )
        self._state_store.save(agent_state)
        short_term = self._context_builder._short_term
        short_term.push_message({"role": "user", "content": query})
        self.save_conversation_session(conversation_id, agent_state)
        return answer, agent_state

    def _try_calendar_fast_path(self, query: str, agent_state: AgentState) -> str | None:
        return try_calendar_fast_path(query, list(agent_state.profile.authorized_tools or []))

    async def _try_reminder_llm_resolve(
        self, query: str, agent_state: AgentState
    ) -> tuple[str, AgentState] | None:
        """Use a focused LLM call to extract reminder title/datetime from free-form text."""
        authorized = list(agent_state.profile.authorized_tools or [])
        write_tools = {"add_reminder", "delete_reminder"}
        if authorized and not set(authorized) & write_tools:
            return None
        if not is_reminder_write_query(query):
            return None

        from core.inference.registry import TaskHint

        provider_name = self._registry.select_for_task(TaskHint.CHAT)
        chat = self._registry.get_chat(provider_name)
        temporal = _now_human()
        llm_intent: ReminderIntent | None = None
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
            tool_args = {"title": intent.title, "datetime_str": intent.datetime_str}
        elif intent.action == "delete":
            if authorized and "delete_reminder" not in authorized:
                return None
            tool_name = "delete_reminder"
            tool_args = {"title": intent.title}
            if intent.datetime_str:
                tool_args["datetime_str"] = intent.datetime_str
        else:
            return None

        mark_skip_context_enricher()
        append_inference_warnings(["reminder_llm_intent"])
        agent_state.pending_tool_name = tool_name
        agent_state.pending_tool_args = tool_args
        answer = _L("confirm.tool_pause", tool_name=tool_name)
        answer += f"\n\n**{intent.title}**"
        if intent.datetime_str and intent.action == "add":
            answer += f"\nCuándo: {intent.datetime_str}"
        elif intent.datetime_str and intent.action == "delete":
            answer += f"\nDía: {intent.datetime_str}"
        self._state_store.save(agent_state)
        return answer, agent_state

    def _try_file_search_fast_path(self, query: str, agent_state: AgentState) -> str | None:
        return try_file_search_fast_path(query, list(agent_state.profile.authorized_tools or []))

    def _finish_file_search_fast_path(
        self,
        query: str,
        conversation_id: str | None,
        answer: str,
        agent_state: AgentState,
    ) -> AgentState:
        mark_skip_context_enricher()
        append_inference_warnings(["file_search_fast_path"])
        self._state_store.save(agent_state)
        short_term = self._context_builder._short_term
        short_term.push_message({"role": "user", "content": query})
        short_term.push_message({"role": "assistant", "content": answer})
        self.save_conversation_session(conversation_id, agent_state)
        return agent_state

    def _finish_reminder_fast_path(
        self,
        query: str,
        conversation_id: str | None,
        result: FastPathResult,
        agent_state: AgentState,
    ) -> tuple[str, AgentState]:
        """Persist a reminder confirmation and pause for tool approval."""
        mark_skip_context_enricher()
        append_inference_warnings(list(result.warnings))
        if (
            result.answer is None
            or result.pending_tool_name is None
            or result.pending_tool_args is None
        ):
            raise ValueError("reminder fast path result is incomplete")
        agent_state.pending_tool_name = result.pending_tool_name
        agent_state.pending_tool_args = result.pending_tool_args
        self._state_store.save(agent_state)
        short_term = self._context_builder._short_term
        short_term.push_message({"role": "user", "content": query})
        short_term.push_message({"role": "assistant", "content": result.answer})
        self.save_conversation_session(conversation_id, agent_state)
        return result.answer, agent_state

    async def _apply_fast_path_result(
        self,
        query: str,
        conversation_id: str | None,
        result: FastPathResult,
        agent_state: AgentState,
    ) -> tuple[str, AgentState]:
        if result.kind in ("time_date", "config_read", "math"):
            if result.warnings:
                append_inference_warnings(list(result.warnings))
            warning = result.warnings[0] if result.warnings else f"{result.kind}_fast_path"
            final_state = self._finish_calendar_fast_path(
                query, conversation_id, result.answer or "", agent_state, warning=warning
            )
            return result.answer or "", final_state

        if result.kind == "file_write":
            if result.warnings:
                append_inference_warnings(list(result.warnings))
            if result.file_write_intent is None:
                raise ValueError("file_write fast path result is incomplete")
            return self._finish_file_write_fast_path(
                query, conversation_id, result.file_write_intent, agent_state
            )

        if result.kind == "reminder":
            return self._finish_reminder_fast_path(query, conversation_id, result, agent_state)

        if result.kind == "calendar_write":
            return self._finish_reminder_fast_path(query, conversation_id, result, agent_state)

        if result.kind == "url_open":
            import webbrowser

            url = result.answer or ""
            if url:
                webbrowser.open(url)
            final_state = self._finish_calendar_fast_path(
                query, conversation_id, f"Opened {url}", agent_state, warning="url_open_fast_path"
            )
            return f"Opened {url}", final_state

        if result.kind == "calendar_read":
            warning = result.warnings[0] if result.warnings else "calendar_fast_path"
            final_state = self._finish_calendar_fast_path(
                query, conversation_id, result.answer or "", agent_state, warning=warning
            )
            return result.answer or "", final_state

        if result.kind == "web_search":
            # Handle follow-up summary request
            if result.warnings and "web_search_follow_up" in result.warnings:
                summary = await self._summarize_web_search_result(query, agent_state)
                if summary:
                    warning = "web_search_follow_up_summary"
                    final_state = self._finish_calendar_fast_path(
                        query, conversation_id, summary, agent_state, warning=warning
                    )
                    return summary, final_state
                # Fallback: return raw result if summarization fails
                raw = agent_state.working_memory.get("last_web_search_result", "")
                warning = "web_search_follow_up_raw"
                final_state = self._finish_calendar_fast_path(
                    query, conversation_id, raw, agent_state, warning=warning
                )
                return raw, final_state

            warning = "web_search_fast_path"
            final_state = self._finish_calendar_fast_path(
                query, conversation_id, result.answer or "", agent_state, warning=warning
            )
            return result.answer or "", final_state

        if result.kind == "file_search":
            if result.warnings:
                append_inference_warnings(list(result.warnings))
            final_state = self._finish_file_search_fast_path(
                query, conversation_id, result.answer or "", agent_state
            )
            return result.answer or "", final_state

        raise ValueError(f"unknown fast path kind: {result.kind}")

    async def _summarize_web_search_result(
        self,
        query: str,
        agent_state: AgentState,
    ) -> str | None:
        """Use LLM to summarize the last web search result for follow-up queries."""
        from core.inference.registry import TaskHint

        raw_result = agent_state.working_memory.get("last_web_search_result")
        original_query = agent_state.working_memory.get("last_web_search_query", "")
        if not raw_result:
            return None

        try:
            provider_name = self._registry.select_for_task(TaskHint.CHAT)
            chat = self._registry.get_chat(provider_name)
        except Exception as exc:
            logger.warning("Web search summary: no chat provider: {}", exc)
            return None

        summary_prompt = f"""The user previously asked: "{original_query}"
You searched the web and found these results:

{raw_result[:3000]}

Now the user asks: "{query}"

Provide a clear, concise summary in the user's language that answers their follow-up question based on the search results above. Include source URLs where relevant."""

        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes web search results clearly and concisely.",
                },
                {"role": "user", "content": summary_prompt},
            ]
            summary = await chat.complete(messages, max_tokens=500, temperature=0.3)
            return summary.strip()
        except Exception as exc:
            logger.warning("Web search summary: LLM failed: {}", exc)
            return None

    # ---------------------------------------------------------------------- #
    # Public entry point
    # ---------------------------------------------------------------------- #

    async def stream(
        self, query: str, agent_id: str, conversation_id: str | None = None
    ) -> AsyncIterator[str]:
        """Stream answer tokens directly, skipping the tool-call loop.

        Runs context assembly then calls chat.stream() so tokens arrive as they
        are produced. Tool use is not supported on this path; callers that need
        tool execution should use run() instead.
        """
        from core.inference.registry import TaskHint  # avoid circular at module level

        self.prepare_conversation(conversation_id, agent_id)
        agent_state = self._state_store.load(agent_id)
        agent_state.execution_count += 1

        provider_name = self._registry.select_for_task(TaskHint.CHAT)
        chat = self._registry.get_chat(provider_name)
        if await self._context_builder.maybe_consolidate(agent_state, chat, chat.context_window()):
            self._state_store.save(agent_state)

        assembled = await self._context_builder.build(query, agent_state)
        ambient_context = ""
        if self._enricher and not should_skip_context_enricher():
            ambient_context = await self._enricher.enrich(query)
        system_prompt = _build_stream_system_prompt(agent_state, assembled, ambient_context)
        messages: list[Message] = [
            {"role": "system", "content": system_prompt},
            *assembled.session_history,
            {"role": "user", "content": _date_preamble() + query},
        ]

        sync_prompt_cache(
            system_prompt,
            list(agent_state.profile.authorized_tools),
            model_id=os.getenv("CEREBRO_LLAMACPP_MODEL", ""),
        )

        full_tokens: list[str] = []
        stream = cast(AsyncIterable[str], chat.stream(messages))
        async for token in stream:
            full_tokens.append(token)
            yield token

        # Persist session summary so context grows across turns
        full_answer = "".join(full_tokens)
        new_exchange = f"Usuario: {query}\nAgente: {full_answer[:500]}"
        agent_state.session_summary = (
            (agent_state.session_summary[-1000:] + "\n---\n" + new_exchange)
            if agent_state.session_summary
            else new_exchange
        )
        self._state_store.save(agent_state)
        self.save_conversation_session(conversation_id, agent_state)
        short_term = self._context_builder._short_term
        short_term.push_message({"role": "user", "content": query})
        short_term.push_message({"role": "assistant", "content": full_answer})

    async def run(
        self,
        query: str,
        agent_id: str,
        conversation_id: str | None = None,
        intent_query: str | None = None,
        attachments: list[dict] | None = None,
    ) -> tuple[str, AgentState]:
        self.prepare_conversation(conversation_id, agent_id)
        agent_state = self._state_store.load(agent_id)
        agent_state.execution_count += 1
        refresh_ram_pressure()

        route_query = intent_query or query

        image_attachments = (
            [
                {"filename": a["filename"], "mime_type": a["mime_type"], "content": a["content"]}
                for a in attachments
                if a.get("type") == "image"
            ]
            if attachments
            else None
        )

        # Start context assembly in parallel with fast path check
        base_state: _RunState = {
            "agent_state": _state_to_dict(agent_state),
            "query": route_query,
            "context": None,
            "messages": [],
            "iterations": 0,
            "tool_calls_count": 0,
            "final_answer": None,
            "next_tool_name": None,
            "next_tool_args": None,
            "seen_tool_calls": [],
            "needs_confirmation": False,
            "pending_tool_name": None,
            "pending_tool_args": None,
            "ambient_context": "",
            "image_attachments": image_attachments,
        }
        context_task = asyncio.create_task(self._context_assembly_node(base_state))

        fast_path_result = await self._fast_path_router.try_all(
            route_query, agent_state, intent=intent_query
        )
        if fast_path_result is not None:
            context_task.cancel()
            try:
                await context_task
            except (asyncio.CancelledError, Exception):
                pass
            return await self._apply_fast_path_result(
                query, conversation_id, fast_path_result, agent_state
            )

        # Fast path missed — await the already-running context assembly
        prefetch_ready = context_task.done()
        context_updates = await context_task
        if prefetch_ready:
            append_inference_warnings(["context_prefetch_ready"])
        else:
            append_inference_warnings(["context_prefetch_still_building"])
        initial: _RunState = {**base_state, **context_updates}
        initial["query"] = query  # Use original query, not route_query

        try:
            result = await asyncio.wait_for(
                self._graph.ainvoke(initial),
                timeout=TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning("Agent '{}' timed out after {}s", agent_id, TIMEOUT_SECONDS)
            result = initial
            result["final_answer"] = "La consulta excedió el tiempo máximo de respuesta."

        final_state = _state_from_dict(result["agent_state"])
        # Restore transient pending-confirmation info from the graph's last state dict.
        if result.get("needs_confirmation"):
            final_state.pending_tool_name = result.get("pending_tool_name")
            final_state.pending_tool_args = result.get("pending_tool_args")
        self._state_store.save(final_state)
        answer = result["final_answer"] or "No se pudo generar una respuesta."

        # ── Reflection-Turn: review answer for quality issues ──────────
        if self._reflector and not final_state.pending_tool_name:
            ctx_str = _context_to_preview(result.get("context"))
            critique = await self._reflector.critique(query, answer, context=ctx_str)
            if critique.needs_correction and critique.score < 10:
                logger.info(
                    "Reflection triggered (score={}) for query '{}'",
                    critique.score,
                    query[:60],
                )
                correction_msg = (
                    "La respuesta anterior puede contener errores. Por favor revísala "
                    "y corrígela teniendo en cuenta estas observaciones:\n"
                    + json.dumps(critique.issues, ensure_ascii=False)
                )
                corrected = await self._reflect_correction(result["messages"], correction_msg)
                if corrected:
                    answer = corrected
                    result["final_answer"] = corrected
                    logger.info("Reflection corrected answer for '{}'", query[:60])
        # ─────────────────────────────────────────────────────────────────

        if not final_state.pending_tool_name:
            short_term = self._context_builder._short_term
            short_term.push_message({"role": "user", "content": query})
            short_term.push_message({"role": "assistant", "content": answer})
        self.save_conversation_session(conversation_id, final_state)
        return answer, final_state

    async def run_streaming(
        self,
        query: str,
        agent_id: str,
        conversation_id: str | None = None,
        intent_query: str | None = None,
        slot_id: int | None = None,
        attachments: list[dict] | None = None,
    ) -> AsyncIterator[str | StreamRunComplete]:
        """Run the tool loop, yielding answer-field tokens when the model replies directly.

        Yields decoded answer characters as they arrive inside the JSON envelope, then a
        final :class:`StreamRunComplete` with the parsed answer and persisted state.
        When live streaming is unavailable or the model selects a tool, only the
        sentinel is yielded (caller should simulate tokens from ``answer``).
        """
        self.prepare_conversation(conversation_id, agent_id)
        agent_state = self._state_store.load(agent_id)
        agent_state.execution_count += 1
        refresh_ram_pressure()

        route_query = intent_query or query

        image_attachments = (
            [
                {"filename": a["filename"], "mime_type": a["mime_type"], "content": a["content"]}
                for a in attachments
                if a.get("type") == "image"
            ]
            if attachments
            else None
        )

        # Start context assembly in parallel with fast path check
        base_state: _RunState = {
            "agent_state": _state_to_dict(agent_state),
            "query": route_query,
            "context": None,
            "messages": [],
            "iterations": 0,
            "tool_calls_count": 0,
            "final_answer": None,
            "next_tool_name": None,
            "next_tool_args": None,
            "seen_tool_calls": [],
            "needs_confirmation": False,
            "pending_tool_name": None,
            "pending_tool_args": None,
            "ambient_context": "",
            "image_attachments": image_attachments,
            "slot_id": slot_id,
        }

        # ── Time-travel debug recording (defined early, used in fast path + main loop) ──
        _tt = self._time_travel
        _run_id = _uuid.uuid4().hex if _tt else None
        _step_num = 0
        # ────────────────────────────────────────────────────────────────────────────────

        context_task = asyncio.create_task(self._context_assembly_node(base_state))

        fast_path_result = await self._fast_path_router.try_all(
            route_query, agent_state, intent=intent_query
        )
        if fast_path_result is not None:
            context_task.cancel()
            try:
                await context_task
            except (asyncio.CancelledError, Exception):
                pass
            answer, final_state = await self._apply_fast_path_result(
                query, conversation_id, fast_path_result, agent_state
            )
            if _tt:
                await _tt.start_run(_run_id, agent_id, query, conversation_id)
                await _tt.record_step(
                    _uuid.uuid4().hex,
                    _run_id,
                    0,
                    "fast_path",
                    output_preview=answer[:500],
                )
                await _tt.end_run(_run_id, success=True)
            yield answer
            yield StreamRunComplete(answer=answer, final_state=final_state)
            return

        # Fast path missed — await context assembly
        prefetch_ready = context_task.done()
        context_updates = await context_task
        if prefetch_ready:
            append_inference_warnings(["context_prefetch_ready"])
        else:
            append_inference_warnings(["context_prefetch_still_building"])
        state: _RunState = {**base_state, **context_updates}
        state["query"] = query

        # Emit context sources event before first token
        ctx_info = context_updates.get("context") or {}
        sources: list[str] = ctx_info.get("sources_used") or []
        if sources:
            yield ContextSourcesEvent(sources=list(sources), episode_count=len(sources))

        if _tt:
            await _tt.start_run(_run_id, agent_id, query, conversation_id)
        # ─────────────────────────────────────────────────────────────

        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                state = {**state, **await self._context_assembly_node(state)}

                if _tt:
                    await _tt.record_step(
                        _uuid.uuid4().hex,
                        _run_id,
                        _step_num,
                        "context_assembly",
                        output_preview=f"context ready, {len(state.get('messages', []))} messages",
                    )

                while True:
                    _step_num += 1
                    reason_updates, token_iter = await self._reason_node_streaming(state)

                    _tokens: list[tuple[str, bool]] = []
                    async for token in token_iter:
                        _tokens.append((token, False))
                        yield token
                    if _tokens:
                        _tokens[-1] = (_tokens[-1][0], True)

                    state = {**state, **reason_updates}

                    _step_id = _uuid.uuid4().hex if _tt else None
                    if _tt:
                        await _tt.record_step(
                            _step_id,
                            _run_id,
                            _step_num,
                            "reason_node",
                            output_preview=(
                                state.get("final_answer")
                                or f"→ tool: {state.get('next_tool_name')}"
                            )[:800],
                            tool_name=state.get("next_tool_name"),
                            tool_args=state.get("next_tool_args"),
                        )
                        if _tokens and _step_id:
                            await _tt.record_tokens(_step_id, _tokens)

                    if self._route_after_reason(state) == "tool_node":
                        state = {**state, **await self._tool_node(state)}
                        if state.get("needs_confirmation"):
                            if _tt:
                                await _tt.record_step(
                                    _uuid.uuid4().hex,
                                    _run_id,
                                    _step_num + 1,
                                    "tool_node",
                                    tool_name=state.get("pending_tool_name"),
                                    tool_args=state.get("pending_tool_args"),
                                    needs_confirmation=True,
                                )
                            break

                        _tool_result = state.get("_last_tool_result", "")
                        if _tt:
                            await _tt.record_step(
                                _uuid.uuid4().hex,
                                _run_id,
                                _step_num + 1,
                                "tool_node",
                                tool_name=state.get("next_tool_name"),
                                tool_args=state.get("next_tool_args"),
                                tool_result_preview=(
                                    str(_tool_result)[:800] if _tool_result else None
                                ),
                            )

                        state = {**state, **await self._observe_node(state)}
                        _step_num += 1
                        if _tt:
                            await _tt.record_step(
                                _uuid.uuid4().hex,
                                _run_id,
                                _step_num,
                                "observe_node",
                                output_preview=f"result ingested, {len(state.get('messages', []))} messages",
                            )
                        continue
                    break

                state = {**state, **await self._update_state_node(state)}
        except TimeoutError:
            logger.warning("Agent '{}' timed out after {}s", agent_id, TIMEOUT_SECONDS)
            state["final_answer"] = "La consulta excedió el tiempo máximo de respuesta."

        final_state = _state_from_dict(state["agent_state"])
        if state.get("needs_confirmation"):
            final_state.pending_tool_name = state.get("pending_tool_name")
            final_state.pending_tool_args = state.get("pending_tool_args")
        self._state_store.save(final_state)
        answer = state.get("final_answer") or "No se pudo generar una respuesta."

        # ── Reflection-Turn (streaming): correct after tokens, before StreamRunComplete ──
        if self._reflector and not state.get("needs_confirmation"):
            ctx_str = _context_to_preview(state.get("context"))
            critique = await self._reflector.critique(query, answer, context=ctx_str)
            if critique.needs_correction and critique.score < 10:
                correction_msg = (
                    "La respuesta anterior puede contener errores. Por favor revísala "
                    "y corrígela teniendo en cuenta estas observaciones:\n"
                    + json.dumps(critique.issues, ensure_ascii=False)
                )
                corrected = await self._reflect_correction(state["messages"], correction_msg)
                if corrected:
                    answer = corrected
                    logger.info("Reflection corrected streamed answer for '{}'", query[:60])
        # ────────────────────────────────────────────────────────────────────────────────

        if not final_state.pending_tool_name:
            short_term = self._context_builder._short_term
            short_term.push_message({"role": "user", "content": query})
            short_term.push_message({"role": "assistant", "content": answer})
        self.save_conversation_session(conversation_id, final_state)
        if _tt:
            await _tt.end_run(_run_id, success=bool(answer) and not state.get("needs_confirmation"))
        yield StreamRunComplete(answer=answer, final_state=final_state)

    # ---------------------------------------------------------------------- #
    # Graph construction
    # ---------------------------------------------------------------------- #

    def _build_graph(self):
        builder = StateGraph(_RunState)

        builder.add_node("context_assembly", self._context_assembly_node)
        builder.add_node("reason_node", self._reason_node)
        builder.add_node("tool_node", self._tool_node)
        builder.add_node("observe_node", self._observe_node)
        builder.add_node("update_state", self._update_state_node)

        builder.set_entry_point("context_assembly")
        builder.add_edge("context_assembly", "reason_node")
        builder.add_conditional_edges(
            "reason_node",
            self._route_after_reason,
            {"tool_node": "tool_node", "update_state": "update_state"},
        )
        builder.add_conditional_edges(
            "tool_node",
            self._route_after_tool,
            {"observe_node": "observe_node", "update_state": "update_state"},
        )
        builder.add_edge("observe_node", "reason_node")
        builder.add_edge("update_state", END)

        return builder.compile()

    # ---------------------------------------------------------------------- #
    # Nodes
    # ---------------------------------------------------------------------- #

    async def _context_assembly_node(self, state: _RunState) -> dict:
        # If messages were already built by async prefetch, skip assembly
        if state.get("messages") and len(state["messages"]) > 0:
            return {}

        agent_state = _state_from_dict(state["agent_state"])
        provider_name = self._registry.select_for_task(
            __import__("core.inference.registry", fromlist=["TaskHint"]).TaskHint.CHAT
        )
        chat = self._registry.get_chat(provider_name)
        if await self._context_builder.maybe_consolidate(agent_state, chat, chat.context_window()):
            self._state_store.save(agent_state)
            state = {**state, "agent_state": _state_to_dict(agent_state)}

        assembled = await self._context_builder.build(state["query"], agent_state)
        ambient_context = ""
        if self._enricher and not should_skip_context_enricher():
            ambient_context = await self._enricher.enrich(state["query"])

        tool_defs = [
            self._tool_definitions[t]
            for t in self._tool_registry
            if (
                not agent_state.profile.authorized_tools
                or t in agent_state.profile.authorized_tools
            )
            and t in self._tool_definitions
            and (self._web_search_enabled() or t != "web_search")
        ]
        system_prompt = _build_system_prompt(
            agent_state, assembled, tool_defs, ambient_context, query=state["query"]
        )
        sync_prompt_cache(
            system_prompt,
            [td.name for td in tool_defs],
            model_id=os.getenv("CEREBRO_LLAMACPP_MODEL", ""),
        )
        logger.debug(
            "Micro-route: agent={} tools_in_prompt={}",
            agent_state.profile.id,
            [td.name for td in tool_defs],
        )

        user_content = _date_preamble() + state["query"]
        if state.get("image_attachments") and getattr(chat, "supports_vision", False):
            content_blocks: list[dict] = [{"type": "text", "text": user_content}]
            for img in state["image_attachments"]:
                content_blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{img['mime_type']};base64,{img['content']}"},
                    }
                )
            user_message: dict = {"role": "user", "content": content_blocks}
        elif state.get("image_attachments"):
            user_message = {
                "role": "user",
                "content": user_content
                + "\n\n[Nota: se adjuntó una imagen pero el modelo actual no soporta procesamiento de imágenes.]",
            }
        else:
            user_message = {"role": "user", "content": user_content}

        messages: list[Message] = [
            {"role": "system", "content": system_prompt},
            *assembled.session_history,
            user_message,
        ]

        return {
            "context": {
                "sources_used": assembled.sources_used,
                "total_tokens_estimated": assembled.total_tokens_estimated,
            },
            "messages": [dict(m) for m in messages],
            "ambient_context": ambient_context,
        }

    async def _reason_node(self, state: _RunState) -> dict:
        updates, _ = await self._reason_node_streaming(state)
        return updates

    async def _reason_node_streaming(self, state: _RunState) -> tuple[dict, AsyncIterator[str]]:
        iterations = state["iterations"] + 1
        provider_name = self._registry.select_for_task(
            __import__("core.inference.registry", fromlist=["TaskHint"]).TaskHint.CHAT
        )
        chat = self._registry.get_chat(provider_name)

        messages: list[Message] = [cast(Message, m) for m in state["messages"]]
        agent_state = _state_from_dict(state["agent_state"])
        if messages and messages[0].get("role") == "system":
            sync_prompt_cache(
                str(messages[0].get("content", "")),
                list(agent_state.profile.authorized_tools),
                model_id=os.getenv("CEREBRO_LLAMACPP_MODEL", ""),
            )
        grammar = build_agent_response_grammar(self._authorized_tools_for_grammar(agent_state))

        slot_id: int | None = state.get("slot_id")
        token_queue: asyncio.Queue[str | None] = asyncio.Queue()
        use_live_stream = _chat_supports_grammar_stream(chat)

        async def _collect_stream() -> str:
            parser = AgentAnswerStreamParser()
            chunks: list[str] = []
            stream_kwargs: dict = {"grammar": grammar}
            if slot_id is not None:
                stream_kwargs["slot_id"] = slot_id
            stream = cast(AsyncIterable[str], chat.stream(messages, **stream_kwargs))
            async for delta in stream:
                chunks.append(delta)
                for token in parser.feed(delta):
                    await token_queue.put(token)
            return "".join(chunks)

        if use_live_stream:
            raw_response = await _collect_stream()
            await token_queue.put(None)
        else:
            raw_response = await chat.complete(messages, grammar=grammar)
            await token_queue.put(None)

        logger.debug("Reason node raw response: {}", raw_response[:200])
        updates = self._build_reason_updates(state, iterations, raw_response)

        async def _drain_tokens() -> AsyncIterator[str]:
            while True:
                item = await token_queue.get()
                if item is None:
                    break
                yield item

        return updates, _drain_tokens()

    def _build_reason_updates(self, state: _RunState, iterations: int, raw_response: str) -> dict:
        known_tools = frozenset(self._tool_registry.keys())
        action, tool_name, args = _parse_llm_response(
            raw_response,
            known_tools=known_tools if known_tools else None,
        )

        if action == "tool" and tool_name and tool_name not in self._tool_registry:
            logger.warning("Parser returned unregistered tool '{}'; answering instead.", tool_name)
            action = "answer"
            args = {"answer": _L("parse.tool_unknown", tool_name=tool_name)}

        if action == "tool" and tool_name:
            dedup_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
            if dedup_key in state["seen_tool_calls"]:
                logger.warning("Duplicate tool call detected: {}. Forcing answer.", dedup_key)
                action = "answer"
                args = {
                    "answer": "Se detectó un bucle en el uso de herramientas. Por favor reformula tu pregunta."
                }

        if iterations >= MAX_ITERATIONS or state["tool_calls_count"] >= MAX_TOOL_CALLS:
            action = "answer"
            if not args.get("answer"):
                args = {
                    "answer": "Se alcanzó el límite de iteraciones. Respuesta parcial basada en el contexto disponible."
                }

        updates: dict = {"iterations": iterations}
        if action == "tool":
            updates["next_tool_name"] = tool_name
            updates["next_tool_args"] = args
        else:
            updates["final_answer"] = args.get("answer", raw_response)
            updates["next_tool_name"] = None
            updates["next_tool_args"] = None

        updated_messages = list(state["messages"])
        updated_messages.append({"role": "assistant", "content": raw_response})
        updates["messages"] = updated_messages
        return updates

    async def _tool_node(self, state: _RunState) -> dict:
        tool_name = state["next_tool_name"]
        tool_args = _normalize_tool_args(tool_name, state["next_tool_args"] or {})

        if self._requires_confirmation(tool_name):
            return {
                "needs_confirmation": True,
                "pending_tool_name": tool_name,
                "pending_tool_args": tool_args,
                "final_answer": _L("confirm.tool_pause", tool_name=tool_name),
            }

        agent_state = _state_from_dict(state["agent_state"])

        # Authorization check (A5 will replace this with PolicyEngine)
        if (
            agent_state.profile.authorized_tools
            and tool_name not in agent_state.profile.authorized_tools
        ):
            result_text = f"Herramienta '{tool_name}' no autorizada para este agente."
            logger.warning(
                "Unauthorized tool call: {} by agent {}", tool_name, agent_state.profile.id
            )
        elif tool_name not in self._tool_registry:
            result_text = f"Herramienta '{tool_name}' no disponible."
            logger.warning("Tool not found in registry: {}", tool_name)
        else:
            try:
                handler = self._tool_registry[tool_name]
                # Filter to only kwargs the handler actually accepts so that
                # small models passing wrong arg names don't cause TypeError.
                sig = inspect.signature(handler)
                accepted = set(sig.parameters.keys())
                filtered_args = {k: v for k, v in tool_args.items() if k in accepted}
                if filtered_args != tool_args:
                    dropped = set(tool_args) - accepted
                    logger.debug("Tool '{}': dropped unknown args {}", tool_name, dropped)
                t0 = time.perf_counter()
                if inspect.iscoroutinefunction(handler):
                    result_text = str(await handler(**filtered_args))
                else:
                    result_text = str(await asyncio.to_thread(handler, **filtered_args))
                tool_latency_ms = (time.perf_counter() - t0) * 1000
            except PathNotAuthorizedError as exc:
                result_text = str(exc)
                tool_latency_ms = 0.0
                logger.warning(
                    "Path not authorized for tool '{}': {} (allowed: {})",
                    tool_name,
                    exc.path,
                    exc.authorized_paths,
                )
            except Exception as e:
                result_text = f"Error ejecutando '{tool_name}': {e}"
                tool_latency_ms = 0.0
                logger.exception("Tool '{}' raised an exception", tool_name)

        # Record in agent state tool_trace
        tc = ToolCall(
            tool_name=tool_name or "unknown",
            args=tool_args,
            result=result_text,
            latency_ms=tool_latency_ms,
        )
        updated_state = _state_to_dict(_state_from_dict(state["agent_state"]))
        updated_state["tool_trace"].append(
            {
                "tool_name": tc.tool_name,
                "args": tc.args,
                "result": tc.result,
                "timestamp": tc.timestamp,
                "latency_ms": tc.latency_ms,
            }
        )

        dedup_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
        seen = list(state["seen_tool_calls"]) + [dedup_key]

        return {
            "agent_state": updated_state,
            "tool_calls_count": state["tool_calls_count"] + 1,
            "seen_tool_calls": seen,
            "_last_tool_result": result_text,  # passed to observe_node via state
        }

    async def _observe_node(self, state: _RunState) -> dict:
        tool_result = state.get("_last_tool_result", "(sin resultado)")
        tool_name = state.get("next_tool_name", "herramienta")

        observation_msg = {
            "role": "user",
            "content": (
                f'Observación de herramienta "{tool_name}" (ejecutada exitosamente):\n'
                f"{tool_result}\n"
                f'Responde ahora al usuario con {{"action": "answer", "answer": "..."}} '
                f"usando este resultado."
            ),
        }
        updated_messages = list(state["messages"]) + [observation_msg]

        return {
            "messages": updated_messages,
            "next_tool_name": None,
            "next_tool_args": None,
        }

    async def _update_state_node(self, state: _RunState) -> dict:
        """Compress session and persist updated summary into agent_state before returning."""
        agent_state = _state_from_dict(state["agent_state"])

        # Don't update session summary when waiting for tool confirmation —
        # the turn isn't complete yet.
        if state.get("needs_confirmation"):
            return {"agent_state": _state_to_dict(agent_state)}

        user_msg = state["query"]
        answer = state["final_answer"] or ""

        new_exchange = f"Usuario: {user_msg}\nAgente: {answer[:500]}"
        if agent_state.session_summary:
            agent_state.session_summary = (
                agent_state.session_summary[-1000:] + "\n---\n" + new_exchange
            )
        else:
            agent_state.session_summary = new_exchange

        return {"agent_state": _state_to_dict(agent_state)}

    # ── Reflection-Turn helpers ────────────────────────────────────────────

    async def _reflect_correction(
        self,
        messages: list[dict],
        correction_msg: str,
    ) -> str | None:
        """Request a corrected answer from the LLM given the issues found."""
        if not messages:
            return None
        corrected_messages = list(messages) + [
            {"role": "user", "content": correction_msg},
        ]
        try:
            provider_name = self._registry.select_for_task(
                __import__("core.inference.registry", fromlist=["TaskHint"]).TaskHint.CHAT
            )
            chat = self._registry.get_chat(provider_name)
            raw = await asyncio.wait_for(
                chat.complete(corrected_messages, temperature=0.1),
                timeout=15.0,
            )
            # Parse the response — same logic as the main parser
            from core.agents.llm_parse_utils import extract_json_object

            parsed = extract_json_object(raw)
            if parsed and "answer" in parsed:
                return str(parsed["answer"])
            return raw.strip()
        except Exception:
            logger.exception("Reflection correction failed")
            return None

    # ---------------------------------------------------------------------- #
    # Routing
    # ---------------------------------------------------------------------- #

    def _route_after_reason(self, state: _RunState) -> str:
        if state.get("next_tool_name") and state["tool_calls_count"] < MAX_TOOL_CALLS:
            return "tool_node"
        return "update_state"

    def _requires_confirmation(self, tool_name: str | None) -> bool:
        if not tool_name:
            return False
        td = self._tool_definitions.get(tool_name)
        if td is not None:
            return bool(td.requires_confirmation)
        return tool_name in CONFIRMATION_REQUIRED_TOOLS

    def _route_after_tool(self, state: _RunState) -> str:
        if state.get("needs_confirmation"):
            return "update_state"
        return "observe_node"

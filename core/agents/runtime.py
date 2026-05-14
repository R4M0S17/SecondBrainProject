from __future__ import annotations

import asyncio
import inspect
import json
import re
from collections.abc import AsyncIterable, AsyncIterator, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypedDict, cast

from langgraph.graph import END, StateGraph
from loguru import logger

from core.agents.state_store import (
    AgentState,
    AgentStateStore,
    ToolCall,
    _state_from_dict,
    _state_to_dict,
)
from core.inference.registry import Message, ProviderRegistry
from core.memory.context_builder import AssembledContext, ContextBuilder
from core.tools.registry import ToolDefinition

if TYPE_CHECKING:
    from core.agents.context_enricher import ContextEnricher

# --------------------------------------------------------------------------- #
# Hard limits (from spec)
# --------------------------------------------------------------------------- #
MAX_ITERATIONS = 10
MAX_TOOL_CALLS = 5
TIMEOUT_SECONDS = 120

# Tools that must pause execution and wait for explicit user approval before running.
CONFIRMATION_REQUIRED_TOOLS: frozenset[str] = frozenset(
    {
        "write_file",
        "execute_python",
        "delete_file",
        "run_script",
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

Responde de forma natural y directa en texto plano. No uses JSON ni ningún formato especial.\
"""


def _date_preamble() -> str:
    """One-line dateline for the LLM user turn only (not persisted in the UI log)."""
    now = datetime.now().astimezone()
    return f"[Contexto del sistema: hoy es {now.strftime('%A %d de %B de %Y, %H:%M %Z')}.] "


def _build_system_prompt(
    agent_state: AgentState,
    context: AssembledContext,
    tool_defs: list[ToolDefinition],
    ambient_context: str = "",
) -> str:
    memory_lines = [f"- {c.content[:200]}" for c in context.retrieved_memory]
    memory_context = "\n".join(memory_lines) if memory_lines else "(sin episodios previos)"
    instructions = agent_state.profile.preferences.get("instructions", "")

    if tool_defs:
        detail_lines = []
        for td in tool_defs:
            if td.parameters:
                params = ", ".join(f"{k}: {v}" for k, v in td.parameters.items())
            else:
                params = "sin argumentos"
            detail_lines.append(f"- {td.name}({params}): {td.description}")
        tools_detail = "\n".join(detail_lines)
    else:
        tools_detail = "ninguna"

    now = datetime.now().astimezone()
    current_date = now.strftime("%A, %Y-%m-%d %H:%M %Z")
    current_year = now.strftime("%Y")
    return _SYSTEM_TEMPLATE.format(
        agent_name=agent_state.profile.name,
        instructions=instructions,
        current_date=current_date,
        current_year=current_year,
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

    now = datetime.now().astimezone()
    current_date = now.strftime("%A, %Y-%m-%d %H:%M %Z")
    current_year = now.strftime("%Y")
    return _STREAM_SYSTEM_TEMPLATE.format(
        agent_name=agent_state.profile.name,
        instructions=instructions,
        current_date=current_date,
        current_year=current_year,
        session_summary=agent_state.session_summary or "(sesión nueva)",
        memory_context=memory_context,
        ambient_context=ambient_context,
    )


def _parse_llm_response(raw: str) -> tuple[str, str | None, dict]:
    """Return (action, tool_name, args). action is 'answer' or 'tool'.

    Handles:
    - Qwen3 <think>…</think> blocks before the JSON
    - Markdown code fences
    - JSON embedded in surrounding prose
    - Non-standard format where action field holds the tool name directly:
        {"action": "get_upcoming_events", "hours_ahead": 24}
    """
    raw = raw.strip()

    # Strip Qwen3 / DeepSeek style thinking blocks
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    # Extract first JSON object from response (handles prose wrapping)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)

    try:
        data = json.loads(raw)
        action = data.get("action", "answer")
        if action == "tool":
            return "tool", data.get("tool"), data.get("args", {})
        if action == "answer":
            return "answer", None, {"answer": data.get("answer", raw)}
        # Fallback: small models sometimes put the tool name directly in "action"
        # e.g. {"action": "get_upcoming_events", "hours_ahead": 24}
        if action not in ("tool", "answer"):
            args = {k: v for k, v in data.items() if k != "action"}
            return "tool", action, args
        return "answer", None, {"answer": data.get("answer", raw)}
    except json.JSONDecodeError:
        return "answer", None, {"answer": raw}


# --------------------------------------------------------------------------- #
# AgentRuntime
# --------------------------------------------------------------------------- #


class AgentRuntime:
    def __init__(
        self,
        registry: ProviderRegistry,
        state_store: AgentStateStore,
        context_builder: ContextBuilder,
        tool_registry: dict[str, Callable[..., Any]] | None = None,
        tool_definitions: dict[str, ToolDefinition] | None = None,
        enricher: ContextEnricher | None = None,
    ) -> None:
        self._registry = registry
        self._state_store = state_store
        self._context_builder = context_builder
        self._tool_registry = tool_registry or {}
        self._tool_definitions = tool_definitions or {}
        self._enricher = enricher
        self._graph = self._build_graph()

    # ---------------------------------------------------------------------- #
    # Public entry point
    # ---------------------------------------------------------------------- #

    async def stream(self, query: str, agent_id: str) -> AsyncIterator[str]:
        """Stream answer tokens directly, skipping the tool-call loop.

        Runs context assembly then calls chat.stream() so tokens arrive as they
        are produced. Tool use is not supported on this path; callers that need
        tool execution should use run() instead.
        """
        from core.inference.registry import TaskHint  # avoid circular at module level

        agent_state = self._state_store.load(agent_id)
        agent_state.execution_count += 1

        assembled = await self._context_builder.build(query, agent_state)
        ambient_context = await self._enricher.enrich(query) if self._enricher else ""
        system_prompt = _build_stream_system_prompt(agent_state, assembled, ambient_context)
        messages: list[Message] = [
            {"role": "system", "content": system_prompt},
            *assembled.session_history,
            {"role": "user", "content": _date_preamble() + query},
        ]

        provider_name = self._registry.select_for_task(TaskHint.CHAT)
        chat = self._registry.get_chat(provider_name)

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

    async def run(self, query: str, agent_id: str) -> tuple[str, AgentState]:
        agent_state = self._state_store.load(agent_id)
        agent_state.execution_count += 1

        initial: _RunState = {
            "agent_state": _state_to_dict(agent_state),
            "query": query,
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
        }

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
        return answer, final_state

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
        agent_state = _state_from_dict(state["agent_state"])
        assembled = await self._context_builder.build(state["query"], agent_state)
        ambient_context = await self._enricher.enrich(state["query"]) if self._enricher else ""

        tool_defs = [
            self._tool_definitions[t]
            for t in self._tool_registry
            if (
                not agent_state.profile.authorized_tools
                or t in agent_state.profile.authorized_tools
            )
            and t in self._tool_definitions
        ]
        system_prompt = _build_system_prompt(agent_state, assembled, tool_defs, ambient_context)

        messages: list[Message] = [
            {"role": "system", "content": system_prompt},
            *assembled.session_history,
            {"role": "user", "content": _date_preamble() + state["query"]},
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
        iterations = state["iterations"] + 1
        provider_name = self._registry.select_for_task(
            __import__("core.inference.registry", fromlist=["TaskHint"]).TaskHint.CHAT
        )
        chat = self._registry.get_chat(provider_name)

        messages: list[Message] = [cast(Message, m) for m in state["messages"]]
        raw_response = await chat.complete(messages)
        logger.debug("Reason node raw response: {}", raw_response[:200])

        action, tool_name, args = _parse_llm_response(raw_response)

        # Detect duplicate tool call → abort loop
        if action == "tool" and tool_name:
            dedup_key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
            if dedup_key in state["seen_tool_calls"]:
                logger.warning("Duplicate tool call detected: {}. Forcing answer.", dedup_key)
                action = "answer"
                args = {
                    "answer": "Se detectó un bucle en el uso de herramientas. Por favor reformula tu pregunta."
                }

        # Enforce iteration and tool-call limits
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

        # Append assistant turn to message history
        updated_messages = list(state["messages"])
        updated_messages.append({"role": "assistant", "content": raw_response})
        updates["messages"] = updated_messages

        return updates

    async def _tool_node(self, state: _RunState) -> dict:
        tool_name = state["next_tool_name"]
        tool_args = state["next_tool_args"] or {}

        # Pause and request user approval for destructive tools.
        if tool_name in CONFIRMATION_REQUIRED_TOOLS:
            return {
                "needs_confirmation": True,
                "pending_tool_name": tool_name,
                "pending_tool_args": tool_args,
                "final_answer": (
                    f"Necesito tu aprobación para ejecutar `{tool_name}`. "
                    "Aprueba o rechaza la acción en el panel de confirmación."
                ),
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
                if inspect.iscoroutinefunction(handler):
                    result_text = str(await handler(**filtered_args))
                else:
                    result_text = str(await asyncio.to_thread(handler, **filtered_args))
            except Exception as e:
                result_text = f"Error ejecutando '{tool_name}': {e}"
                logger.exception("Tool '{}' raised an exception", tool_name)

        # Record in agent state tool_trace
        tc = ToolCall(tool_name=tool_name or "unknown", args=tool_args, result=result_text)
        updated_state = _state_to_dict(_state_from_dict(state["agent_state"]))
        updated_state["tool_trace"].append(
            {
                "tool_name": tc.tool_name,
                "args": tc.args,
                "result": tc.result,
                "timestamp": tc.timestamp,
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

    # ---------------------------------------------------------------------- #
    # Routing
    # ---------------------------------------------------------------------- #

    def _route_after_reason(self, state: _RunState) -> str:
        if state.get("next_tool_name") and state["tool_calls_count"] < MAX_TOOL_CALLS:
            return "tool_node"
        return "update_state"

    def _route_after_tool(self, state: _RunState) -> str:
        if state.get("needs_confirmation"):
            return "update_state"
        return "observe_node"

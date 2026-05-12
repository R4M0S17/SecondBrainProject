"""Module 7 — Agent Orchestration (LangGraph).

Standalone ReAct kernel. No state persistence — accepts plain message lists
and returns a final AgentState. The A2 AgentRuntime builds on top of this
by adding persistent profiles, ContextBuilder, and disk state.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from loguru import logger

from core.inference.registry import ChatProvider, Message

MAX_ITERATIONS = 10
MAX_TOOL_CALLS = 5
TIMEOUT_SECONDS = 120


# --------------------------------------------------------------------------- #
# Public data model
# --------------------------------------------------------------------------- #


@dataclass
class AgentState:
    """Matches the Module 7 spec exactly."""

    messages: list[dict]  # role/content dicts
    tools_called: list[str] = field(default_factory=list)
    iterations: int = 0
    final_answer: str | None = None


# --------------------------------------------------------------------------- #
# Internal LangGraph state
# --------------------------------------------------------------------------- #


class _GraphState(TypedDict):
    messages: list[dict]
    tools_called: list[str]
    iterations: int
    final_answer: str | None
    next_tool: str | None
    next_args: dict | None
    seen_calls: list[str]
    # _tool_result is injected by tool_node and consumed by observe_node;
    # not in the TypedDict schema so we access it via .get()


# --------------------------------------------------------------------------- #
# Response parser (shared with runtime.py to avoid drift)
# --------------------------------------------------------------------------- #


def _parse_response(raw: str) -> tuple[str, str | None, dict]:
    """Return (action, tool_name, args). action is 'answer' or 'tool'."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(raw)
        action = data.get("action", "answer")
        if action == "tool":
            return "tool", data.get("tool"), data.get("args", {})
        return "answer", None, {"answer": data.get("answer", raw)}
    except json.JSONDecodeError:
        return "answer", None, {"answer": raw}


# --------------------------------------------------------------------------- #
# Kernel
# --------------------------------------------------------------------------- #


class CerebroKernel:
    """Pure LangGraph ReAct kernel — no persistence, no profiles.

    Takes a ChatProvider and an optional dict of tool handlers, runs the
    reason → tool → observe loop, and returns an AgentState.
    """

    def __init__(
        self,
        provider: ChatProvider,
        tools: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        self._provider = provider
        self._tools = tools or {}
        self._graph = self._build_graph()

    # ---------------------------------------------------------------------- #
    # Public
    # ---------------------------------------------------------------------- #

    async def run(self, messages: list[dict]) -> AgentState:
        """Run the kernel from an initial message list and return final state."""
        initial: _GraphState = {
            "messages": list(messages),
            "tools_called": [],
            "iterations": 0,
            "final_answer": None,
            "next_tool": None,
            "next_args": None,
            "seen_calls": [],
        }
        try:
            result = await asyncio.wait_for(
                self._graph.ainvoke(initial),
                timeout=TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning("CerebroKernel timed out after {}s", TIMEOUT_SECONDS)
            result = dict(initial)
            result["final_answer"] = "Timeout: la consulta superó el límite de 120 segundos."

        return AgentState(
            messages=result["messages"],
            tools_called=result["tools_called"],
            iterations=result["iterations"],
            final_answer=result["final_answer"],
        )

    # ---------------------------------------------------------------------- #
    # Graph construction
    # ---------------------------------------------------------------------- #

    def _build_graph(self):
        builder = StateGraph(_GraphState)

        builder.add_node("reason_node", self._reason_node)
        builder.add_node("tool_node", self._tool_node)
        builder.add_node("observe_node", self._observe_node)
        builder.add_node("end_node", self._end_node)

        builder.set_entry_point("reason_node")
        builder.add_conditional_edges(
            "reason_node",
            self._route_after_reason,
            {"tool_node": "tool_node", "end_node": "end_node"},
        )
        builder.add_edge("tool_node", "observe_node")
        builder.add_edge("observe_node", "reason_node")
        builder.add_edge("end_node", END)

        return builder.compile()

    # ---------------------------------------------------------------------- #
    # Nodes
    # ---------------------------------------------------------------------- #

    async def _reason_node(self, state: _GraphState) -> dict:
        iterations = state["iterations"] + 1
        messages: list[Message] = [Message(**m) for m in state["messages"]]
        raw = await self._provider.complete(messages)
        logger.debug("reason_node raw: {}", raw[:200])

        action, tool_name, args = _parse_response(raw)

        # Duplicate tool call detection → abort loop
        if action == "tool" and tool_name:
            key = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
            if key in state["seen_calls"]:
                logger.warning("Kernel: duplicate tool call '{}', forcing answer.", key)
                action = "answer"
                args = {
                    "answer": "Se detectó un bucle en el uso de herramientas. Por favor reformula tu pregunta."
                }

        # Hard limits
        if iterations >= MAX_ITERATIONS or len(state["tools_called"]) >= MAX_TOOL_CALLS:
            action = "answer"
            if not args.get("answer"):
                args = {
                    "answer": "Se alcanzó el límite de iteraciones. Respuesta parcial basada en el contexto disponible."
                }

        updated_messages = list(state["messages"])
        updated_messages.append({"role": "assistant", "content": raw})

        updates: dict = {"iterations": iterations, "messages": updated_messages}
        if action == "tool":
            updates["next_tool"] = tool_name
            updates["next_args"] = args
        else:
            updates["final_answer"] = args.get("answer", raw)
            updates["next_tool"] = None
            updates["next_args"] = None

        return updates

    async def _tool_node(self, state: _GraphState) -> dict:
        tool_name = state["next_tool"]
        tool_args = state["next_args"] or {}

        if tool_name not in self._tools:
            result = f"Herramienta '{tool_name}' no disponible."
            logger.warning("Kernel: tool '{}' not found in registry.", tool_name)
        else:
            try:
                handler = self._tools[tool_name]
                if inspect.iscoroutinefunction(handler):
                    result = str(await handler(**tool_args))
                else:
                    result = str(await asyncio.to_thread(handler, **tool_args))
            except Exception as exc:
                result = f"Error ejecutando '{tool_name}': {exc}"
                logger.exception("Kernel: tool '{}' raised an exception.", tool_name)

        key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
        return {
            "tools_called": list(state["tools_called"]) + [tool_name or "unknown"],
            "seen_calls": list(state["seen_calls"]) + [key],
            "_tool_result": result,
        }

    async def _observe_node(self, state: _GraphState) -> dict:
        result = state.get("_tool_result", "(sin resultado)")  # type: ignore[call-overload]
        tool_name = state.get("next_tool", "herramienta")  # type: ignore[call-overload]
        obs: dict = {"role": "user", "content": f"[Resultado de {tool_name}]: {result}"}
        return {
            "messages": list(state["messages"]) + [obs],
            "next_tool": None,
            "next_args": None,
        }

    async def _end_node(self, state: _GraphState) -> dict:  # noqa: ARG002
        return {}

    # ---------------------------------------------------------------------- #
    # Routing
    # ---------------------------------------------------------------------- #

    def _route_after_reason(self, state: _GraphState) -> str:
        if state.get("next_tool") and len(state["tools_called"]) < MAX_TOOL_CALLS:
            return "tool_node"
        return "end_node"

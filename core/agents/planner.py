"""A7 — Multi-step Task Decomposition.

Decomposes complex queries into ordered sub-steps and executes them sequentially,
showing progress to the user.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from core.agents.runtime import AgentRuntime
    from core.agents.state_store import AgentState


class TaskPlanner:
    """Wraps AgentRuntime to handle multi-step task decomposition."""

    def __init__(self, runtime: AgentRuntime) -> None:
        self._runtime = runtime

    @staticmethod
    def is_complex_task(query: str) -> bool:
        """Heuristic to detect if a task is multi-step and should be decomposed."""
        q_lower = query.lower()
        keywords = [
            "organize",
            "plan",
            "create and then",
            "for each",
            "step by step",
            "first",
            "then",
            "one by one",
            "in order",
            "sequentially",
            "list of steps",
            "how to",
        ]
        return any(kw in q_lower for kw in keywords)

    async def decompose(self, query: str) -> list[str]:
        """Decompose a query into ordered steps.

        Sends a one-shot LLM prompt asking for a JSON array of steps.
        Falls back to [query] if the LLM returns non-JSON or errors.
        """
        prompt = f"""You are a task planning assistant.
Break down the following complex task into numbered steps.
Return ONLY a valid JSON array of strings (each string is one step).
No explanation, no markdown, just the JSON array.

Task: {query}

JSON array:"""

        try:
            from core.inference.registry import TaskHint

            provider_name = self._runtime._registry.select_for_task(TaskHint.CHAT)
            chat = self._runtime._registry.get_chat(provider_name)
            response = await chat.complete([{"role": "user", "content": prompt}])

            # Extract JSON from response (handle markdown code fences, etc.)
            response = response.strip()
            if response.startswith("```"):
                lines = response.splitlines()
                response = "\n".join(
                    lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                )

            # Find first JSON array
            m = re.search(r"\[.*\]", response, re.DOTALL)
            if m:
                response = m.group(0)

            steps = json.loads(response)
            if isinstance(steps, list) and all(isinstance(s, str) for s in steps):
                return steps
        except Exception as e:
            logger.warning("TaskPlanner.decompose failed: {}", e)

        return [query]

    async def execute_plan(
        self, steps: list[str], agent_id: str
    ) -> AsyncIterator[tuple[int, str, AgentState]]:
        """Execute each step sequentially and yield (step_index, answer, state).

        This is a generator that yields the result of each step as it completes.
        """
        for i, step in enumerate(steps):
            logger.info("Executing step {}/{}: {}", i + 1, len(steps), step[:100])
            try:
                answer, final_state = await self._runtime.run(step, agent_id)
                yield i, answer, final_state
            except Exception as e:
                logger.exception("Step {} failed: {}", i, e)
                yield i, f"Step {i} failed: {e}", None

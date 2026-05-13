"""A7 — Multi-step Task Decomposition.

Decomposes complex queries into ordered sub-steps and executes them sequentially,
showing progress to the user.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Final

from loguru import logger
from pydantic import BaseModel, field_validator

if TYPE_CHECKING:
    from core.agents.runtime import AgentRuntime
    from core.agents.state_store import AgentState

MAX_STEPS_PER_TASK = 20
STEP_TIMEOUT_SEC = 300
MAX_FAILURES_ALLOWED = 5
COMPLEXITY_SCORE_THRESHOLD: Final = 2


class Step(BaseModel):
    """Validated step from task decomposition."""

    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Step content must not be empty")
        return v.strip()


class TaskPlanner:
    """Wraps AgentRuntime to handle multi-step task decomposition."""

    def __init__(self, runtime: AgentRuntime) -> None:
        self._runtime = runtime

    @staticmethod
    def is_complex_task(query: str) -> bool:
        """Heuristic to detect if a task is multi-step and should be decomposed.

        Uses weighted keyword scoring to reduce false positives/negatives.
        Strong keywords (weight=2): clear multi-step intent
        Weak keywords (weight=1): potential multi-step intent
        Threshold: score >= 2 indicates complex task
        """
        q_lower = query.lower()

        # Strong indicators of multi-step tasks (weight=2 each)
        strong_keywords = [
            "organize",
            "plan",
            "create and then",
            "for each",
            "step by step",
            "one by one",
            "in order",
            "sequentially",
            "list of steps",
        ]

        # Weak indicators - context-dependent (weight=1 each)
        weak_keywords = [
            "then",
            "first",
            "how to",
            "build",
            "set up",
            "configure",
        ]

        # Calculate weighted score
        score = sum(2 for kw in strong_keywords if kw in q_lower)
        score += sum(1 for kw in weak_keywords if kw in q_lower)

        return score >= COMPLEXITY_SCORE_THRESHOLD

    @staticmethod
    def _parse_step_response(response: str) -> list[str] | None:
        """Parse step response with multiple strategies.

        Returns parsed list of steps or None if all strategies fail.
        """
        response = response.strip()

        # Strategy 1: Direct JSON parse
        try:
            obj = json.loads(response)
            if isinstance(obj, list) and all(isinstance(s, str) for s in obj):
                return obj
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code fences
        if "```" in response:
            lines = response.splitlines()
            in_fence = False
            fence_lines = []
            for line in lines:
                if line.strip().startswith("```"):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    fence_lines.append(line)
            if fence_lines:
                fence_content = "\n".join(fence_lines).strip()
                try:
                    obj = json.loads(fence_content)
                    if isinstance(obj, list) and all(isinstance(s, str) for s in obj):
                        return obj
                except json.JSONDecodeError:
                    pass

        # Strategy 3: Extract from square brackets (greedy)
        bracket_matches = list(re.finditer(r"\[.*?\]", response, re.DOTALL))
        for m in bracket_matches:
            try:
                obj = json.loads(m.group(0))
                if isinstance(obj, list) and all(isinstance(s, str) for s in obj):
                    return obj
            except json.JSONDecodeError:
                continue

        # Strategy 4: Extract line-by-line numbered steps
        numbered_steps = []
        for line in response.splitlines():
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
                # Remove leading number/bullet
                clean = re.sub(r"^[\d\.\-\*\s]+", "", line).strip()
                if clean:
                    numbered_steps.append(clean)
        if numbered_steps:
            return numbered_steps

        return None

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

            # Try multiple parsing strategies
            steps = self._parse_step_response(response)
            if steps:
                logger.info("TaskPlanner.decompose succeeded: {} steps", len(steps))
                return steps
            else:
                logger.warning("TaskPlanner.decompose failed to parse response: {}", response[:100])
        except Exception as e:
            logger.exception("TaskPlanner.decompose LLM error: {}", e)

        return [query]

    async def execute_plan(
        self, steps: list[str], agent_id: str
    ) -> AsyncIterator[tuple[int, str, AgentState | None]]:
        """Execute each step sequentially with timeout and step limit protection.

        This is a generator that yields the result of each step as it completes.
        Enforces maximum step count and per-step timeout to prevent runaway execution.
        """
        if len(steps) > MAX_STEPS_PER_TASK:
            logger.warning(
                "Task contains {} steps, exceeds MAX_STEPS_PER_TASK ({}). "
                "Truncating to {} steps.",
                len(steps),
                MAX_STEPS_PER_TASK,
                MAX_STEPS_PER_TASK,
            )
            steps = steps[:MAX_STEPS_PER_TASK]

        start_time = time.time()
        consecutive_failures = 0

        for i, step in enumerate(steps):
            logger.info("Executing step {}/{}: {}", i + 1, len(steps), step[:100])
            try:
                answer, final_state = await asyncio.wait_for(
                    self._runtime.run(step, agent_id), timeout=STEP_TIMEOUT_SEC
                )
                yield i, answer, final_state
                consecutive_failures = 0
            except TimeoutError:
                consecutive_failures += 1
                msg = f"Step {i} timed out after {STEP_TIMEOUT_SEC}s"
                logger.warning(msg)
                yield i, msg, None
                if consecutive_failures >= MAX_FAILURES_ALLOWED:
                    logger.error(
                        "Max consecutive failures ({}) reached. Aborting remaining {} steps.",
                        MAX_FAILURES_ALLOWED,
                        len(steps) - i - 1,
                    )
                    break
            except Exception as e:
                consecutive_failures += 1
                logger.exception("Step {} failed: {}", i, e)
                yield i, f"Step {i} failed: {e}", None
                if consecutive_failures >= MAX_FAILURES_ALLOWED:
                    logger.error(
                        "Max consecutive failures ({}) reached. Aborting remaining {} steps.",
                        MAX_FAILURES_ALLOWED,
                        len(steps) - i - 1,
                    )
                    break

        total_time = time.time() - start_time
        logger.info(
            "Plan execution completed: {}/{} steps, {:.1f}s elapsed",
            i + 1,
            len(steps),
            total_time,
        )

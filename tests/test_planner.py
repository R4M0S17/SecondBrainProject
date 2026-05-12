"""Tests for A7 — Task Planner."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agents.planner import TaskPlanner
from core.agents.state_store import AgentProfile, AgentState, ToolCall


def _make_profile(agent_id: str = "test-agent") -> AgentProfile:
    now = datetime.now(UTC).isoformat()
    return AgentProfile(
        id=agent_id,
        name=agent_id,
        domain_tags=["general"],
        authorized_tools=[],
        preferences={"instructions": "Sé conciso."},
        created_at=now,
        updated_at=now,
    )


def _make_state(agent_id: str = "test-agent") -> AgentState:
    return AgentState(
        profile=_make_profile(agent_id),
        session_summary="",
        working_memory={"goal": "planning"},
        tool_trace=[],
        semantic_memory_refs=[],
        execution_count=0,
        last_active=datetime.now(UTC).isoformat(),
    )


def test_is_complex_task_detects_keywords():
    """is_complex_task() should identify planning keywords."""
    assert TaskPlanner.is_complex_task("organize my files into folders")
    assert TaskPlanner.is_complex_task("plan my week")
    assert TaskPlanner.is_complex_task("create and then organize the files")
    assert TaskPlanner.is_complex_task("for each file in the folder do something")
    assert TaskPlanner.is_complex_task("step by step: first create, then organize")


def test_is_complex_task_returns_false_for_simple():
    """is_complex_task() should return False for simple queries."""
    assert not TaskPlanner.is_complex_task("what is the weather today")
    assert not TaskPlanner.is_complex_task("who is the president")
    assert not TaskPlanner.is_complex_task("tell me a joke")


@pytest.mark.asyncio
async def test_decompose_returns_list():
    """decompose() should return a list of step strings."""
    runtime = MagicMock()
    runtime._registry = MagicMock()

    planner = TaskPlanner(runtime)

    # Mock the LLM response
    json_response = json.dumps(
        ["Step 1: Gather requirements", "Step 2: Design solution", "Step 3: Implement"]
    )

    with patch.object(runtime._registry, "select_for_task", return_value="test-provider"):
        with patch.object(
            runtime._registry, "get_chat", return_value=AsyncMock()
        ) as mock_get_chat:
            mock_chat = AsyncMock()
            mock_chat.complete = AsyncMock(return_value=json_response)
            mock_get_chat.return_value = mock_chat

            steps = await planner.decompose("Plan my project")
            assert isinstance(steps, list)
            assert len(steps) == 3
            assert "Step 1" in steps[0]


@pytest.mark.asyncio
async def test_decompose_fallback_on_non_json():
    """decompose() should return [query] if LLM returns invalid JSON."""
    runtime = MagicMock()
    runtime._registry = MagicMock()

    planner = TaskPlanner(runtime)

    with patch.object(runtime._registry, "select_for_task", return_value="test-provider"):
        with patch.object(
            runtime._registry, "get_chat", return_value=AsyncMock()
        ) as mock_get_chat:
            mock_chat = AsyncMock()
            mock_chat.complete = AsyncMock(return_value="This is not JSON")
            mock_get_chat.return_value = mock_chat

            query = "Plan my project"
            steps = await planner.decompose(query)
            assert steps == [query]


@pytest.mark.asyncio
async def test_decompose_handles_markdown_code_fences():
    """decompose() should extract JSON from markdown code fences."""
    runtime = MagicMock()
    runtime._registry = MagicMock()

    planner = TaskPlanner(runtime)

    json_response = r"""
Here's your plan:
```json
["Step 1", "Step 2", "Step 3"]
```
"""

    with patch.object(runtime._registry, "select_for_task", return_value="test-provider"):
        with patch.object(
            runtime._registry, "get_chat", return_value=AsyncMock()
        ) as mock_get_chat:
            mock_chat = AsyncMock()
            mock_chat.complete = AsyncMock(return_value=json_response)
            mock_get_chat.return_value = mock_chat

            steps = await planner.decompose("Plan my project")
            assert len(steps) == 3


@pytest.mark.asyncio
async def test_execute_plan_runs_each_step():
    """execute_plan() should call runtime.run() for each step and yield results."""
    runtime = MagicMock()
    agent_id = "test-agent"

    planner = TaskPlanner(runtime)

    # Mock runtime.run() to return deterministic answers
    async def mock_run(step, aid):
        state = _make_state(aid)
        return f"Answer to: {step}", state

    runtime.run = AsyncMock(side_effect=mock_run)

    steps = ["Step 1: Do A", "Step 2: Do B", "Step 3: Do C"]
    results = []

    async for step_idx, answer, state in planner.execute_plan(steps, agent_id):
        results.append((step_idx, answer))

    assert len(results) == 3
    assert results[0] == (0, "Answer to: Step 1: Do A")
    assert results[1] == (1, "Answer to: Step 2: Do B")
    assert results[2] == (2, "Answer to: Step 3: Do C")


@pytest.mark.asyncio
async def test_execute_plan_continues_on_error():
    """execute_plan() should yield error message and continue to next step on failure."""
    runtime = MagicMock()
    agent_id = "test-agent"

    planner = TaskPlanner(runtime)

    call_count = [0]

    async def mock_run_with_error(step, aid):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("Step 2 failed")
        state = _make_state(aid)
        return f"Answer to: {step}", state

    runtime.run = AsyncMock(side_effect=mock_run_with_error)

    steps = ["Step 1", "Step 2 (will fail)", "Step 3"]
    results = []

    async for step_idx, answer, state in planner.execute_plan(steps, agent_id):
        results.append((step_idx, answer, state is not None))

    assert len(results) == 3
    assert results[0][2] is True  # Step 0 succeeded
    assert "failed" in results[1][1].lower()  # Step 1 error message
    assert results[1][2] is False  # Step 1 state is None
    assert results[2][2] is True  # Step 2 succeeded

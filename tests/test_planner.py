"""Tests for A7 — Task Planner."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agents.planner import (
    MAX_FAILURES_ALLOWED,
    MAX_STEPS_PER_TASK,
    STEP_TIMEOUT_SEC,
    TaskPlanner,
)
from core.agents.state_store import AgentProfile, AgentState


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
        with patch.object(runtime._registry, "get_chat", return_value=AsyncMock()) as mock_get_chat:
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
        with patch.object(runtime._registry, "get_chat", return_value=AsyncMock()) as mock_get_chat:
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
        with patch.object(runtime._registry, "get_chat", return_value=AsyncMock()) as mock_get_chat:
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


@pytest.mark.asyncio
async def test_execute_plan_enforces_max_steps():
    """execute_plan() should truncate steps exceeding MAX_STEPS_PER_TASK."""
    runtime = MagicMock()
    agent_id = "test-agent"

    planner = TaskPlanner(runtime)

    async def mock_run(step, aid):
        state = _make_state(aid)
        return f"Answer: {step}", state

    runtime.run = AsyncMock(side_effect=mock_run)

    # Create more steps than MAX_STEPS_PER_TASK
    steps = [f"Step {i}" for i in range(MAX_STEPS_PER_TASK + 5)]
    results = []

    async for step_idx, answer, state in planner.execute_plan(steps, agent_id):
        results.append(step_idx)

    assert len(results) == MAX_STEPS_PER_TASK
    assert runtime.run.call_count == MAX_STEPS_PER_TASK


@pytest.mark.asyncio
async def test_execute_plan_step_timeout():
    """execute_plan() should catch timeout errors and continue execution."""
    runtime = MagicMock()
    agent_id = "test-agent"

    planner = TaskPlanner(runtime)

    call_count = [0]

    async def mock_run_with_timeout(step, aid):
        call_count[0] += 1
        if call_count[0] == 2:
            # Simulate timeout by sleeping longer than STEP_TIMEOUT_SEC
            await asyncio.sleep(STEP_TIMEOUT_SEC + 1)
        state = _make_state(aid)
        return f"Answer: {step}", state

    runtime.run = AsyncMock(side_effect=mock_run_with_timeout)

    steps = ["Step 1", "Step 2 (timeout)", "Step 3"]
    results = []

    async for step_idx, answer, state in planner.execute_plan(steps, agent_id):
        results.append((step_idx, answer, state))

    assert len(results) == 3
    assert "timed out" in results[1][1].lower()
    assert results[1][2] is None  # state should be None for timeout


@pytest.mark.asyncio
async def test_execute_plan_circuit_breaker_on_failures():
    """execute_plan() should stop after MAX_FAILURES_ALLOWED consecutive failures."""
    runtime = MagicMock()
    agent_id = "test-agent"

    planner = TaskPlanner(runtime)

    call_count = [0]

    async def mock_run_all_fail(step, aid):
        call_count[0] += 1
        raise RuntimeError(f"Step {step} failed")

    runtime.run = AsyncMock(side_effect=mock_run_all_fail)

    # Create enough steps to exceed MAX_FAILURES_ALLOWED
    steps = [f"Step {i}" for i in range(MAX_FAILURES_ALLOWED + 5)]
    results = []

    async for step_idx, answer, state in planner.execute_plan(steps, agent_id):
        results.append((step_idx, answer))

    # Should stop after MAX_FAILURES_ALLOWED failures
    assert len(results) == MAX_FAILURES_ALLOWED
    assert runtime.run.call_count == MAX_FAILURES_ALLOWED


@pytest.mark.asyncio
async def test_execute_plan_failure_counter_resets_on_success():
    """execute_plan() should continue past MAX_FAILURES_ALLOWED if there are successes."""
    runtime = MagicMock()
    agent_id = "test-agent"

    planner = TaskPlanner(runtime)

    call_count = [0]

    async def mock_run_alternating(step, aid):
        call_count[0] += 1
        state = _make_state(aid)
        # Fail on odd calls, succeed on even
        if call_count[0] % 2 == 1:
            raise RuntimeError("Step failed")
        return f"Answer: {step}", state

    runtime.run = AsyncMock(side_effect=mock_run_alternating)

    steps = [f"Step {i}" for i in range(10)]
    results = []

    async for step_idx, answer, state in planner.execute_plan(steps, agent_id):
        results.append((step_idx, answer, state is not None))

    # All steps should execute since failures and successes alternate
    assert len(results) == 10
    assert runtime.run.call_count == 10


def test_parse_step_response_direct_json():
    """_parse_step_response() should parse valid JSON directly."""
    response = '["Step 1", "Step 2", "Step 3"]'
    steps = TaskPlanner._parse_step_response(response)
    assert steps == ["Step 1", "Step 2", "Step 3"]


def test_parse_step_response_markdown_fences():
    """_parse_step_response() should extract JSON from markdown fences."""
    response = """Here's your plan:
```json
["Step 1", "Step 2"]
```
Done."""
    steps = TaskPlanner._parse_step_response(response)
    assert steps == ["Step 1", "Step 2"]


def test_parse_step_response_greedy_brackets():
    """_parse_step_response() should extract JSON from multiple bracket sets."""
    response = 'Some text ["Step A"] more text ["Step 1", "Step 2"] end'
    steps = TaskPlanner._parse_step_response(response)
    # Should find the first valid JSON array with multiple items
    assert steps == ["Step 1", "Step 2"]


def test_parse_step_response_numbered_lines():
    """_parse_step_response() should fall back to numbered lines."""
    response = """1. Create a file
2. Edit the file
3. Save the file"""
    steps = TaskPlanner._parse_step_response(response)
    assert len(steps) == 3
    assert steps[0] == "Create a file"
    assert steps[1] == "Edit the file"
    assert steps[2] == "Save the file"


def test_parse_step_response_bullet_points():
    """_parse_step_response() should handle bullet points."""
    response = """- First task
- Second task
* Third task"""
    steps = TaskPlanner._parse_step_response(response)
    assert len(steps) == 3
    assert "First task" in steps[0]
    assert "Second task" in steps[1]
    assert "Third task" in steps[2]


def test_parse_step_response_invalid_json_fallback():
    """_parse_step_response() should return None if all strategies fail."""
    response = "This is just plain text with no structured data"
    steps = TaskPlanner._parse_step_response(response)
    assert steps is None


def test_parse_step_response_empty_array():
    """_parse_step_response() should reject empty arrays."""
    response = "[]"
    steps = TaskPlanner._parse_step_response(response)
    assert steps is None


def test_parse_step_response_non_string_items():
    """_parse_step_response() should reject arrays with non-string items."""
    response = '["Step 1", 2, "Step 3"]'
    steps = TaskPlanner._parse_step_response(response)
    assert steps is None


def test_is_complex_task_strong_keywords():
    """Strong keywords (weight=2) alone should trigger decomposition."""
    assert TaskPlanner.is_complex_task("organize my files")
    assert TaskPlanner.is_complex_task("step by step guide")
    assert TaskPlanner.is_complex_task("for each item do something")


def test_is_complex_task_weak_keywords_need_multiple():
    """Weak keywords (weight=1) need multiple to trigger decomposition."""
    # Single weak keyword should NOT trigger
    assert not TaskPlanner.is_complex_task("tell me how to bake a cake")
    assert not TaskPlanner.is_complex_task("what happens then?")

    # Multiple weak keywords should trigger (score >= 2)
    assert TaskPlanner.is_complex_task("first do this, then do that")
    assert TaskPlanner.is_complex_task("how to build and configure this")


def test_is_complex_task_mixed_keywords():
    """Mix of strong and weak keywords should trigger."""
    assert TaskPlanner.is_complex_task("plan and then execute")
    assert TaskPlanner.is_complex_task("organize files, first sort them")


def test_is_complex_task_reduces_false_positives():
    """Improved heuristic should avoid false positives."""
    # These should NOT be decomposed (no strong keywords, insufficient weak)
    assert not TaskPlanner.is_complex_task("what is the weather today?")
    assert not TaskPlanner.is_complex_task("tell me a joke")
    assert not TaskPlanner.is_complex_task("who won the game yesterday?")


def test_is_complex_task_catches_real_multistep():
    """Should catch clear multi-step tasks."""
    assert TaskPlanner.is_complex_task("build a website and then deploy it")
    assert TaskPlanner.is_complex_task("organize files into folders, then archive them")
    assert TaskPlanner.is_complex_task("create project structure step by step")

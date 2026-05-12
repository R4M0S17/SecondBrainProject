"""Tests for Module 7 — Agent Orchestration (LangGraph kernel)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.agents.kernel import MAX_ITERATIONS, MAX_TOOL_CALLS, AgentState, CerebroKernel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kernel(
    responses: list[str],
    tools: dict | None = None,
) -> CerebroKernel:
    """Build a CerebroKernel whose provider replays the given response list."""
    responses_iter = iter(responses)

    async def fake_complete(messages, **_kwargs):
        try:
            return next(responses_iter)
        except StopIteration:
            return '{"action": "answer", "answer": "fallback"}'

    mock_provider = MagicMock()
    mock_provider.complete = fake_complete

    return CerebroKernel(provider=mock_provider, tools=tools or {})


# ---------------------------------------------------------------------------
# Test 1: Agent resolves a 2-step task that requires one tool use
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_resolves_two_step_task_with_tool():
    """Kernel must call a tool, observe result, then produce a final answer."""
    kernel = _make_kernel(
        responses=[
            '{"action": "tool", "tool": "get_info", "args": {"item_id": "42"}}',
            '{"action": "answer", "answer": "El resultado es: data_42"}',
        ],
        tools={"get_info": lambda item_id: f"data_{item_id}"},
    )

    result = await kernel.run([{"role": "user", "content": "Dame info del ítem 42"}])

    assert isinstance(result, AgentState)
    assert result.final_answer is not None
    assert "data_42" in result.final_answer
    assert "get_info" in result.tools_called
    assert result.iterations == 2


# ---------------------------------------------------------------------------
# Test 2: Agent respects the max iterations limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_respects_max_iterations():
    """When the provider keeps requesting tools, the kernel must stop at MAX_ITERATIONS."""
    # Provider always wants another tool call — kernel must break the loop
    always_tool = [
        f'{{"action": "tool", "tool": "inf_tool", "args": {{"n": {i}}}}}'
        for i in range(MAX_ITERATIONS + 5)
    ]
    kernel = _make_kernel(
        responses=always_tool,
        tools={"inf_tool": lambda n: f"result_{n}"},
    )

    result = await kernel.run([{"role": "user", "content": "Loop"}])

    assert result.final_answer is not None
    assert result.iterations <= MAX_ITERATIONS
    assert len(result.tools_called) <= MAX_TOOL_CALLS


# ---------------------------------------------------------------------------
# Test 3: Duplicate tool call detection aborts the loop correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_detects_and_aborts_duplicate_tool_call():
    """If the LLM requests the same tool with the same args twice, the kernel
    must detect the duplicate, force a final answer, and not loop infinitely."""
    call_count = 0

    async def same_call_twice(messages, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            # Same tool, same args — second occurrence must be caught
            return '{"action": "tool", "tool": "dup_tool", "args": {"x": 1}}'
        return '{"action": "answer", "answer": "done"}'

    mock_provider = MagicMock()
    mock_provider.complete = same_call_twice

    kernel = CerebroKernel(
        provider=mock_provider,
        tools={"dup_tool": lambda x: f"value_{x}"},
    )

    result = await kernel.run([{"role": "user", "content": "Llama la herramienta"}])

    # Must terminate with a non-empty answer
    assert isinstance(result, AgentState)
    assert result.final_answer is not None
    assert len(result.final_answer) > 0
    # The duplicate was detected — dup_tool called only once
    assert result.tools_called.count("dup_tool") == 1

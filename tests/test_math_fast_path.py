"""Tests for FIX_TEST2 H3.1 — zero-token math fast path."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.math_fast_path import extract_pure_math_expression, try_pure_math_fast_path
from core.agents.runtime import AgentRuntime
from core.agents.state_store import AgentStateStore
from core.inference.registry import ProviderRegistry


def test_extract_pure_expression():
    assert extract_pure_math_expression("17 * 23") == "17 * 23"
    assert extract_pure_math_expression("  450 * 1.16  ") == "450 * 1.16"
    assert extract_pure_math_expression("17×23?") == "17*23"


def test_extract_embedded_in_english_prompt():
    assert extract_pure_math_expression("What is 17 × 23? Show only the number.") == "17 * 23"


def test_extract_rejects_non_math():
    assert extract_pure_math_expression("hello") is None
    assert extract_pure_math_expression("391") is None
    assert extract_pure_math_expression("What is seventeen times twenty-three?") is None


def test_try_pure_math_fast_path():
    assert try_pure_math_fast_path("17*23", ["evaluate_math"]) == "391"
    assert try_pure_math_fast_path("17*23", ["read_file"]) is None
    assert try_pure_math_fast_path("10/0", ["evaluate_math"]) is None


@pytest.mark.asyncio
async def test_runtime_math_fast_path_bypasses_llm(tmp_path):
    agent_id = "general-v1"
    store = AgentStateStore(state_dir=str(tmp_path))
    state = store.load(agent_id)
    state.profile.authorized_tools = ["evaluate_math"]
    store.save(state)

    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(return_value='{"action":"answer","answer":"wrong"}')
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    mock_builder = MagicMock()
    mock_builder._short_term = MagicMock()
    mock_builder._short_term.push_message = MagicMock()

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=mock_builder,
        tool_registry={},
    )

    answer, _ = await runtime.run("17 * 23", agent_id)
    assert answer == "391"
    mock_chat.complete.assert_not_called()


@pytest.mark.asyncio
async def test_runtime_phrased_math_fast_path(tmp_path):
    agent_id = "general-v1"
    store = AgentStateStore(state_dir=str(tmp_path))
    state = store.load(agent_id)
    state.profile.authorized_tools = ["evaluate_math"]
    store.save(state)

    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(return_value='{"action":"answer","answer":"397"}')
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    mock_builder = MagicMock()
    mock_builder._short_term = MagicMock()
    mock_builder._short_term.push_message = MagicMock()

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=mock_builder,
        tool_registry={},
    )

    answer, _ = await runtime.run("What is 17 × 23? Show only the number.", agent_id)
    assert answer == "391"
    mock_chat.complete.assert_not_called()

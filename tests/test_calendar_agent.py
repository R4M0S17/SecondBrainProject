"""Module 7.3 — Calendar Agent integration tests.

Verifies that POST /api/query with agent="calendar-v1" returns a valid response
and that calendar tool calls surface in metadata.tools_called.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.specialized import CALENDAR_AGENT_ID, CALENDAR_TOOLS
from core.agents.state_store import AgentProfile, AgentState, ToolCall
from core.observability.response_meta import MetricsCollector
from ui.tray.server import app, app_state

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_state():
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    yield
    app_state.runtime = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _make_calendar_state(tool_calls: list[ToolCall] | None = None) -> AgentState:
    now = "2026-01-01T00:00:00Z"
    profile = AgentProfile(
        id=CALENDAR_AGENT_ID,
        name="Asistente de Calendario",
        domain_tags=["calendar"],
        authorized_tools=CALENDAR_TOOLS,
        preferences={},
        created_at=now,
        updated_at=now,
    )
    return AgentState(
        profile=profile,
        session_summary="",
        working_memory={},
        tool_trace=tool_calls or [],
        semantic_memory_refs=[],
        execution_count=1,
        last_active=now,
    )


@pytest.fixture
def mock_runtime():
    rt = AsyncMock()
    rt.run.return_value = ("Tienes una reunión mañana a las 10:00.", _make_calendar_state())
    rt._state_store = MagicMock()
    rt._state_store.load.return_value = _make_calendar_state()
    app_state.runtime = rt
    return rt


@pytest.fixture
def mock_runtime_with_tool_call():
    tc = ToolCall(
        tool_name="get_upcoming_events",
        args={"hours_ahead": 24},
        result="- Team standup at 2026-01-02 10:00 UTC",
    )
    state_with_tool = _make_calendar_state(tool_calls=[tc])

    rt = AsyncMock()
    rt.run.return_value = ("Tienes una reunión: Team standup.", state_with_tool)
    # pre-run snapshot returns empty trace so the new tool call is isolated
    rt._state_store = MagicMock()
    rt._state_store.load.return_value = _make_calendar_state(tool_calls=[])
    app_state.runtime = rt
    return rt


# ──────────────────────────────────────────────────────────────────────────────
# 7.3 — POST /api/query with calendar-v1 returns valid response
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_calendar_agent_query_returns_200(client, mock_runtime):
    async with client as c:
        resp = await c.post(
            "/api/query",
            json={"question": "¿Qué tengo mañana?", "agent": "calendar-v1"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_calendar_agent_query_returns_answer_and_metadata(client, mock_runtime):
    async with client as c:
        resp = await c.post(
            "/api/query",
            json={"question": "¿Qué tengo mañana?", "agent": "calendar-v1"},
        )
    data = resp.json()
    assert "answer" in data
    assert "metadata" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0


@pytest.mark.asyncio
async def test_calendar_agent_sets_active_agent(client, mock_runtime):
    async with client as c:
        await c.post(
            "/api/query",
            json={"question": "¿Qué tengo?", "agent": "calendar-v1"},
        )
    assert app_state.active_agent_id == CALENDAR_AGENT_ID


@pytest.mark.asyncio
async def test_calendar_agent_runtime_called_with_correct_agent_id(client, mock_runtime):
    async with client as c:
        await c.post(
            "/api/query",
            json={"question": "muéstrame mis eventos", "agent": "calendar-v1"},
        )
    mock_runtime.run.assert_called_once()
    _query, agent_id = mock_runtime.run.call_args.args
    assert agent_id == CALENDAR_AGENT_ID


# ──────────────────────────────────────────────────────────────────────────────
# 7.3 — Calendar tools appear in metadata.tools_called
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_calendar_tools_appear_in_metadata(client, mock_runtime_with_tool_call):
    async with client as c:
        resp = await c.post(
            "/api/query",
            json={"question": "¿Qué eventos tengo?", "agent": "calendar-v1"},
        )
    data = resp.json()
    tools_called = data["metadata"]["tools_called"]
    assert len(tools_called) == 1
    assert tools_called[0]["name"] == "get_upcoming_events"


@pytest.mark.asyncio
async def test_calendar_tool_call_has_expected_fields(client, mock_runtime_with_tool_call):
    async with client as c:
        resp = await c.post(
            "/api/query",
            json={"question": "muéstrame eventos", "agent": "calendar-v1"},
        )
    tool = resp.json()["metadata"]["tools_called"][0]
    assert "name" in tool
    assert "args_summary" in tool
    assert "result_summary" in tool
    assert "latency_ms" in tool
    assert "approved" in tool

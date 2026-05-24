"""Tests for Module 9 — Tool Confirmation Flow."""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.conversation_store import ConversationStore
from core.agents.runtime import CONFIRMATION_REQUIRED_TOOLS
from core.agents.state_store import AgentProfile, AgentState
from core.observability.response_meta import MetricsCollector
from ui.tray.server import app, app_state

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    app_state._pending_tools = {}
    app_state.conv_store = ConversationStore(str(tmp_path))
    yield
    app_state.runtime = None
    app_state._pending_tools = {}
    app_state.conv_store = ConversationStore(str(tmp_path))


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _make_agent_state(pending_tool_name=None, pending_tool_args=None):
    from datetime import datetime

    now = datetime.now(UTC).isoformat()
    state = AgentState(
        profile=AgentProfile(
            id="general-v1",
            name="General",
            domain_tags=[],
            authorized_tools=[],
            preferences={},
            created_at=now,
            updated_at=now,
        ),
        session_summary="",
        working_memory={},
        tool_trace=[],
        semantic_memory_refs=[],
        execution_count=1,
        last_active=now,
    )
    state.pending_tool_name = pending_tool_name
    state.pending_tool_args = pending_tool_args
    return state


# ──────────────────────────────────────────────────────────────────────────────
# CONFIRMATION_REQUIRED_TOOLS constant
# ──────────────────────────────────────────────────────────────────────────────


def test_confirmation_required_tools_contains_write_file():
    assert "write_file" in CONFIRMATION_REQUIRED_TOOLS


def test_confirmation_required_tools_contains_execute_python():
    assert "execute_python" in CONFIRMATION_REQUIRED_TOOLS


def test_confirmation_required_tools_contains_create_calendar_event():
    assert "create_calendar_event" in CONFIRMATION_REQUIRED_TOOLS


def test_confirmation_required_tools_contains_add_reminder():
    assert "add_reminder" in CONFIRMATION_REQUIRED_TOOLS


# ──────────────────────────────────────────────────────────────────────────────
# AgentRuntime._requires_confirmation
# ──────────────────────────────────────────────────────────────────────────────


def test_requires_confirmation_uses_registry_flag():
    from core.agents.runtime import AgentRuntime
    from core.inference.registry import ProviderRegistry
    from core.tools.registry import AuditLevel, ToolDefinition, ToolRegistry, ToolScope

    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="create_calendar_event",
            description="",
            handler=lambda **_: "",
            required_permission="tools.calendar.write",
            requires_confirmation=True,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.FULL,
        )
    )
    reg.register(
        ToolDefinition(
            name="get_upcoming_events",
            description="",
            handler=lambda **_: "",
            required_permission="tools.calendar.read",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
        )
    )

    runtime = AgentRuntime(
        registry=MagicMock(spec=ProviderRegistry),
        state_store=MagicMock(),
        context_builder=MagicMock(),
        tool_definitions=reg.definitions(),
    )

    assert runtime._requires_confirmation("create_calendar_event") is True
    assert runtime._requires_confirmation("get_upcoming_events") is False


def test_requires_confirmation_fallback_without_definition():
    from core.agents.runtime import AgentRuntime
    from core.inference.registry import ProviderRegistry

    runtime = AgentRuntime(
        registry=MagicMock(spec=ProviderRegistry),
        state_store=MagicMock(),
        context_builder=MagicMock(),
        tool_definitions={},
    )

    assert runtime._requires_confirmation("write_file") is True
    assert runtime._requires_confirmation("not_a_tool") is False


def test_confirm_tool_pause_message_default_spanish():
    from core.i18n.messages import _L

    msg = _L("confirm.tool_pause", tool_name="write_file")
    assert "write_file" in msg
    assert "aprobación" in msg.lower()


@pytest.mark.asyncio
async def test_create_calendar_event_pauses_for_confirmation(tmp_path):
    from core.agents.runtime import AgentRuntime
    from core.agents.specialized import CALENDAR_AGENT_ID, make_calendar_profile
    from core.agents.state_store import AgentStateStore
    from core.inference.registry import ProviderRegistry
    from core.tools.registry import ToolRegistry, register_calendar_tools

    store = AgentStateStore(state_dir=str(tmp_path))
    calendar_state = store.load(CALENDAR_AGENT_ID)
    calendar_state.profile = make_calendar_profile()
    store.save(calendar_state)

    tool_reg = ToolRegistry()
    register_calendar_tools(tool_reg)

    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(
        return_value=(
            '{"action": "tool", "tool": "create_calendar_event", '
            '"args": {"title": "Cerebro smoke", "datetime_str": "tomorrow 4pm"}}'
        )
    )
    mock_chat.context_window = MagicMock(return_value=4096)

    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    mock_context = MagicMock()
    mock_context.retrieved_memory = []
    mock_context.session_history = []
    mock_context.retrieved_documents = []
    mock_context.agent_summary = ""
    mock_context.total_tokens_estimated = 10
    mock_context.sources_used = []

    mock_builder = MagicMock()
    mock_builder.maybe_consolidate = AsyncMock(return_value=False)
    mock_builder.build = AsyncMock(return_value=mock_context)

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=mock_builder,
        tool_registry=tool_reg.handlers(),
        tool_definitions=tool_reg.definitions(),
    )

    answer, final_state = await runtime.run("crea evento mañana 4pm", CALENDAR_AGENT_ID)

    assert final_state.pending_tool_name == "create_calendar_event"
    assert "create_calendar_event" in answer
    assert "aprobación" in answer.lower()


# ──────────────────────────────────────────────────────────────────────────────
# AgentState transient fields
# ──────────────────────────────────────────────────────────────────────────────


def test_agent_state_pending_tool_defaults_to_none():
    state = _make_agent_state()
    assert state.pending_tool_name is None
    assert state.pending_tool_args is None


def test_agent_state_pending_tool_fields_settable():
    state = _make_agent_state(
        pending_tool_name="write_file", pending_tool_args={"path": "/tmp/x.txt", "content": "hi"}
    )
    assert state.pending_tool_name == "write_file"
    assert state.pending_tool_args == {"path": "/tmp/x.txt", "content": "hi"}


# ──────────────────────────────────────────────────────────────────────────────
# /api/query — pending_tool in response when runtime signals it
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_returns_pending_tool_when_runtime_signals(client):
    final_state = _make_agent_state(
        pending_tool_name="write_file",
        pending_tool_args={"path": "/tmp/test.txt", "content": "hello"},
    )
    rt = AsyncMock()
    rt.run.return_value = (
        "Necesito tu aprobación para ejecutar `write_file`.",
        final_state,
    )
    app_state.runtime = rt

    async with client as c:
        r = await c.post("/api/query", json={"question": "write a file", "agent": "general-v1"})

    assert r.status_code == 200
    body = r.json()
    assert body["metadata"]["pending_tool"] is not None
    assert body["metadata"]["pending_tool"]["name"] == "write_file"


@pytest.mark.asyncio
async def test_query_stores_pending_tool_in_app_state(client):
    final_state = _make_agent_state(
        pending_tool_name="write_file",
        pending_tool_args={"path": "/tmp/test.txt", "content": "hello"},
    )
    rt = AsyncMock()
    rt.run.return_value = ("Necesito aprobación.", final_state)
    app_state.runtime = rt

    async with client as c:
        r = await c.post("/api/query", json={"question": "write a file", "agent": "general-v1"})

    body = r.json()
    conv_id = body["conversation_id"]
    assert conv_id in app_state._pending_tools
    assert app_state._pending_tools[conv_id]["tool_name"] == "write_file"


@pytest.mark.asyncio
async def test_query_no_pending_tool_when_runtime_completes_normally(client):
    final_state = _make_agent_state()  # pending_tool_name=None
    rt = AsyncMock()
    rt.run.return_value = ("Respuesta normal.", final_state)
    app_state.runtime = rt

    async with client as c:
        r = await c.post("/api/query", json={"question": "hello", "agent": "general-v1"})

    assert r.status_code == 200
    assert r.json()["metadata"]["pending_tool"] is None


# ──────────────────────────────────────────────────────────────────────────────
# /api/tool-confirm — approve path
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_confirm_approve_executes_tool(client):
    conv_id = app_state.conv_store.create("general-v1")
    app_state._pending_tools[conv_id] = {
        "tool_name": "write_file",
        "tool_args": {"path": "/tmp/x.txt", "content": "hi"},
        "agent_id": "general-v1",
    }

    mock_handler = MagicMock(return_value="File written successfully.")
    rt = MagicMock()
    rt._tool_registry = {"write_file": mock_handler}
    app_state.runtime = rt

    async with client as c:
        r = await c.post(
            "/api/tool-confirm", json={"conversation_id": conv_id, "decision": "approve"}
        )

    assert r.status_code == 200
    body = r.json()
    assert "write_file" in body["answer"]
    assert "File written successfully." in body["answer"]
    assert body["metadata"]["tools_called"][0]["approved"] is True


@pytest.mark.asyncio
async def test_tool_confirm_approve_removes_pending_entry(client):
    conv_id = app_state.conv_store.create("general-v1")
    app_state._pending_tools[conv_id] = {
        "tool_name": "write_file",
        "tool_args": {},
        "agent_id": "general-v1",
    }
    rt = MagicMock()
    rt._tool_registry = {"write_file": MagicMock(return_value="ok")}
    app_state.runtime = rt

    async with client as c:
        await c.post("/api/tool-confirm", json={"conversation_id": conv_id, "decision": "approve"})

    assert conv_id not in app_state._pending_tools


# ──────────────────────────────────────────────────────────────────────────────
# /api/tool-confirm — deny path
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_confirm_deny_skips_tool(client):
    conv_id = app_state.conv_store.create("general-v1")
    app_state._pending_tools[conv_id] = {
        "tool_name": "write_file",
        "tool_args": {"path": "/tmp/x.txt"},
        "agent_id": "general-v1",
    }

    async with client as c:
        r = await c.post("/api/tool-confirm", json={"conversation_id": conv_id, "decision": "deny"})

    assert r.status_code == 200
    body = r.json()
    assert "write_file" in body["answer"]
    assert body["metadata"]["tools_called"][0]["approved"] is False


@pytest.mark.asyncio
async def test_tool_confirm_deny_removes_pending_entry(client):
    conv_id = app_state.conv_store.create("general-v1")
    app_state._pending_tools[conv_id] = {
        "tool_name": "write_file",
        "tool_args": {},
        "agent_id": "general-v1",
    }

    async with client as c:
        await c.post("/api/tool-confirm", json={"conversation_id": conv_id, "decision": "deny"})

    assert conv_id not in app_state._pending_tools


# ──────────────────────────────────────────────────────────────────────────────
# /api/tool-confirm — error paths
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_confirm_returns_404_for_unknown_conv(client):
    async with client as c:
        r = await c.post(
            "/api/tool-confirm", json={"conversation_id": "nonexistent", "decision": "approve"}
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_tool_confirm_returns_200_even_if_tool_handler_raises(client):
    conv_id = app_state.conv_store.create("general-v1")
    app_state._pending_tools[conv_id] = {
        "tool_name": "write_file",
        "tool_args": {},
        "agent_id": "general-v1",
    }
    rt = MagicMock()
    rt._tool_registry = {"write_file": MagicMock(side_effect=RuntimeError("disk full"))}
    app_state.runtime = rt

    async with client as c:
        r = await c.post(
            "/api/tool-confirm", json={"conversation_id": conv_id, "decision": "approve"}
        )

    assert r.status_code == 200
    assert "Error" in r.json()["answer"]

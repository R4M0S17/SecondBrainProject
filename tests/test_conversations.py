"""Tests for Module 8 — Conversation History API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.conversation_store import ConversationStore
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
    app_state.conv_store = ConversationStore(str(tmp_path))
    yield
    app_state.runtime = None
    app_state.conv_store = ConversationStore(str(tmp_path))


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def mock_runtime():
    rt = AsyncMock()
    rt.run.return_value = (
        "Test answer.",
        MagicMock(tool_trace=[], pending_tool_name=None, pending_tool_args=None),
    )
    app_state.runtime = rt
    return rt


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/conversations
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_conversations_empty(client):
    async with client as c:
        resp = await c.get("/api/conversations")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_conversations_after_query(client, mock_runtime):
    async with client as c:
        await c.post("/api/query", json={"question": "first question"})
        resp = await c.get("/api/conversations")
    convs = resp.json()
    assert len(convs) == 1
    assert convs[0]["first_user_message"] == "first question"
    assert convs[0]["message_count"] == 2


@pytest.mark.asyncio
async def test_list_conversations_has_required_fields(client, mock_runtime):
    async with client as c:
        await c.post("/api/query", json={"question": "hello"})
        resp = await c.get("/api/conversations")
    conv = resp.json()[0]
    for field in (
        "conv_id",
        "agent_id",
        "started_at",
        "last_active",
        "message_count",
        "first_user_message",
    ):
        assert field in conv, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_list_conversations_multiple_sessions(client, mock_runtime):
    async with client as c:
        await c.post("/api/query", json={"question": "question one"})
        await c.post("/api/query", json={"question": "question two"})
        resp = await c.get("/api/conversations")
    assert len(resp.json()) == 2


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/query — conversation_id in response
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_returns_conversation_id(client, mock_runtime):
    async with client as c:
        resp = await c.post("/api/query", json={"question": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "conversation_id" in data
    assert len(data["conversation_id"]) > 0


@pytest.mark.asyncio
async def test_query_with_same_conv_id_accumulates_turns(client, mock_runtime):
    async with client as c:
        r1 = await c.post("/api/query", json={"question": "first"})
        conv_id = r1.json()["conversation_id"]
        await c.post("/api/query", json={"question": "second", "conversation_id": conv_id})
        detail = await c.get(f"/api/conversations/{conv_id}")
    messages = detail.json()["messages"]
    assert len(messages) == 4  # user + assistant × 2 turns
    assert messages[0]["content"] == "first"
    assert messages[2]["content"] == "second"


@pytest.mark.asyncio
async def test_query_unknown_conv_id_creates_new_conversation(client, mock_runtime):
    async with client as c:
        resp = await c.post(
            "/api/query",
            json={"question": "hello", "conversation_id": "nonexistent-id"},
        )
    assert resp.status_code == 200
    new_id = resp.json()["conversation_id"]
    assert new_id != "nonexistent-id"


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/conversations/{conv_id}
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_conversation_detail(client, mock_runtime):
    async with client as c:
        q_resp = await c.post("/api/query", json={"question": "test question"})
        conv_id = q_resp.json()["conversation_id"]
        resp = await c.get(f"/api/conversations/{conv_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["conv_id"] == conv_id
    messages = data["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "test question"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Test answer."


@pytest.mark.asyncio
async def test_get_conversation_detail_has_required_fields(client, mock_runtime):
    async with client as c:
        q_resp = await c.post("/api/query", json={"question": "hello"})
        conv_id = q_resp.json()["conversation_id"]
        resp = await c.get(f"/api/conversations/{conv_id}")
    data = resp.json()
    for field in ("conv_id", "agent_id", "started_at", "last_active", "messages"):
        assert field in data, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_get_conversation_unknown_id_returns_404(client):
    async with client as c:
        resp = await c.get("/api/conversations/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_conversation_messages_have_role_content_timestamp(client, mock_runtime):
    async with client as c:
        q_resp = await c.post("/api/query", json={"question": "hi"})
        conv_id = q_resp.json()["conversation_id"]
        resp = await c.get(f"/api/conversations/{conv_id}")
    for msg in resp.json()["messages"]:
        assert "role" in msg
        assert "content" in msg
        assert "timestamp" in msg

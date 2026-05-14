"""Tests for /api/wizard status — Phase 6 recommend_lite (FIX_CEREBRO)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.conversation_store import ConversationStore
from core.observability.response_meta import MetricsCollector
from ui.tray.server import app, app_state


@pytest.fixture(autouse=True)
def _reset_app_state(tmp_path):
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    app_state.conv_store = ConversationStore(str(tmp_path))
    app_state._wizard_done = False
    app_state.macos_permissions = {"calendar": "unknown"}
    yield
    app_state.runtime = None


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_wizard_status_recommend_lite_true_at_10gb_ram(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CEREBRO_INFERENCE_BACKEND", "llamacpp")

    mem = MagicMock()
    mem.total = 10 * 2**30
    monkeypatch.setattr("ui.tray.wizard.psutil.virtual_memory", lambda: mem)
    monkeypatch.setattr(
        "ui.tray.server._llamacpp_running",
        AsyncMock(return_value=False),
    )

    async with client as c:
        resp = await c.get("/api/wizard/status")
    assert resp.status_code == 200
    assert resp.json()["recommend_lite"] is True


@pytest.mark.asyncio
async def test_wizard_status_recommend_lite_false_above_10gb(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CEREBRO_INFERENCE_BACKEND", "llamacpp")

    mem = MagicMock()
    mem.total = 16 * 2**30
    monkeypatch.setattr("ui.tray.wizard.psutil.virtual_memory", lambda: mem)
    monkeypatch.setattr(
        "ui.tray.server._llamacpp_running",
        AsyncMock(return_value=False),
    )

    async with client as c:
        resp = await c.get("/api/wizard/status")
    assert resp.json()["recommend_lite"] is False


@pytest.mark.asyncio
async def test_wizard_status_recommend_lite_in_claude_mode(client, monkeypatch):
    monkeypatch.setenv("CEREBRO_INFERENCE_BACKEND", "claude")
    mem = MagicMock()
    mem.total = 8 * 2**30
    monkeypatch.setattr("ui.tray.wizard.psutil.virtual_memory", lambda: mem)

    async with client as c:
        resp = await c.get("/api/wizard/status")
    assert resp.status_code == 200
    assert resp.json()["recommend_lite"] is True


@pytest.mark.asyncio
async def test_wizard_reprobe_calendar_permission_updates_state(client, monkeypatch):
    app_state.macos_permissions["calendar"] = "denied"
    monkeypatch.setattr(
        "core.observability.macos_perms.probe_calendar_permission",
        AsyncMock(return_value="ok"),
    )
    async with client as c:
        resp = await c.post("/api/wizard/reprobe-calendar-permission")
    assert resp.status_code == 200
    assert resp.json() == {"calendar": "ok"}
    assert app_state.macos_permissions["calendar"] == "ok"

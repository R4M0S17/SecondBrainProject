from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.conversation_store import ConversationStore
from core.observability.ram_monitor import RamMonitor
from core.observability.response_meta import MetricsCollector
from ui.tray.server import app, app_state


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    app_state.conv_store = ConversationStore(str(tmp_path))
    app_state.ram_monitor = RamMonitor()
    app_state.model_manager = None
    app_state.llama_health_monitor = None
    app_state.time_travel_recorder = None
    app_state.workflow_store = None
    yield
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    app_state.conv_store = ConversationStore(str(tmp_path))
    app_state.ram_monitor = RamMonitor()
    app_state.model_manager = None
    app_state.llama_health_monitor = None
    app_state.time_travel_recorder = None
    app_state.workflow_store = None


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def mock_recorder():
    recorder = MagicMock()
    recorder.get_runs.return_value = [
        {
            "id": "run-1",
            "agent_id": "general-v1",
            "query": "hello world",
            "conversation_id": None,
            "created_at": time.time(),
            "duration_ms": 1234.5,
            "success": True,
        }
    ]
    recorder.get_run_steps.return_value = [
        {
            "id": "step-1",
            "run_id": "run-1",
            "step_number": 0,
            "node_name": "context_assembly",
            "input_preview": None,
            "output_preview": "context ready, 5 messages",
            "tool_name": None,
            "tool_args_json": None,
            "tool_result_preview": None,
            "needs_confirmation": False,
            "timestamp": time.time(),
        }
    ]
    recorder.get_step_detail.return_value = {
        "id": "step-1",
        "run_id": "run-1",
        "step_number": 0,
        "node_name": "context_assembly",
        "input_preview": None,
        "output_preview": "context ready, 5 messages",
        "tool_name": None,
        "tool_args_json": None,
        "tool_result_preview": None,
        "needs_confirmation": False,
        "timestamp": time.time(),
        "tokens": [
            {"token_order": 0, "token_text": "Hello", "is_final": 0},
            {"token_order": 1, "token_text": " world", "is_final": 1},
        ],
    }
    return recorder


class TestTimeTravelDebugger:
    async def test_list_runs_empty_when_no_recorder(self, client):
        resp = await client.get("/api/debug/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_runs_with_recorder(self, client, mock_recorder):
        app_state.time_travel_recorder = mock_recorder
        resp = await client.get("/api/debug/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "run-1"
        assert data[0]["query"] == "hello world"
        assert data[0]["success"] is True
        mock_recorder.get_runs.assert_called_once_with(limit=50, offset=0)

    async def test_list_runs_pagination(self, client, mock_recorder):
        app_state.time_travel_recorder = mock_recorder
        resp = await client.get("/api/debug/runs?limit=10&offset=5")
        assert resp.status_code == 200
        mock_recorder.get_runs.assert_called_once_with(limit=10, offset=5)

    async def test_run_steps_empty_when_no_recorder(self, client):
        resp = await client.get("/api/debug/runs/run-1/steps")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_run_steps_with_recorder(self, client, mock_recorder):
        app_state.time_travel_recorder = mock_recorder
        resp = await client.get("/api/debug/runs/run-1/steps")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "step-1"
        assert data[0]["node_name"] == "context_assembly"
        mock_recorder.get_run_steps.assert_called_once_with("run-1")

    async def test_step_detail_404_when_no_recorder(self, client):
        resp = await client.get("/api/debug/steps/step-1")
        assert resp.status_code == 404

    async def test_step_detail_with_recorder(self, client, mock_recorder):
        app_state.time_travel_recorder = mock_recorder
        resp = await client.get("/api/debug/steps/step-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "step-1"
        assert data["node_name"] == "context_assembly"
        assert len(data["tokens"]) == 2
        assert data["tokens"][0]["token_text"] == "Hello"
        mock_recorder.get_step_detail.assert_called_once_with("step-1")

    async def test_step_detail_not_found(self, client, mock_recorder):
        mock_recorder.get_step_detail.return_value = None
        app_state.time_travel_recorder = mock_recorder
        resp = await client.get("/api/debug/steps/missing-id")
        assert resp.status_code == 404

    async def test_recorder_records_run_data(self, client, mock_recorder):
        app_state.time_travel_recorder = mock_recorder
        detail = mock_recorder.get_step_detail("step-1")
        assert detail is not None
        assert detail["tokens"][0]["token_order"] == 0
        assert detail["tokens"][0]["is_final"] == 0
        assert detail["tokens"][1]["is_final"] == 1

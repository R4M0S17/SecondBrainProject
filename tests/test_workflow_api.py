from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.conversation_store import ConversationStore
from core.automation.workflow_store import WorkflowStore
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

    db_path = str(tmp_path / "automation.sqlite")
    app_state.workflow_store = WorkflowStore(db_path=db_path)
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
    if app_state.workflow_store is not None:
        app_state.workflow_store.close()
    app_state.workflow_store = None


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def seeded_store(tmp_path):
    db_path = str(tmp_path / "automation.sqlite")
    store = WorkflowStore(db_path=db_path)
    wid = store.save(
        name="Test Workflow",
        applescript='display dialog "hello"',
        description="A test workflow",
        parameters=[{"name": "name", "type": "string", "description": "Your name"}],
        tags=["test", "demo"],
    )
    return store, wid


class TestWorkflowAPI:
    async def test_list_empty(self, client):
        resp = await client.get("/api/workflows")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_workflow(self, client, seeded_store, tmp_path):
        store, wid = seeded_store
        app_state.workflow_store = store
        resp = await client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == wid
        assert data[0]["name"] == "Test Workflow"
        assert data[0]["description"] == "A test workflow"
        assert data[0]["tags"] == ["test", "demo"]
        assert data[0]["parameters"] == [
            {"name": "name", "type": "string", "description": "Your name"}
        ]
        assert data[0]["run_count"] == 0

    async def test_get_workflow(self, client, seeded_store, tmp_path):
        store, wid = seeded_store
        app_state.workflow_store = store
        resp = await client.get(f"/api/workflows/{wid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == wid
        assert data["name"] == "Test Workflow"

    async def test_get_workflow_not_found(self, client):
        app_state.workflow_store = WorkflowStore(db_path="/tmp/test_wf.sqlite")
        resp = await client.get("/api/workflows/nonexistent")
        assert resp.status_code == 404

    async def test_get_workflow_no_store(self, client):
        app_state.workflow_store = None
        resp = await client.get("/api/workflows/some-id")
        assert resp.status_code == 404

    async def test_delete_workflow(self, client, seeded_store, tmp_path):
        store, wid = seeded_store
        app_state.workflow_store = store
        resp = await client.delete(f"/api/workflows/{wid}")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True}

        resp = await client.get("/api/workflows")
        assert resp.json() == []

    async def test_delete_workflow_not_found(self, client):
        app_state.workflow_store = WorkflowStore(db_path="/tmp/test_wf2.sqlite")
        resp = await client.delete("/api/workflows/nonexistent")
        assert resp.status_code == 404

    async def test_run_workflow(self, client, seeded_store, tmp_path):
        store, wid = seeded_store
        app_state.workflow_store = store
        with patch.object(subprocess, "run") as mock_run:
            mock_result = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="hello from osascript", stderr=""
            )
            mock_run.return_value = mock_result
            resp = await client.post(f"/api/workflows/{wid}/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "Workflow ejecutado correctamente" in data["result"]

    async def test_run_workflow_increments_count(self, client, seeded_store, tmp_path):
        store, wid = seeded_store
        app_state.workflow_store = store
        with patch.object(subprocess, "run") as mock_run:
            mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
            mock_run.return_value = mock_result
            await client.post(f"/api/workflows/{wid}/run")
        wf = store.get(wid)
        assert wf is not None
        assert wf["run_count"] == 1
        assert wf["last_run"] is not None

    async def test_run_workflow_not_found(self, client):
        app_state.workflow_store = WorkflowStore(db_path="/tmp/test_wf3.sqlite")
        with patch.object(subprocess, "run") as mock_run:
            resp = await client.post("/api/workflows/nonexistent/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "Error" in data["result"]
        mock_run.assert_not_called()

    async def test_list_multiple_workflows(self, client, tmp_path):
        db_path = str(tmp_path / "multi.sqlite")
        store = WorkflowStore(db_path=db_path)
        w1 = store.save(name="First", applescript="beep", tags=["a"])
        w2 = store.save(name="Second", applescript="beep 2", tags=["b"])
        w3 = store.save(name="Third", applescript="beep 3", tags=["c"])
        app_state.workflow_store = store
        resp = await client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        names = {w["name"] for w in data}
        assert names == {"First", "Second", "Third"}

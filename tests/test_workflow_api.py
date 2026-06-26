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


class MockRecorder:
    """Lightweight recorder stand-in for API tests."""

    def __init__(self, events: list | None = None) -> None:
        self._recording = False
        self._events = list(events or [])
        self._started_at: float | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def started_at(self) -> float | None:
        return self._started_at

    @property
    def duration_sec(self) -> float:
        return 1.5 if self._started_at else 0.0

    def get_events(self):
        return list(self._events)

    def get_unique_apps(self) -> list[str]:
        apps: list[str] = []
        seen: set[str] = set()
        for ev in self._events:
            name = getattr(ev, "app_name", None)
            if name and name not in seen:
                seen.add(name)
                apps.append(name)
        return apps

    def start(self) -> None:
        import time

        self._recording = True
        self._started_at = time.time()

    def stop(self):
        self._recording = False
        return list(self._events)

    def cancel(self) -> None:
        self._recording = False
        self._events = []
        self._started_at = None


class TestWorkflowRecordAPI:
    async def test_record_start_and_status(self, client, monkeypatch):
        from core.automation.recorder import ActionEvent

        monkeypatch.setattr("core.automation.service.HAS_QUARTZ", True)
        rec = MockRecorder(
            [
                ActionEvent(timestamp=1.0, action_type="key_down", key_char="a", app_name="Finder"),
            ]
        )
        app_state.recorder = rec

        resp = await client.post("/api/workflows/record/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "recording"
        assert "started_at" in data

        status = await client.get("/api/workflows/record/status")
        assert status.status_code == 200
        body = status.json()
        assert body["recording"] is True
        assert body["event_count"] == 1
        assert body["apps"] == ["Finder"]

    async def test_record_start_conflict(self, client, monkeypatch):
        monkeypatch.setattr("core.automation.service.HAS_QUARTZ", True)
        rec = MockRecorder()
        rec._recording = True
        app_state.recorder = rec

        resp = await client.post("/api/workflows/record/start")
        assert resp.status_code == 409

    async def test_record_cancel(self, client, monkeypatch):
        monkeypatch.setattr("core.automation.service.HAS_QUARTZ", True)
        rec = MockRecorder()
        rec._recording = True
        app_state.recorder = rec

        resp = await client.post("/api/workflows/record/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        assert rec.is_recording is False

    async def test_record_stop_too_few_events(self, client, monkeypatch):
        from core.automation.recorder import ActionEvent

        monkeypatch.setattr("core.automation.service.HAS_QUARTZ", True)
        rec = MockRecorder(
            [
                ActionEvent(timestamp=1.0, action_type="key_down", app_name="Safari"),
                ActionEvent(timestamp=2.0, action_type="key_down", app_name="Safari"),
            ]
        )
        rec._recording = True
        app_state.recorder = rec

        resp = await client.post("/api/workflows/record/stop")
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error_key"] == "workflows.error.too_few_events"

    async def test_record_stop_creates_workflow(self, client, monkeypatch, tmp_path):
        import json
        from unittest.mock import AsyncMock, MagicMock

        from core.automation.recorder import ActionEvent

        monkeypatch.setattr("core.automation.service.HAS_QUARTZ", True)
        events = [
            ActionEvent(timestamp=1.0, action_type="key_down", key_char="a", app_name="Notes"),
            ActionEvent(timestamp=2.0, action_type="key_down", key_char="b", app_name="Notes"),
            ActionEvent(timestamp=3.0, action_type="left_click", mouse_x=10, mouse_y=20, app_name="Notes"),
        ]
        rec = MockRecorder(events)
        rec._recording = True
        app_state.recorder = rec

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "name": "Typed Note",
                    "description": "Types and clicks",
                    "applescript": 'tell application "Notes" to activate',
                    "parameters": [],
                    "steps": [
                        {"order": 1, "app": "Notes", "action": "Activar", "detail": ""},
                    ],
                    "tags": ["notes"],
                }
            )
        )
        mock_registry = MagicMock()
        mock_registry.get_chat.return_value = mock_provider
        app_state.provider_registry = mock_registry

        resp = await client.post("/api/workflows/record/stop", json={"name": "My Routine"})
        assert resp.status_code == 200
        wf = resp.json()
        assert wf["name"] == "My Routine"
        assert wf["workflow_type"] == "desktop"
        assert len(wf["steps"]) >= 1
        assert wf["applescript"]

    async def test_record_unavailable_no_recorder(self, client):
        app_state.recorder = None
        resp = await client.post("/api/workflows/record/start")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "workflows.error.recorder_unavailable"

    async def test_record_unavailable_no_quartz(self, client, monkeypatch):
        monkeypatch.setattr("core.automation.service.HAS_QUARTZ", False)
        app_state.recorder = MockRecorder()
        resp = await client.post("/api/workflows/record/start")
        assert resp.status_code == 503


class TestWorkflowPatchAPI:
    async def test_patch_workflow(self, client, seeded_store, tmp_path):
        store, wid = seeded_store
        app_state.workflow_store = store
        resp = await client.patch(
            f"/api/workflows/{wid}",
            json={"name": "Renamed", "description": "Updated desc", "tags": ["new"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Renamed"
        assert data["description"] == "Updated desc"
        assert data["tags"] == ["new"]

    async def test_patch_not_found(self, client):
        app_state.workflow_store = WorkflowStore(db_path="/tmp/test_patch.sqlite")
        resp = await client.patch("/api/workflows/missing", json={"name": "X"})
        assert resp.status_code == 404


class TestWorkflowRunAPI:
    async def test_run_with_params(self, client, seeded_store, tmp_path):
        store, wid = seeded_store
        store.update(wid, applescript='on run argv\nreturn item 1 of argv')
        store._conn.execute(
            "UPDATE workflows SET parameters = ? WHERE id = ?",
            ('[{"name": "msg", "type": "string", "description": "msg", "default": "hi"}]', wid),
        )
        store._conn.commit()
        app_state.workflow_store = store
        with patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="hi", stderr=""
            )
            resp = await client.post(f"/api/workflows/{wid}/run", json={"params": {"msg": "hello"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "run_id" in data
        runs = store.list_runs(wid)
        assert len(runs) == 1
        assert runs[0]["success"] is True
        assert runs[0]["params"]["msg"] == "hello"

    async def test_run_failed_records_error(self, client, seeded_store, tmp_path):
        store, wid = seeded_store
        app_state.workflow_store = store
        with patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="script error"
            )
            resp = await client.post(f"/api/workflows/{wid}/run")
        data = resp.json()
        assert data["success"] is False
        runs = store.list_runs(wid)
        assert len(runs) == 1
        assert runs[0]["success"] is False
        assert "script error" in (runs[0]["error"] or "")

    async def test_list_runs(self, client, seeded_store, tmp_path):
        store, wid = seeded_store
        store.record_run(
            wid,
            started_at=1.0,
            finished_at=2.0,
            success=True,
            output="ok",
            params={"a": "b"},
        )
        app_state.workflow_store = store
        resp = await client.get(f"/api/workflows/{wid}/runs")
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) == 1
        assert runs[0]["success"] is True


class TestWorkflowRecipesAPI:
    async def test_list_templates(self, client):
        resp = await client.get("/api/workflows/recipes/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        keys = {t["recipe_key"] for t in data}
        assert "calendar_to_file" in keys

    async def test_install_recipe(self, client, tmp_path):
        db_path = str(tmp_path / "recipes.sqlite")
        app_state.workflow_store = WorkflowStore(db_path=db_path)
        resp = await client.post(
            "/api/workflows/recipes",
            json={"template_id": "recipe-calendar-week-md", "name": "Mi semana"},
        )
        assert resp.status_code == 200
        wf = resp.json()
        assert wf["name"] == "Mi semana"
        assert wf["workflow_type"] == "recipe"
        assert wf["recipe_key"] == "calendar_to_file"

    async def test_run_recipe_calendar(self, client, tmp_path, monkeypatch):
        db_path = str(tmp_path / "recipes_run.sqlite")
        store = WorkflowStore(db_path=db_path)
        wid = store.save(
            name="Cal export",
            applescript="",
            workflow_type="recipe",
            recipe_key="calendar_to_file",
            steps=[{"order": 1, "action": "read"}],
            parameters=[{"name": "filename", "type": "string", "default": "semana.md"}],
        )
        app_state.workflow_store = store

        monkeypatch.setattr(
            "core.automation.recipes.fetch_calendar_read_answer",
            lambda q, tools, **kw: "## Eventos\n- Reunión lunes",
        )
        monkeypatch.setattr(
            "core.automation.recipes.write_file",
            lambda path, content, paths: f"Escrito en {path}",
        )

        resp = await client.post(f"/api/workflows/{wid}/run", json={"params": {"filename": "test.md"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "Escrito" in data["result"] or "Archivo" in data["result"]


class TestWorkflowPhase4API:
    async def test_export_workflow(self, client, seeded_store):
        store, wid = seeded_store
        store.update(wid, steps=[{"order": 1, "action": "Click Save"}])
        app_state.workflow_store = store
        resp = await client.get(f"/api/workflows/{wid}/export")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 1
        assert data["name"] == "Test Workflow"
        assert data["steps"][0]["action"] == "Click Save"

    async def test_import_workflow(self, client, tmp_path):
        db_path = str(tmp_path / "import.sqlite")
        app_state.workflow_store = WorkflowStore(db_path=db_path)
        payload = {
            "export": {
                "version": 1,
                "name": "Imported flow",
                "description": "From JSON",
                "workflow_type": "desktop",
                "applescript": 'display dialog "hi"',
                "parameters": [],
                "steps": [{"order": 1, "action": "Open app"}],
                "tags": ["imported"],
            }
        }
        resp = await client.post("/api/workflows/import", json=payload)
        assert resp.status_code == 200
        wf = resp.json()
        assert wf["name"] == "Imported flow"
        assert wf["steps"][0]["action"] == "Open app"

    async def test_patch_steps(self, client, seeded_store):
        store, wid = seeded_store
        app_state.workflow_store = store
        new_steps = [{"order": 1, "action": "Updated step"}]
        resp = await client.patch(f"/api/workflows/{wid}", json={"steps": new_steps})
        assert resp.status_code == 200
        assert resp.json()["steps"] == new_steps

    async def test_dry_run_skips_osascript(self, client, seeded_store):
        store, wid = seeded_store
        store.update(wid, steps=[{"order": 1, "action": "Test action"}])
        app_state.workflow_store = store
        with patch("core.automation.service.subprocess.run") as mock_run:
            resp = await client.post(
                f"/api/workflows/{wid}/run",
                json={"params": {"name": "Ada"}, "dry_run": True},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data.get("dry_run") is True
        assert "Dry run" in data["result"]
        mock_run.assert_not_called()

    async def test_from_conversation_write_file(self, client, tmp_path):
        db_path = str(tmp_path / "conv.sqlite")
        app_state.workflow_store = WorkflowStore(db_path=db_path)
        conv_id = app_state.conv_store.create("general-v1")
        app_state.conv_store.append(
            conv_id,
            "guarda el calendario",
            "Listo, archivo creado.",
            metadata={
                "tools_called": [
                    {
                        "name": "write_file",
                        "approved": True,
                        "result_summary": "Archivo escrito en semana.md",
                    }
                ]
            },
        )
        resp = await client.post(
            "/api/workflows/from-conversation",
            json={"conversation_id": conv_id, "turn_index": 1},
        )
        assert resp.status_code == 200
        wf = resp.json()
        assert wf["workflow_type"] == "recipe"
        assert wf["recipe_key"] == "calendar_to_file"
        assert "from-chat" in wf["tags"]

    async def test_from_conversation_no_tools(self, client, tmp_path):
        db_path = str(tmp_path / "conv2.sqlite")
        app_state.workflow_store = WorkflowStore(db_path=db_path)
        conv_id = app_state.conv_store.create("general-v1")
        app_state.conv_store.append(conv_id, "hola", "hola", metadata={})
        resp = await client.post(
            "/api/workflows/from-conversation",
            json={"conversation_id": conv_id, "turn_index": 1},
        )
        assert resp.status_code == 422

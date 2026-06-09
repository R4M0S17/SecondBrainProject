"""Tests for core/automation/ — Desktop Recorder + Workflow Store."""

from __future__ import annotations

import json
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.automation.recorder import ActionEvent, Recorder
from core.automation.workflow_store import WorkflowStore

# ── ActionEvent ───────────────────────────────────────────────────────


class TestActionEvent:
    def test_to_dict(self):
        ev = ActionEvent(
            timestamp=123.0,
            action_type="key_down",
            key_code=0,
            key_char="a",
            app_name="Terminal",
        )
        d = ev.to_dict()
        assert d["action_type"] == "key_down"
        assert d["key_char"] == "a"
        assert d["app_name"] == "Terminal"

    def test_to_dict_defaults(self):
        ev = ActionEvent(timestamp=456.0, action_type="click")
        d = ev.to_dict()
        assert d["key_code"] is None
        assert d["mouse_x"] is None


# ── WorkflowStore ─────────────────────────────────────────────────────


class TestWorkflowStore:
    @pytest.fixture
    def store(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name
        store = WorkflowStore(db_path)
        yield store
        store.close()
        import os

        os.unlink(db_path)

    def test_save_and_get(self, store):
        wid = store.save(
            name="Test Workflow",
            applescript='display dialog "Hello"',
            description="A test",
            parameters=[{"name": "msg", "type": "string", "description": "message"}],
            tags=["test"],
        )
        assert wid is not None
        wf = store.get(wid)
        assert wf is not None
        assert wf["name"] == "Test Workflow"
        assert len(wf["parameters"]) == 1
        assert "test" in wf["tags"]

    def test_list_all(self, store):
        store.save(name="WF1", applescript="beep")
        store.save(name="WF2", applescript="beep 2")
        all_wf = store.list_all()
        assert len(all_wf) == 2

    def test_get_nonexistent(self, store):
        assert store.get("nonexistent") is None

    def test_delete(self, store):
        wid = store.save(name="ToDelete", applescript="beep")
        assert store.delete(wid) is True
        assert store.get(wid) is None

    def test_delete_nonexistent(self, store):
        assert store.delete("nope") is False

    def test_increment_run_count(self, store):
        wid = store.save(name="Counter", applescript="beep")
        wf = store.get(wid)
        assert wf["run_count"] == 0
        store.increment_run_count(wid)
        wf = store.get(wid)
        assert wf["run_count"] == 1

    def test_search(self, store):
        store.save(name="Backup Script", applescript="do shell script", tags=["backup"])
        store.save(name="Other", applescript="beep", tags=["misc"])
        results = store.search("backup")
        assert len(results) >= 1
        assert "Backup" in results[0]["name"]

    def test_update(self, store):
        wid = store.save(name="Old", applescript="beep")
        store.update(wid, name="New", tags=["updated"])
        wf = store.get(wid)
        assert wf["name"] == "New"
        assert "updated" in wf["tags"]


# ── Recorder (no pyobjc) ──────────────────────────────────────────────


class TestRecorderNoPyobjc:
    def test_init(self):
        rec = Recorder()
        assert rec.is_recording is False
        assert rec.event_count == 0

    def test_start_stop_no_pyobjc(self):
        """Without pyobjc, start/stop should work but capture no events."""
        rec = Recorder()
        rec.start()
        assert rec.is_recording is True
        events = rec.stop()
        assert isinstance(events, list)
        # Should be empty since pyobjc not available
        assert len(events) == 0

    def test_double_start(self):
        rec = Recorder()
        rec.start()
        rec.start()  # should not crash
        rec.stop()
        assert rec.is_recording is False

    def test_stop_without_start(self):
        rec = Recorder()
        events = rec.stop()
        assert events == []


# ── Generalizer ───────────────────────────────────────────────────────


class TestGeneralizer:
    @pytest.fixture
    def sample_events(self):
        return [
            ActionEvent(timestamp=1.0, action_type="key_down", key_char="n", app_name="TextEdit"),
            ActionEvent(timestamp=1.1, action_type="key_down", key_char="e", app_name="TextEdit"),
            ActionEvent(timestamp=1.2, action_type="key_down", key_char="w", app_name="TextEdit"),
            ActionEvent(
                timestamp=2.0,
                action_type="left_click",
                mouse_x=100,
                mouse_y=200,
                app_name="TextEdit",
            ),
        ]

    async def test_generalize_events_success(self, sample_events):
        from core.automation.generalizer import generalize_events

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "name": "Type Text",
                    "description": "Types 'new' and clicks",
                    "applescript": 'tell application "System Events"\n  keystroke "new"\nend tell',
                    "parameters": [],
                    "tags": ["text", "typing"],
                }
            )
        )

        result = await generalize_events(sample_events, mock_provider)
        assert result["name"] == "Type Text"
        assert "keystroke" in result["applescript"]

    async def test_generalize_empty_events(self):
        from core.automation.generalizer import GeneralizationError, generalize_events

        mock_provider = MagicMock()
        with pytest.raises(GeneralizationError, match="No events"):
            await generalize_events([], mock_provider)

    async def test_generalize_provider_error(self, sample_events):
        from core.automation.generalizer import GeneralizationError, generalize_events

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=RuntimeError("LLM down"))
        with pytest.raises(GeneralizationError, match="LLM call failed"):
            await generalize_events(sample_events, mock_provider)

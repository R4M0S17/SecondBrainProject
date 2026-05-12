"""Module 13 — Packaging & Distribution tests.

Covers:
  - WizardSession: sentinel-based first-launch detection, mark_setup_complete,
    current_step, check_llamacpp, check_models, set_watched_paths
  - _write_watched_paths: in-place TOML patching
  - wizard_router: FastAPI endpoints via TestClient with monkeypatched _DATA_DIR
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ui.tray.wizard_router as _wr
from ui.tray.wizard import WizardError, WizardSession, WizardStep, _write_watched_paths
from ui.tray.wizard_router import wizard_router

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_client(data_dir: Path) -> TestClient:
    """Mount wizard_router on a fresh app with data_dir injected."""
    _wr._DATA_DIR = data_dir
    test_app = FastAPI()
    test_app.include_router(wizard_router)
    return TestClient(test_app)


def _make_session(tmp_path: Path, **kw) -> WizardSession:
    return WizardSession(data_dir=tmp_path, **kw)


# ── TestFirstLaunch ───────────────────────────────────────────────────────────


class TestFirstLaunch:
    def test_is_first_launch_when_no_sentinel(self, tmp_path):
        s = _make_session(tmp_path)
        assert s.is_first_launch() is True

    def test_is_not_first_launch_after_mark_complete(self, tmp_path):
        s = _make_session(tmp_path)
        s.mark_setup_complete()
        assert s.is_first_launch() is False


# ── TestMarkComplete ──────────────────────────────────────────────────────────


class TestMarkComplete:
    def test_creates_sentinel_file(self, tmp_path):
        s = _make_session(tmp_path)
        s.mark_setup_complete()
        assert (tmp_path / ".wizard_complete").exists()

    def test_creates_data_dir_if_missing(self, tmp_path):
        data_dir = tmp_path / "nested" / "dir"
        s = WizardSession(data_dir=data_dir)
        s.mark_setup_complete()
        assert data_dir.exists()

    def test_idempotent_when_called_twice(self, tmp_path):
        s = _make_session(tmp_path)
        s.mark_setup_complete()
        s.mark_setup_complete()  # must not raise
        assert (tmp_path / ".wizard_complete").exists()


# ── TestCurrentStep ───────────────────────────────────────────────────────────


class TestCurrentStep:
    def test_returns_llamacpp_when_not_started(self, tmp_path):
        assert _make_session(tmp_path).current_step() == WizardStep.LLAMACPP

    def test_returns_done_when_complete(self, tmp_path):
        s = _make_session(tmp_path)
        s.mark_setup_complete()
        assert s.current_step() == WizardStep.DONE


# ── TestCheckLlamaCpp ─────────────────────────────────────────────────────────


class TestCheckLlamaCpp:
    def test_returns_true_when_server_responds_200(self, tmp_path):
        s = _make_session(tmp_path)
        mock_resp = MagicMock(status_code=200)
        with patch("httpx.get", return_value=mock_resp):
            assert s.check_llamacpp() is True

    def test_returns_false_when_connection_refused(self, tmp_path):
        s = _make_session(tmp_path)
        with patch("httpx.get", side_effect=Exception("connection refused")):
            assert s.check_llamacpp() is False

    def test_returns_false_on_non_200_status(self, tmp_path):
        s = _make_session(tmp_path)
        mock_resp = MagicMock(status_code=503)
        with patch("httpx.get", return_value=mock_resp):
            assert s.check_llamacpp() is False


# ── TestCheckModels ───────────────────────────────────────────────────────────


class TestCheckModels:
    def test_returns_true_when_gguf_file_exists(self, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "phi4-mini.gguf").touch()
        s = _make_session(tmp_path)
        assert s.check_models(models_dir=models_dir) is True

    def test_returns_false_when_dir_does_not_exist(self, tmp_path):
        s = _make_session(tmp_path)
        assert s.check_models(models_dir=tmp_path / "no_such_dir") is False

    def test_returns_false_when_dir_is_empty(self, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        s = _make_session(tmp_path)
        assert s.check_models(models_dir=models_dir) is False

    def test_ignores_non_gguf_files(self, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "README.md").touch()
        s = _make_session(tmp_path)
        assert s.check_models(models_dir=models_dir) is False


# ── TestSetWatchedPaths ───────────────────────────────────────────────────────


class TestSetWatchedPaths:
    def _make_settings(self, tmp_path: Path) -> Path:
        settings = tmp_path / "settings.toml"
        settings.write_text("[ingestion]\nwatched_paths = []\n", encoding="utf-8")
        return settings

    def test_rejects_empty_list(self, tmp_path):
        s = _make_session(tmp_path)
        with pytest.raises(WizardError, match="At least one folder"):
            s.set_watched_paths([], settings_path=self._make_settings(tmp_path))

    def test_rejects_nonexistent_directory(self, tmp_path):
        s = _make_session(tmp_path)
        with pytest.raises(WizardError, match="Not a valid directory"):
            s.set_watched_paths(
                [str(tmp_path / "no_such_dir")],
                settings_path=self._make_settings(tmp_path),
            )

    def test_writes_paths_to_settings_toml(self, tmp_path):
        settings = self._make_settings(tmp_path)
        folder = tmp_path / "docs"
        folder.mkdir()
        s = _make_session(tmp_path)
        s.set_watched_paths([str(folder)], settings_path=settings)
        content = settings.read_text()
        assert str(folder) in content

    def test_marks_wizard_complete_after_setting_paths(self, tmp_path):
        settings = self._make_settings(tmp_path)
        folder = tmp_path / "notes"
        folder.mkdir()
        s = _make_session(tmp_path)
        s.set_watched_paths([str(folder)], settings_path=settings)
        assert not s.is_first_launch()

    def test_accepts_multiple_valid_paths(self, tmp_path):
        settings = self._make_settings(tmp_path)
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        s = _make_session(tmp_path)
        s.set_watched_paths([str(a), str(b)], settings_path=settings)
        content = settings.read_text()
        assert str(a) in content
        assert str(b) in content


# ── TestWriteWatchedPaths ─────────────────────────────────────────────────────


class TestWriteWatchedPaths:
    def test_replaces_empty_list(self, tmp_path):
        settings = tmp_path / "settings.toml"
        settings.write_text("[ingestion]\nwatched_paths = []\n", encoding="utf-8")
        _write_watched_paths(["/home/user/docs"], settings)
        assert '"/home/user/docs"' in settings.read_text()

    def test_replaces_nonempty_existing_list(self, tmp_path):
        settings = tmp_path / "settings.toml"
        settings.write_text('[ingestion]\nwatched_paths = ["/old/path"]\n', encoding="utf-8")
        _write_watched_paths(["/new/path"], settings)
        content = settings.read_text()
        assert "/new/path" in content
        assert "/old/path" not in content

    def test_preserves_other_toml_content(self, tmp_path):
        settings = tmp_path / "settings.toml"
        settings.write_text(
            "[ingestion]\nchunk_size = 512\nwatched_paths = []\nchunk_overlap = 64\n",
            encoding="utf-8",
        )
        _write_watched_paths(["/docs"], settings)
        content = settings.read_text()
        assert "chunk_size = 512" in content
        assert "chunk_overlap = 64" in content


# ── TestWizardRouter ──────────────────────────────────────────────────────────


class TestWizardRouter:
    def test_status_is_first_launch_true_when_no_sentinel(self, tmp_path):
        client = _make_client(tmp_path)
        r = client.get("/wizard/status")
        assert r.status_code == 200
        assert r.json()["is_first_launch"] is True

    def test_status_step_is_llamacpp_when_not_complete(self, tmp_path):
        client = _make_client(tmp_path)
        r = client.get("/wizard/status")
        assert r.json()["step"] == "llamacpp"

    def test_status_step_is_done_after_complete(self, tmp_path):
        WizardSession(data_dir=tmp_path).mark_setup_complete()
        client = _make_client(tmp_path)
        r = client.get("/wizard/status")
        assert r.json()["step"] == "done"
        assert r.json()["is_first_launch"] is False

    def test_llamacpp_step_returns_ok_true_when_available(self, tmp_path):
        client = _make_client(tmp_path)
        mock_resp = MagicMock(status_code=200)
        with patch("httpx.get", return_value=mock_resp):
            r = client.post("/wizard/step/llamacpp")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_llamacpp_step_returns_ok_false_when_unavailable(self, tmp_path):
        client = _make_client(tmp_path)
        with patch("httpx.get", side_effect=Exception("refused")):
            r = client.post("/wizard/step/llamacpp")
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_model_step_returns_ok_true_when_gguf_exists(self, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        (models_dir / "phi4-mini.gguf").touch()
        client = _make_client(tmp_path)
        with patch("ui.tray.wizard._MODELS_DIR", models_dir):
            r = client.post("/wizard/step/model")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_model_step_returns_ok_false_when_no_gguf(self, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        client = _make_client(tmp_path)
        with patch("ui.tray.wizard._MODELS_DIR", models_dir):
            r = client.post("/wizard/step/model")
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_folders_step_returns_400_on_invalid_path(self, tmp_path):
        client = _make_client(tmp_path)
        r = client.post("/wizard/step/folders", json={"paths": ["/nonexistent/path"]})
        assert r.status_code == 400

    def test_folders_step_returns_ok_on_valid_path(self, tmp_path):
        folder = tmp_path / "watch"
        folder.mkdir()
        fake_settings = tmp_path / "settings.toml"
        fake_settings.write_text("[ingestion]\nwatched_paths = []\n", encoding="utf-8")
        client = _make_client(tmp_path)
        with patch("ui.tray.wizard._DEFAULT_SETTINGS", fake_settings):
            r = client.post("/wizard/step/folders", json={"paths": [str(folder)]})
        assert r.status_code == 200
        assert r.json()["ok"] is True

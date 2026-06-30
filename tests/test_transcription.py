"""Tests for the transcription module (WhisperManager + API endpoints)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from core.transcription.whisper_manager import IDLE_SHUTDOWN_SECONDS, WhisperManager


@pytest.fixture
def whisper_manager() -> WhisperManager:
    return WhisperManager()


@pytest.mark.asyncio
class TestWhisperManager:
    async def test_is_available_returns_false_when_bin_missing(
        self, whisper_manager: WhisperManager
    ) -> None:
        with (
            patch("core.transcription.whisper_manager.WHISPER_BIN_PATH") as mock_bin,
            patch("core.transcription.whisper_manager.WHISPER_MODEL_PATH") as mock_model,
        ):
            mock_bin.exists.return_value = False
            mock_model.exists.return_value = False
            assert whisper_manager.is_available is False

    async def test_is_available_returns_true_when_bin_and_model_exist(
        self, whisper_manager: WhisperManager
    ) -> None:
        with (
            patch("core.transcription.whisper_manager.WHISPER_BIN_PATH") as mock_bin,
            patch("core.transcription.whisper_manager.WHISPER_MODEL_PATH") as mock_model,
        ):
            mock_bin.exists.return_value = True
            mock_model.exists.return_value = True
            assert whisper_manager.is_available is True

    async def test_is_running_returns_false_when_not_started(
        self, whisper_manager: WhisperManager
    ) -> None:
        assert whisper_manager.is_running is False

    async def test_ensure_running_returns_false_when_not_available(
        self, whisper_manager: WhisperManager
    ) -> None:
        with patch.object(WhisperManager, "is_available", PropertyMock(return_value=False)):
            result = await whisper_manager.ensure_running()
            assert result is False

    async def test_health_check_has_idle_fields(self, whisper_manager: WhisperManager) -> None:
        health = await whisper_manager.health_check()
        assert "idle_seconds" in health
        assert "idle_shutdown_seconds" in health
        assert health["idle_shutdown_seconds"] == IDLE_SHUTDOWN_SECONDS

    async def test_health_check_not_running(self, whisper_manager: WhisperManager) -> None:
        with patch.object(WhisperManager, "is_available", PropertyMock(return_value=True)):
            health = await whisper_manager.health_check()
        assert health["running"] is False
        assert health["reachable"] is False
        assert health["available"] is True

    async def test_health_check_not_available(self, whisper_manager: WhisperManager) -> None:
        with patch.object(WhisperManager, "is_available", PropertyMock(return_value=False)):
            health = await whisper_manager.health_check()
        assert health["available"] is False
        assert health["running"] is False

    async def test_shutdown_noop_when_not_running(self, whisper_manager: WhisperManager) -> None:
        whisper_manager.shutdown()
        assert whisper_manager.is_running is False

    async def test_transcribe_raises_when_not_available(
        self, whisper_manager: WhisperManager
    ) -> None:
        whisper_manager.ensure_running = AsyncMock(return_value=False)  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="whisper-server no disponible"):
            await whisper_manager.transcribe(b"fake wav data")

    @patch("builtins.open", new_callable=MagicMock)
    @patch("core.transcription.whisper_manager.os.unlink")
    @patch("core.transcription.whisper_manager.tempfile.NamedTemporaryFile")
    @patch("core.transcription.whisper_manager.httpx.AsyncClient")
    async def test_transcribe_success(
        self,
        mock_client_cls: MagicMock,
        mock_temp: MagicMock,
        mock_unlink: MagicMock,
        mock_open: MagicMock,
        whisper_manager: WhisperManager,
    ) -> None:
        temp_mock = MagicMock()
        temp_mock.name = "/tmp/fake.wav"
        mock_temp.return_value.__enter__.return_value = temp_mock

        mock_file_handle = MagicMock()
        mock_file_handle.read.return_value = b"fake wav content"
        mock_open.return_value.__enter__.return_value = mock_file_handle

        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "text": "  Hola mundo  ",
            "language": "es",
            "segments": [{"t1": 150}],
        }
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_http_client

        whisper_manager.ensure_running = AsyncMock(return_value=True)  # type: ignore[method-assign]

        result = await whisper_manager.transcribe(b"fake wav data")

        assert result["text"] == "  Hola mundo  "
        mock_http_client.post.assert_called_once()

    async def test_transcribe_updates_last_use(self, whisper_manager: WhisperManager) -> None:
        whisper_manager.ensure_running = AsyncMock(return_value=True)  # type: ignore[method-assign]
        whisper_manager._last_use = 0.0
        whisper_manager._process = MagicMock()

        with (
            patch("core.transcription.whisper_manager.tempfile.NamedTemporaryFile") as mock_temp,
            patch("core.transcription.whisper_manager.httpx.AsyncClient") as mock_client,
            patch("builtins.open", MagicMock()),
            patch("core.transcription.whisper_manager.os.unlink"),
        ):
            mock_temp.return_value.__enter__.return_value.name = "/tmp/fake.wav"
            mock_http = MagicMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"text": "test", "language": "es"}
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__.return_value = mock_http

            await whisper_manager.transcribe(b"data")

        assert whisper_manager._last_use > 0

    async def test_health_check_reachable(self, whisper_manager: WhisperManager) -> None:
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=MagicMock(status_code=200))

        class FakeAsyncClient:
            async def __aenter__(self):
                return mock_http_client

            async def __aexit__(self, *args):
                pass

        with (
            patch.object(WhisperManager, "is_available", PropertyMock(return_value=True)),
            patch.object(WhisperManager, "is_running", PropertyMock(return_value=True)),
            patch(
                "core.transcription.whisper_manager.httpx.AsyncClient",
                return_value=FakeAsyncClient(),
            ),
        ):
            health = await whisper_manager.health_check()

        assert health["running"] is True
        assert health["reachable"] is True
        assert health["idle_seconds"] >= 0

    async def test_shutdown_cancels_watchdog(self, whisper_manager: WhisperManager) -> None:
        task = AsyncMock()
        task.done = MagicMock(return_value=False)  # type: ignore[method-assign]
        whisper_manager._watchdog_task = task
        whisper_manager._process = MagicMock()
        whisper_manager._process.poll = MagicMock(return_value=None)

        whisper_manager.shutdown()

        task.cancel.assert_called_once()

    async def test_watchdog_not_started_if_not_running(
        self, whisper_manager: WhisperManager
    ) -> None:
        assert whisper_manager._watchdog_task is None


@pytest.mark.asyncio
class TestTranscribeAPI:
    """Integration tests for the /api/transcribe* endpoints."""

    @pytest.fixture(autouse=True)
    def _setup_app_state(self):
        from ui.tray.server import app_state

        app_state.whisper = None
        yield
        app_state.whisper = None

    async def test_health_no_whisper(self) -> None:
        transport = ASGITransport(app=_build_test_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/transcribe/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["running"] is False

    async def test_start_no_whisper(self) -> None:
        transport = ASGITransport(app=_build_test_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/transcribe/start")
        assert resp.status_code == 503

    async def test_stop_noop(self) -> None:
        transport = ASGITransport(app=_build_test_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/transcribe/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    async def test_post_transcribe_with_mock_whisper(self) -> None:
        from ui.tray.server import app_state

        whisper = MagicMock()
        whisper.transcribe = AsyncMock(
            return_value={
                "text": "Hola mundo",
                "language": "es",
                "segments": [{"t1": 150}],
            }
        )
        app_state.whisper = whisper

        transport = ASGITransport(app=_build_test_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/transcribe",
                files={"file": ("audio.wav", _minimal_wav(), "audio/wav")},
                data={"language": "es"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Hola mundo"
        assert data["language"] == "es"
        assert data["duration_ms"] == 1500

    async def test_health_with_mock_whisper(self) -> None:
        from ui.tray.server import app_state

        whisper = MagicMock()
        whisper.health_check = AsyncMock(
            return_value={
                "available": True,
                "running": True,
                "reachable": True,
                "model": "ggml-base.bin",
                "port": 8765,
                "idle_seconds": 42.0,
                "idle_shutdown_seconds": 300,
            }
        )
        app_state.whisper = whisper

        transport = ASGITransport(app=_build_test_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/transcribe/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is True
        assert data["idle_seconds"] == 42.0

    async def test_start_with_mock_whisper(self) -> None:
        from ui.tray.server import app_state

        whisper = MagicMock()
        whisper.ensure_running = AsyncMock(return_value=True)
        app_state.whisper = whisper

        transport = ASGITransport(app=_build_test_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/transcribe/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    async def test_start_fails_with_mock_whisper(self) -> None:
        from ui.tray.server import app_state

        whisper = MagicMock()
        whisper.ensure_running = AsyncMock(return_value=False)
        app_state.whisper = whisper

        transport = ASGITransport(app=_build_test_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/transcribe/start")
        assert resp.status_code == 503

    async def test_post_transcribe_rejects_empty(self) -> None:
        transport = ASGITransport(app=_build_test_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/transcribe",
                files={"file": ("audio.wav", b"", "audio/wav")},
            )
        assert resp.status_code == 400

    async def test_post_transcribe_rejects_large(self) -> None:
        from ui.tray.server import app_state

        whisper = MagicMock()
        app_state.whisper = whisper
        transport = ASGITransport(app=_build_test_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/transcribe",
                files={"file": ("audio.wav", b"\x00" * 11_000_000, "audio/wav")},
            )
        assert resp.status_code == 413


def _build_test_app():
    """Create a minimal FastAPI app with only the transcription routes."""
    from fastapi import FastAPI

    from ui.tray.server import api

    app = FastAPI()
    app.include_router(api)
    return app


def _minimal_wav() -> bytes:
    """Return a 44-byte minimal valid WAV header."""
    import struct

    sample_rate = 16000
    num_samples = 0
    data_size = num_samples * 2
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        data_size,
    )

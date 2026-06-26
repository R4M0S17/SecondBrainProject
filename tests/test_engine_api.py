"""Tests for /api/engine/* endpoints and engine_manager integration."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from core.inference.engine_desired import get_engine_desired, set_engine_desired
from core.inference.engine_manager import EngineStatus
from core.inference.health_monitor import LlamaServerHealthMonitor
from core.observability.ram_monitor import RamMonitor
from core.observability.response_meta import MetricsCollector
from ui.tray.server import app, app_state


@pytest.fixture(autouse=True)
def reset_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CEREBRO_STATE", str(tmp_path))
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.router = MagicMock()
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {"model": "Qwen3.5-2B-UD-Q4_K_XL.gguf"}
    app_state.ram_monitor = RamMonitor()
    app_state.model_manager = None
    app_state.llama_health_monitor = None
    app_state.engine_suspender = None
    monkeypatch.setenv("CEREBRO_INFERENCE_BACKEND", "llamacpp")
    yield


@pytest.fixture
def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _mock_status(
    *,
    desired: str = "on",
    running: bool = True,
    embed_running: bool = False,
) -> EngineStatus:
    return EngineStatus(
        desired=desired,  # type: ignore[arg-type]
        running=running,
        model="Qwen3.5-2B-UD-Q4_K_XL.gguf",
        llama_server="up" if running else "down",
        embed_running=embed_running,
    )


@pytest.mark.asyncio
async def test_engine_status_endpoint(client: AsyncClient) -> None:
    with patch(
        "core.inference.engine_manager.get_status",
        return_value=_mock_status(desired="off", running=False),
    ):
        async with client as c:
            resp = await c.get("/api/engine/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["desired"] == "off"
    assert data["running"] is False
    assert data["model"] == "Qwen3.5-2B-UD-Q4_K_XL.gguf"
    assert data["llama_server"] == "down"
    assert data["embed_running"] is False


@pytest.mark.asyncio
async def test_engine_start_sets_desired_on(client: AsyncClient) -> None:
    with patch(
        "core.inference.engine_manager.start_engine_sync",
        return_value=_mock_status(desired="on", running=True),
    ):
        async with client as c:
            resp = await c.post("/api/engine/start")
    assert resp.status_code == 200
    assert resp.json()["running"] is True
    assert resp.json()["desired"] == "on"


@pytest.mark.asyncio
async def test_engine_start_returns_503_when_unhealthy(client: AsyncClient) -> None:
    with patch(
        "core.inference.engine_manager.start_engine_sync",
        return_value=_mock_status(desired="on", running=False),
    ):
        async with client as c:
            resp = await c.post("/api/engine/start")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_engine_start_rejects_non_llamacpp_backend(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setenv("CEREBRO_INFERENCE_BACKEND", "claude")
    async with client as c:
        resp = await c.post("/api/engine/start")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_engine_stop_sets_desired_off(client: AsyncClient, tmp_path: Path) -> None:
    set_engine_desired("on")
    with patch("core.inference.engine_manager.stop_all_engines"):
        async with client as c:
            resp = await c.post("/api/engine/stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["desired"] == "off"
    assert data["running"] is False
    assert get_engine_desired() == "off"


@pytest.mark.asyncio
async def test_engine_stop_prevents_health_monitor_restart(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    set_engine_desired("on")
    spawned: list[str] = []

    async def always_fail() -> bool:
        return False

    monitor = LlamaServerHealthMonitor(
        "http://127.0.0.1:8080",
        ping_interval_s=0.02,
        failure_threshold=2,
        ping=always_fail,
        spawn_engine=lambda: spawned.append("ok"),
    )
    app_state.llama_health_monitor = monitor

    with patch("core.inference.engine_manager.stop_all_engines"):
        async with client as c:
            resp = await c.post("/api/engine/stop")
        assert resp.status_code == 200

    assert get_engine_desired() == "off"

    await monitor.start()
    await asyncio.sleep(0.12)
    await monitor.stop()

    assert not spawned
    assert monitor.snapshot().message == "engine_desired_off"


@pytest.mark.asyncio
async def test_stop_engine_sync_persists_desired_off(tmp_path: Path) -> None:
    from core.inference.engine_manager import stop_engine_sync

    set_engine_desired("on")
    with patch("core.inference.engine_manager.stop_all_engines"):
        status = stop_engine_sync()
    assert status.desired == "off"
    assert get_engine_desired() == "off"
    engine_file = tmp_path / "engine.json"
    assert engine_file.is_file()
    assert json.loads(engine_file.read_text())["desired"] == "off"

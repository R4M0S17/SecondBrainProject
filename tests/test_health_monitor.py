from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.inference.health_monitor import LlamaServerHealthMonitor
from core.observability.ram_monitor import RamMonitor
from ui.tray.server import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_health_monitor_sets_up_after_successful_ping():
    ping_results = [False, True, True]

    async def fake_ping() -> bool:
        return ping_results.pop(0) if ping_results else True

    monitor = LlamaServerHealthMonitor(
        "http://127.0.0.1:8080",
        ping_interval_s=0.02,
        failure_threshold=2,
        ping=fake_ping,
        spawn_engine=lambda: None,
    )
    await monitor.start()
    await asyncio.sleep(0.08)
    await monitor.stop()

    assert monitor.snapshot().llama_server == "up"


@pytest.mark.asyncio
async def test_health_monitor_restarts_after_consecutive_failures():
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
    await monitor.start()
    await asyncio.sleep(0.1)
    await monitor.stop()

    snap = monitor.snapshot()
    assert spawned
    assert snap.restart_count_session == 1
    assert snap.llama_server in ("restarting", "down")
    assert snap.last_restart_at is not None


@pytest.mark.asyncio
async def test_health_monitor_defers_restart_on_ram_critical():
    spawned: list[str] = []
    ram = MagicMock(spec=RamMonitor)
    ram.snapshot.return_value = {
        "pressure": "critical",
        "used_gb": 7.0,
        "available_gb": 0.4,
        "total_gb": 8.0,
    }

    async def always_fail() -> bool:
        return False

    monitor = LlamaServerHealthMonitor(
        "http://127.0.0.1:8080",
        ping_interval_s=0.02,
        failure_threshold=1,
        ping=always_fail,
        ram_monitor=ram,
        spawn_engine=lambda: spawned.append("ok"),
    )
    await monitor.start()
    await asyncio.sleep(0.06)
    await monitor.stop()

    assert not spawned
    assert monitor.snapshot().llama_server == "down"
    assert monitor.snapshot().message == "ram_pressure_critical"


@pytest.mark.asyncio
async def test_health_monitor_restart_limit():
    spawned: list[str] = []

    async def always_fail() -> bool:
        return False

    monitor = LlamaServerHealthMonitor(
        "http://127.0.0.1:8080",
        ping_interval_s=0.01,
        failure_threshold=1,
        max_restarts_per_window=2,
        restart_window_s=60.0,
        ping=always_fail,
        spawn_engine=lambda: spawned.append("ok"),
    )
    monitor._restart_times = [datetime.now(UTC), datetime.now(UTC)]

    await monitor.start()
    await asyncio.sleep(0.05)
    await monitor.stop()

    assert not spawned
    assert monitor.snapshot().message == "restart_limit_exceeded"


@pytest.mark.asyncio
async def test_api_health_endpoint(client):
    from ui.tray.server import app_state

    async def ok_ping() -> bool:
        return True

    app_state.llama_health_monitor = LlamaServerHealthMonitor(
        "http://127.0.0.1:8080",
        ping_interval_s=60.0,
        ping=ok_ping,
        spawn_engine=lambda: None,
    )
    app_state.llama_health_monitor._state = "up"

    async with client as c:
        resp = await c.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["llama_server"] == "up"
    assert data["restart_count_session"] == 0

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core.inference.engine_desired import get_engine_desired, set_engine_desired
from core.inference.health_monitor import LlamaServerHealthMonitor


@pytest.fixture
def engine_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "engine.json"
    monkeypatch.setenv("CEREBRO_STATE", str(tmp_path))
    return path


def test_engine_desired_defaults_to_off(engine_state_file: Path) -> None:
    assert get_engine_desired() == "off"


def test_engine_desired_persists_off(engine_state_file: Path) -> None:
    set_engine_desired("off")
    assert engine_state_file.is_file()
    assert get_engine_desired() == "off"


def test_engine_desired_persists_on(engine_state_file: Path) -> None:
    set_engine_desired("off")
    set_engine_desired("on")
    assert get_engine_desired() == "on"


@pytest.mark.asyncio
async def test_health_monitor_skips_restart_when_engine_desired_off(
    engine_state_file: Path,
) -> None:
    set_engine_desired("off")
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

    assert not spawned
    snap = monitor.snapshot()
    assert snap.llama_server == "down"
    assert snap.message == "engine_desired_off"


@pytest.mark.asyncio
async def test_health_monitor_restarts_when_engine_desired_on(
    engine_state_file: Path,
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
    await monitor.start()
    await asyncio.sleep(0.1)
    await monitor.stop()

    assert spawned

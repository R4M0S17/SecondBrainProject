"""Unit tests for core.observability.ram_monitor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.observability.ram_monitor import RamMonitor


@pytest.fixture
def monitor() -> RamMonitor:
    return RamMonitor()


def test_snapshot_pressure_ok(monkeypatch, monitor: RamMonitor) -> None:
    vm = MagicMock()
    vm.total = 16 * 1024**3
    vm.available = 4.0 * 1024**3
    monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
    s = monitor.snapshot()
    assert s["pressure"] == "ok"
    assert s["available_gb"] == pytest.approx(4.0, rel=0.01)


def test_snapshot_pressure_warn(monkeypatch, monitor: RamMonitor) -> None:
    vm = MagicMock()
    vm.total = 16 * 1024**3
    vm.available = 1.5 * 1024**3
    monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
    assert monitor.snapshot()["pressure"] == "warn"


def test_snapshot_pressure_critical(monkeypatch, monitor: RamMonitor) -> None:
    vm = MagicMock()
    vm.total = 16 * 1024**3
    vm.available = 0.5 * 1024**3
    monkeypatch.setattr("psutil.virtual_memory", lambda: vm)
    assert monitor.snapshot()["pressure"] == "critical"

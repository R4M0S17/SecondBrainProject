"""RAM pressure snapshot for /api/status and query backpressure."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Literal, TypedDict

import psutil

RamPressure = Literal["ok", "warn", "critical"]

_ram_pressure: ContextVar[RamPressure] = ContextVar("_ram_pressure", default="ok")


def set_ram_pressure(p: RamPressure) -> None:
    _ram_pressure.set(p)


def current_ram_pressure() -> RamPressure:
    return _ram_pressure.get()


def refresh_ram_pressure() -> RamPressure:
    snap = RamMonitor().snapshot()
    _ram_pressure.set(snap["pressure"])
    return snap["pressure"]


class RamSnapshot(TypedDict):
    used_gb: float
    available_gb: float
    total_gb: float
    pressure: RamPressure


class RamMonitor:
    """Classifies memory pressure from host available RAM (Cerebro / 8 GB safe profile)."""

    def snapshot(self) -> RamSnapshot:
        vm = psutil.virtual_memory()
        total_gb = vm.total / (1024**3)
        available_gb = vm.available / (1024**3)
        used_gb = total_gb - available_gb
        if available_gb < 1.0:
            pressure: RamPressure = "critical"
        elif available_gb < 1.8:
            pressure = "warn"
        else:
            pressure = "ok"
        return {
            "used_gb": round(used_gb, 2),
            "available_gb": round(available_gb, 2),
            "total_gb": round(total_gb, 2),
            "pressure": pressure,
        }

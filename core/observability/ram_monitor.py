"""RAM pressure snapshot for /api/status and query backpressure."""

from __future__ import annotations

from typing import Literal, TypedDict

import psutil

RamPressure = Literal["ok", "warn", "critical"]


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

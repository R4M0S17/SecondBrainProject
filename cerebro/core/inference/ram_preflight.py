"""Pre-flight RAM checks before llama.cpp inference."""

from __future__ import annotations

import os

from loguru import logger

from core.inference.inference_warnings import append_inference_warnings, mark_skip_context_enricher
from core.inference.prompt_cache import prompt_cache_path
from core.observability.ram_monitor import RamMonitor, set_ram_pressure

RAM_WARNING_CRITICAL = "ram_pressure_critical"
RAM_WARNING_WARN = "ram_pressure_warn"

_MIN_AVAILABLE_GB = float(os.getenv("CEREBRO_RAM_MIN_AVAILABLE_GB", "0.5"))


def _purge_prompt_cache() -> None:
    cache = prompt_cache_path()
    sidecar = cache.with_name(cache.name + ".sha256")
    if cache.exists():
        cache.unlink()
    if sidecar.exists():
        sidecar.unlink()


def run_ram_preflight(monitor: RamMonitor | None = None) -> list[str]:
    """Log pressure, optionally purge caches, and record warning codes for metadata."""
    snap = (monitor or RamMonitor()).snapshot()
    set_ram_pressure(snap["pressure"])
    warnings: list[str] = []

    critical = snap["pressure"] == "critical" or snap["available_gb"] < _MIN_AVAILABLE_GB
    if critical:
        logger.warning(
            "System RAM critical ({} / {} GB, available {} GB); inference may trigger swap",
            snap["used_gb"],
            snap["total_gb"],
            snap["available_gb"],
        )
        warnings.append(RAM_WARNING_CRITICAL)
        _purge_prompt_cache()
        mark_skip_context_enricher()
    elif snap["pressure"] == "warn":
        warnings.append(RAM_WARNING_WARN)

    if warnings:
        append_inference_warnings(warnings)
    return warnings


def collect_ram_warnings(monitor: RamMonitor | None = None) -> list[str]:
    """Non-destructive snapshot for API handlers (no cache purge)."""
    snap = (monitor or RamMonitor()).snapshot()
    if snap["pressure"] == "critical" or snap["available_gb"] < _MIN_AVAILABLE_GB:
        return [RAM_WARNING_CRITICAL]
    if snap["pressure"] == "warn":
        return [RAM_WARNING_WARN]
    return []

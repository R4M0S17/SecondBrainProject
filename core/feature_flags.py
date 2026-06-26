"""Product feature flags — single source of truth for optional capabilities."""

from __future__ import annotations

import os
from typing import Any

MAIN_CHAT_MODEL = "Qwen3.5-2B-UD-Q4_K_XL.gguf"
LOW_POWER_CHAT_MODEL = "qwen2.5-0.5b-instruct-q5_k_m.gguf"


def low_power_mode_enabled() -> bool:
    """Low Power (0.5B Nano) is off by default until Nano v2 ships."""
    return os.getenv("CEREBRO_LOW_POWER_ENABLED", "").lower() in ("1", "true", "yes")


def auto_start_engine_enabled() -> bool:
    """Whether main.py should spawn llama-server on boot (legacy: opt-in via true)."""
    return os.getenv("CEREBRO_AUTO_START_ENGINE", "false").lower() in ("1", "true", "yes")


def is_sandbox() -> bool:
    """True when running in Docker/sandbox mode (no macOS calendar/automation tools)."""
    return os.getenv("CEREBRO_MODE", "native").lower() == "sandbox"


def is_low_power_model(model: str | None) -> bool:
    if not model:
        return False
    lower = model.lower()
    return "0.5b" in lower or "0_5b" in lower


def apply_profile_guard(config: dict[str, Any]) -> dict[str, Any]:
    """Force normal profile + main model when Low Power is disabled."""
    if low_power_mode_enabled():
        return config
    out = dict(config)
    if out.get("profile") == "low-power":
        out["profile"] = "normal"
    model = out.get("model")
    if isinstance(model, str) and is_low_power_model(model):
        out["model"] = MAIN_CHAT_MODEL
    return out


def config_needs_low_power_migration(config: dict[str, Any]) -> bool:
    if low_power_mode_enabled():
        return False
    if config.get("profile") == "low-power":
        return True
    model = config.get("model")
    return isinstance(model, str) and is_low_power_model(model)

"""Persist user intent for llama-server lifecycle (engine-backend split)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

EngineDesired = Literal["on", "off"]


def _state_path() -> Path:
    state_dir = Path(os.getenv("CEREBRO_STATE", "~/.cerebro/state")).expanduser()
    return state_dir / "engine.json"


def get_engine_desired() -> EngineDesired:
    """Return whether the user wants the local llama-server running."""
    path = _state_path()
    if not path.is_file():
        return "off"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        desired = data.get("desired", "off")
        if desired == "off":
            return "off"
        if desired == "on":
            return "on"
    except (json.JSONDecodeError, OSError, TypeError):
        pass
    return "off"


def set_engine_desired(desired: EngineDesired) -> None:
    """Persist user intent (used by /api/engine/start|stop in a later phase)."""
    if desired not in ("on", "off"):
        raise ValueError(f"invalid engine desired state: {desired!r}")
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"desired": desired}, indent=2) + "\n", encoding="utf-8")

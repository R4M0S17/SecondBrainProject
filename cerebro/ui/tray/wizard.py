"""Module 13 — First-launch onboarding wizard.

Three-step flow driven by the Tauri frontend via /wizard/* endpoints:
    1. check_llamacpp()    — verify llama.cpp server is reachable (GET /health)
    2. check_models()      — verify required GGUF files exist in bin/models/
    3. set_watched_paths() — validate and persist folder list to settings.toml

A sentinel file at data_dir/.wizard_complete marks completion; its presence
is the sole source of truth for is_first_launch().
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import httpx
import psutil
from loguru import logger

# ── constants ─────────────────────────────────────────────────────────────────

_DEFAULT_SETTINGS = Path(__file__).parent.parent.parent / "config" / "settings.toml"
_MODELS_DIR = Path(__file__).parent.parent.parent / "bin" / "models"


# ── public types ──────────────────────────────────────────────────────────────


class WizardStep(StrEnum):
    LLAMACPP = "llamacpp"
    MODEL = "model"
    FOLDERS = "folders"
    DONE = "done"


class WizardError(Exception): ...


def recommend_lite_profile() -> bool:
    """True when total system RAM is at most 10 GB (wizard may suggest lite profile)."""
    try:
        return psutil.virtual_memory().total <= 10 * 2**30
    except Exception:
        return False


# ── session ───────────────────────────────────────────────────────────────────


@dataclass
class WizardSession:
    """Stateless wizard session; sentinel file on disk tracks completion."""

    data_dir: Path
    chat_model: str = "Qwen_Qwen3.5-2B-Q4_K_M.gguf"
    embed_model: str = "nomic-embed-text"

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)

    @property
    def _sentinel(self) -> Path:
        return self.data_dir / ".wizard_complete"

    # ── launch detection ──────────────────────────────────────────────────────

    def is_first_launch(self) -> bool:
        return not self._sentinel.exists()

    def current_step(self) -> WizardStep:
        return WizardStep.DONE if self._sentinel.exists() else WizardStep.LLAMACPP

    @property
    def skip_llamacpp_check(self) -> bool:
        return os.environ.get("CEREBRO_INFERENCE_BACKEND", "").lower() == "claude"

    @property
    def skip_models_check(self) -> bool:
        return os.environ.get("CEREBRO_INFERENCE_BACKEND", "").lower() == "claude"

    def mark_setup_complete(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._sentinel.touch()

    # ── step 1: llama.cpp ─────────────────────────────────────────────────────

    def check_llamacpp(self) -> bool:
        """Return True if the llama.cpp server answers GET /health with HTTP 200."""
        url = os.getenv("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080")
        try:
            r = httpx.get(f"{url}/health", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    # ── step 2: model verification ────────────────────────────────────────────

    def check_models(self, models_dir: Path | None = None) -> bool:
        """Return True if at least one GGUF file exists in bin/models/."""
        d = models_dir or _MODELS_DIR
        if not d.is_dir():
            return False
        return any(d.glob("*.gguf"))

    # ── step 3: folder selection ──────────────────────────────────────────────

    def set_watched_paths(
        self,
        paths: list[str],
        *,
        settings_path: Path | None = None,
    ) -> None:
        """Validate *paths*, write to settings.toml, then mark wizard complete."""
        if not paths:
            raise WizardError("At least one folder must be selected.")

        resolved: list[str] = []
        for p in paths:
            rp = Path(p).expanduser().resolve()
            if not rp.is_dir():
                raise WizardError(f"Not a valid directory: {p}")
            resolved.append(str(rp))

        _write_watched_paths(resolved, settings_path or _DEFAULT_SETTINGS)
        self.mark_setup_complete()
        logger.info("Watched paths set: {}", resolved)


# ── config helper ─────────────────────────────────────────────────────────────


def _write_watched_paths(paths: list[str], settings_path: Path) -> None:
    """Patch watched_paths in settings.toml using an in-place line replacement."""
    text = settings_path.read_text(encoding="utf-8")
    new_value = "watched_paths = " + json.dumps(paths)
    patched = re.sub(r"^watched_paths\s*=.*$", new_value, text, flags=re.MULTILINE)
    settings_path.write_text(patched, encoding="utf-8")

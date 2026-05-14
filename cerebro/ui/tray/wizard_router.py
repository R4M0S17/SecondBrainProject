"""Module 13 — FastAPI router for the first-launch onboarding wizard.

Mount on the main app at startup (optional — only needed when is_first_launch()):

    from ui.tray.wizard_router import wizard_router
    app.include_router(wizard_router)

Endpoints:
    GET  /wizard/status           — {is_first_launch, step}
    POST /wizard/step/llamacpp    — check llama.cpp server reachability
    POST /wizard/step/model       — verify GGUF model files exist in bin/models/
    POST /wizard/step/folders     — save watched paths and complete setup

The production tray app uses ``/api/wizard/*`` in ``ui/tray/server.py`` (including
``POST /api/wizard/reprobe-calendar-permission`` after the user grants Calendar
Automation). This legacy router is kept for packaging tests and alternate mounts.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ui.tray.wizard import WizardError, WizardSession

wizard_router = APIRouter(prefix="/wizard", tags=["wizard"])

_DATA_DIR = Path(os.path.expanduser(os.getenv("CEREBRO_DATA", "~/.cerebro")))


def _session() -> WizardSession:
    return WizardSession(data_dir=_DATA_DIR)


# ── request models ────────────────────────────────────────────────────────────


class FolderSelection(BaseModel):
    paths: list[str]


# ── endpoints ─────────────────────────────────────────────────────────────────


@wizard_router.get("/status")
def wizard_status() -> dict:
    s = _session()
    return {"is_first_launch": s.is_first_launch(), "step": s.current_step().value}


@wizard_router.post("/step/llamacpp")
def wizard_check_llamacpp() -> dict:
    s = _session()
    if s.skip_llamacpp_check:
        return {
            "ok": True,
            "status": "skipped",
            "reason": "Claude API mode — llama.cpp not needed for inference",
        }
    return {"ok": s.check_llamacpp()}


@wizard_router.post("/step/model")
def wizard_check_models() -> dict:
    s = _session()
    if s.skip_models_check:
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        return {
            "ok": has_key,
            "status": "skipped",
            "message": (
                "ANTHROPIC_API_KEY is set — Claude API ready"
                if has_key
                else "Set ANTHROPIC_API_KEY for Claude API inference"
            ),
        }
    return {"ok": s.check_models()}


@wizard_router.post("/step/folders")
def wizard_set_folders(body: FolderSelection) -> dict:
    try:
        _session().set_watched_paths(body.paths)
        return {"ok": True}
    except WizardError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

"""Shared workflow recording and persistence logic for API and agent tools."""

from __future__ import annotations

import subprocess
import time
from typing import Any

from loguru import logger

from core.automation.generalizer import GeneralizationError, generalize_events
from core.automation.recorder import ActionEvent, HAS_QUARTZ
from core.automation.recipes import run_recipe

MIN_RECORDING_EVENTS = 3


def event_to_preview(ev: ActionEvent) -> dict[str, Any]:
    app = ev.app_name or "unknown"
    match ev.action_type:
        case "key_down":
            detail = f"key '{ev.key_char or ev.key_code}'"
        case "left_click" | "right_click":
            detail = f"click at ({ev.mouse_x}, {ev.mouse_y})"
        case "modifier":
            detail = "modifier changed"
        case _:
            detail = ev.action_type
    return {
        "timestamp": ev.timestamp,
        "app": app,
        "action": ev.action_type,
        "detail": detail,
    }


def events_to_steps(events: list[ActionEvent]) -> list[dict[str, Any]]:
    """Build human-readable steps from raw events (fallback when LLM omits steps)."""
    steps: list[dict[str, Any]] = []
    for i, ev in enumerate(events, 1):
        preview = event_to_preview(ev)
        steps.append(
            {
                "order": i,
                "app": preview["app"],
                "action": preview["action"],
                "detail": preview["detail"],
            }
        )
    return steps


class RecordingUnavailableError(Exception):
    """Recorder missing or macOS accessibility not granted."""

    def __init__(self, error_key: str = "workflows.error.accessibility_required") -> None:
        self.error_key = error_key
        super().__init__(error_key)


class RecordingConflictError(Exception):
    """Recording already active or no active session."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class TooFewEventsError(Exception):
    """Not enough captured events to generalize."""

    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"Only {count} events captured; need at least {MIN_RECORDING_EVENTS}")


def _require_recorder(recorder: Any) -> None:
    if recorder is None:
        raise RecordingUnavailableError("workflows.error.recorder_unavailable")
    if not HAS_QUARTZ:
        raise RecordingUnavailableError("workflows.error.recorder_unavailable")


def start_recording(recorder: Any) -> dict[str, Any]:
    _require_recorder(recorder)
    if recorder.is_recording:
        raise RecordingConflictError("Recording already in progress")
    recorder.start()
    return {"status": "recording", "started_at": recorder.started_at}


def get_recording_status(recorder: Any) -> dict[str, Any]:
    if recorder is None:
        return {
            "recording": False,
            "event_count": 0,
            "apps": [],
            "duration_sec": 0.0,
            "started_at": None,
            "preview": [],
        }
    preview = [event_to_preview(ev) for ev in recorder.get_events()[-30:]]
    return {
        "recording": recorder.is_recording,
        "event_count": recorder.event_count,
        "apps": recorder.get_unique_apps(),
        "duration_sec": recorder.duration_sec,
        "started_at": recorder.started_at,
        "preview": preview,
    }


def cancel_recording(recorder: Any) -> dict[str, Any]:
    _require_recorder(recorder)
    if not recorder.is_recording:
        raise RecordingConflictError("No recording in progress")
    recorder.cancel()
    return {"status": "cancelled"}


async def stop_and_create_workflow(
    recorder: Any,
    workflow_store: Any,
    chat_provider_getter: Any,
    *,
    name: str | None = None,
) -> dict[str, Any]:
    _require_recorder(recorder)
    if not recorder.is_recording:
        raise RecordingConflictError("No recording in progress")

    events = recorder.stop()
    if len(events) < MIN_RECORDING_EVENTS:
        raise TooFewEventsError(len(events))

    provider = chat_provider_getter() if callable(chat_provider_getter) else None
    if provider is None:
        raise GeneralizationError("No inference provider available")

    try:
        result = await generalize_events(events, provider)
    except Exception:
        logger.exception("Workflow generalization failed")
        raise

    if workflow_store is None:
        raise RuntimeError("Workflow store not available")

    steps = result.get("steps") or events_to_steps(events)
    wf_name = name or result.get("name", "Untitled Workflow")

    wid = workflow_store.save(
        name=wf_name,
        applescript=result["applescript"],
        description=result.get("description", ""),
        parameters=result.get("parameters", []),
        tags=result.get("tags", []),
        steps=steps,
        workflow_type="desktop",
    )
    wf = workflow_store.get(wid)
    if wf is None:
        raise RuntimeError("Failed to load saved workflow")
    return wf


def _build_osascript_argv(parameters: list[dict[str, Any]], params: dict[str, str]) -> list[str]:
    argv: list[str] = []
    for spec in parameters:
        name = spec.get("name", "")
        if name in params and str(params[name]).strip():
            argv.append(str(params[name]))
        elif spec.get("default") is not None:
            argv.append(str(spec["default"]))
        else:
            argv.append("")
    return argv


def execute_desktop_workflow(
    wf: dict[str, Any],
    params: dict[str, str] | None = None,
) -> tuple[bool, str, str | None]:
    """Run AppleScript workflow. Returns (success, output_or_message, error)."""
    applescript = wf.get("applescript", "")
    if not applescript.strip():
        return False, "", "Workflow has no AppleScript"

    merged = params or {}
    argv = _build_osascript_argv(wf.get("parameters") or [], merged)
    cmd = ["osascript", "-e", applescript, *argv]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0)
    except subprocess.TimeoutExpired:
        return False, "", "Workflow exceeded maximum time (30s)"
    except Exception as exc:
        logger.exception("Workflow execution failed")
        return False, "", str(exc)

    if result.returncode != 0:
        err = result.stderr.strip() or "osascript failed"
        return False, "", err

    output = result.stdout.strip()
    message = f"Workflow ejecutado correctamente.\n{output}" if output else "Workflow ejecutado correctamente."
    return True, message, None


def format_dry_run(wf: dict[str, Any], params: dict[str, str] | None = None) -> str:
    """Human-readable preview without executing."""
    lines = [f"Dry run — {wf.get('name', 'workflow')}", ""]
    for step in wf.get("steps") or []:
        order = step.get("order", "?")
        action = step.get("action", "")
        app = step.get("app")
        prefix = f"{order}. "
        lines.append(f"{prefix}{action}" + (f" ({app})" if app else ""))
    merged = params or {}
    if merged:
        lines.append("")
        lines.append("Parámetros:")
        for k, v in merged.items():
            lines.append(f"  {k} = {v}")
    wf_type = wf.get("workflow_type") or "desktop"
    if wf_type == "desktop" and wf.get("applescript"):
        lines.append("")
        lines.append("(AppleScript no ejecutado en dry-run)")
    return "\n".join(lines)


async def run_workflow(
    workflow_store: Any,
    workflow_id: str,
    params: dict[str, str] | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute workflow (desktop or recipe), persist run history, return API payload."""
    if workflow_store is None:
        return {"result": "Error: workflow store no disponible.", "success": False}

    wf = workflow_store.get(workflow_id)
    if wf is None:
        return {"result": f"Error: workflow '{workflow_id}' no encontrado.", "success": False}

    started = time.time()
    workflow_type = wf.get("workflow_type") or "desktop"
    merged_params = {k: str(v) for k, v in (params or {}).items()}

    if dry_run:
        message = format_dry_run(wf, merged_params)
        finished = time.time()
        run_id = workflow_store.record_run(
            workflow_id,
            started_at=started,
            finished_at=finished,
            success=True,
            output=message,
            params=merged_params,
        )
        return {
            "result": message,
            "success": True,
            "run_id": run_id,
            "dry_run": True,
        }

    if workflow_type == "recipe":
        recipe_key = wf.get("recipe_key") or ""
        output = run_recipe(recipe_key, wf, merged_params)
        success = not output.startswith("Error")
        error = output if not success else None
        message = output
    else:
        success, message, error = execute_desktop_workflow(wf, merged_params)

    finished = time.time()
    run_id = workflow_store.record_run(
        workflow_id,
        started_at=started,
        finished_at=finished,
        success=success,
        output=message if success else None,
        error=error or (message if not success else None),
        params=merged_params,
    )
    if success:
        workflow_store.increment_run_count(workflow_id)

    return {
        "result": message,
        "success": success,
        "run_id": run_id,
        "error": error,
    }

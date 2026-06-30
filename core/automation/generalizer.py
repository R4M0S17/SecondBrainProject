"""LLM-based generalization: raw ActionEvent[] → reusable AppleScript.

When a recording session is stopped, the event sequence is sent to the
primary chat provider which outputs an AppleScript snippet with
parameterised variables.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from core.automation.recorder import ActionEvent

# Helper script written to disk — avoids shell quoting issues in AppleScript
_CLICK_HELPER_PATH = Path.home() / ".cerebro" / "click_helper.py"
_CLICK_HELPER_SRC = '''\
#!/usr/bin/env python3
"""Mouse click helper for Cerebro workflows. Args: x y [right]"""
import sys, time
try:
    import Quartz
    x = int(sys.argv[1])
    y = int(sys.argv[2])
    right = len(sys.argv) > 3 and sys.argv[3] == "right"
    btn_down = Quartz.kCGEventRightMouseDown if right else Quartz.kCGEventLeftMouseDown
    btn_up   = Quartz.kCGEventRightMouseUp   if right else Quartz.kCGEventLeftMouseUp
    btn      = Quartz.kCGMouseButtonRight    if right else Quartz.kCGMouseButtonLeft
    pt = Quartz.CGPoint(x, y)
    for t in (btn_down, btn_up):
        e = Quartz.CGEventCreateMouseEvent(None, t, pt, btn)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
    time.sleep(0.05)
except Exception as exc:
    print(f"click_helper error: {exc}", file=sys.stderr)
    sys.exit(1)
'''


def _ensure_click_helper() -> str:
    """Write click_helper.py to ~/.cerebro/ and return its path."""
    _CLICK_HELPER_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CLICK_HELPER_PATH.write_text(_CLICK_HELPER_SRC)
    _CLICK_HELPER_PATH.chmod(0o755)
    return str(_CLICK_HELPER_PATH)


# Python interpreter from the current venv
_PYTHON = sys.executable

_GENERALIZATION_PROMPT = """\
Eres un ingeniero de automatización macOS. Tu trabajo es analizar una
secuencia de acciones de usuario capturadas y generar un script AppleScript
reutilizable que reproduzca esas acciones en las apps target.

REGLAS:
1. IGNORA completamente acciones en apps: Cerebro, python3, python3.14, Electron.
2. Enfócate en las acciones en el resto de apps (Finder, Safari, Notes, etc.).
3. Usa System Events para clicks y keystrokes reales.
4. El script DEBE ser ejecutable con `osascript`.
5. Para clicks: tell application "System Events" to click at {x, y}
6. Para teclas: tell application "System Events" to keystroke "texto"
7. Activa la app target antes de sus acciones: tell application "X" to activate

Responde SOLO con JSON válido, sin texto antes ni después, sin markdown:
{"name":"nombre","description":"descripción","applescript":"script completo aquí","parameters":[],"steps":[],"tags":[]}

La secuencia de acciones capturadas:
"""


def _events_to_text(events: list[ActionEvent]) -> str:
    """Format events as human-readable action log."""
    lines = []
    for i, ev in enumerate(events, 1):
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
        lines.append(f"  {i}. [{app}] {detail}")
    return "\n".join(lines)


def _extract_json(raw: str) -> dict[str, Any]:
    """Try several strategies to extract and return a parsed JSON dict from LLM output."""
    raw = raw.strip()

    # Strip <think>...</think> blocks (Qwen3)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Strip markdown fences ```json ... ``` or ``` ... ```
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        candidate = fence.group(1).strip()
        try:
            return json.loads(candidate)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    # Try the full raw string first
    try:
        parsed: dict[str, Any] = json.loads(raw)
        # Handle agent wrapper format: {"action":"answer","answer":"..."}
        if isinstance(parsed, dict) and "answer" in parsed and "applescript" not in parsed:
            # The model wrapped the response — treat answer as the raw text
            inner = parsed["answer"]
            return _extract_json(inner)
        return parsed
    except json.JSONDecodeError:
        pass

    # Find outermost { ... } block and retry
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in: {raw[:300]}")


def _fallback_applescript(events: list[ActionEvent]) -> str:
    """Generate working AppleScript that replays captured actions.

    - Mouse clicks: calls click_helper.py via do shell script (no quoting issues).
    - Keystrokes: uses System Events keystroke / key code.
    """
    helper = _ensure_click_helper()
    python = _PYTHON

    EXCLUDED_APPS = {"Cerebro", "cerebro", "Electron", "python3", "python3.14"}
    MODIFIER_KEYS = {
        "Command",
        "Shift",
        "Option",
        "Control",
        "RightShift",
        "RightOption",
        "RightControl",
        "Fn",
        "CapsLock",
    }
    SPECIAL_KEY_CODES = {"Return", "Tab", "Space", "Delete", "Escape"}

    current_app: str | None = None
    action_blocks: list[str] = []

    for ev in events:
        app = ev.app_name
        if app and app not in EXCLUDED_APPS and app != current_app:
            action_blocks.append(f'tell application "{app}" to activate')
            action_blocks.append("delay 0.4")
            current_app = app

        if ev.action_type == "key_down" and ev.key_char:
            char = ev.key_char
            if char in MODIFIER_KEYS:
                pass  # skip standalone modifiers
            elif char in SPECIAL_KEY_CODES and ev.key_code is not None:
                action_blocks.append(f'tell application "System Events" to key code {ev.key_code}')
            elif len(char) == 1:
                escaped = char.replace("\\", "\\\\").replace('"', '\\"')
                action_blocks.append(f'tell application "System Events" to keystroke "{escaped}"')

        elif ev.action_type in ("left_click", "right_click") and ev.mouse_x is not None:
            x, y = int(ev.mouse_x), int(ev.mouse_y)  # type: ignore[arg-type]
            right_arg = " right" if ev.action_type == "right_click" else ""
            # Clean path — no spaces or special chars that need escaping
            action_blocks.append(f'do shell script "{python} {helper} {x} {y}{right_arg}"')
            action_blocks.append("delay 0.15")

    if not action_blocks:
        return (
            "-- No se grabaron acciones fuera de Cerebro\n"
            'display dialog "No hay acciones para reproducir"'
        )

    return "-- Workflow generado automáticamente desde grabación\n\n" + "\n".join(action_blocks)


class GeneralizationError(Exception):
    pass


async def generalize_events(
    events: list[ActionEvent],
    chat_provider: Any,
    timeout: float = 90.0,
) -> dict[str, Any]:
    """Send event sequence to the LLM and parse the AppleScript result.

    Returns a dict with keys: name, description, applescript, parameters, tags.
    Falls back to a basic script if the LLM fails or returns unusable output.
    """
    if not events:
        raise GeneralizationError("No events to generalize")

    event_log = _events_to_text(events)
    messages = [
        {"role": "system", "content": _GENERALIZATION_PROMPT},
        {"role": "user", "content": event_log},
    ]

    raw = ""
    try:
        raw = await asyncio.wait_for(
            chat_provider.complete(messages, temperature=0.2),
            timeout=timeout,
        )
        logger.debug(f"Generalizer LLM raw response (first 500 chars): {raw[:500]}")
    except TimeoutError:
        logger.warning(f"Generalizer LLM timed out after {timeout}s — using fallback")
        return _make_fallback_result(events)
    except Exception as exc:
        logger.warning(f"Generalizer LLM call failed: {exc} — using fallback")
        return _make_fallback_result(events)

    # Try to parse JSON
    try:
        result = _extract_json(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            f"Generalizer could not parse JSON: {exc} — using fallback. Raw: {raw[:300]}"
        )
        return _make_fallback_result(events)

    name = result.get("name") or "Workflow grabado"
    description = result.get("description") or ""
    applescript = result.get("applescript") or ""
    parameters = result.get("parameters") or []
    steps = result.get("steps") or []
    tags = result.get("tags") or []

    # If LLM gave us empty applescript, use fallback
    if not applescript.strip():
        logger.warning("Generalizer: LLM returned empty applescript — using fallback")
        applescript = _fallback_applescript(events)

    if not steps:
        from core.automation.service import events_to_steps

        steps = events_to_steps(events)

    return {
        "name": name,
        "description": description,
        "applescript": applescript,
        "parameters": parameters,
        "steps": steps,
        "tags": tags,
    }


def _make_fallback_result(events: list[ActionEvent]) -> dict[str, Any]:
    """Build a minimal result when the LLM is unavailable or returns bad output."""
    from core.automation.service import events_to_steps

    apps = list({ev.app_name for ev in events if ev.app_name})
    name = f"Rutina en {apps[0]}" if apps else "Rutina grabada"
    return {
        "name": name,
        "description": f"Grabada automáticamente ({len(events)} acciones)",
        "applescript": _fallback_applescript(events),
        "parameters": [],
        "steps": events_to_steps(events),
        "tags": apps[:3],
    }

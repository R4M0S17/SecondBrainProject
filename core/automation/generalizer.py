"""LLM-based generalization: raw ActionEvent[] → reusable AppleScript.

When a recording session is stopped, the event sequence is sent to the
primary chat provider which outputs an AppleScript snippet with
parameterised variables.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from core.automation.recorder import ActionEvent

_GENERALIZATION_PROMPT = """\
Eres un ingeniero de automatización macOS. Tu trabajo es analizar una
secuencia de acciones de usuario capturadas y generar un script AppleScript
reutilizable que reproduzca esas acciones.

REGLAS:
1. Identifica los pasos clave y elimina redundancias.
2. Parametriza valores variables (nombres de archivos, textos, rutas).
3. El script DEBE ser ejecutable con `osascript`.
4. Incluye comentarios explicativos.
5. Si hay repeticiones (ej: mismo clic 3 veces), generaliza a un bucle.

Responde SOLO con JSON sin markdown:
{
  "name": "nombre_del_workflow",
  "description": "descripción corta",
  "applescript": "el script AppleScript completo",
  "parameters": [
    {"name": "param1", "type": "string", "description": "qué es este parámetro"}
  ],
  "tags": ["etiqueta1", "etiqueta2"]
}

La secuencia de acciones capturadas:
"""

_APPLESCRIPT_TEMPLATE = """\
-- Workflow: {name}
-- {description}

on run {param_list}
    {body}
end run
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


class GeneralizationError(Exception):
    pass


async def generalize_events(
    events: list[ActionEvent],
    chat_provider: Any,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Send event sequence to the LLM and parse the AppleScript result.

    Returns a dict with keys: ``name``, ``description``, ``applescript``,
    ``parameters``, ``tags``.

    Raises ``GeneralizationError`` on failure.
    """
    if not events:
        raise GeneralizationError("No events to generalize")

    event_log = _events_to_text(events)
    messages = [
        {"role": "system", "content": _GENERALIZATION_PROMPT},
        {"role": "user", "content": event_log},
    ]

    try:
        raw = await asyncio.wait_for(
            chat_provider.complete(messages, temperature=0.3),
            timeout=timeout,
        )
    except Exception as exc:
        raise GeneralizationError(f"LLM call failed: {exc}") from exc

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GeneralizationError(f"LLM returned invalid JSON: {exc}\nRaw: {raw[:500]}") from exc

    name = result.get("name", "Untitled Workflow")
    description = result.get("description", "")
    applescript = result.get("applescript", "")
    parameters = result.get("parameters", [])
    tags = result.get("tags", [])

    if not applescript:
        raise GeneralizationError("LLM returned empty AppleScript")

    return {
        "name": name,
        "description": description,
        "applescript": applescript,
        "parameters": parameters,
        "tags": tags,
    }

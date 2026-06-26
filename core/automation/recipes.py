"""Built-in assistant recipe templates and execution handlers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.agents.calendar_fast_path import fetch_calendar_read_answer
from core.agents.file_search_fast_path import authorized_read_paths
from core.agents.file_write_fast_path import authorized_write_paths, default_write_root
from core.tools.handlers.calendar import add_reminder
from core.tools.handlers.filesystem import search_files, write_file

_CALENDAR_TOOLS = ["get_upcoming_events", "search_upcoming", "query_events"]

RECIPE_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "recipe-calendar-week-md",
        "recipe_key": "calendar_to_file",
        "name": "Exportar semana a Markdown",
        "description": "Crea un archivo con tus eventos de esta semana",
        "parameters": [
            {
                "name": "filename",
                "type": "string",
                "description": "Nombre del archivo",
                "default": "semana.md",
            },
        ],
        "steps": [
            {"order": 1, "action": "Leer calendario de esta semana"},
            {"order": 2, "action": "Generar Markdown"},
            {"order": 3, "action": "Guardar en CEREBRO_FILES_PATH"},
        ],
        "tags": ["calendario", "archivo"],
    },
    {
        "id": "recipe-search-pdfs-desktop",
        "recipe_key": "search_pdfs_desktop",
        "name": "Buscar PDFs en Desktop",
        "description": "Lista archivos PDF en tu escritorio",
        "parameters": [
            {
                "name": "max_results",
                "type": "number",
                "description": "Máximo de resultados",
                "default": "20",
            },
        ],
        "steps": [
            {"order": 1, "action": "Buscar archivos *.pdf"},
            {"order": 2, "action": "Mostrar resultados ordenados por fecha"},
        ],
        "tags": ["archivos", "pdf"],
    },
    {
        "id": "recipe-reminder",
        "recipe_key": "add_reminder",
        "name": "Crear recordatorio",
        "description": "Añade un recordatorio al calendario",
        "parameters": [
            {
                "name": "title",
                "type": "string",
                "description": "Título del recordatorio",
                "default": "",
            },
            {
                "name": "when",
                "type": "string",
                "description": "Cuándo (ej. mañana a las 9am)",
                "default": "mañana a las 9am",
            },
        ],
        "steps": [
            {"order": 1, "action": "Interpretar fecha y hora"},
            {"order": 2, "action": "Crear evento en Calendario"},
        ],
        "tags": ["calendario", "recordatorio"],
    },
]


def list_templates() -> list[dict[str, Any]]:
    return [dict(t) for t in RECIPE_TEMPLATES]


def get_template(template_id: str) -> dict[str, Any] | None:
    for t in RECIPE_TEMPLATES:
        if t["id"] == template_id:
            return dict(t)
    return None


def install_template(
    workflow_store: Any,
    template_id: str,
    *,
    name: str | None = None,
) -> dict[str, Any] | None:
    template = get_template(template_id)
    if template is None or workflow_store is None:
        return None
    wid = workflow_store.save(
        name=name or template["name"],
        applescript="",
        description=template["description"],
        parameters=template["parameters"],
        tags=list(template.get("tags", [])),
        steps=template["steps"],
        workflow_type="recipe",
        recipe_key=template["recipe_key"],
    )
    return workflow_store.get(wid)


def _param_value(params: dict[str, str], spec: dict[str, Any]) -> str:
    name = spec["name"]
    if name in params and str(params[name]).strip():
        return str(params[name]).strip()
    default = spec.get("default")
    return str(default) if default is not None else ""


def _merge_params(wf: dict[str, Any], params: dict[str, str] | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for spec in wf.get("parameters") or []:
        merged[spec["name"]] = _param_value(params or {}, spec)
    if params:
        merged.update({k: str(v) for k, v in params.items()})
    return merged


def run_recipe(recipe_key: str, wf: dict[str, Any], params: dict[str, str] | None = None) -> str:
    """Execute a recipe workflow by key. Returns human-readable result."""
    merged = _merge_params(wf, params)
    match recipe_key:
        case "calendar_to_file":
            return _run_calendar_to_file(merged)
        case "search_pdfs_desktop":
            return _run_search_pdfs_desktop(merged)
        case "add_reminder":
            return _run_add_reminder(merged)
        case _:
            return f"Error: receta desconocida '{recipe_key}'"


def _run_calendar_to_file(params: dict[str, str]) -> str:
    filename = params.get("filename", "semana.md").strip() or "semana.md"
    if not filename.endswith(".md"):
        filename = f"{filename}.md"

    body = fetch_calendar_read_answer(
        "muéstrame los eventos de esta semana en mi calendario",
        _CALENDAR_TOOLS,
    )
    if not body or not body.strip():
        return "No se encontraron eventos de calendario para esta semana."

    write_root = default_write_root()
    target = str((Path(write_root) / filename).resolve())
    result = write_file(target, body.strip(), authorized_write_paths())
    if result.startswith("Error"):
        return result
    return f"Archivo creado: {target}\n\n{body.strip()[:500]}"


def _run_search_pdfs_desktop(params: dict[str, str]) -> str:
    try:
        max_results = int(params.get("max_results", "20") or "20")
    except ValueError:
        max_results = 20
    max_results = max(1, min(max_results, 50))

    desktop = str(Path.home() / "Desktop")
    read_paths = authorized_read_paths()
    return search_files(
        "*.pdf",
        read_paths,
        base_path=desktop,
        extension=".pdf",
        max_results=max_results,
    )


def _run_add_reminder(params: dict[str, str]) -> str:
    title = params.get("title", "").strip()
    when = params.get("when", "").strip()
    if not title:
        return "Error: el título del recordatorio es obligatorio."
    if not when:
        return "Error: indica cuándo debe ser el recordatorio."
    return add_reminder(title=title, datetime_str=when)

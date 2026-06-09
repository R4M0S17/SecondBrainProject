from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from functools import partial
from typing import Any

from core.agents.state_store import AgentProfile


class ToolScope(StrEnum):
    LOCAL = "local"
    SANDBOXED = "sandboxed"
    RESTRICTED = "restricted"


class AuditLevel(StrEnum):
    NONE = "none"
    METADATA = "metadata"
    FULL = "full"


@dataclass
class ToolDefinition:
    name: str
    description: str
    handler: Callable
    required_permission: str
    requires_confirmation: bool
    scope: ToolScope
    audit_level: AuditLevel
    parameters: dict[str, str] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not registered")
        return self._tools[name]

    def list_for_agent(self, agent: AgentProfile) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.name in agent.authorized_tools]

    def is_authorized(self, tool_name: str, agent: AgentProfile) -> bool:
        return tool_name in agent.authorized_tools and tool_name in self._tools

    def handlers(self) -> dict[str, Callable]:
        return {name: td.handler for name, td in self._tools.items()}

    def definitions(self) -> dict[str, ToolDefinition]:
        return dict(self._tools)


def register_calendar_tools(registry: ToolRegistry) -> None:
    """Register Module 7 calendar ToolDefinitions into a ToolRegistry instance."""
    from core.tools.handlers.calendar import (
        add_reminder,
        create_calendar_event,
        delete_reminder,
        get_upcoming_events,
        query_events,
        search_upcoming,
    )

    registry.register(
        ToolDefinition(
            name="get_upcoming_events",
            description="List upcoming calendar events within a given time window",
            handler=get_upcoming_events,
            required_permission="tools.calendar.read",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={"hours_ahead": "int — número de horas hacia adelante (default: 24)"},
        )
    )
    registry.register(
        ToolDefinition(
            name="query_events",
            description="Search upcoming calendar events by keyword (title or description)",
            handler=query_events,
            required_permission="tools.calendar.read",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={
                "keyword": "str — palabra clave a buscar en título o descripción",
                "hours_ahead": "int — ventana de búsqueda en horas (default: 168)",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="search_upcoming",
            description=(
                "Search upcoming events long-range (default 365 days) by keyword. "
                "Use for 'next birthday', 'next anniversary', 'next holiday' queries."
            ),
            handler=search_upcoming,
            required_permission="tools.calendar.read",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={
                "keyword": "str — texto a buscar en título o descripción del evento",
                "days_ahead": "int — días hacia adelante a buscar (default: 365)",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="create_calendar_event",
            description="Create a timed event in Apple Calendar (use for meetings, appointments)",
            handler=create_calendar_event,
            required_permission="tools.calendar.write",
            requires_confirmation=True,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.FULL,
            parameters={
                "title": "str — título del evento",
                "datetime_str": "str — fecha/hora en lenguaje natural o ISO (ej: 'next monday at 3pm')",
                "duration_mins": "int — duración en minutos (default: 60)",
                "description": "str — descripción opcional del evento",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="add_reminder",
            description=(
                "Create a short timed reminder as an Apple Calendar event "
                "(use for 'remind me to', 'crea un recordatorio', 'recuérdame' — not meetings)"
            ),
            handler=add_reminder,
            required_permission="tools.calendar.write",
            requires_confirmation=True,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.FULL,
            parameters={
                "title": "str — título del recordatorio",
                "datetime_str": "str — fecha/hora en lenguaje natural o ISO (ej: 'next saturday', 'tomorrow at 9am')",
                "notes": "str — notas opcionales",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="delete_reminder",
            description="Delete a calendar event by exact title (including reminder-style events)",
            handler=delete_reminder,
            required_permission="tools.calendar.write",
            requires_confirmation=True,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.FULL,
            parameters={
                "title": "str — título exacto del recordatorio a borrar",
                "datetime_str": "str — opcional: día (ej. 'mañana') para acotar la búsqueda",
            },
        )
    )


def register_filesystem_tools(
    registry: ToolRegistry,
    authorized_read_paths: list[str],
    authorized_write_paths: list[str],
) -> None:
    """Register filesystem ToolDefinitions into a ToolRegistry instance.

    authorized_paths are bound via partial so the LLM never sees them as
    callable arguments.
    """
    from core.tools.handlers.execution import execute_python, run_script
    from core.tools.handlers.filesystem import (
        create_directory,
        create_python_file,
        delete_file,
        list_directory,
        read_file,
        search_files,
        write_file,
    )
    from core.tools.handlers.upload import handle_file_upload

    registry.register(
        ToolDefinition(
            name="read_file",
            description="Read the full text content of a file",
            handler=partial(read_file, authorized_paths=authorized_read_paths),
            required_permission="tools.fs.read",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={"path": "str — ruta absoluta al archivo"},
        )
    )
    registry.register(
        ToolDefinition(
            name="write_file",
            description="Write or overwrite a file with the given text content",
            handler=partial(write_file, authorized_paths=authorized_write_paths),
            required_permission="tools.fs.write",
            requires_confirmation=True,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.FULL,
            parameters={
                "path": "str — ruta absoluta al archivo destino",
                "content": "str — contenido a escribir",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="create_directory",
            description="Create a directory (and any missing parent directories)",
            handler=partial(create_directory, authorized_paths=authorized_write_paths),
            required_permission="tools.fs.write",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={"path": "str — ruta del directorio a crear"},
        )
    )
    registry.register(
        ToolDefinition(
            name="list_directory",
            description="List the immediate contents of a directory",
            handler=partial(list_directory, authorized_paths=authorized_read_paths),
            required_permission="tools.fs.read",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={"path": "str — ruta del directorio a listar"},
        )
    )
    registry.register(
        ToolDefinition(
            name="search_files",
            description="Recursively search for files by name pattern within authorized folders",
            handler=partial(search_files, authorized_paths=authorized_read_paths),
            required_permission="tools.fs.read",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={
                "pattern": "str — patrón glob o nombre (ej: '*.py', 'report', 'README')",
                "base_path": "str — directorio raíz de búsqueda (opcional)",
                "extension": "str — filtrar por extensión (ej: '.py', '.md') (opcional)",
                "max_results": "int — límite de resultados (default: 20)",
                "name_contains": "str — subcadena en el nombre del archivo (opcional)",
                "query_text": "str — buscar texto dentro del archivo (opcional)",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="create_python_file",
            description="Save a Python script to the CerebroFiles folder (does not execute it)",
            handler=partial(create_python_file, authorized_paths=authorized_write_paths),
            required_permission="tools.fs.write",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.FULL,
            parameters={
                "filename": "str — nombre del archivo con extensión .py (sin separadores de ruta)",
                "code": "str — contenido del script Python",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="execute_python",
            description="Execute Python code in a sandboxed environment (RestrictedPython) with allowed: math, datetime, json, re, collections, itertools",
            handler=partial(execute_python),
            required_permission="tools.fs.write",
            requires_confirmation=True,
            scope=ToolScope.SANDBOXED,
            audit_level=AuditLevel.FULL,
            parameters={
                "code": "str — Python code to execute",
                "timeout_seconds": "int — maximum execution time in seconds (default: 10)",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="run_script",
            description="Execute a saved Python script file and return its output",
            handler=partial(run_script, authorized_paths=authorized_write_paths),
            required_permission="tools.fs.write",
            requires_confirmation=True,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.FULL,
            parameters={
                "filepath": "str — ruta absoluta al script .py a ejecutar",
                "timeout_seconds": "int — tiempo máximo de ejecución en segundos (default: 30)",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="delete_file",
            description="Move a file to Trash (requires confirmation)",
            handler=partial(delete_file, authorized_paths=authorized_write_paths),
            required_permission="tools.fs.write",
            requires_confirmation=True,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.FULL,
            parameters={"path": "str — ruta absoluta al archivo a eliminar"},
        )
    )
    registry.register(
        ToolDefinition(
            name="upload_file",
            description="Process an uploaded file (PDF, image, or text) and extract its content for AI analysis",
            handler=partial(handle_file_upload, authorized_paths=authorized_read_paths),
            required_permission="tools.fs.read",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={
                "file_path": "str — ruta absoluta al archivo cargado (PDF, imagen o texto)"
            },
        )
    )


def register_macos_tools(registry: ToolRegistry) -> None:
    """Register macOS app integration tools into a ToolRegistry instance."""
    from core.tools.handlers.macos import (
        create_note,
        search_notes,
        send_notification,
        spotlight_search,
    )

    registry.register(
        ToolDefinition(
            name="spotlight_search",
            description="Search the local filesystem using macOS Spotlight (mdfind)",
            handler=spotlight_search,
            required_permission="tools.macos.search",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={
                "query": "str — término de búsqueda para Spotlight",
                "max_results": "int — número máximo de resultados (default: 10)",
                "kind": "str — filtro de tipo: 'pdf', 'image', 'text', 'folder' (opcional)",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="create_note",
            description="Create a note in Apple Notes app",
            handler=create_note,
            required_permission="tools.macos.notes.write",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.FULL,
            parameters={
                "title": "str — título de la nota",
                "body": "str — contenido de la nota (texto plano o HTML)",
                "folder": "str — carpeta destino en Notes (default: 'Notes')",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="search_notes",
            description="Search Apple Notes by keyword (matches title and body)",
            handler=search_notes,
            required_permission="tools.macos.notes.read",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={
                "query": "str — palabra clave a buscar en títulos y cuerpo de notas",
                "max_results": "int — número máximo de resultados (default: 10)",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="send_notification",
            description="Send a macOS system desktop notification",
            handler=send_notification,
            required_permission="tools.macos.notify",
            requires_confirmation=False,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
            parameters={
                "title": "str — título de la notificación",
                "message": "str — cuerpo del mensaje",
            },
        )
    )


def register_math_tools(registry: ToolRegistry) -> None:
    from core.tools.handlers.math import evaluate_math

    registry.register(
        ToolDefinition(
            name="evaluate_math",
            description=(
                "Evaluate a deterministic numeric expression "
                "(arithmetic, parentheses, power). Use for any math the user asks."
            ),
            handler=evaluate_math,
            required_permission="tools.math.eval",
            requires_confirmation=False,
            scope=ToolScope.SANDBOXED,
            audit_level=AuditLevel.METADATA,
            parameters={"expression": "str — expresión numérica (ej: '17*23')"},
        )
    )


def register_automation_tools(
    registry: ToolRegistry,
    recorder: Any,
    workflow_store: Any,
    chat_provider_getter: Any,
) -> None:
    """Register Desktop Automation tools (recording + workflow playback)."""
    from core.automation.tools import (
        make_run_workflow,
        make_start_recording,
        make_stop_recording,
    )

    registry.register(
        ToolDefinition(
            name="start_recording",
            description="Begin capturing mouse and keyboard events on macOS to record a reusable workflow",
            handler=make_start_recording(recorder),
            required_permission="tools.automation.record",
            requires_confirmation=True,
            scope=ToolScope.RESTRICTED,
            audit_level=AuditLevel.FULL,
        )
    )
    registry.register(
        ToolDefinition(
            name="stop_recording",
            description="Stop recording and generalise the captured events into a reusable AppleScript workflow",
            handler=make_stop_recording(recorder, workflow_store, chat_provider_getter),
            required_permission="tools.automation.record",
            requires_confirmation=False,
            scope=ToolScope.RESTRICTED,
            audit_level=AuditLevel.FULL,
        )
    )
    registry.register(
        ToolDefinition(
            name="run_workflow",
            description="Execute a previously recorded automation workflow by its ID",
            handler=make_run_workflow(workflow_store),
            required_permission="tools.automation.execute",
            requires_confirmation=True,
            scope=ToolScope.RESTRICTED,
            audit_level=AuditLevel.FULL,
            parameters={"workflow_id": "str — ID del workflow a ejecutar"},
        )
    )


def register_web_tools(registry: ToolRegistry) -> None:
    """Register web search & fetch ToolDefinitions into a ToolRegistry instance."""
    from core.tools.handlers.web import web_fetch, web_search

    registry.register(
        ToolDefinition(
            name="web_search",
            description=(
                "Search the internet for current information using a web search engine. "
                "Use for news, facts, recent events, or any question that needs up-to-date data."
            ),
            handler=web_search,
            required_permission="tools.web.read",
            requires_confirmation=False,
            scope=ToolScope.SANDBOXED,
            audit_level=AuditLevel.METADATA,
            parameters={
                "query": "str — search query in natural language",
                "max_results": "int — number of results to return (default: 5)",
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="web_fetch",
            description=(
                "Fetch and extract readable text content from a specific URL. "
                "Use to read full articles or pages found via web_search."
            ),
            handler=web_fetch,
            required_permission="tools.web.read",
            requires_confirmation=False,
            scope=ToolScope.SANDBOXED,
            audit_level=AuditLevel.METADATA,
            parameters={"url": "str — full URL to fetch (https://...)"},
        )
    )

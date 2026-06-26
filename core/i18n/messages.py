"""User-visible message catalog (Spanish default; ``CEREBRO_LOCALE`` for locale)."""

from __future__ import annotations

import os
from typing import Any

_MESSAGES_ES: dict[str, str] = {
    "confirm.tool_pause": (
        "Necesito tu aprobación para ejecutar `{tool_name}`. "
        "Aprueba o rechaza la acción en el panel de confirmación."
    ),
    "parse.llm_fallback": (
        "No pude interpretar la respuesta del modelo. Intenta reformular tu pregunta."
    ),
    "parse.tool_unknown": "La herramienta '{tool_name}' no está disponible.",
    "fastpath.content_from_calendar": "(Contenido obtenido del calendario.)",
    "fastpath.content_generated": "(Contenido generado a partir de tu descripción.)",
    "fastpath.file_details": (
        "\n\nArchivo: `{filename}`\n"
        "Ruta: `{path}`\n"
        "Contenido ({char_count} caracteres): {content_preview}"
    ),
    "fastpath.reminder_title": "\n\n**{title}**",
    "fastpath.reminder_when": "\nCuándo: {datetime_str}",
    "fastpath.reminder_day": "\nDía: {datetime_str}",
    "error.timeout": "Timeout: la consulta superó el límite de 120 segundos.",
    "error.tool_loop": "Se detectó un bucle en el uso de herramientas. Por favor reformula tu pregunta.",
    "error.max_iterations": "Se alcanzó el límite de iteraciones. Respuesta parcial basada en el contexto disponible.",
    "error.unauthorized_tool": "Herramienta '{tool_name}' no autorizada para este agente.",
    "error.tool_not_found": "Herramienta '{tool_name}' no disponible.",
    "rag.no_info": "No encontré información sobre eso en tus documentos.",
    "web.truncated": "\n[... Texto truncado por límite de contexto]",
    "web.search_error": "Error en búsqueda {backend}: {exc_name} — {exc}",
    "web.no_results": "No se encontraron resultados.",
    "web.fetch_timeout": "Error: Timeout al acceder a {url} (límite: {timeout}s)",
    "web.fetch_http_error": "Error: HTTP {code} al acceder a {url}",
    "web.fetch_connection_error": "Error de conexión: {exc}",
    "web.no_content": "(no se pudo extraer contenido de la página)",
    "filesystem.not_found": "No se encontraron archivos ({detail}) en: {roots_label}",
    "filesystem.showing_results": "Mostrando {shown} de {total} (límite {cap}):\n",
    "filesystem.search_filter_pattern": "patrón '{value}'",
    "filesystem.search_filter_name": "nombre contiene '{value}'",
    "filesystem.search_filter_extension": "extensión '{value}'",
    "filesystem.search_filter_text": "texto '{value}'",
    "calendar.default_event_title": "Evento",
    "calendar.with_person": "Con {name}",
}

_MESSAGES_EN: dict[str, str] = {
    "confirm.tool_pause": (
        "I need your approval to run `{tool_name}`. "
        "Approve or reject the action in the confirmation panel."
    ),
    "parse.llm_fallback": (
        "I couldn't parse the model's response. Try rephrasing your question."
    ),
    "parse.tool_unknown": "The tool '{tool_name}' is not available.",
    "fastpath.content_from_calendar": "(Content obtained from calendar.)",
    "fastpath.content_generated": "(Content generated from your description.)",
    "fastpath.file_details": (
        "\n\nFile: `{filename}`\n"
        "Path: `{path}`\n"
        "Content ({char_count} chars): {content_preview}"
    ),
    "fastpath.reminder_title": "\n\n**{title}**",
    "fastpath.reminder_when": "\nWhen: {datetime_str}",
    "fastpath.reminder_day": "\nDay: {datetime_str}",
    "error.timeout": "Timeout: the query exceeded the 120-second limit.",
    "error.tool_loop": "A tool loop was detected. Please rephrase your question.",
    "error.max_iterations": (
        "Iteration limit reached. Partial answer based on available context."
    ),
    "error.unauthorized_tool": "Tool '{tool_name}' is not authorized for this agent.",
    "error.tool_not_found": "Tool '{tool_name}' is not available.",
    "rag.no_info": "I couldn't find information about that in your documents.",
    "web.truncated": "\n[... Text truncated due to context limit]",
    "web.search_error": "Search error ({backend}): {exc_name} — {exc}",
    "web.no_results": "No results found.",
    "web.fetch_timeout": "Error: Timeout fetching {url} (limit: {timeout}s)",
    "web.fetch_http_error": "Error: HTTP {code} fetching {url}",
    "web.fetch_connection_error": "Connection error: {exc}",
    "web.no_content": "(could not extract page content)",
    "filesystem.not_found": "No files found ({detail}) in: {roots_label}",
    "filesystem.showing_results": "Showing {shown} of {total} (limit {cap}):\n",
    "filesystem.search_filter_pattern": "pattern '{value}'",
    "filesystem.search_filter_name": "name contains '{value}'",
    "filesystem.search_filter_extension": "extension '{value}'",
    "filesystem.search_filter_text": "text '{value}'",
    "calendar.default_event_title": "Event",
    "calendar.with_person": "With {name}",
}


def _catalog() -> dict[str, str]:
    locale = os.getenv("CEREBRO_LOCALE", "es").lower()
    if locale.startswith("en"):
        return _MESSAGES_EN
    return _MESSAGES_ES


def _L(key: str, **kwargs: Any) -> str:
    """Resolve a message key with optional ``str.format`` placeholders."""
    template = _catalog().get(key)
    if template is None:
        return key
    return template.format(**kwargs)

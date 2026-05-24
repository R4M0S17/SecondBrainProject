"""User-visible message catalog (Spanish default; ``CEREBRO_LOCALE`` for future locales)."""

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
}

# Future: _MESSAGES_EN = {...}


def _catalog() -> dict[str, str]:
    locale = os.getenv("CEREBRO_LOCALE", "es").lower()
    if locale.startswith("en"):
        return _MESSAGES_ES  # English catalog not shipped yet — fall back to Spanish
    return _MESSAGES_ES


def _L(key: str, **kwargs: Any) -> str:
    """Resolve a message key with optional ``str.format`` placeholders."""
    template = _catalog().get(key)
    if template is None:
        return key
    return template.format(**kwargs)

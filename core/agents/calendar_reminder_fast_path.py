"""Deterministic calendar write pre-route — recordatorios → eventos en Calendario (sin LLM JSON)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.tools.handlers.calendar import add_reminder, delete_reminder

_WRITE_TOOL_NAMES = frozenset({"add_reminder", "delete_reminder", "create_calendar_event"})

# crea [un] recordatorio mañana a las 3pm con nombre "pruebaCalendario"
_ADD_WHEN_TITLE_RE = re.compile(
    r"(?:crea|crear|agrega|agregar|añade|añadir)\s+(?:un\s+)?(?:recordatorio|reminder|tarea)\s+"
    r"(?P<when>.+?)\s+con\s+(?:nombre|titulo|título|llamado|called)\s+"
    r"[\"']?(?P<title>[^\"']+)[\"']?\s*$",
    re.IGNORECASE,
)

# crea recordatorio llamado X para mañana a las 3pm
_ADD_TITLE_WHEN_RE = re.compile(
    r"(?:crea|crear|agrega|agregar|añade|añadir)\s+(?:un\s+)?(?:recordatorio|reminder|tarea)\s+"
    r"(?:llamado|de\s+nombre|nombrado|called|named)\s+[\"']?(?P<title>[^\"']+)[\"']?"
    r"\s+(?:para|el|en|a)\s+(?P<when>.+?)\s*$",
    re.IGNORECASE,
)

# recuérdame comprar leche mañana a las 3pm
_RECUERDAME_RE = re.compile(
    r"(?:recu[eé]rdame|remind\s+me(?:\s+to)?)\s+"
    r"(?P<title>.+?)\s+(?:para|el|en|a|on)\s+(?P<when>.+?)\s*$",
    re.IGNORECASE,
)

# borra el recordatorio / evento pruebaCalendario
_DELETE_REMINDER_RE = re.compile(
    r"(?:borra|borrar|elimina|eliminar|quita|quitar)\s+(?:el\s+)?"
    r"(?:recordatorio|reminder|tarea|evento|event|cita)\s+"
    r"(?:del\s+calendario\s+)?"
    r"(?:llamado|de\s+nombre|nombrado|called|named)?\s*[\"']?(?P<title>[^\"']+)[\"']?\s*$",
    re.IGNORECASE,
)

_READ_HINT_RE = re.compile(
    r"\b(pr[oó]ximo|proximo|cu[aá]ndo|when|lista|listar|mu[eé]strame|muestra|hay)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReminderWriteIntent:
    action: str  # "add" | "delete"
    title: str
    when: str = ""


def _parse_add_intent(text: str) -> ReminderWriteIntent | None:
    for pattern in (_ADD_WHEN_TITLE_RE, _ADD_TITLE_WHEN_RE, _RECUERDAME_RE):
        m = pattern.search(text)
        if m:
            title = m.group("title").strip().strip("\"'")
            when = m.group("when").strip()
            if title and when:
                return ReminderWriteIntent(action="add", title=title, when=when)
    return None


def _parse_delete_intent(text: str) -> ReminderWriteIntent | None:
    m = _DELETE_REMINDER_RE.search(text)
    if not m:
        return None
    title = m.group("title").strip().strip("\"'")
    if title:
        return ReminderWriteIntent(action="delete", title=title)
    return None


def try_calendar_reminder_fast_path(
    query: str,
    authorized_tools: list[str] | None,
) -> str | None:
    """Create or delete a reminder when the query is an explicit write intent."""
    tools = set(authorized_tools or [])
    if tools and not tools & _WRITE_TOOL_NAMES:
        return None

    text = query.strip()
    if not text or _READ_HINT_RE.search(text):
        return None

    delete_intent = _parse_delete_intent(text)
    if delete_intent is not None:
        if tools and "delete_reminder" not in tools:
            return None
        return delete_reminder(delete_intent.title)

    add_intent = _parse_add_intent(text)
    if add_intent is not None:
        if tools and "add_reminder" not in tools:
            return None
        return add_reminder(add_intent.title, add_intent.when)

    return None

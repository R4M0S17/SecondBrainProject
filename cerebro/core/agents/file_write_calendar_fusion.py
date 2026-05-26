"""File write + calendar read fusion.

When the user asks to create a file whose body should come from the calendar
(e.g. próximos cumpleaños), fetch schedule text and queue ``write_file`` instead
of answering with calendar output only.
"""

from __future__ import annotations

import re

from core.agents.calendar_fast_path import fetch_calendar_read_answer
from core.agents.file_write_fast_path import (
    FileWriteIntent,
    authorized_write_paths,
    parse_file_write_intent,
)

_CALENDAR_CONTENT_RE = re.compile(
    r"\b("
    r"cumpleaños|cumpleaño|cumpleannos|cumpleanos|cumplea(?:ñ|n)os|cumplea(?:ñ|n)o|"
    r"cumple|birthday|aniversario|anniversary|"
    r"calendario|agenda|"
    r"eventos?\s+pr[oó]ximos?|pr[oó]ximos?\s+eventos?|"
    r"pr[oó]ximos?\s+\d+\s+(cumple|eventos?)|"
    r"los\s+pr[oó]ximos?\s+\d+\s+(cumple|eventos?)|"
    r"mi\s+calendario|my\s+calendar|"
    r"meetings?\s+(today|tomorrow|this\s+week)|"
    r"qu[eé]\s+tengo\s+(en\s+)?(el\s+)?(calendario|agenda)"
    r")\b",
    re.IGNORECASE,
)

_CALENDAR_TOOL_NAMES = frozenset(
    {"get_upcoming_events", "search_upcoming", "query_events"},
)


def is_calendar_backed_file_content(text: str) -> bool:
    """True when file body should be filled from calendar tools, not the LLM."""
    return bool(_CALENDAR_CONTENT_RE.search(text.strip()))


def is_file_write_calendar_export_query(query: str) -> bool:
    """True when the user wants a file whose body comes from calendar data."""
    intent = parse_file_write_intent(query.strip())
    if intent is None:
        return False
    blob = (getattr(intent, "content_spec", None) or intent.content or "").strip()
    return is_calendar_backed_file_content(blob)


def try_calendar_body_for_file_write(
    query: str,
    authorized_tools: list[str] | None,
) -> str | None:
    """Run calendar fast-path logic using the full user query (limits still apply)."""
    tools = list(authorized_tools or [])
    if tools and not (set(tools) & _CALENDAR_TOOL_NAMES):
        return None
    return fetch_calendar_read_answer(query, tools)


def try_file_write_calendar_fusion(
    query: str,
    authorized_tools: list[str] | None,
    *,
    write_roots: list[str] | None = None,
) -> FileWriteIntent | None:
    """Parse a create-file query and pre-fill body from calendar when applicable."""
    tools = list(authorized_tools or [])

    roots = write_roots or authorized_write_paths()
    intent = parse_file_write_intent(query, write_roots=roots)
    if intent is None:
        return None

    blob = (getattr(intent, "content_spec", None) or intent.content or "").strip()
    if not is_calendar_backed_file_content(blob):
        return None

    body = try_calendar_body_for_file_write(query, tools)
    if not body or not body.strip():
        return None

    return FileWriteIntent(
        path=intent.path,
        content=body.strip(),
        filename=intent.filename,
        content_source="literal",
        content_spec=blob,
        generated=True,
        filled_from="calendar",
    )

"""Deterministic calendar pre-route (Problem B / FIX_TEST2 H3.x).

Runs calendar read tools without relying on the LLM to emit valid tool JSON.
"""

from __future__ import annotations

import os
import re

from core.tools.handlers.calendar import get_upcoming_events, query_events, search_upcoming

_BIRTHDAY_RE = re.compile(
    r"\b(cumpleaños|cumpleaño|cumple|birthday|cumpleaños|aniversario|anniversary)\b",
    re.IGNORECASE,
)

_UPCOMING_RE = re.compile(
    r"\b(pr[oó]ximo|proximo|next)\s+evento\b|"
    r"\beventos?\s+(pr[oó]ximos?|proximos?|de\s+hoy|esta\s+semana|del\s+d[ií]a)\b|"
    r"\b(qu[eé]|que)\s+tengo\s+(en\s+)?(el\s+)?(calendario|agenda)\b|"
    r"\bwhat\s+do\s+i\s+have\s+(on\s+)?(my\s+)?(calendar|schedule)\b|"
    r"\bwhat'?s\s+on\s+my\s+calendar\b|"
    r"\b(lista|listar|mu[eé]strame|muestra)\s+(los\s+)?eventos\b|"
    r"\bmeetings?\s+(today|tomorrow|this\s+week)\b|"
    r"\bcalendario\s+(de\s+)?(hoy|mañana|manana|esta\s+semana)\b|"
    r"\bagenda\s+(de\s+)?(hoy|mañana|manana)\b",
    re.IGNORECASE,
)

_HOURS_RE = re.compile(r"\b(\d{1,3})\s*(horas?|hours?|h)\b", re.IGNORECASE)
_DAYS_RE = re.compile(r"\b(\d{1,3})\s*(d[ií]as?|days?)\b", re.IGNORECASE)

_CALENDAR_TOOL_NAMES = frozenset(
    {"get_upcoming_events", "search_upcoming", "query_events"},
)


def _ics_path() -> str | None:
    raw = os.getenv("CEREBRO_ICS", "~/.cerebro/calendar.ics").strip()
    if not raw:
        return None
    return os.path.expanduser(raw)


def _extract_hours(query: str, default: int = 24) -> int:
    m = _HOURS_RE.search(query)
    if m:
        return max(1, min(int(m.group(1)), 24 * 14))
    m = _DAYS_RE.search(query)
    if m:
        return max(1, min(int(m.group(1)) * 24, 24 * 30))
    if re.search(r"\besta\s+semana\b|this\s+week", query, re.I):
        return 24 * 7
    if re.search(r"\bmañana\b|\bmanana\b|\btomorrow\b", query, re.I):
        return 48
    return default


def _birthday_keyword(query: str) -> str:
    if re.search(r"\bbirthday\b", query, re.I):
        return "birthday"
    if re.search(r"\banniversary\b|\baniversario\b", query, re.I):
        return "anniversary"
    return "cumple"


def try_calendar_fast_path(
    query: str,
    authorized_tools: list[str] | None,
    *,
    ics_path: str | None = None,
) -> str | None:
    """Run a calendar read tool when the query clearly asks for schedule/birthdays."""
    tools = set(authorized_tools or [])
    if tools and not tools & _CALENDAR_TOOL_NAMES:
        return None

    text = query.strip()
    if not text:
        return None

    path = ics_path if ics_path is not None else _ics_path()

    if _BIRTHDAY_RE.search(text):
        if "search_upcoming" in tools or not tools:
            kw = _birthday_keyword(text)
            days = 365
            m = _DAYS_RE.search(text)
            if m:
                days = max(7, min(int(m.group(1)), 365))
            return search_upcoming(kw, days_ahead=days, ics_path=path)
        if "query_events" in tools:
            return query_events(_birthday_keyword(text), hours_ahead=24 * 365, ics_path=path)
        return None

    if _UPCOMING_RE.search(text):
        if "get_upcoming_events" in tools or not tools:
            hours = _extract_hours(text, default=24)
            return get_upcoming_events(hours_ahead=hours, ics_path=path)
        return None

    return None

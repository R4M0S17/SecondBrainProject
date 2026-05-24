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
    r"\b(cual|cu[aá]l)\s+es\s+el\s+pr[oó]ximo\s+evento\b|"
    r"\bevento\s+m[aá]s\s+cercano\b|"
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

_LIMIT_ONE_RE = re.compile(
    r"\b(solo|solamente|únicamente|unicamente|nada\s+más|nadamas)\s+"
    r"(un[oa]?|uno|una|1)\b|"
    r"\b(tell\s+me)\s+solo\s+un[oa]?\b|"
    r"\bdime\s+solo\s+un[oa]?\b|"
    r"\bonly\s+one\b",
    re.IGNORECASE,
)
_LIMIT_TWO_RE = re.compile(
    r"\b(solo|solamente)\s+(dos|2)\b|\bonly\s+two\b",
    re.IGNORECASE,
)
_LIMIT_THREE_RE = re.compile(
    r"\b(solo|solamente)\s+(tres|3)\b|\bonly\s+three\b",
    re.IGNORECASE,
)
_SHOW_ALL_RE = re.compile(
    r"\b(todos|todas|lista\s+completa|todos\s+los|all\s+birthdays)\b",
    re.IGNORECASE,
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
    if re.search(r"\b(pr[oó]ximo|proximo|next)\s+evento\b", query, re.I):
        return max(default, 24 * 14)
    return default


def _upcoming_max_results(query: str) -> int:
    """Cap general upcoming listings; single answer for 'próximo evento'."""
    if _SHOW_ALL_RE.search(query):
        return 0
    if _LIMIT_ONE_RE.search(query):
        return 1
    if re.search(r"\b(pr[oó]ximo|proximo|next)\s+evento\b", query, re.I):
        if not re.search(r"\beventos\b", query, re.I):
            return 1
    if _LIMIT_TWO_RE.search(query):
        return 2
    if _LIMIT_THREE_RE.search(query):
        return 3
    return 5


def _birthday_max_results(query: str) -> int:
    """Default cap 3; honor explicit solo uno/dos/tres or full list."""
    if _SHOW_ALL_RE.search(query):
        return 0
    if _LIMIT_ONE_RE.search(query):
        return 1
    if _LIMIT_TWO_RE.search(query):
        return 2
    if _LIMIT_THREE_RE.search(query):
        return 3
    return 3


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
            max_results = _birthday_max_results(text)
            return search_upcoming(kw, days_ahead=days, ics_path=path, max_results=max_results)
        if "query_events" in tools:
            return query_events(_birthday_keyword(text), hours_ahead=24 * 365, ics_path=path)
        return None

    if _UPCOMING_RE.search(text):
        if "get_upcoming_events" in tools or not tools:
            hours = _extract_hours(text, default=24)
            max_results = _upcoming_max_results(text)
            return get_upcoming_events(
                hours_ahead=hours,
                ics_path=path,
                max_events=max_results,
                fast_apple=True,
            )
        return None

    return None

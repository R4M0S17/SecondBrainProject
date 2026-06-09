"""Deterministic calendar pre-route (Problem B / FIX_TEST2 H3.x).

Runs calendar read tools without relying on the LLM to emit valid tool JSON.
"""

from __future__ import annotations

import os
import re

from core.agents.calendar_query_parse import extract_calendar_date_filter
from core.tools.handlers.calendar import (
    get_upcoming_events_for_query,
    query_events,
    search_upcoming,
)

_BIRTHDAY_RE = re.compile(
    r"\b(cumpleaños|cumpleaño|cumple|birthday|cumpleaños|aniversario|anniversary)\b",
    re.IGNORECASE,
)

_UPCOMING_RE = re.compile(
    r"\b(pr[oó]xim[oa]|proxim[oa]|next)\s+(evento|reuni[oó]n|cita|meeting)\b|"
    r"\b(pr[oó]xim[oa]|proxim[oa]|next)\s+(evento|reuni[oó]n|cita|meeting)"
    r"\s+en\s+(mi\s+)?(calendario|agenda)\b|"
    r"\b(cual|cu[aá]l)\s+es\s+(el|la)\s+pr[oó]xim[oa]\s+(evento|reuni[oó]n|cita|meeting)\b|"
    r"\bevento\s+m[aá]s\s+cercano\b|"
    r"\beventos?\s+(pr[oó]ximos?|proximos?|de\s+hoy|esta\s+semana|del\s+d[ií]a)\b|"
    r"\b(qu[eé]|que)\s+tengo\s+(en\s+)?(el\s+)?(calendario|agenda)\b|"
    r"\b(qu[eé]|que)\s+(tengo|hay)\s+(para\s+)?(mañana|manana|hoy)\b|"
    r"\bwhat\s+do\s+i\s+have\s+(on\s+)?(my\s+)?(calendar|schedule)\b|"
    r"\bwhat'?s\s+on\s+my\s+calendar\b|"
    r"\b(lista|listar|mu[eé]strame|muestra)\s+(los\s+)?eventos\b|"
    r"\bmeetings?\s+(today|tomorrow|this\s+week)\b|"
    r"\bcalendario\s+(de\s+)?(hoy|mañana|manana|esta\s+semana)\b|"
    r"\bagenda\s+(de\s+)?(hoy|mañana|manana)\b|"
    r"\b(qu[eé]|que)\s+hay\s+(en\s+)?(mi\s+)?(calendario|agenda)\b|"
    r"\bdo\s+i\s+have\s+(anything|any\s+meetings?)\b|"
    r"\bam\s+i\s+busy\b",
    re.IGNORECASE,
)

# Day-scoped schedule (may not say "próximo evento")
_DAY_SCHEDULE_RE = re.compile(
    r"\b(?:qu[eé]|que)\s+tengo\s+(?:(?:el|la|para(?:\s+el|\s+la)?)\s+)?"
    r"(?:lunes|martes|mi[eé]rcoles|miercoles|jueves|viernes|s[aá]bado|sabado|domingo|"
    r"ma[nñ]ana|manana|hoy|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
    r"\beventos?\s+del?\s+"
    r"(?:lunes|martes|mi[eé]rcoles|miercoles|jueves|viernes|s[aá]bado|sabado|domingo|"
    r"ma[nñ]ana|manana|hoy|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
    r"\breuniones?\s+del?\s+"
    r"(?:lunes|martes|mi[eé]rcoles|miercoles|jueves|viernes|s[aá]bado|sabado|domingo|"
    r"ma[nñ]ana|manana|hoy|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
    r"\bagenda\s+(?:del|de|para)\s+"
    r"(?:lunes|martes|mi[eé]rcoles|miercoles|jueves|viernes|s[aá]bado|sabado|domingo|"
    r"ma[nñ]ana|manana|hoy|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)

_AFTER_BEFORE_RE = re.compile(
    r"\b(?:despu[eé]s|despues|tras|after|following|antes|before|hasta|until)\s+"
    r"(?:de(?:l|l\s+la)?\s+)?"
    r"(?:lunes|martes|mi[eé]rcoles|miercoles|jueves|viernes|s[aá]bado|sabado|domingo|"
    r"ma[nñ]ana|manana|hoy|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
    re.IGNORECASE,
)

_FREE_BUSY_RE = re.compile(
    r"\b(?:estoy\s+libre|tengo\s+libre|tengo\s+algo|am\s+i\s+free|libre\s+el|libre\s+para)\b",
    re.IGNORECASE,
)

_COUNT_EVENTS_RE = re.compile(
    r"\b(?:cu[aá]ntos?|cuantos?|how\s+many)\s+eventos\b",
    re.IGNORECASE,
)

_EVENT_KEYWORD_RE = re.compile(
    r"\b(?:busca(?:r)?|encuentra|hay)\s+(?:alg[uú]n|una|un)?\s*"
    r"(?:evento|reuni[oó]n|cita)\s+"
    r"(?:con|de|sobre|llamad[oa]|titulad[oa]|que\s+se\s+llama)\s+['\"]?([^'\"?\n]+?)['\"]?"
    r"(?:\s+en\s+(?:mi\s+)?(?:calendario|agenda))?\s*\??\s*$",
    re.IGNORECASE,
)

_HOURS_RE = re.compile(r"\b(\d{1,3})\s*(horas?|hours?|h)\b", re.IGNORECASE)
_DAYS_RE = re.compile(r"\b(\d{1,3})\s*(d[ií]as?|days?)\b", re.IGNORECASE)

_CALENDAR_TOOL_NAMES = frozenset(
    {"get_upcoming_events", "search_upcoming", "query_events"},
)
_CALENDAR_CONTEXT_RE = re.compile(
    r"\b(?:calendario|agenda|eventos?|reuniones?|citas?|tengo|hay|calendar|schedule|meetings?)\b",
    re.IGNORECASE,
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
_PROX_N_CUMPLE_RE = re.compile(
    # "los 4 proximos cumpleaños" / "4 proximos cumpleaños" / "proximos 4 cumpleaños"
    r"(?:\b(?:los\s+)?pr[oó]ximos?\s+(?P<n>\d+)\s+cumple(?:años|año)?\b)"
    r"|(?:\b(?:los\s+)?(?P<n2>\d+)\s+pr[oó]ximos?\s+cumple(?:años|año)?\b)",
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
    if re.search(r"\bhoy\b|\btoday\b", query, re.I):
        return 24
    if re.search(r"\bmañana\b|\bmanana\b|\btomorrow\b", query, re.I):
        return 48
    if re.search(
        r"\b(pr[oó]xim[oa]|proxim[oa]|next)\s+(evento|reuni[oó]n|cita|meeting)\b",
        query,
        re.I,
    ):
        if not re.search(r"\b(eventos|reuniones|citas|meetings)\b", query, re.I):
            return 24 * 7  # single "próximo/a [evento|reunión]" — 1 week
        return max(default, 24 * 7)
    if _AFTER_BEFORE_RE.search(query) or _DAY_SCHEDULE_RE.search(query):
        return 24 * 30
    return default


def _upcoming_max_results(query: str) -> int:
    """Cap general upcoming listings; single answer for 'próximo evento'."""
    if _SHOW_ALL_RE.search(query):
        return 0
    if _LIMIT_ONE_RE.search(query):
        return 1
    if re.search(
        r"\b(pr[oó]xim[oa]|proxim[oa]|next)\s+(evento|reuni[oó]n|cita|meeting)\b",
        query,
        re.I,
    ):
        if not re.search(r"\b(eventos|reuniones|citas|meetings)\b", query, re.I):
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
    m = _PROX_N_CUMPLE_RE.search(query)
    if m:
        # Negative => "strict mode": obey exactly N requested, even if multiple
        # birthdays fall on the same day (no same-day bundling).
        n_raw = m.groupdict().get("n") or m.groupdict().get("n2") or "1"
        return -max(1, min(int(n_raw), 10))
    if _LIMIT_ONE_RE.search(query):
        return -1
    if _LIMIT_TWO_RE.search(query):
        return -2
    if _LIMIT_THREE_RE.search(query):
        return -3
    return 3


def _birthday_keyword(query: str) -> str:
    if re.search(r"\bbirthday\b", query, re.I):
        return "birthday"
    if re.search(r"\banniversary\b|\baniversario\b", query, re.I):
        return "anniversary"
    return "cumple"


def _is_calendar_read_query(text: str) -> bool:
    if extract_calendar_date_filter(text) is not None and _CALENDAR_CONTEXT_RE.search(text):
        return True
    return bool(
        _UPCOMING_RE.search(text)
        or _DAY_SCHEDULE_RE.search(text)
        or _AFTER_BEFORE_RE.search(text)
        or _FREE_BUSY_RE.search(text)
        or _COUNT_EVENTS_RE.search(text)
    )


def _extract_event_keyword(text: str) -> str | None:
    m = _EVENT_KEYWORD_RE.search(text)
    if not m:
        return None
    kw = m.group(1).strip().strip("'\"")
    return kw if len(kw) >= 2 else None


def fetch_calendar_read_answer(
    query: str,
    authorized_tools: list[str] | None,
    *,
    ics_path: str | None = None,
) -> str | None:
    """Run calendar read tools for *query* (used by chat fast-path and file-export fusion)."""
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

    event_kw = _extract_event_keyword(text)
    if event_kw and ("query_events" in tools or not tools):
        hours = _extract_hours(text, default=24 * 14)
        return query_events(event_kw, hours_ahead=hours, ics_path=path)

    if _is_calendar_read_query(text):
        if "get_upcoming_events" in tools or not tools:
            hours = _extract_hours(text, default=24)
            max_results = _upcoming_max_results(text)
            count_only = bool(_COUNT_EVENTS_RE.search(text))
            free_busy = bool(_FREE_BUSY_RE.search(text))
            return get_upcoming_events_for_query(
                text,
                hours_ahead=hours,
                ics_path=path,
                max_events=max_results,
                fast_apple=True,
                count_only=count_only,
                free_busy=free_busy,
            )
        return None

    return None


def try_calendar_fast_path(
    query: str,
    authorized_tools: list[str] | None,
    *,
    ics_path: str | None = None,
) -> str | None:
    """Run a calendar read tool when the query clearly asks for schedule/birthdays."""
    text = query.strip()
    if not text:
        return None

    from core.agents.file_write_calendar_fusion import is_file_write_calendar_export_query

    if is_file_write_calendar_export_query(text):
        return None

    return fetch_calendar_read_answer(query, authorized_tools, ics_path=ics_path)

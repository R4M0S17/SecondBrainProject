"""Module 7 — Calendar tool handlers.

LLM-callable tools for querying calendar events.
The .ics file path is resolved from the CEREBRO_ICS env var
(default: ~/.cerebro/calendar.ics).  Pass ics_path explicitly in tests.
"""

from __future__ import annotations

import os
import platform
from datetime import date, datetime, timedelta, tzinfo

import dateparser

from core.agents.calendar_query_parse import (
    CalendarDateFilter,
    extract_calendar_date_filter,
    filter_events_by_date,
    scope_phrase_for_filter,
)
from integrations.calendar_reader import (
    BackendResult,
    CalendarEvent,
    CalendarReader,
    calendar_write_failure_hint,
    create_apple_calendar_event,
    delete_apple_calendar_event_by_title,
)

_FAST_APPLE_TIMEOUT = int(os.getenv("CEREBRO_CALENDAR_OSASCRIPT_FAST_TIMEOUT", "12"))

# Short calendar block for "recordatorio" / reminder-style requests (not Apple Reminders app).
_REMINDER_EVENT_DURATION_MINS = 30

_ICS_PATH = os.path.expanduser(os.getenv("CEREBRO_ICS", "~/.cerebro/calendar.ics"))


def _local_tz() -> tzinfo:
    tz = datetime.now().astimezone().tzinfo
    assert tz is not None
    return tz


def _parse_event_datetime(datetime_str: str) -> datetime | None:
    """Parse natural language datetimes as local wall-clock time (not UTC)."""
    local = _local_tz()
    tz_name = getattr(local, "key", None)
    settings: dict[str, object] = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
    }
    if tz_name:
        settings["TIMEZONE"] = tz_name

    parsed = dateparser.parse(datetime_str, settings=settings)
    if parsed is None:
        parsed = dateparser.parse(datetime_str, settings={"PREFER_DATES_FROM": "future"})
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local)
    return parsed.astimezone(local)


def _format_local_event_time(dt: datetime) -> str:
    local = dt.astimezone(_local_tz())
    return local.strftime("%A %d de %B de %Y, %H:%M")


def _day_from_datetime_str(datetime_str: str) -> date | None:
    if not datetime_str.strip():
        return None
    parsed = _parse_event_datetime(datetime_str)
    if parsed is None:
        return None
    return parsed.date()


def _use_apple_calendar() -> bool:
    mode = os.getenv("CEREBRO_CALENDAR_APPLE", "auto").lower()
    if mode in ("0", "false", "no", "off"):
        return False
    return platform.system() == "Darwin"


def format_merged_calendar_result(
    result: BackendResult,
    hours_ahead: int,
    now_str: str,
    *,
    max_events: int = 0,
    total_before_limit: int | None = None,
    scope_label: str = "",
    count_only: bool = False,
) -> str:
    """Turn merged BackendResult into user-facing Spanish text (Phase 4)."""
    if result.status == "permission_denied":
        raw = (result.detail or "").strip()
        if raw == "contacts" or raw.endswith("; contacts"):
            return (
                f"Fecha y hora actual: {now_str}\n"
                "No tengo permiso para leer Contactos (cumpleaños). Abre "
                "Ajustes del sistema → Privacidad y seguridad → Automatización, "
                "y autoriza Contacts para Python/Cerebro. Luego vuelve a preguntar."
            )
        return (
            f"Fecha y hora actual: {now_str}\n"
            "No tengo permiso para leer Apple Calendar. Abre "
            "Ajustes del sistema → Privacidad y seguridad → Automatización, "
            "y autoriza Calendar para Python/Cerebro. Luego vuelve a preguntar."
        )
    if result.status == "timeout":
        return (
            f"Fecha y hora actual: {now_str}\n"
            "Apple Calendar tardó demasiado en responder. Reintenta en unos segundos "
            "o exporta tu calendario a ~/.cerebro/calendar.ics (CEREBRO_ICS)."
        )
    if result.status == "error" and not result.events:
        detail = (result.detail or "error desconocido")[:240]
        return f"Fecha y hora actual: {now_str}\nError al consultar calendarios: {detail}"
    if result.status == "no_calendar" and not result.events:
        return (
            f"Fecha y hora actual: {now_str}\n"
            f"Sin eventos en las próximas {hours_ahead} horas. "
            f"(Archivo .ics no encontrado: {result.detail})"
        )
    if not result.events:
        if scope_label:
            return f"Fecha y hora actual: {now_str}\nSin eventos {scope_label}."
        return f"Fecha y hora actual: {now_str}\nSin eventos en las próximas {hours_ahead} horas."

    if count_only:
        n = len(result.events)
        word = "evento" if n == 1 else "eventos"
        scope = f" {scope_label}" if scope_label else f" en las próximas {hours_ahead} horas"
        return f"Fecha y hora actual: {now_str}\nTienes {n} {word}{scope}."

    partial_note = ""
    if result.detail == "partial_apple_timeout":
        partial_note = (
            "\n(Apple Calendar no respondió a tiempo; se muestran eventos de otras fuentes.)"
        )

    scope_suffix = f" ({scope_label})" if scope_label else ""
    if max_events == 1 and len(result.events) == 1:
        if scope_label:
            header = f"Fecha y hora actual: {now_str}\nPróximo evento {scope_label}:"
        else:
            header = f"Fecha y hora actual: {now_str}\nPróximo evento en tu calendario:"
    elif (
        max_events > 0
        and total_before_limit is not None
        and len(result.events) < total_before_limit
    ):
        header = (
            f"Fecha y hora actual: {now_str}\n"
            f"Eventos próximos{scope_suffix} (mostrando {len(result.events)}; próximas {hours_ahead}h):"
        )
    else:
        header = (
            f"Fecha y hora actual: {now_str}\n"
            f"Eventos próximos{scope_suffix} (próximas {hours_ahead}h):"
        )
    lines = [header + partial_note]
    for ev in result.events:
        fmt = "%Y-%m-%d %H:%M %Z" if ev.start.tzinfo else "%Y-%m-%d %H:%M"
        line = f"- {ev.title} a las {ev.start.strftime(fmt)}"
        if ev.location:
            line += f" [{ev.location}]"
        if ev.description:
            line += f" — {ev.description[:120]}"
        lines.append(line)
    return "\n".join(lines)


def get_upcoming_events(
    hours_ahead: int = 24,
    ics_path: str | None = None,
    *,
    max_events: int = 0,
    fast_apple: bool = True,
    date_filter: CalendarDateFilter | None = None,
    count_only: bool = False,
    free_busy: bool = False,
) -> str:
    """Return a formatted list of upcoming calendar events.

    Args:
        hours_ahead: How many hours ahead to look (default 24).
        ics_path: Override the .ics file path (for testing).
        max_events: Cap listed events (0 = no cap). Use 1 for "próximo evento".
        fast_apple: Shorter osascript timeout; skips birthday-only backends.
        date_filter: Optional after/before/on day window parsed from the user query.
        count_only: Return only a count of matching events.
        free_busy: Answer whether the user is free in the scoped window.
    """
    path = ics_path or _ICS_PATH
    apple_timeout = _FAST_APPLE_TIMEOUT if fast_apple and _use_apple_calendar() else None
    reader = CalendarReader(
        ics_path=path,
        use_apple_calendar=_use_apple_calendar(),
        include_birthday_backends=False,
        apple_timeout_sec=apple_timeout,
    )
    result = reader.get_upcoming_events_v2(hours_ahead=hours_ahead)
    if result.events and date_filter is not None:
        filtered = filter_events_by_date(result.events, date_filter)
        result = BackendResult(events=filtered, status=result.status, detail=result.detail)
    total = len(result.events)
    if max_events > 0 and result.events:
        result = BackendResult(
            events=limit_keyword_event_matches(result.events, max_results=max_events),
            status=result.status,
            detail=result.detail,
        )
    now = datetime.now().astimezone()
    now_str = now.strftime("%A %d de %B de %Y, %H:%M %Z")
    scope_label = scope_phrase_for_filter(date_filter)
    if free_busy and date_filter is not None:
        return _format_free_busy(result, now_str, scope_label)
    return format_merged_calendar_result(
        result,
        hours_ahead,
        now_str,
        max_events=max_events,
        total_before_limit=total,
        scope_label=scope_label,
        count_only=count_only,
    )


def _format_free_busy(result: BackendResult, now_str: str, scope_label: str) -> str:
    if result.status in ("permission_denied", "timeout", "error", "no_calendar"):
        return format_merged_calendar_result(result, 0, now_str, scope_label=scope_label)
    if not result.events:
        return f"Fecha y hora actual: {now_str}\nSí, estás libre {scope_label}."
    lines = [f"Fecha y hora actual: {now_str}\nNo, tienes eventos {scope_label}:"]
    for ev in result.events:
        fmt = "%Y-%m-%d %H:%M %Z" if ev.start.tzinfo else "%Y-%m-%d %H:%M"
        lines.append(f"- {ev.title} a las {ev.start.strftime(fmt)}")
    return "\n".join(lines)


def get_upcoming_events_for_query(
    query: str,
    hours_ahead: int = 24,
    ics_path: str | None = None,
    *,
    max_events: int = 0,
    fast_apple: bool = True,
    count_only: bool = False,
    free_busy: bool = False,
) -> str:
    """Like get_upcoming_events but parses after/before/on anchors from the query text."""
    date_filter = extract_calendar_date_filter(query)
    return get_upcoming_events(
        hours_ahead=hours_ahead,
        ics_path=ics_path,
        max_events=max_events,
        fast_apple=fast_apple,
        date_filter=date_filter,
        count_only=count_only,
        free_busy=free_busy,
    )


def query_events(keyword: str, hours_ahead: int = 168, ics_path: str | None = None) -> str:
    """Search upcoming calendar events by keyword (matches title or description).

    Args:
        keyword: Text to search for.
        hours_ahead: Search window in hours (default 168 = 7 days).
        ics_path: Override the .ics file path (for testing).
    """
    path = ics_path or _ICS_PATH
    reader = CalendarReader(
        ics_path=path,
        use_apple_calendar=_use_apple_calendar(),
        include_birthday_backends=False,
        apple_timeout_sec=_FAST_APPLE_TIMEOUT if _use_apple_calendar() else None,
    )
    result = reader.get_upcoming_events_v2(hours_ahead=hours_ahead)
    now_str = datetime.now().astimezone().strftime("%A %d de %B de %Y, %H:%M %Z")
    if result.status in ("permission_denied", "timeout") or (
        result.status in ("error", "no_calendar") and not result.events
    ):
        return format_merged_calendar_result(result, hours_ahead, now_str)

    kw = keyword.lower()
    matches = [ev for ev in result.events if kw in ev.title.lower() or kw in ev.description.lower()]
    if not matches:
        return f"Fecha y hora actual: {now_str}\nSin eventos que coincidan con '{keyword}' en las próximas {hours_ahead} horas."

    lines = [f"Fecha y hora actual: {now_str}\nEventos que coinciden con '{keyword}':"]
    for ev in matches:
        fmt = "%Y-%m-%d %H:%M %Z" if ev.start.tzinfo else "%Y-%m-%d %H:%M"
        line = f"- {ev.title} a las {ev.start.strftime(fmt)}"
        if ev.location:
            line += f" [{ev.location}]"
        lines.append(line)
    return "\n".join(lines)


def limit_keyword_event_matches(
    events: list[CalendarEvent],
    max_results: int = 3,
) -> list[CalendarEvent]:
    """Cap keyword search results for birthdays: max N, or all on the next event day."""
    if not events:
        return []
    sorted_ev = sorted(events, key=lambda ev: ev.start)

    # Strict mode: negative max_results means "obey exactly N requested",
    # even when multiple events fall on the same day.
    strict = max_results < 0
    if strict:
        max_results = abs(max_results)

    if max_results <= 0:
        return sorted_ev

    if max_results == 1:
        return sorted_ev[:1]
    first_day = sorted_ev[0].start.date()
    same_day = [ev for ev in sorted_ev if ev.start.date() == first_day]
    if not strict and len(same_day) > 1:
        return same_day
    return sorted_ev[:max_results]


def search_upcoming(
    keyword: str,
    days_ahead: int = 365,
    ics_path: str | None = None,
    max_results: int = 3,
) -> str:
    """Search upcoming events long-range (up to days_ahead days) matching a keyword.

    Use this for "when is the next birthday/anniversary/holiday" type queries that
    require looking further than the default 7-day window.

    Args:
        keyword: Text to search for in event title or description.
        days_ahead: How many days ahead to search (default 365).
        ics_path: Override the .ics file path (for testing).
    """
    path = ics_path or _ICS_PATH
    reader = CalendarReader(
        ics_path=path,
        use_apple_calendar=_use_apple_calendar(),
        include_birthday_backends=True,
        apple_timeout_sec=_FAST_APPLE_TIMEOUT if _use_apple_calendar() else None,
    )
    result = reader.get_upcoming_events_v2(hours_ahead=days_ahead * 24)
    now_str = datetime.now().astimezone().strftime("%A %d de %B de %Y, %H:%M %Z")
    if result.status in ("permission_denied", "timeout") or (
        result.status in ("error", "no_calendar") and not result.events
    ):
        return format_merged_calendar_result(result, days_ahead * 24, now_str)

    kw = keyword.lower()
    all_matches = [
        ev for ev in result.events if kw in ev.title.lower() or kw in ev.description.lower()
    ]
    if not all_matches:
        return f"Fecha y hora actual: {now_str}\nSin eventos que coincidan con '{keyword}' en los próximos {days_ahead} días."

    matches = limit_keyword_event_matches(all_matches, max_results=max_results)
    if len(matches) == 1:
        header = (
            f"Fecha y hora actual: {now_str}\n"
            f"Próximo evento que coincide con '{keyword}' (próximos {days_ahead} días):"
        )
    elif len(matches) < len(all_matches):
        header = (
            f"Fecha y hora actual: {now_str}\n"
            f"Próximos eventos que coinciden con '{keyword}' "
            f"(mostrando {len(matches)} de {len(all_matches)}; próximos {days_ahead} días):"
        )
    else:
        header = (
            f"Fecha y hora actual: {now_str}\n"
            f"Eventos que coinciden con '{keyword}' (próximos {days_ahead} días):"
        )
    lines = [header]
    for ev in matches:
        fmt = "%Y-%m-%d %H:%M %Z" if ev.start.tzinfo else "%Y-%m-%d %H:%M"
        line = f"- {ev.title} a las {ev.start.strftime(fmt)}"
        if ev.location:
            line += f" [{ev.location}]"
        lines.append(line)
    return "\n".join(lines)


def create_calendar_event(
    title: str,
    datetime_str: str,
    duration_mins: int = 60,
    description: str = "",
) -> str:
    """Create a timed event in Apple Calendar.

    Args:
        title: Event title.
        datetime_str: Natural language or ISO date/time (e.g. "next monday at 3pm").
        duration_mins: Duration in minutes (default 60).
        description: Optional event description.
    """
    start = _parse_event_datetime(datetime_str)
    if start is None:
        return (
            f"Could not parse '{datetime_str}' as a date/time. "
            "Please try a more specific format like 'Monday at 3pm' or '2026-05-20 15:00'."
        )

    end = start + timedelta(minutes=duration_mins)
    iso_start = start.isoformat()
    iso_end = end.isoformat()

    if platform.system() != "Darwin":
        return (
            f"Apple Calendar is only available on macOS. "
            f"Would have created: '{title}' at {iso_start} for {duration_mins} min."
        )

    success, err = create_apple_calendar_event(title, iso_start, iso_end, description)
    if not success:
        hint = calendar_write_failure_hint(err)
        return f"No pude crear el evento '{title}' en Calendario. {hint}"

    return f"Created event '{title}' on {_format_local_event_time(start)} ({duration_mins} min)."


def add_reminder(title: str, datetime_str: str, notes: str = "") -> str:
    """Create a timed reminder as an event in Apple Calendar (not the Reminders app).

    Use for "remind me to", "crea un recordatorio", "recuérdame" — short calendar blocks.

    Args:
        title: Event title.
        datetime_str: Natural language or ISO date/time (e.g. "next saturday", "tomorrow at 9am").
        notes: Optional description on the calendar event.
    """
    start = _parse_event_datetime(datetime_str)
    if start is None:
        return (
            f"No pude interpretar '{datetime_str}' como fecha/hora. "
            "Prueba un formato como 'mañana a las 3pm' o '2026-05-20 15:00'."
        )

    end = start + timedelta(minutes=_REMINDER_EVENT_DURATION_MINS)
    iso_start = start.isoformat()
    iso_end = end.isoformat()

    if platform.system() != "Darwin":
        return (
            f"Apple Calendar solo está disponible en macOS. "
            f"Se habría creado el recordatorio '{title}' el {iso_start}."
        )

    success, err = create_apple_calendar_event(title, iso_start, iso_end, notes)
    if not success:
        hint = calendar_write_failure_hint(err)
        return f"No pude crear el recordatorio '{title}' en Calendario. {hint}"

    return (
        f"Recordatorio '{title}' añadido al calendario para el "
        f"{_format_local_event_time(start)} (duración {_REMINDER_EVENT_DURATION_MINS} min)."
    )


def delete_reminder(title: str, datetime_str: str = "") -> str:
    """Delete a calendar event by exact title on Apple Calendar.

    Args:
        title: Event title to remove (recordatorios se guardan como eventos).
        datetime_str: Optional day window (e.g. 'mañana') when the user specifies which day.
    """
    if platform.system() != "Darwin":
        return (
            f"Apple Calendar solo está disponible en macOS. "
            f"Se habría borrado el evento '{title}'."
        )

    on_day = _day_from_datetime_str(datetime_str)
    removed = delete_apple_calendar_event_by_title(title, on_day=on_day)
    if removed == 0:
        return f"No encontré ningún evento llamado '{title}' en Calendario."
    if removed < 0:
        return f"No pude borrar '{title}' del calendario. Revisa permisos de Automatización."
    if removed == 1:
        return f"Evento '{title}' eliminado del calendario."
    return f"Eliminé {removed} eventos llamados '{title}' del calendario."

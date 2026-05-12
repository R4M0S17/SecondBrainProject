"""Module 7 — Calendar tool handlers.

LLM-callable tools for querying calendar events.
The .ics file path is resolved from the CEREBRO_ICS env var
(default: ~/.cerebro/calendar.ics).  Pass ics_path explicitly in tests.
"""

from __future__ import annotations

import os
import platform
from datetime import UTC, datetime, timedelta

import dateparser

from integrations.calendar_reader import (
    CalendarReader,
    add_apple_reminder,
    create_apple_calendar_event,
)

_ICS_PATH = os.path.expanduser(os.getenv("CEREBRO_ICS", "~/.cerebro/calendar.ics"))


def get_upcoming_events(hours_ahead: int = 24, ics_path: str | None = None) -> str:
    """Return a formatted list of upcoming calendar events.

    Args:
        hours_ahead: How many hours ahead to look (default 24).
        ics_path: Override the .ics file path (for testing).
    """
    path = ics_path or _ICS_PATH
    reader = CalendarReader(ics_path=path, use_apple_calendar=platform.system() == "Darwin")
    events = reader.get_upcoming_events(hours_ahead=hours_ahead)
    now = datetime.now().astimezone()
    now_str = now.strftime("%A %d de %B de %Y, %H:%M %Z")
    if not events:
        return f"Fecha y hora actual: {now_str}\nSin eventos en las próximas {hours_ahead} horas."

    lines = [f"Fecha y hora actual: {now_str}\nEventos próximos (próximas {hours_ahead}h):"]
    for ev in events:
        fmt = "%Y-%m-%d %H:%M %Z" if ev.start.tzinfo else "%Y-%m-%d %H:%M"
        line = f"- {ev.title} a las {ev.start.strftime(fmt)}"
        if ev.location:
            line += f" [{ev.location}]"
        if ev.description:
            line += f" — {ev.description[:120]}"
        lines.append(line)
    return "\n".join(lines)


def query_events(keyword: str, hours_ahead: int = 168, ics_path: str | None = None) -> str:
    """Search upcoming calendar events by keyword (matches title or description).

    Args:
        keyword: Text to search for.
        hours_ahead: Search window in hours (default 168 = 7 days).
        ics_path: Override the .ics file path (for testing).
    """
    path = ics_path or _ICS_PATH
    reader = CalendarReader(ics_path=path, use_apple_calendar=platform.system() == "Darwin")
    events = reader.get_upcoming_events(hours_ahead=hours_ahead)
    kw = keyword.lower()
    matches = [ev for ev in events if kw in ev.title.lower() or kw in ev.description.lower()]
    now_str = datetime.now().astimezone().strftime("%A %d de %B de %Y, %H:%M %Z")
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


def search_upcoming(keyword: str, days_ahead: int = 365, ics_path: str | None = None) -> str:
    """Search upcoming events long-range (up to days_ahead days) matching a keyword.

    Use this for "when is the next birthday/anniversary/holiday" type queries that
    require looking further than the default 7-day window.

    Args:
        keyword: Text to search for in event title or description.
        days_ahead: How many days ahead to search (default 365).
        ics_path: Override the .ics file path (for testing).
    """
    path = ics_path or _ICS_PATH
    reader = CalendarReader(ics_path=path, use_apple_calendar=platform.system() == "Darwin")
    events = reader.get_upcoming_events(hours_ahead=days_ahead * 24)
    kw = keyword.lower()
    matches = [ev for ev in events if kw in ev.title.lower() or kw in ev.description.lower()]
    now_str = datetime.now().astimezone().strftime("%A %d de %B de %Y, %H:%M %Z")
    if not matches:
        return f"Fecha y hora actual: {now_str}\nSin eventos que coincidan con '{keyword}' en los próximos {days_ahead} días."

    lines = [
        f"Fecha y hora actual: {now_str}\nEventos que coinciden con '{keyword}' (próximos {days_ahead} días):"
    ]
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
    start = dateparser.parse(datetime_str, settings={"PREFER_DATES_FROM": "future"})
    if start is None:
        return (
            f"Could not parse '{datetime_str}' as a date/time. "
            "Please try a more specific format like 'Monday at 3pm' or '2026-05-20 15:00'."
        )

    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)

    end = start + timedelta(minutes=duration_mins)
    iso_start = start.isoformat()
    iso_end = end.isoformat()

    if platform.system() != "Darwin":
        return (
            f"Apple Calendar is only available on macOS. "
            f"Would have created: '{title}' at {iso_start} for {duration_mins} min."
        )

    success = create_apple_calendar_event(title, iso_start, iso_end, description)
    if not success:
        return f"Failed to create event '{title}' in Apple Calendar. Check that Calendar has Automation permission."

    fmt = "%A, %B %-d at %-I:%M %p"
    return f"Created event '{title}' on {start.strftime(fmt)} ({duration_mins} min)."


def add_reminder(title: str, datetime_str: str, notes: str = "") -> str:
    """Add a task/reminder to Apple Reminders app.

    Use for "remind me to", "don't forget", "to-do" requests — not for meetings.

    Args:
        title: Reminder title.
        datetime_str: Natural language or ISO date/time (e.g. "next saturday", "tomorrow at 9am").
        notes: Optional notes or extra context.
    """
    due = dateparser.parse(datetime_str, settings={"PREFER_DATES_FROM": "future"})
    if due is None:
        return (
            f"Could not parse '{datetime_str}' as a date/time. "
            "Please try a more specific format like 'Saturday at 9am' or '2026-05-20 09:00'."
        )

    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)

    iso_datetime = due.isoformat()

    if platform.system() != "Darwin":
        return (
            f"Apple Reminders is only available on macOS. "
            f"Would have created reminder: '{title}' due {iso_datetime}."
        )

    success = add_apple_reminder(title, iso_datetime, notes)
    if not success:
        return f"Failed to add reminder '{title}'. Check that Reminders has Automation permission."

    fmt = "%A, %B %-d at %-I:%M %p"
    return f"Added reminder '{title}' due {due.strftime(fmt)}."

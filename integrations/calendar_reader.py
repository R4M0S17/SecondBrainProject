"""Module 11 — Calendar Integration.

Provides a CalendarReader facade backed by:
  - ICalBackend: reads a local .ics file via the icalendar library
  - AppleCalendarBackend: queries Apple Calendar via osascript JXA (macOS only)

Google Calendar is deferred to v2.0 (requires OAuth).
"""

from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from icalendar import Calendar as ICalendar
from loguru import logger

# ──────────────────────────────────────────────────────────────────────────────
# Domain types
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class CalendarEvent:
    title: str
    start: datetime
    end: datetime
    description: str = ""
    location: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# iCal backend
# ──────────────────────────────────────────────────────────────────────────────


class ICalBackend:
    """Read events from a local .ics file using the icalendar library."""

    def __init__(self, ics_path: str) -> None:
        self._path = Path(ics_path)

    def get_upcoming_events(self, hours_ahead: int = 24) -> list[CalendarEvent]:
        if not self._path.exists():
            logger.warning("iCal file not found: {}", self._path)
            return []
        try:
            raw = self._path.read_bytes()
            cal = ICalendar.from_ical(raw)
        except Exception as exc:
            logger.warning("Failed to parse iCal file {}: {}", self._path, exc)
            return []

        now = datetime.now().astimezone()
        cutoff = now + timedelta(hours=hours_ahead)
        events: list[CalendarEvent] = []

        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            event = _ical_component_to_event(component)
            if event is None:
                continue
            start = event.start
            if not start.tzinfo:
                start = start.replace(tzinfo=UTC)
                event = CalendarEvent(
                    title=event.title,
                    start=start,
                    end=event.end if event.end.tzinfo else event.end.replace(tzinfo=UTC),
                    description=event.description,
                    location=event.location,
                )
            if now <= start <= cutoff:
                events.append(event)

        return events


def _ical_component_to_event(component) -> CalendarEvent | None:
    """Convert a VEVENT icalendar component to a CalendarEvent; None on error."""
    try:
        title = str(component.get("SUMMARY", ""))
        description = str(component.get("DESCRIPTION", ""))
        location = str(component.get("LOCATION", ""))

        dtstart = component.get("DTSTART")
        if dtstart is None:
            return None
        dtend = component.get("DTEND")

        start_dt = dtstart.dt
        end_dt = dtend.dt if dtend is not None else start_dt

        # all-day events carry a date, not a datetime — promote to midnight UTC
        if isinstance(start_dt, date) and not isinstance(start_dt, datetime):
            start_dt = datetime(start_dt.year, start_dt.month, start_dt.day, tzinfo=UTC)
        if isinstance(end_dt, date) and not isinstance(end_dt, datetime):
            end_dt = datetime(end_dt.year, end_dt.month, end_dt.day, tzinfo=UTC)

        return CalendarEvent(
            title=title,
            start=start_dt,
            end=end_dt,
            description=description,
            location=location,
        )
    except Exception as exc:
        logger.debug("Skipping malformed VEVENT: {}", exc)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Apple Calendar backend (macOS only)
# ──────────────────────────────────────────────────────────────────────────────

# JXA script: two-phase query.
# Phase 1: whose() date filter for non-recurring future events (fast).
# Phase 2: yearly recurring events (birthdays, anniversaries).
#   Apple Calendar stores recurring events with their ORIGINAL startDate (e.g. 2021),
#   so whose(startDate >= now) misses them entirely. We scan for FREQ=YEARLY events,
#   compute the next annual occurrence, then fetch details only for matches (two-pass
#   to minimise IPC calls: startDate first, summary only for events in window).
_JXA_TEMPLATE = """\
var app = Application("Calendar");
var events = [];
var now = new Date();
var cutoff = new Date(now.getTime() + {hours_ahead} * 3600000);

function nextAnnual(d) {{
    var next = new Date(now.getFullYear(), d.getMonth(), d.getDate(),
                        d.getHours(), d.getMinutes(), d.getSeconds());
    if (next < now) next.setFullYear(next.getFullYear() + 1);
    return next;
}}

app.calendars().forEach(function(cal) {{
    try {{
        // Phase 1: future non-recurring events via fast date filter
        var future = cal.events.whose({{_and: [
            {{startDate: {{_greaterThanEquals: now}}}},
            {{startDate: {{_lessThanEquals: cutoff}}}}
        ]}})();
        future.forEach(function(ev) {{
            try {{
                var start = ev.startDate();
                events.push({{
                    title: ev.summary() || "",
                    start: start.toISOString(),
                    end: (ev.endDate() || start).toISOString(),
                    description: ev.description() || "",
                    location: ev.location() || ""
                }});
            }} catch(e) {{}}
        }});

        // Phase 2: yearly recurring events — two-pass to minimise IPC overhead
        var yearly = cal.events.whose({{recurrence: {{_contains: "FREQ=YEARLY"}}}})();
        var inWindow = [];
        for (var i = 0; i < yearly.length; i++) {{
            try {{
                var orig = yearly[i].startDate();
                var next = nextAnnual(orig);
                if (next >= now && next <= cutoff) inWindow.push({{i: i, next: next}});
            }} catch(e) {{}}
        }}
        for (var j = 0; j < inWindow.length; j++) {{
            try {{
                var ev = yearly[inWindow[j].i];
                var next = inWindow[j].next;
                events.push({{
                    title: ev.summary() || "",
                    start: next.toISOString(),
                    end: new Date(next.getTime() + 3600000).toISOString(),
                    description: "",
                    location: ""
                }});
            }} catch(e) {{}}
        }}
    }} catch(e) {{}}
}});
JSON.stringify(events);
"""


class AppleCalendarBackend:
    """Query Apple Calendar via osascript JavaScript for Automation (macOS only)."""

    def get_upcoming_events(self, hours_ahead: int = 24) -> list[CalendarEvent]:
        if platform.system() != "Darwin":
            logger.debug("AppleCalendarBackend is macOS-only; skipping on {}", platform.system())
            return []

        script = _JXA_TEMPLATE.format(hours_ahead=hours_ahead)
        try:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", script],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except Exception as exc:
            logger.warning("osascript execution failed: {}", exc)
            return []

        if result.returncode != 0:
            logger.warning("osascript returned non-zero: {}", result.stderr.strip())
            return []

        raw = result.stdout.strip()
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except Exception as exc:
            logger.warning("Failed to parse osascript JSON output: {}", exc)
            return []

        events: list[CalendarEvent] = []
        for item in data:
            try:
                events.append(
                    CalendarEvent(
                        title=item.get("title", ""),
                        start=datetime.fromisoformat(item["start"]),
                        end=datetime.fromisoformat(item["end"]),
                        description=item.get("description", ""),
                        location=item.get("location", ""),
                    )
                )
            except Exception as exc:
                logger.debug("Skipping malformed Apple Calendar event: {}", exc)

        return events


# ──────────────────────────────────────────────────────────────────────────────
# Apple Calendar writer (macOS only)
# ──────────────────────────────────────────────────────────────────────────────

# String values are inserted as JSON literals (json.dumps) to prevent JS injection.
_JXA_CREATE_TEMPLATE = """\
var app = Application("Calendar");
var cal = app.defaultCalendar();
var ev = app.CalendarEvent({{
    summary: {title},
    startDate: new Date("{iso_start}"),
    endDate: new Date("{iso_end}"),
    description: {description}
}});
cal.events.push(ev);
"ok";
"""


def create_apple_calendar_event(
    title: str,
    iso_start: str,
    iso_end: str,
    description: str = "",
) -> bool:
    """Create an event in the default Apple Calendar via osascript. Returns True on success."""
    if platform.system() != "Darwin":
        logger.warning("create_apple_calendar_event is macOS-only")
        return False

    script = _JXA_CREATE_TEMPLATE.format(
        title=json.dumps(title),
        iso_start=iso_start,
        iso_end=iso_end,
        description=json.dumps(description),
    )
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        logger.warning("osascript create event failed: {}", exc)
        return False

    if result.returncode != 0:
        logger.warning("osascript create event returned non-zero: {}", result.stderr.strip())
        return False

    return True


# ──────────────────────────────────────────────────────────────────────────────
# Apple Reminders writer (macOS only)
# ──────────────────────────────────────────────────────────────────────────────

# String values are inserted as JSON literals (json.dumps) to prevent JS injection.
_JXA_ADD_REMINDER_TEMPLATE = """\
var app = Application("Reminders");
var list = app.defaultList();
list.reminders.push(app.Reminder({{
    name: {title},
    dueDate: new Date("{iso_datetime}"),
    body: {notes}
}}));
"ok";
"""


def add_apple_reminder(title: str, iso_datetime: str, notes: str = "") -> bool:
    """Add a reminder to the default Apple Reminders list via osascript. Returns True on success."""
    if platform.system() != "Darwin":
        logger.warning("add_apple_reminder is macOS-only")
        return False

    script = _JXA_ADD_REMINDER_TEMPLATE.format(
        title=json.dumps(title),
        iso_datetime=iso_datetime,
        notes=json.dumps(notes),
    )
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        logger.warning("osascript add reminder failed: {}", exc)
        return False

    if result.returncode != 0:
        logger.warning("osascript add reminder returned non-zero: {}", result.stderr.strip())
        return False

    return True


# ──────────────────────────────────────────────────────────────────────────────
# Birthday backend (macOS only — queries Contacts app)
# ──────────────────────────────────────────────────────────────────────────────

_JXA_BIRTHDAYS_TEMPLATE = """\
var app = Application("Calendar");
var now = new Date();
var cutoff = new Date(now.getTime() + {hours_ahead} * 3600000);
var results = [];

function nextAnnual(d) {{
    var next = new Date(now.getFullYear(), d.getMonth(), d.getDate());
    if (next < now) next.setFullYear(next.getFullYear() + 1);
    return next;
}}

// Find Birthdays calendar by name (try both English and Spanish)
var bdayCal = null;
app.calendars().forEach(function(cal) {{
    var name = cal.name();
    if (name === "Birthdays" || name === "Cumpleaños") bdayCal = cal;
}});

// If found, iterate all events and project to next annual occurrence
if (bdayCal) {{
    bdayCal.events().forEach(function(ev) {{
        try {{
            var orig = ev.startDate();
            var next = nextAnnual(orig);
            if (next >= now && next <= cutoff) {{
                results.push({{ title: ev.summary() || "", start: next.toISOString() }});
            }}
        }} catch(e) {{}}
    }});
}}
// Fallback: scan all calendars for events with "birthday"/"cumpleaños" in title
if (results.length === 0) {{
    app.calendars().forEach(function(cal) {{
        try {{
            cal.events().forEach(function(ev) {{
                try {{
                    var t = (ev.summary() || "").toLowerCase();
                    if (t.indexOf("birthday") >= 0 || t.indexOf("cumpleaños") >= 0) {{
                        var orig = ev.startDate();
                        var next = nextAnnual(orig);
                        if (next >= now && next <= cutoff) {{
                            results.push({{ title: ev.summary(), start: next.toISOString() }});
                        }}
                    }}
                }} catch(e) {{}}
            }});
        }} catch(e) {{}}
    }});
}}
JSON.stringify(results);
"""


class BirthdayBackend:
    """Query upcoming birthdays from the Apple Calendar "Birthdays" calendar via osascript (macOS only).

    Targets the Calendar app directly (not Contacts) because birthdays are stored
    as events in the dedicated "Birthdays" calendar with their original start date.
    Falls back to scanning all calendars for events whose title contains
    "birthday" or "cumpleaños" if no dedicated Birthdays calendar is found.
    """

    def get_upcoming_events(self, hours_ahead: int = 8760) -> list[CalendarEvent]:
        if platform.system() != "Darwin":
            logger.debug("BirthdayBackend is macOS-only; skipping on {}", platform.system())
            return []

        script = _JXA_BIRTHDAYS_TEMPLATE.format(hours_ahead=hours_ahead)
        try:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as exc:
            logger.warning("BirthdayBackend osascript failed: {}", exc)
            return []

        if result.returncode != 0:
            logger.warning("BirthdayBackend osascript non-zero: {}", result.stderr.strip())
            return []

        raw = result.stdout.strip()
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except Exception as exc:
            logger.warning("BirthdayBackend failed to parse JSON: {}", exc)
            return []

        events: list[CalendarEvent] = []
        for item in data:
            try:
                start = datetime.fromisoformat(item["start"])
                if start.tzinfo is None:
                    start = start.replace(tzinfo=UTC)
                end = start + timedelta(hours=24)
                events.append(CalendarEvent(title=item["title"], start=start, end=end))
            except Exception as exc:
                logger.debug("Skipping malformed birthday entry: {}", exc)

        return events


# ──────────────────────────────────────────────────────────────────────────────
# Facade
# ──────────────────────────────────────────────────────────────────────────────


class CalendarReader:
    """Aggregate events from all configured backends.

    Backends are queried in order (iCal first, then Apple Calendar, then Birthdays).
    Results are merged, deduplicated by (title, start ISO string), and
    sorted ascending by start time.
    """

    def __init__(
        self,
        ics_path: str | None = None,
        use_apple_calendar: bool = False,
    ) -> None:
        self._backends: list = []
        if ics_path:
            self._backends.append(ICalBackend(ics_path))
        if use_apple_calendar:
            self._backends.append(AppleCalendarBackend())
            self._backends.append(BirthdayBackend())

    def get_upcoming_events(self, hours_ahead: int = 24) -> list[CalendarEvent]:
        if not self._backends:
            return []

        seen: set[tuple[str, str]] = set()
        merged: list[CalendarEvent] = []

        for backend in self._backends:
            try:
                for ev in backend.get_upcoming_events(hours_ahead):
                    key = (ev.title, ev.start.isoformat())
                    if key not in seen:
                        seen.add(key)
                        merged.append(ev)
            except Exception as exc:
                logger.warning("Backend {} error: {}", type(backend).__name__, exc)

        merged.sort(key=lambda e: e.start)
        return merged

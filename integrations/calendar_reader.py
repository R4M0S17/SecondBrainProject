"""Module 11 — Calendar Integration.

Provides a CalendarReader facade backed by:
  - ICalBackend: reads a local .ics file via the icalendar library
  - AppleCalendarBackend: queries Apple Calendar via osascript JXA (macOS only)

Google Calendar is deferred to v2.0 (requires OAuth).
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Literal

import dateparser
from icalendar import Calendar as ICalendar
from loguru import logger

_AS_RECORD_SEP = "|||"
_SKIPPED_CALENDAR_NAMES = frozenset(
    {
        "Birthdays",
        "Cumpleaños",
        "Siri Suggestions",
        "Scheduled Reminders",
        "Festivos en Guatemala",
    }
)

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


BackendStatus = Literal["ok", "permission_denied", "no_calendar", "timeout", "error"]


@dataclass
class BackendResult:
    """Structured outcome from a calendar backend (Phase 4 — FIX_CEREBRO)."""

    events: list[CalendarEvent] = field(default_factory=list)
    status: BackendStatus = "ok"
    detail: str = ""


def _stderr_suggests_automation_denied(stderr: str) -> bool:
    t = stderr.lower()
    return bool(
        re.search(r"\(-1743\)|\b1743\b", stderr)
        or "not allowed" in t
        or "isn't allowed to send" in t
        or "not authorized" in t
    )


def _merge_calendar_backend_results(
    partials: list[BackendResult], merged_events: list[CalendarEvent]
) -> BackendResult:
    """Prefer showing real events; otherwise surface the worst blocking status."""
    if merged_events:
        seen: set[tuple[str, str]] = set()
        deduped: list[CalendarEvent] = []
        for ev in sorted(merged_events, key=lambda e: e.start):
            key = (ev.title, ev.start.isoformat())
            if key not in seen:
                seen.add(key)
                deduped.append(ev)
        detail = ""
        if any(p.status == "timeout" for p in partials):
            detail = "partial_apple_timeout"
        return BackendResult(events=deduped, status="ok", detail=detail)

    priority: tuple[BackendStatus, ...] = (
        "permission_denied",
        "timeout",
        "no_calendar",
        "error",
        "ok",
    )
    worst: BackendStatus = "ok"
    details: list[str] = []
    for p in partials:
        if p.status != "ok":
            if priority.index(p.status) < priority.index(worst):
                worst = p.status
            if p.detail:
                details.append(p.detail)
    return BackendResult(events=[], status=worst, detail="; ".join(details)[:1000])


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

    def get_upcoming_events_v2(self, hours_ahead: int = 24) -> BackendResult:
        if not self._path.exists():
            return BackendResult(status="no_calendar", detail=str(self._path))
        events = self.get_upcoming_events(hours_ahead=hours_ahead)
        return BackendResult(events=events, status="ok")


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
# AppleScript read: JXA ``whose`` date ranges often return nothing on modern Calendar.app.
_AS_FETCH_UPCOMING = """\
tell application "Calendar"
    set now to current date
    set cutoffDate to now + ({hours_ahead} * hours)
    set skipCal to {{{skip_list}}}
    set out to ""
    repeat with cal in calendars
        set cName to name of cal
        if skipCal contains cName then
        else
            try
                repeat with ev in (every event of cal whose start date ≥ now and start date ≤ cutoffDate)
                    set t to summary of ev
                    if t is missing value then set t to ""
                    set out to out & t & "{sep}" & (start date of ev as string) & "{sep}" & (end date of ev as string) & linefeed
                end repeat
            end try
        end if
    end repeat
    return out
end tell
"""


def _local_tzinfo() -> tzinfo:
    tz = datetime.now().astimezone().tzinfo
    assert tz is not None
    return tz


def _parse_applescript_date_string(raw: str) -> datetime | None:
    """Parse ``Saturday, 28 May 2026 at 3:00:00 PM`` from Calendar AppleScript."""
    text = raw.replace("\u202f", " ").strip()
    if not text:
        return None
    tz_name = getattr(_local_tzinfo(), "key", None)
    settings: dict[str, object] = {}
    if tz_name:
        settings["TIMEZONE"] = tz_name
    parsed = dateparser.parse(text, settings=settings)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_local_tzinfo())
    return parsed.astimezone()


def _fetch_upcoming_via_applescript(hours_ahead: int) -> tuple[list[CalendarEvent], str]:
    """Return upcoming events using AppleScript (reliable) and filter window in Python."""
    skip_list = ", ".join(f'"{n}"' for n in sorted(_SKIPPED_CALENDAR_NAMES))
    script = _AS_FETCH_UPCOMING.format(
        sep=_AS_RECORD_SEP,
        skip_list=skip_list,
        hours_ahead=hours_ahead,
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=max(8, int(os.getenv("CEREBRO_CALENDAR_OSASCRIPT_FAST_TIMEOUT", "30"))),
        )
    except subprocess.TimeoutExpired:
        return [], "osascript timed out"
    except Exception as exc:
        return [], str(exc)

    stderr = (result.stderr or "").strip()
    if result.returncode != 0:
        return [], stderr or f"exit {result.returncode}"

    now = datetime.now().astimezone()
    cutoff = now + timedelta(hours=hours_ahead)
    events: list[CalendarEvent] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(_AS_RECORD_SEP)
        if len(parts) < 2:
            continue
        title = parts[0].strip()
        start = _parse_applescript_date_string(parts[1])
        if start is None or start < now or start > cutoff:
            continue
        end = start
        if len(parts) >= 3:
            parsed_end = _parse_applescript_date_string(parts[2])
            if parsed_end is not None:
                end = parsed_end
        events.append(
            CalendarEvent(
                title=title,
                start=start,
                end=end,
                description="",
                location="",
            )
        )
    events.sort(key=lambda e: e.start)
    return events, ""


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

    _DEFAULT_TIMEOUT_SEC = int(os.getenv("CEREBRO_CALENDAR_OSASCRIPT_TIMEOUT", "35"))
    _FAST_TIMEOUT_SEC = int(os.getenv("CEREBRO_CALENDAR_OSASCRIPT_FAST_TIMEOUT", "30"))

    def __init__(self, *, timeout_sec: int | None = None) -> None:
        self._timeout_sec = timeout_sec if timeout_sec is not None else self._DEFAULT_TIMEOUT_SEC

    @staticmethod
    def _events_from_apple_json(data: list) -> list[CalendarEvent]:
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

    def get_upcoming_events_v2(self, hours_ahead: int = 24) -> BackendResult:
        if platform.system() != "Darwin":
            logger.debug("AppleCalendarBackend is macOS-only; skipping on {}", platform.system())
            return BackendResult()

        events, err = _fetch_upcoming_via_applescript(hours_ahead)
        if err:
            if "timed out" in err.lower():
                logger.warning("Apple Calendar read timed out ({}h window)", hours_ahead)
                return BackendResult(status="timeout", detail=err)
            if _stderr_suggests_automation_denied(err):
                return BackendResult(status="permission_denied", detail=err)
            logger.warning("Apple Calendar read failed: {}", err[:200])
            return BackendResult(status="error", detail=err)
        return BackendResult(events=events, status="ok")

    async def get_upcoming_events_async(
        self, hours_ahead: int = 24, communicate_timeout: float = 3.0
    ) -> BackendResult:
        if platform.system() != "Darwin":
            return BackendResult()

        try:
            events, err = await asyncio.wait_for(
                asyncio.to_thread(_fetch_upcoming_via_applescript, hours_ahead),
                timeout=communicate_timeout,
            )
        except TimeoutError:
            return BackendResult(status="timeout", detail="osascript communicate timeout")

        if err:
            if "timed out" in err.lower():
                return BackendResult(status="timeout", detail=err)
            if _stderr_suggests_automation_denied(err):
                return BackendResult(status="permission_denied", detail=err)
            return BackendResult(status="error", detail=err)
        return BackendResult(events=events, status="ok")

    def get_upcoming_events(self, hours_ahead: int = 24) -> list[CalendarEvent]:
        return self.get_upcoming_events_v2(hours_ahead=hours_ahead).events


# ──────────────────────────────────────────────────────────────────────────────
# Apple Calendar writer (macOS only)
# ──────────────────────────────────────────────────────────────────────────────


def _automation_denied(stderr: str) -> bool:
    t = stderr.lower()
    return bool(
        re.search(r"\(-1743\)|\b1743\b", t)
        or "not allowed" in t
        or "isn't allowed to send" in t
        or "not authorized" in t
        or "privilege" in t
    )


def _parse_iso_to_local(iso: str) -> datetime:
    normalized = iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is not None:
        return dt.astimezone()
    return dt


_MONTHS_AS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _applescript_set_date_block(var_name: str, dt: datetime) -> str:
    """Build AppleScript that sets a date via components (avoids broken ``date \"MM/DD/YYYY\"`` parsing)."""
    local = dt.astimezone() if dt.tzinfo is not None else dt
    month = _MONTHS_AS[local.month - 1]
    return (
        f"set {var_name} to current date\n"
        f"set year of {var_name} to {local.year}\n"
        f"set month of {var_name} to {month}\n"
        f"set day of {var_name} to {local.day}\n"
        f"set hours of {var_name} to {local.hour}\n"
        f"set minutes of {var_name} to {local.minute}\n"
        f"set seconds of {var_name} to 0"
    )


# AppleScript is reliable for Calendar writes; JXA ``CalendarEvent`` often returns -1708.
_AS_CREATE_TEMPLATE = """\
{start_block}
{end_block}
tell application "Calendar"
    tell first calendar whose writable is true
        make new event at end with properties {{summary:{title}, start date:startDate, end date:endDate, description:{description}}}
    end tell
end tell
"""


def create_apple_calendar_event(
    title: str,
    iso_start: str,
    iso_end: str,
    description: str = "",
) -> tuple[bool, str]:
    """Create an event in the first writable Apple Calendar via osascript.

    Returns:
        (True, "") on success, (False, error_detail) on failure.
    """
    if platform.system() != "Darwin":
        logger.warning("create_apple_calendar_event is macOS-only")
        return False, "macOS only"

    try:
        start_dt = _parse_iso_to_local(iso_start)
        end_dt = _parse_iso_to_local(iso_end)
    except ValueError as exc:
        logger.warning("create_apple_calendar_event invalid ISO dates: {}", exc)
        return False, str(exc)

    script = _AS_CREATE_TEMPLATE.format(
        start_block=_applescript_set_date_block("startDate", start_dt),
        end_block=_applescript_set_date_block("endDate", end_dt),
        title=json.dumps(title),
        description=json.dumps(description),
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        logger.warning("osascript create event failed: {}", exc)
        return False, str(exc)

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        logger.warning("osascript create event returned non-zero: {}", err)
        return False, err

    return True, ""


def calendar_write_failure_hint(stderr: str) -> str:
    """User-facing hint after a failed Calendar write (permission vs script/other)."""
    if _automation_denied(stderr):
        return (
            "Revisa Ajustes → Privacidad y seguridad → Automatización: activa **Calendario** "
            "para la app que ejecuta Python (Cerebro, Terminal o el ícono de Python)."
        )
    if "-1708" in stderr or "message not understood" in stderr.lower():
        return "Error al hablar con la app Calendario (script). Reinicia Calendario y el backend."
    return "Revisa permisos de Automatización para Calendario o reinicia la app Calendario."


_AS_DELETE_BY_TITLE_TEMPLATE = """\
{day_start_block}
{day_end_block}
tell application "Calendar"
    set removedCount to 0
    set matchTitle to {title}
    set needle to {needle}
    repeat with cal in calendars
        try
            set theEvents to every event of cal whose summary contains needle
            repeat with ev in theEvents
                if summary of ev is matchTitle then
                    set sd to start date of ev
                    if sd ≥ dayStart and sd < dayEnd then
                        delete ev
                        set removedCount to removedCount + 1
                    end if
                end if
            end repeat
        end try
    end repeat
    return removedCount
end tell
"""


def _delete_search_window(
    on_day: date | None,
) -> tuple[datetime, datetime]:
    """Inclusive start, exclusive end (local) for AppleScript event filtering."""
    local = datetime.now().astimezone().tzinfo
    if on_day is not None:
        start = datetime.combine(on_day, datetime.min.time()).replace(tzinfo=local)
        return start, start + timedelta(days=1)
    now = datetime.now().astimezone()
    return now - timedelta(days=1), now + timedelta(days=60)


def delete_apple_calendar_event_by_title(
    title: str,
    *,
    on_day: date | None = None,
) -> int:
    """Delete calendar events with an exact title (search uses contains, then exact match).

    Returns count removed, -1 on error.
    """
    if platform.system() != "Darwin":
        logger.warning("delete_apple_calendar_event_by_title is macOS-only")
        return -1

    title = title.strip()
    if not title:
        return 0

    needle = title if len(title) >= 3 else title
    day_start, day_end = _delete_search_window(on_day)
    script = _AS_DELETE_BY_TITLE_TEMPLATE.format(
        day_start_block=_applescript_set_date_block("dayStart", day_start),
        day_end_block=_applescript_set_date_block("dayEnd", day_end),
        title=json.dumps(title),
        needle=json.dumps(needle),
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        logger.warning("osascript delete calendar event failed: {}", exc)
        return -1

    if result.returncode != 0:
        logger.warning(
            "osascript delete calendar event returned non-zero: {}", result.stderr.strip()
        )
        return -1

    try:
        return int((result.stdout or "0").strip())
    except ValueError:
        return 0


# ──────────────────────────────────────────────────────────────────────────────
# Birthday backends (macOS only — Calendar first, then Contacts fallback)
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

function isBirthdayCalendarName(rawName) {{
    var name = (rawName || "").toLowerCase();
    if (name === "birthdays" || name === "cumpleaños" || name === "geburtstage" || name === "anniversaires")
        return true;
    if (name.indexOf("birthday") >= 0 || name.indexOf("cumple") >= 0)
        return true;
    return false;
}}

function looksLikeBirthdayTitle(rawTitle) {{
    if (!rawTitle) return false;
    var t = rawTitle.toLowerCase();
    if (t.indexOf("birthday") >= 0 || t.indexOf("cumpleaños") >= 0 || t.indexOf("cumple") >= 0)
        return true;
    return /^.+(?:'|\\u2019)s birthday$/i.test(rawTitle);
}}

// Prefer a dedicated Birthdays-style calendar (exact locales, then fuzzy name)
var bdayCal = null;
var cals = app.calendars();
for (var ci = 0; ci < cals.length; ci++) {{
    if (isBirthdayCalendarName(cals[ci].name())) {{ bdayCal = cals[ci]; break; }}
}}

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
// Fallback: any calendar — titles that look like birthdays (incl. "Name's birthday" on iCloud)
if (results.length === 0) {{
    app.calendars().forEach(function(cal) {{
        try {{
            cal.events().forEach(function(ev) {{
                try {{
                    var summary = ev.summary() || "";
                    if (!looksLikeBirthdayTitle(summary)) return;
                    var orig = ev.startDate();
                    var next = nextAnnual(orig);
                    if (next >= now && next <= cutoff) {{
                        results.push({{ title: summary, start: next.toISOString() }});
                    }}
                }} catch(e) {{}}
            }});
        }} catch(e) {{}}
    }});
}}
JSON.stringify(results);
"""

# Contacts.app birthday fallback when Calendar has no birthday events (Phase 5 — FIX_CEREBRO).
_JXA_CONTACTS_BIRTHDAYS = """\
var ab = Application("Contacts");
var people = ab.people();
var out = [];
people.forEach(function(p) {
    try {
        var b = p.birthday();
        if (b) {
            var nm = "";
            try { nm = p.name() || ""; } catch(e1) { nm = ""; }
            out.push({ name: String(nm), month: b.getMonth() + 1, day: b.getDate() });
        }
    } catch(e) {}
});
JSON.stringify(out);
"""


class BirthdayBackend:
    """Query upcoming birthdays from Apple Calendar via osascript (macOS only).

    Picks dedicated birthday calendars (Birthdays, Cumpleaños, Geburtstage,
    Anniversaires, or names containing *birthday* / *cumple*), then falls back to
    any calendar whose event titles look like birthdays (keywords or *Name's birthday*).
    """

    _OSASCRIPT_TIMEOUT_SEC = int(os.getenv("CEREBRO_CALENDAR_OSASCRIPT_TIMEOUT", "35"))

    @staticmethod
    def _events_from_birthday_json(data: list) -> list[CalendarEvent]:
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

    def get_upcoming_events_v2(self, hours_ahead: int = 8760) -> BackendResult:
        if platform.system() != "Darwin":
            logger.debug("BirthdayBackend is macOS-only; skipping on {}", platform.system())
            return BackendResult()

        script = _JXA_BIRTHDAYS_TEMPLATE.format(hours_ahead=hours_ahead)
        try:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", script],
                capture_output=True,
                text=True,
                timeout=self._OSASCRIPT_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "BirthdayBackend osascript timed out after {}s", self._OSASCRIPT_TIMEOUT_SEC
            )
            return BackendResult(status="timeout", detail="osascript timed out")
        except Exception as exc:
            logger.warning("BirthdayBackend osascript failed: {}", exc)
            return BackendResult(status="error", detail=str(exc))

        stderr = (result.stderr or "").strip()
        if result.returncode != 0:
            logger.warning("BirthdayBackend osascript non-zero: {}", stderr)
            st: BackendStatus = (
                "permission_denied" if _stderr_suggests_automation_denied(stderr) else "error"
            )
            return BackendResult(status=st, detail=stderr or f"exit {result.returncode}")

        raw = (result.stdout or "").strip()
        if not raw:
            return BackendResult()

        try:
            data = json.loads(raw)
        except Exception as exc:
            logger.warning("BirthdayBackend failed to parse JSON: {}", exc)
            return BackendResult(status="error", detail=str(exc))

        if not isinstance(data, list):
            return BackendResult(status="error", detail="unexpected JSON shape")

        return BackendResult(events=self._events_from_birthday_json(data), status="ok")

    async def get_upcoming_events_async(
        self, hours_ahead: int = 8760, communicate_timeout: float = 3.0
    ) -> BackendResult:
        if platform.system() != "Darwin":
            return BackendResult()

        script = _JXA_BIRTHDAYS_TEMPLATE.format(hours_ahead=hours_ahead)
        try:
            proc = await asyncio.create_subprocess_exec(
                "osascript",
                "-l",
                "JavaScript",
                "-e",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as exc:
            return BackendResult(status="error", detail=str(exc))

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=communicate_timeout
            )
        except TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except TimeoutError:
                pass
            return BackendResult(status="timeout", detail="osascript communicate timeout")

        stderr = (stderr_b or b"").decode(errors="replace").strip()
        stdout = (stdout_b or b"").decode(errors="replace").strip()
        if proc.returncode != 0:
            st: BackendStatus = (
                "permission_denied" if _stderr_suggests_automation_denied(stderr) else "error"
            )
            return BackendResult(status=st, detail=stderr or f"exit {proc.returncode}")

        if not stdout:
            return BackendResult()

        try:
            data = json.loads(stdout)
        except Exception as exc:
            return BackendResult(status="error", detail=str(exc))

        if not isinstance(data, list):
            return BackendResult(status="error", detail="unexpected JSON shape")

        return BackendResult(events=self._events_from_birthday_json(data), status="ok")

    def get_upcoming_events(self, hours_ahead: int = 8760) -> list[CalendarEvent]:
        return self.get_upcoming_events_v2(hours_ahead=hours_ahead).events


def _contacts_birthdays_json_to_events(
    data: list,
    hours_ahead: int,
    *,
    now_override: datetime | None = None,
) -> list[CalendarEvent]:
    """Build next-occurrence CalendarEvent rows from Contacts JXA JSON."""
    now = (now_override or datetime.now()).astimezone()
    cutoff = now + timedelta(hours=hours_ahead)
    tz = now.tzinfo or UTC
    events: list[CalendarEvent] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            name = str(item.get("name", "")).strip() or "?"
            month = int(item["month"])
            day = int(item["day"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            y = now.year
            candidate = datetime(y, month, day, 0, 0, 0, tzinfo=tz)
            if candidate < now:
                candidate = candidate.replace(year=y + 1)
        except ValueError:
            continue
        if not (now <= candidate <= cutoff):
            continue
        title = f"Cumpleaños de {name}"
        end = candidate + timedelta(hours=24)
        events.append(CalendarEvent(title=title, start=candidate, end=end))
    events.sort(key=lambda e: e.start)
    return events


class ContactsBirthdayBackend:
    """Upcoming birthdays from Contacts.app when Calendar has none (macOS only)."""

    _OSASCRIPT_TIMEOUT_SEC = int(os.getenv("CEREBRO_CALENDAR_OSASCRIPT_TIMEOUT", "35"))

    def get_upcoming_events_v2(self, hours_ahead: int = 8760) -> BackendResult:
        if platform.system() != "Darwin":
            logger.debug("ContactsBirthdayBackend is macOS-only; skipping")
            return BackendResult()

        script = _JXA_CONTACTS_BIRTHDAYS
        try:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", script],
                capture_output=True,
                text=True,
                timeout=self._OSASCRIPT_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "ContactsBirthdayBackend osascript timed out after {}s",
                self._OSASCRIPT_TIMEOUT_SEC,
            )
            return BackendResult(status="timeout", detail="osascript timed out")
        except Exception as exc:
            logger.warning("ContactsBirthdayBackend osascript failed: {}", exc)
            return BackendResult(status="error", detail=str(exc))

        stderr = (result.stderr or "").strip()
        if result.returncode != 0:
            logger.warning("ContactsBirthdayBackend osascript non-zero: {}", stderr)
            st: BackendStatus = (
                "permission_denied" if _stderr_suggests_automation_denied(stderr) else "error"
            )
            detail = (
                "contacts" if st == "permission_denied" else (stderr or f"exit {result.returncode}")
            )
            return BackendResult(status=st, detail=detail)

        raw = (result.stdout or "").strip()
        if not raw:
            return BackendResult()

        try:
            data = json.loads(raw)
        except Exception as exc:
            logger.warning("ContactsBirthdayBackend failed to parse JSON: {}", exc)
            return BackendResult(status="error", detail=str(exc))

        if not isinstance(data, list):
            return BackendResult(status="error", detail="unexpected JSON shape")

        events = _contacts_birthdays_json_to_events(data, hours_ahead)
        return BackendResult(events=events, status="ok")

    async def get_upcoming_events_async(
        self, hours_ahead: int = 8760, communicate_timeout: float = 3.0
    ) -> BackendResult:
        if platform.system() != "Darwin":
            return BackendResult()

        try:
            proc = await asyncio.create_subprocess_exec(
                "osascript",
                "-l",
                "JavaScript",
                "-e",
                _JXA_CONTACTS_BIRTHDAYS,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as exc:
            return BackendResult(status="error", detail=str(exc))

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=communicate_timeout
            )
        except TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except TimeoutError:
                pass
            return BackendResult(status="timeout", detail="osascript communicate timeout")

        stderr = (stderr_b or b"").decode(errors="replace").strip()
        stdout = (stdout_b or b"").decode(errors="replace").strip()
        if proc.returncode != 0:
            st: BackendStatus = (
                "permission_denied" if _stderr_suggests_automation_denied(stderr) else "error"
            )
            detail = (
                "contacts" if st == "permission_denied" else (stderr or f"exit {proc.returncode}")
            )
            return BackendResult(status=st, detail=detail)

        if not stdout:
            return BackendResult()

        try:
            data = json.loads(stdout)
        except Exception as exc:
            return BackendResult(status="error", detail=str(exc))

        if not isinstance(data, list):
            return BackendResult(status="error", detail="unexpected JSON shape")

        events = _contacts_birthdays_json_to_events(data, hours_ahead)
        return BackendResult(events=events, status="ok")

    def get_upcoming_events(self, hours_ahead: int = 8760) -> list[CalendarEvent]:
        return self.get_upcoming_events_v2(hours_ahead=hours_ahead).events


class BirthdayChainBackend:
    """Runs Calendar birthdays first; if ok and empty, queries Contacts."""

    def __init__(self) -> None:
        self._calendar = BirthdayBackend()
        self._contacts = ContactsBirthdayBackend()

    def get_upcoming_events_v2(self, hours_ahead: int = 8760) -> BackendResult:
        first = self._calendar.get_upcoming_events_v2(hours_ahead)
        if first.events or first.status != "ok":
            return first
        return self._contacts.get_upcoming_events_v2(hours_ahead)

    async def get_upcoming_events_async(
        self, hours_ahead: int = 8760, communicate_timeout: float = 3.0
    ) -> BackendResult:
        first = await self._calendar.get_upcoming_events_async(hours_ahead, communicate_timeout)
        if first.events or first.status != "ok":
            return first
        return await self._contacts.get_upcoming_events_async(hours_ahead, communicate_timeout)

    def get_upcoming_events(self, hours_ahead: int = 8760) -> list[CalendarEvent]:
        return self.get_upcoming_events_v2(hours_ahead=hours_ahead).events


# ──────────────────────────────────────────────────────────────────────────────
# Facade
# ──────────────────────────────────────────────────────────────────────────────


class CalendarReader:
    """Aggregate events from all configured backends.

    Backends are queried in order (iCal first, then Apple Calendar, then birthday chain).
    Results are merged, deduplicated by (title, start ISO string), and
    sorted ascending by start time.
    """

    def __init__(
        self,
        ics_path: str | None = None,
        use_apple_calendar: bool = False,
        *,
        include_birthday_backends: bool = False,
        apple_timeout_sec: int | None = None,
    ) -> None:
        self._backends: list = []
        if ics_path:
            self._backends.append(ICalBackend(ics_path))
        if use_apple_calendar:
            self._backends.append(AppleCalendarBackend(timeout_sec=apple_timeout_sec))
            if include_birthday_backends:
                self._backends.append(BirthdayChainBackend())

    def get_upcoming_events_v2(self, hours_ahead: int = 24) -> BackendResult:
        if not self._backends:
            return BackendResult()

        partials: list[BackendResult] = []
        merged: list[CalendarEvent] = []
        seen: set[tuple[str, str]] = set()

        for backend in self._backends:
            try:
                if hasattr(backend, "get_upcoming_events_v2"):
                    br = backend.get_upcoming_events_v2(hours_ahead)
                else:
                    evs = backend.get_upcoming_events(hours_ahead)
                    br = BackendResult(events=evs, status="ok")
            except Exception as exc:
                logger.warning("Backend {} error: {}", type(backend).__name__, exc)
                br = BackendResult(status="error", detail=str(exc))

            partials.append(br)
            for ev in br.events:
                key = (ev.title, ev.start.isoformat())
                if key not in seen:
                    seen.add(key)
                    merged.append(ev)

        return _merge_calendar_backend_results(partials, merged)

    async def get_upcoming_events_async(
        self, hours_ahead: int = 24, apple_communicate_timeout: float = 3.0
    ) -> BackendResult:
        """Async merge for ContextEnricher — kills hung osascript on timeout."""
        if not self._backends:
            return BackendResult()

        partials: list[BackendResult] = []
        merged: list[CalendarEvent] = []
        seen: set[tuple[str, str]] = set()

        for backend in self._backends:
            try:
                if isinstance(
                    backend,
                    AppleCalendarBackend | BirthdayBackend | BirthdayChainBackend,
                ):
                    br = await backend.get_upcoming_events_async(
                        hours_ahead, communicate_timeout=apple_communicate_timeout
                    )
                elif hasattr(backend, "get_upcoming_events_v2"):
                    br = await asyncio.to_thread(backend.get_upcoming_events_v2, hours_ahead)
                else:
                    evs = await asyncio.to_thread(backend.get_upcoming_events, hours_ahead)
                    br = BackendResult(events=evs, status="ok")
            except Exception as exc:
                logger.warning("Backend {} async error: {}", type(backend).__name__, exc)
                br = BackendResult(status="error", detail=str(exc))

            partials.append(br)
            for ev in br.events:
                key = (ev.title, ev.start.isoformat())
                if key not in seen:
                    seen.add(key)
                    merged.append(ev)

        return _merge_calendar_backend_results(partials, merged)

    def get_upcoming_events(self, hours_ahead: int = 24) -> list[CalendarEvent]:
        return self.get_upcoming_events_v2(hours_ahead=hours_ahead).events

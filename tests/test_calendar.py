"""Tests for Module 11 — Calendar Integration."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from integrations.calendar_reader import (
    _JXA_BIRTHDAYS_TEMPLATE,
    AppleCalendarBackend,
    BirthdayBackend,
    CalendarReader,
    ICalBackend,
)

# ──────────────────────────────────────────────────────────────────────────────
# .ics content helpers
# ──────────────────────────────────────────────────────────────────────────────

_ICS_HEADER = "BEGIN:VCALENDAR\r\n" "VERSION:2.0\r\n" "PRODID:-//Test//Test//EN\r\n"
_ICS_FOOTER = "END:VCALENDAR\r\n"


def _make_ics(events: list[str]) -> bytes:
    return (_ICS_HEADER + "".join(events) + _ICS_FOOTER).encode()


def _vevent(
    title: str,
    start: datetime,
    end: datetime | None = None,
    description: str = "",
    location: str = "",
) -> str:
    fmt = "%Y%m%dT%H%M%SZ"
    end = end or (start + timedelta(hours=1))
    lines = [
        "BEGIN:VEVENT",
        f"SUMMARY:{title}",
        f"DTSTART:{start.strftime(fmt)}",
        f"DTEND:{end.strftime(fmt)}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{description}")
    if location:
        lines.append(f"LOCATION:{location}")
    lines.append("END:VEVENT")
    return "\r\n".join(lines) + "\r\n"


def _vevent_allday(title: str, date_str: str) -> str:
    return (
        "BEGIN:VEVENT\r\n"
        f"SUMMARY:{title}\r\n"
        f"DTSTART;VALUE=DATE:{date_str}\r\n"
        f"DTEND;VALUE=DATE:{date_str}\r\n"
        "END:VEVENT\r\n"
    )


# ──────────────────────────────────────────────────────────────────────────────
# ICalBackend — happy path
# ──────────────────────────────────────────────────────────────────────────────


def test_ical_returns_event_within_window(tmp_path: Path):
    now = datetime.now(UTC)
    start = now + timedelta(hours=2)
    ics = _make_ics(
        [_vevent("Team meeting", start, description="Sprint review", location="Room A")]
    )
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    events = ICalBackend(str(p)).get_upcoming_events(hours_ahead=24)

    assert len(events) == 1
    assert events[0].title == "Team meeting"
    assert events[0].description == "Sprint review"
    assert events[0].location == "Room A"


def test_ical_filters_event_outside_window(tmp_path: Path):
    now = datetime.now(UTC)
    ics = _make_ics([_vevent("Far future", now + timedelta(hours=48))])
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    events = ICalBackend(str(p)).get_upcoming_events(hours_ahead=24)

    assert events == []


def test_ical_filters_past_event(tmp_path: Path):
    now = datetime.now(UTC)
    ics = _make_ics([_vevent("Yesterday", now - timedelta(hours=2))])
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    events = ICalBackend(str(p)).get_upcoming_events(hours_ahead=24)

    assert events == []


def test_ical_multiple_events_all_returned(tmp_path: Path):
    now = datetime.now(UTC)
    ics = _make_ics(
        [
            _vevent("Event A", now + timedelta(hours=1)),
            _vevent("Event B", now + timedelta(hours=5)),
        ]
    )
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    events = ICalBackend(str(p)).get_upcoming_events(hours_ahead=24)

    titles = {e.title for e in events}
    assert "Event A" in titles
    assert "Event B" in titles


def test_ical_event_fields_populated(tmp_path: Path):
    now = datetime.now(UTC)
    start = now + timedelta(hours=1)
    end = start + timedelta(hours=2)
    ics = _make_ics(
        [_vevent("Review", start, end=end, description="Docs review", location="Online")]
    )
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    ev = ICalBackend(str(p)).get_upcoming_events(hours_ahead=24)[0]

    assert ev.title == "Review"
    assert ev.start.tzinfo is not None
    assert ev.end > ev.start
    assert ev.description == "Docs review"
    assert ev.location == "Online"


# ──────────────────────────────────────────────────────────────────────────────
# ICalBackend — error handling
# ──────────────────────────────────────────────────────────────────────────────


def test_ical_returns_empty_for_missing_file():
    events = ICalBackend("/nonexistent/path/calendar.ics").get_upcoming_events()
    assert events == []


def test_ical_returns_empty_for_invalid_content(tmp_path: Path):
    p = tmp_path / "bad.ics"
    p.write_bytes(b"NOT VALID ICAL CONTENT !!!@#$%")

    events = ICalBackend(str(p)).get_upcoming_events()

    assert isinstance(events, list)


def test_ical_parses_all_day_event(tmp_path: Path):
    ics = _make_ics([_vevent_allday("Birthday", "20290510")])
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    events = ICalBackend(str(p)).get_upcoming_events(hours_ahead=99999)

    assert len(events) == 1
    assert events[0].title == "Birthday"
    assert events[0].start.tzinfo is not None


# ──────────────────────────────────────────────────────────────────────────────
# AppleCalendarBackend
# ──────────────────────────────────────────────────────────────────────────────


def _apple_ok(events: list[dict]) -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = json.dumps(events)
    m.stderr = ""
    return m


def test_apple_backend_returns_events():
    now = datetime.now(UTC)
    start = (now + timedelta(hours=1)).isoformat()
    end = (now + timedelta(hours=2)).isoformat()
    payload = [
        {"title": "Standup", "start": start, "end": end, "description": "Daily", "location": "Zoom"}
    ]

    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch("integrations.calendar_reader.subprocess.run", return_value=_apple_ok(payload)):
            events = AppleCalendarBackend().get_upcoming_events(hours_ahead=24)

    assert len(events) == 1
    assert events[0].title == "Standup"
    assert events[0].description == "Daily"
    assert events[0].location == "Zoom"


def test_apple_backend_skips_on_non_macos():
    with patch("integrations.calendar_reader.platform.system", return_value="Linux"):
        events = AppleCalendarBackend().get_upcoming_events()

    assert events == []


def test_apple_backend_returns_empty_on_osascript_error():
    m = MagicMock()
    m.returncode = 1
    m.stdout = ""
    m.stderr = "Calendar not accessible"

    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch("integrations.calendar_reader.subprocess.run", return_value=m):
            events = AppleCalendarBackend().get_upcoming_events()

    assert events == []


def test_apple_backend_handles_subprocess_exception():
    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch(
            "integrations.calendar_reader.subprocess.run", side_effect=OSError("osascript missing")
        ):
            events = AppleCalendarBackend().get_upcoming_events()

    assert events == []


def test_apple_backend_handles_empty_output():
    m = MagicMock()
    m.returncode = 0
    m.stdout = ""
    m.stderr = ""

    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch("integrations.calendar_reader.subprocess.run", return_value=m):
            events = AppleCalendarBackend().get_upcoming_events()

    assert events == []


def test_apple_backend_handles_invalid_json():
    m = MagicMock()
    m.returncode = 0
    m.stdout = "NOT JSON"
    m.stderr = ""

    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch("integrations.calendar_reader.subprocess.run", return_value=m):
            events = AppleCalendarBackend().get_upcoming_events()

    assert events == []


# ──────────────────────────────────────────────────────────────────────────────
# CalendarReader facade
# ──────────────────────────────────────────────────────────────────────────────


def test_reader_no_backends_returns_empty():
    assert CalendarReader().get_upcoming_events() == []


def test_reader_uses_ical_backend(tmp_path: Path):
    now = datetime.now(UTC)
    ics = _make_ics([_vevent("Project sync", now + timedelta(hours=3))])
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    events = CalendarReader(ics_path=str(p)).get_upcoming_events(hours_ahead=24)

    assert len(events) == 1
    assert events[0].title == "Project sync"


def test_reader_events_sorted_by_start(tmp_path: Path):
    now = datetime.now(UTC)
    ics = _make_ics(
        [
            _vevent("Event A", now + timedelta(hours=10)),
            _vevent("Event B", now + timedelta(hours=2)),
            _vevent("Event C", now + timedelta(hours=5)),
        ]
    )
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    events = CalendarReader(ics_path=str(p)).get_upcoming_events(hours_ahead=24)

    assert len(events) == 3
    assert events[0].title == "Event B"
    assert events[1].title == "Event C"
    assert events[2].title == "Event A"


def test_reader_deduplicates_same_event_across_backends(tmp_path: Path):
    now = datetime.now(UTC)
    start = now + timedelta(hours=3)
    ics = _make_ics([_vevent("Shared", start)])
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    reader = CalendarReader(ics_path=str(p))
    # inject a second backend that returns an identical event
    duplicate = MagicMock(spec=["get_upcoming_events"])
    ical_events = ICalBackend(str(p)).get_upcoming_events(hours_ahead=24)
    duplicate.get_upcoming_events.return_value = ical_events
    reader._backends.append(duplicate)

    events = reader.get_upcoming_events(hours_ahead=24)

    assert len(events) == 1


def test_reader_backend_exception_does_not_propagate():
    reader = CalendarReader()
    bad_backend = MagicMock(spec=["get_upcoming_events"])
    bad_backend.get_upcoming_events.side_effect = RuntimeError("boom")
    reader._backends.append(bad_backend)

    events = reader.get_upcoming_events()

    assert events == []


def test_reader_includes_birthday_backend_on_macos():
    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        reader = CalendarReader(use_apple_calendar=True)
    backend_types = [type(b).__name__ for b in reader._backends]
    assert "AppleCalendarBackend" in backend_types
    assert "BirthdayChainBackend" in backend_types


# ──────────────────────────────────────────────────────────────────────────────
# BirthdayBackend
# ──────────────────────────────────────────────────────────────────────────────


def _birthday_ok(entries: list[dict]) -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = json.dumps(entries)
    m.stderr = ""
    return m


def test_birthday_backend_returns_events():
    now = datetime.now(UTC)
    start = (now + timedelta(days=10)).replace(hour=0, minute=0, second=0, microsecond=0)
    payload = [{"title": "Alice's Birthday", "start": start.isoformat()}]

    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch(
            "integrations.calendar_reader.subprocess.run", return_value=_birthday_ok(payload)
        ):
            events = BirthdayBackend().get_upcoming_events(hours_ahead=8760)

    assert len(events) == 1
    assert events[0].title == "Alice's Birthday"
    assert events[0].end == events[0].start + timedelta(hours=24)


def test_birthday_backend_skips_on_non_macos():
    with patch("integrations.calendar_reader.platform.system", return_value="Linux"):
        events = BirthdayBackend().get_upcoming_events()
    assert events == []


def test_birthday_backend_returns_empty_on_osascript_error():
    m = MagicMock()
    m.returncode = 1
    m.stdout = ""
    m.stderr = "Contacts not accessible"

    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch("integrations.calendar_reader.subprocess.run", return_value=m):
            events = BirthdayBackend().get_upcoming_events()
    assert events == []


def test_birthday_backend_handles_subprocess_exception():
    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch(
            "integrations.calendar_reader.subprocess.run", side_effect=OSError("osascript missing")
        ):
            events = BirthdayBackend().get_upcoming_events()
    assert events == []


def test_birthday_backend_handles_invalid_json():
    m = MagicMock()
    m.returncode = 0
    m.stdout = "NOT JSON"
    m.stderr = ""

    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch("integrations.calendar_reader.subprocess.run", return_value=m):
            events = BirthdayBackend().get_upcoming_events()
    assert events == []


# ──────────────────────────────────────────────────────────────────────────────
# search_upcoming handler
# ──────────────────────────────────────────────────────────────────────────────


def test_search_upcoming_finds_birthday_in_fixture(tmp_path: Path):
    now = datetime.now(UTC)
    ics = _make_ics([_vevent("Bob's Birthday", now + timedelta(days=60))])
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    from core.tools.handlers.calendar import search_upcoming

    result = search_upcoming("birthday", days_ahead=365, ics_path=str(p))

    assert "Bob's Birthday" in result


def test_search_upcoming_returns_no_match_message(tmp_path: Path):
    now = datetime.now(UTC)
    ics = _make_ics([_vevent("Team Sync", now + timedelta(days=5))])
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    from core.tools.handlers.calendar import search_upcoming

    result = search_upcoming("dentist", days_ahead=365, ics_path=str(p))

    assert "Sin eventos" in result
    assert "dentist" in result


def test_search_upcoming_uses_days_not_hours(tmp_path: Path):
    now = datetime.now(UTC)
    # Event is 200 days away — beyond query_events default (7d) but within 365d
    ics = _make_ics([_vevent("Anniversary Dinner", now + timedelta(days=200))])
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    from core.tools.handlers.calendar import search_upcoming

    result = search_upcoming("anniversary", days_ahead=365, ics_path=str(p))

    assert "Anniversary Dinner" in result


# ──────────────────────────────────────────────────────────────────────────────
# add_apple_reminder (integrations layer)
# ──────────────────────────────────────────────────────────────────────────────

from integrations.calendar_reader import add_apple_reminder


def _reminder_ok() -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = "ok"
    m.stderr = ""
    return m


def test_add_apple_reminder_returns_true_on_success():
    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch("integrations.calendar_reader.subprocess.run", return_value=_reminder_ok()):
            result = add_apple_reminder(
                "Call doctor", "2026-05-20T09:00:00+00:00", "bring insurance card"
            )
    assert result is True


def test_add_apple_reminder_returns_false_on_non_macos():
    with patch("integrations.calendar_reader.platform.system", return_value="Linux"):
        result = add_apple_reminder("Call doctor", "2026-05-20T09:00:00+00:00")
    assert result is False


def test_add_apple_reminder_returns_false_on_osascript_error():
    m = MagicMock()
    m.returncode = 1
    m.stdout = ""
    m.stderr = "Reminders not accessible"
    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch("integrations.calendar_reader.subprocess.run", return_value=m):
            result = add_apple_reminder("Task", "2026-05-20T09:00:00+00:00")
    assert result is False


def test_add_apple_reminder_returns_false_on_subprocess_exception():
    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch(
            "integrations.calendar_reader.subprocess.run", side_effect=OSError("osascript missing")
        ):
            result = add_apple_reminder("Task", "2026-05-20T09:00:00+00:00")
    assert result is False


# ──────────────────────────────────────────────────────────────────────────────
# add_reminder handler
# ──────────────────────────────────────────────────────────────────────────────

from core.tools.handlers.calendar import add_reminder as handler_add_reminder


def test_add_reminder_success():
    with patch("core.tools.handlers.calendar.platform.system", return_value="Darwin"):
        with patch("core.tools.handlers.calendar.add_apple_reminder", return_value=True):
            result = handler_add_reminder("Call doctor", "2026-05-20 09:00")
    assert "Call doctor" in result
    assert "Failed" not in result


def test_add_reminder_non_macos_returns_informative_message():
    with patch("core.tools.handlers.calendar.platform.system", return_value="Linux"):
        result = handler_add_reminder("Buy milk", "tomorrow at 9am")
    assert "macOS" in result
    assert "Buy milk" in result


def test_add_reminder_bad_date_returns_error():
    result = handler_add_reminder("Something", "not a date xyzzy")
    assert "Could not parse" in result
    assert "not a date xyzzy" in result


def test_add_reminder_osascript_failure_returns_error():
    with patch("core.tools.handlers.calendar.platform.system", return_value="Darwin"):
        with patch("core.tools.handlers.calendar.add_apple_reminder", return_value=False):
            result = handler_add_reminder("Fix bug", "2026-06-01 10:00")
    assert "Failed" in result
    assert "Fix bug" in result


def test_add_reminder_notes_passed_through():
    with patch("core.tools.handlers.calendar.platform.system", return_value="Darwin"):
        with patch("core.tools.handlers.calendar.add_apple_reminder", return_value=True) as mock_fn:
            handler_add_reminder("Dentist", "2026-06-01 10:00", notes="bring X-rays")
    mock_fn.assert_called_once()
    _, _, notes_arg = mock_fn.call_args[0]
    assert notes_arg == "bring X-rays"


# ──────────────────────────────────────────────────────────────────────────────
# Bug 0-A: Birthday backend targets Calendar app, not Contacts (Phase 0 fix)
# ──────────────────────────────────────────────────────────────────────────────


def test_birthday_template_targets_calendar_not_contacts():
    assert 'Application("Calendar")' in _JXA_BIRTHDAYS_TEMPLATE
    assert "Contacts" not in _JXA_BIRTHDAYS_TEMPLATE


def test_birthday_template_has_no_freq_yearly_filter():
    assert "FREQ=YEARLY" not in _JXA_BIRTHDAYS_TEMPLATE


def test_birthday_template_includes_fallback_title_scan():
    assert "indexOf" in _JXA_BIRTHDAYS_TEMPLATE
    assert "birthday" in _JXA_BIRTHDAYS_TEMPLATE
    assert "cumpleaños" in _JXA_BIRTHDAYS_TEMPLATE
    assert "geburtstage" in _JXA_BIRTHDAYS_TEMPLATE.lower()
    assert "anniversaires" in _JXA_BIRTHDAYS_TEMPLATE.lower()


# ──────────────────────────────────────────────────────────────────────────────
# Bug 0-B: Calendar handler outputs local timezone, not hardcoded UTC (Phase 0 fix)
# ──────────────────────────────────────────────────────────────────────────────


def test_get_upcoming_events_uses_local_timezone_format(tmp_path):
    """get_upcoming_events must include %Z timezone abbreviation, not hardcoded 'UTC'."""
    ics = _make_ics([])
    p = tmp_path / "cal.ics"
    p.write_bytes(ics)

    local_dt = datetime(2026, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("America/Mexico_City"))
    mock_now = MagicMock()
    mock_now.astimezone.return_value = local_dt

    from core.tools.handlers.calendar import get_upcoming_events

    with patch("core.tools.handlers.calendar.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        result = get_upcoming_events(hours_ahead=24, ics_path=str(p))

    assert "CST" in result
    # Must not have the old hardcoded " UTC" suffix
    assert result.count(" UTC") == 0

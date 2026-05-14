"""Tests for integrations.calendar_reader — Phase 4 structured BackendResult + merge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations import calendar_reader as calendar_reader_mod
from integrations.calendar_reader import (
    AppleCalendarBackend,
    BackendResult,
    BirthdayBackend,
    BirthdayChainBackend,
    CalendarEvent,
    CalendarReader,
    ContactsBirthdayBackend,
    ICalBackend,
    _merge_calendar_backend_results,
)


def test_merge_prefers_events_over_permission_when_ical_has_data():
    """Merged events from a healthy backend should win over Apple permission_denied."""
    t0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    ev = CalendarEvent(title="ICS", start=t0, end=t0 + timedelta(hours=1))
    partials = [
        BackendResult(events=[ev], status="ok"),
        BackendResult(events=[], status="permission_denied", detail="denied"),
    ]
    merged = [ev]
    r = _merge_calendar_backend_results(partials, merged)
    assert r.status == "ok"
    assert len(r.events) == 1
    assert r.events[0].title == "ICS"


def test_merge_permission_when_no_events():
    partials = [
        BackendResult(events=[], status="permission_denied", detail="x"),
    ]
    r = _merge_calendar_backend_results(partials, [])
    assert r.status == "permission_denied"


def test_ical_backend_v2_missing_file(tmp_path: Path):
    p = tmp_path / "missing.ics"
    br = ICalBackend(str(p)).get_upcoming_events_v2(24)
    assert br.status == "no_calendar"
    assert br.events == []


def test_calendar_reader_get_upcoming_events_v2_dedup(tmp_path: Path):
    """Same (title, start) from two backends appears once."""
    t0 = datetime(2026, 7, 1, 15, 0, 0, tzinfo=UTC)
    ev = CalendarEvent(title="Dup", start=t0, end=t0 + timedelta(hours=1))

    class _FakeA:
        def get_upcoming_events_v2(self, hours_ahead: int) -> BackendResult:
            return BackendResult(events=[ev], status="ok")

    class _FakeB:
        def get_upcoming_events_v2(self, hours_ahead: int) -> BackendResult:
            return BackendResult(events=[ev], status="ok")

    reader = CalendarReader.__new__(CalendarReader)
    reader._backends = [_FakeA(), _FakeB()]
    out = reader.get_upcoming_events_v2(hours_ahead=24)
    assert out.status == "ok"
    assert len(out.events) == 1


def test_birthday_jxa_template_has_calendar_discovery_and_apostrophe_pattern():
    t = calendar_reader_mod._JXA_BIRTHDAYS_TEMPLATE
    assert "geburtstage" in t.lower()
    assert "anniversaires" in t.lower()
    assert "looksLikeBirthdayTitle" in t
    assert "s birthday" in t


def test_contacts_birthday_fallback_chain_uses_contacts_when_calendar_empty():
    t0 = datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC)
    ev = CalendarEvent(title="Cumpleaños de Pat", start=t0, end=t0 + timedelta(hours=24))
    with patch.object(
        BirthdayBackend,
        "get_upcoming_events_v2",
        return_value=BackendResult(events=[], status="ok"),
    ):
        with patch.object(
            ContactsBirthdayBackend,
            "get_upcoming_events_v2",
            return_value=BackendResult(events=[ev], status="ok"),
        ):
            r = BirthdayChainBackend().get_upcoming_events_v2(8760)
    assert r.status == "ok"
    assert r.events == [ev]


def test_contacts_birthday_chain_skips_contacts_when_calendar_has_events():
    t0 = datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC)
    cal_ev = CalendarEvent(title="Cal Bday", start=t0, end=t0 + timedelta(hours=24))
    spy = MagicMock(
        return_value=BackendResult(events=[CalendarEvent(title="X", start=t0, end=t0)], status="ok")
    )
    with patch.object(
        BirthdayBackend,
        "get_upcoming_events_v2",
        return_value=BackendResult(events=[cal_ev], status="ok"),
    ):
        with patch.object(ContactsBirthdayBackend, "get_upcoming_events_v2", spy):
            r = BirthdayChainBackend().get_upcoming_events_v2(8760)
    assert r.events == [cal_ev]
    spy.assert_not_called()


def test_contacts_birthdays_json_to_events_respects_window():
    fixed = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
    evs = calendar_reader_mod._contacts_birthdays_json_to_events(
        [{"name": "Ada", "month": 7, "day": 1}], hours_ahead=8760, now_override=fixed
    )
    assert len(evs) == 1
    assert "Ada" in evs[0].title
    assert evs[0].start.month == 7 and evs[0].start.day == 1


@pytest.mark.asyncio
async def test_apple_backend_async_timeout_kills_process():
    proc = MagicMock()
    proc.communicate = AsyncMock(side_effect=TimeoutError)
    proc.kill = MagicMock()
    proc.wait = AsyncMock(return_value=0)

    async def fake_exec(*_a, **_k):
        return proc

    with patch("integrations.calendar_reader.platform.system", return_value="Darwin"):
        with patch(
            "integrations.calendar_reader.asyncio.create_subprocess_exec",
            side_effect=fake_exec,
        ):
            b = AppleCalendarBackend()
            r = await b.get_upcoming_events_async(24, communicate_timeout=0.1)
    proc.kill.assert_called_once()
    assert r.status == "timeout"

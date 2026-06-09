"""Tests for calendar date-anchor parsing (after/before/on day)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.agents.calendar_query_parse import (
    DateFilterKind,
    extract_calendar_date_filter,
    filter_events_by_date,
    hours_window_for_filter,
)
from integrations.calendar_reader import CalendarEvent


def _next_weekday(weekday: int) -> datetime:
    """Next occurrence of weekday (0=Mon) from now, at least 1 day ahead if today."""
    now = datetime.now(UTC)
    delta = (weekday - now.weekday()) % 7
    if delta == 0:
        delta = 7
    return now + timedelta(days=delta)


def test_extract_after_thursday():
    filt = extract_calendar_date_filter("cual es el proximo evento despues del jueves?")
    assert filt is not None
    assert filt.kind == DateFilterKind.AFTER
    assert filt.anchor_day.weekday() == 3


def test_extract_on_friday():
    filt = extract_calendar_date_filter("que tengo el viernes en el calendario")
    assert filt is not None
    assert filt.kind == DateFilterKind.ON
    assert filt.anchor_day.weekday() == 4


def test_extract_on_tomorrow_without_article():
    filt = extract_calendar_date_filter("que tengo para mañana?")
    assert filt is not None
    assert filt.kind == DateFilterKind.ON


def test_extract_on_next_monday():
    filt = extract_calendar_date_filter("que tengo el próximo lunes?")
    assert filt is not None
    assert filt.kind == DateFilterKind.ON
    assert filt.anchor_day.weekday() == 0


def test_extract_on_spanish_written_date():
    filt = extract_calendar_date_filter("eventos del 14 de junio")
    assert filt is not None
    assert filt.kind == DateFilterKind.ON


def test_extract_on_loose_phrase_with_calendar_context():
    filt = extract_calendar_date_filter("en mi calendario para 2027-01-14")
    assert filt is not None
    assert filt.kind == DateFilterKind.ON
    assert filt.anchor_day.year == 2027


def test_hours_window_for_far_on_date():
    filt = extract_calendar_date_filter("que tengo el 2027-01-14")
    assert filt is not None
    hours = hours_window_for_filter(filt, base_hours=24)
    assert hours > 24 * 30


def test_filter_after_thursday_excludes_thursday_event():
    thursday = _next_weekday(3).replace(hour=15, minute=0, second=0, microsecond=0)
    friday = thursday + timedelta(days=1)
    friday = friday.replace(hour=10, minute=0)
    events = [
        CalendarEvent("Thu meeting", thursday, thursday + timedelta(hours=1)),
        CalendarEvent("Fri meeting", friday, friday + timedelta(hours=1)),
    ]
    filt = extract_calendar_date_filter("proximo evento despues del jueves")
    assert filt is not None
    out = filter_events_by_date(events, filt)
    assert len(out) == 1
    assert out[0].title == "Fri meeting"


def test_filter_on_day_only_same_day(tmp_path):
    thursday = _next_weekday(3).replace(hour=9, minute=0, second=0, microsecond=0)
    friday = thursday + timedelta(days=1)
    events = [
        CalendarEvent("Only Thu", thursday, thursday + timedelta(hours=1)),
        CalendarEvent("Only Fri", friday, friday + timedelta(hours=1)),
    ]
    filt = extract_calendar_date_filter("eventos del jueves")
    assert filt is not None
    assert filt.kind == DateFilterKind.ON
    out = filter_events_by_date(events, filt)
    assert len(out) == 1
    assert out[0].title == "Only Thu"

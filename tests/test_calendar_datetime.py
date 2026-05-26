"""Calendar reminder datetime parsing — local wall clock, not UTC."""

from __future__ import annotations

from core.tools.handlers.calendar import _parse_event_datetime


def test_manana_3pm_stays_local_afternoon():
    parsed = _parse_event_datetime("mañana a las 3pm")
    assert parsed is not None
    local = parsed.astimezone()
    assert local.hour == 15
    assert local.minute == 0

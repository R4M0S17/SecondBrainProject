"""Apple Calendar read via AppleScript (not JXA date whose)."""

from __future__ import annotations

from integrations.calendar_reader import _fetch_upcoming_via_applescript


def test_fetch_upcoming_returns_ok_status():
    events, err = _fetch_upcoming_via_applescript(24 * 14)
    assert err == ""
    assert isinstance(events, list)

#!/usr/bin/env python3
"""Generate manual_tests/fixtures/calendar_e2e.ics with a near meeting + future birthday."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent / "calendar_e2e.ics"

_ICS_HEADER = "BEGIN:VCALENDAR\r\n" "VERSION:2.0\r\n" "PRODID:-//Cerebro//E2E//EN\r\n"
_ICS_FOOTER = "END:VCALENDAR\r\n"


def _vevent(title: str, start: datetime) -> str:
    end = start + timedelta(hours=1)
    fmt = "%Y%m%dT%H%M%SZ"
    return (
        "BEGIN:VEVENT\r\n"
        f"SUMMARY:{title}\r\n"
        f"DTSTART:{start.strftime(fmt)}\r\n"
        f"DTEND:{end.strftime(fmt)}\r\n"
        "END:VEVENT\r\n"
    )


def main() -> None:
    now = datetime.now(UTC)
    ics = _ICS_HEADER + _vevent("E2E Team Meeting", now + timedelta(hours=4))
    ics += _vevent("Ana cumpleaños", now + timedelta(days=30))
    ics += _ICS_FOOTER
    OUT.write_bytes(ics.encode())
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

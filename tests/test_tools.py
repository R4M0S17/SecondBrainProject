"""Tests for Module 6 — Tool Use & Action Layer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.tools.handlers.execution import execute_python
from core.tools.handlers.filesystem import (
    PathNotAuthorizedError,
    create_directory,
    list_directory,
    read_file,
    validate_path,
    write_file,
)
from core.tools.handlers.utils import create_note, get_current_datetime

# ---------------------------------------------------------------------------
# validate_path
# ---------------------------------------------------------------------------


def test_validate_path_accepts_child(tmp_path):
    child = tmp_path / "sub" / "file.txt"
    assert validate_path(str(child), [str(tmp_path)]) is True


def test_validate_path_rejects_sibling(tmp_path):
    sibling = tmp_path.parent / "other" / "file.txt"
    assert validate_path(str(sibling), [str(tmp_path)]) is False


# ---------------------------------------------------------------------------
# read_file — rejects paths outside authorized_paths
# ---------------------------------------------------------------------------


def test_read_file_rejects_unauthorized_path(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (allowed / "doc.txt").write_text("hello")
    with pytest.raises(PathNotAuthorizedError):
        read_file(str(tmp_path / "secret.txt"), [str(allowed)])


def test_read_file_allows_authorized_path(tmp_path):
    (tmp_path / "doc.txt").write_text("hello world")
    result = read_file(str(tmp_path / "doc.txt"), [str(tmp_path)])
    assert result == "hello world"


def test_read_file_nonexistent_returns_error(tmp_path):
    result = read_file(str(tmp_path / "missing.txt"), [str(tmp_path)])
    assert "Error" in result or "not found" in result


# ---------------------------------------------------------------------------
# write_file / create_directory / list_directory
# ---------------------------------------------------------------------------


def test_write_file_creates_content(tmp_path):
    target = tmp_path / "out.txt"
    ok = write_file(str(target), "data", [str(tmp_path)])
    assert ok is True
    assert target.read_text() == "data"


def test_write_file_rejects_unauthorized(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    with pytest.raises(PathNotAuthorizedError):
        write_file(str(tmp_path / "evil.txt"), "x", [str(allowed)])


def test_create_directory_creates_nested(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    ok = create_directory(str(target), [str(tmp_path)])
    assert ok is True
    assert target.is_dir()


def test_list_directory_returns_children(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    result = list_directory(str(tmp_path), [str(tmp_path)])
    names = [p.split("/")[-1] for p in result]
    assert "a.txt" in names and "b.txt" in names


def test_list_directory_nonexistent_returns_empty(tmp_path):
    result = list_directory(str(tmp_path / "ghost"), [str(tmp_path)])
    assert result == []


# ---------------------------------------------------------------------------
# execute_python — blocks disallowed imports
# ---------------------------------------------------------------------------


def test_execute_python_blocks_import_os():
    result = execute_python("import os; print(os.getcwd())")
    assert "Error" in result or "ImportError" in result


def test_execute_python_blocks_import_sys():
    result = execute_python("import sys; print(sys.path)")
    assert "Error" in result or "ImportError" in result


def test_execute_python_blocks_import_subprocess():
    result = execute_python("import subprocess; subprocess.run(['ls'])")
    assert "Error" in result or "ImportError" in result


def test_execute_python_blocks_os_alias_escape():
    result = execute_python("import os as _os; print(_os.getcwd())")
    assert "Error" in result or "ImportError" in result


# ---------------------------------------------------------------------------
# execute_python — enforces timeout
# ---------------------------------------------------------------------------


def test_execute_python_timeout():
    result = execute_python("while True: pass", timeout_seconds=1)
    assert "TimeoutError" in result or "timeout" in result.lower()


# ---------------------------------------------------------------------------
# execute_python — structured error on bad input
# ---------------------------------------------------------------------------


def test_execute_python_syntax_error():
    result = execute_python("def broken(:")
    assert "SyntaxError" in result or "Error" in result


def test_execute_python_runtime_error():
    result = execute_python("x = 1 / 0")
    assert "Error" in result or "ZeroDivisionError" in result


# ---------------------------------------------------------------------------
# execute_python — allowed modules work
# ---------------------------------------------------------------------------


def test_execute_python_allows_math():
    result = execute_python("import math; print(math.pi)")
    assert "3.14" in result


def test_execute_python_allows_json():
    result = execute_python("import json; print(json.dumps({'a': 1}))")
    assert '{"a": 1}' in result


def test_execute_python_allows_datetime():
    result = execute_python("import datetime; print(datetime.date.today().year)")
    assert "20" in result  # year starts with "20"


# ---------------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------------


def test_get_current_datetime_is_iso():
    dt = get_current_datetime()
    assert "T" in dt and "+" in dt or "Z" in dt or dt.endswith("+00:00")


def test_create_note_writes_file(tmp_path):
    path = create_note("My Note", "Some content", str(tmp_path / "notes"))
    from pathlib import Path

    p = Path(path)
    assert p.exists()
    assert "My Note" in p.read_text()
    assert "Some content" in p.read_text()


# ---------------------------------------------------------------------------
# calendar handlers (Module 7)
# ---------------------------------------------------------------------------

from datetime import UTC

from core.tools.handlers.calendar import get_upcoming_events, query_events


def _write_ics(path, events_ics: str) -> str:
    """Write a minimal .ics file and return its path string."""
    content = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\n"
        + events_ics
        + "END:VCALENDAR\r\n"
    )
    p = path / "test.ics"
    p.write_bytes(content.encode())
    return str(p)


def _vevent_soon(
    title: str, hours_from_now: float = 2.0, description: str = "", location: str = ""
) -> str:
    from datetime import datetime, timedelta

    start = datetime.now(UTC) + timedelta(hours=hours_from_now)
    end = start + timedelta(hours=1)
    fmt = "%Y%m%dT%H%M%SZ"
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
    lines.append("END:VEVENT\r\n")
    return "\r\n".join(lines)


def test_get_upcoming_events_no_ics_returns_no_events_message(tmp_path):
    with patch("core.tools.handlers.calendar.platform.system", return_value="Linux"):
        result = get_upcoming_events(ics_path=str(tmp_path / "nonexistent.ics"))
    assert "Sin eventos" in result


def test_get_upcoming_events_returns_event_title(tmp_path):
    ics = _write_ics(tmp_path, _vevent_soon("Team standup", location="Zoom"))
    result = get_upcoming_events(ics_path=ics)
    assert "Team standup" in result
    assert "Zoom" in result


def test_get_upcoming_events_includes_description(tmp_path):
    ics = _write_ics(tmp_path, _vevent_soon("Review", description="Sprint retrospective"))
    result = get_upcoming_events(ics_path=ics)
    assert "Sprint retrospective" in result


def test_get_upcoming_events_empty_calendar_says_no_events(tmp_path):
    ics = _write_ics(tmp_path, "")
    with patch("core.tools.handlers.calendar.platform.system", return_value="Linux"):
        result = get_upcoming_events(ics_path=ics)
    assert "Sin eventos" in result


def test_query_events_finds_keyword_in_title(tmp_path):
    ics = _write_ics(tmp_path, _vevent_soon("Doctor appointment"))
    result = query_events("doctor", ics_path=ics, hours_ahead=24)
    assert "Doctor appointment" in result


def test_query_events_finds_keyword_in_description(tmp_path):
    ics = _write_ics(tmp_path, _vevent_soon("Meeting", description="dentist checkup"))
    result = query_events("dentist", ics_path=ics, hours_ahead=24)
    assert "Meeting" in result


def test_query_events_no_match_returns_message(tmp_path):
    ics = _write_ics(tmp_path, _vevent_soon("Team lunch"))
    result = query_events("dentist", ics_path=ics, hours_ahead=24)
    assert "Sin eventos" in result
    assert "dentist" in result


def test_query_events_case_insensitive(tmp_path):
    ics = _write_ics(tmp_path, _vevent_soon("BUDGET Review"))
    result = query_events("budget", ics_path=ics, hours_ahead=24)
    assert "BUDGET Review" in result

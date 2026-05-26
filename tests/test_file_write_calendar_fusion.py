"""Tests for file-write + calendar fusion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from core.agents.file_write_calendar_fusion import (
    is_calendar_backed_file_content,
    try_file_write_calendar_fusion,
)
from core.agents.reminder_intent_resolver import is_reminder_write_query
from core.agents.runtime import AgentRuntime
from core.agents.state_store import AgentStateStore
from core.inference.registry import ProviderRegistry
from tests.test_calendar import _make_ics, _vevent


def test_is_calendar_backed_file_content():
    assert is_calendar_backed_file_content("de los proximos 3 cumpleaños en mi calendario")
    assert not is_calendar_backed_file_content("hola que tal")


def test_calendar_fast_path_skips_file_export_query():
    from core.agents.calendar_fast_path import try_calendar_fast_path

    q = (
        "crea un archivo pruebacalendario.txt con contenido de los proximos "
        "3 cumpleaños en mi calendario"
    )
    assert try_calendar_fast_path(q, ["search_upcoming"]) is None


def test_fusion_birthdays_proximos_four_respects_strict_cap(tmp_path, monkeypatch):
    # Ensure calendar reader uses ICS backend (no osascript on non-mac).
    monkeypatch.setenv("CEREBRO_CALENDAR_APPLE", "0")
    ics = tmp_path / "cal.ics"
    now = datetime.now(UTC)
    # Create multiple birthdays including two on the earliest day.
    events = [
        _vevent("Cumple Gemelo A", now + timedelta(days=10)),
        _vevent("Cumple Gemelo B", now + timedelta(days=10, hours=3)),
    ]
    events.extend(_vevent(f"Cumple Persona {i}", now + timedelta(days=10 + i)) for i in range(1, 6))
    ics.write_bytes(_make_ics(events))
    monkeypatch.setenv("CEREBRO_ICS", str(ics))

    roots = [str(tmp_path)]
    q = "crea un archivo calendarioprueba.txt con los 4 proximos cumpleaños en mi calendario"

    intent = try_file_write_calendar_fusion(
        q,
        ["write_file", "search_upcoming"],
        write_roots=roots,
    )
    assert intent is not None
    assert intent.filename == "calendarioprueba.txt"
    assert intent.filled_from == "calendar"
    assert "mostrando 4" in intent.content


def test_fusion_accepts_calendar_export_without_contenido_keyword(tmp_path):
    roots = [str(tmp_path)]
    q = "crea un archivo calendarioprueba.txt con los 3 proximos cumpleaños en mi calendario"
    calendar_text = (
        "Próximos eventos que coinciden con 'cumple' (mostrando 3 de 27):\n- Cumple Ximena\n"
    )
    with patch(
        "core.agents.file_write_calendar_fusion.fetch_calendar_read_answer",
        return_value=calendar_text,
    ):
        intent = try_file_write_calendar_fusion(
            q,
            ["write_file", "search_upcoming"],
            write_roots=roots,
        )
    assert intent is not None
    assert intent.filename == "calendarioprueba.txt"
    assert intent.filled_from == "calendar"
    assert "Cumple Ximena" in intent.content


def test_fusion_works_without_write_file_on_calendar_profile(tmp_path):
    """Calendar agent on disk may lack write_file until ensure_profiles; runtime widens tools."""
    roots = [str(tmp_path)]
    q = (
        "crea un archivo pruebacalendario.txt con contenido de los proximos "
        "3 cumpleaños en mi calendario"
    )
    calendar_text = "Fecha y hora actual: test\n- Cumple A\n"
    with patch(
        "core.agents.file_write_calendar_fusion.fetch_calendar_read_answer",
        return_value=calendar_text,
    ):
        intent = try_file_write_calendar_fusion(
            q,
            ["search_upcoming", "query_events"],
            write_roots=roots,
        )
    assert intent is not None
    assert "Cumple A" in intent.content
    assert intent.filled_from == "calendar"


def test_user_prompt_is_not_reminder_write():
    q = (
        "crea un archivo pruebacalendario.txt con contenido de los proximos "
        "3 cumpleaños en mi calendario"
    )
    assert not is_reminder_write_query(q)


def test_fusion_uses_fetch_not_blocked_by_export_guard(tmp_path):
    """Regression: export guard in try_calendar_fast_path must not block fusion fetch."""
    q = (
        "crea un archivo pruebacalendario.txt con contenido de los proximos "
        "3 cumpleaños en mi calendario"
    )
    calendar_text = "Próximos eventos que coinciden con 'cumple' (mostrando 3 de 27):\n- Cumple A\n"
    with patch(
        "core.agents.file_write_calendar_fusion.fetch_calendar_read_answer",
        return_value=calendar_text,
    ) as fetch:
        intent = try_file_write_calendar_fusion(
            q,
            ["search_upcoming"],
            write_roots=[str(tmp_path)],
        )
        fetch.assert_called_once()
    assert intent is not None
    assert "Cumple A" in intent.content
    assert intent.filled_from == "calendar"


def test_fusion_prefills_birthdays(tmp_path):
    roots = [str(tmp_path)]
    calendar_text = (
        "Próximos eventos que coinciden con 'cumple' (mostrando 3 de 27):\n"
        "- Cumple Ximena a las 2026-06-02\n"
    )
    query = (
        "crea un archivo pruebacalendario.txt con contenido de los proximos "
        "3 cumpleaños en mi calendario"
    )
    with patch(
        "core.agents.file_write_calendar_fusion.fetch_calendar_read_answer",
        return_value=calendar_text,
    ):
        intent = try_file_write_calendar_fusion(
            query,
            ["write_file", "search_upcoming"],
            write_roots=roots,
        )
    assert intent is not None
    assert intent.filename == "pruebacalendario.txt"
    assert "Cumple Ximena" in intent.content
    assert intent.filled_from == "calendar"
    assert intent.path == str((tmp_path / "pruebacalendario.txt").resolve())


@pytest.mark.asyncio
async def test_runtime_calendar_agent_file_fusion_pending_tool(tmp_path, monkeypatch):
    """calendar-v1 without write_file in profile still queues write via runtime widening."""
    from core.agents.specialized import CALENDAR_TOOLS

    monkeypatch.setenv("CEREBRO_FILES_PATH", str(tmp_path))
    calendar_text = "Fecha y hora actual: test\n- Cumple Ximena\n"
    q = (
        "crea un archivo pruebacalendario.txt con contenido de los proximos "
        "3 cumpleaños en mi calendario"
    )
    store = AgentStateStore(state_dir=str(tmp_path / "state"))
    state = store.load("calendar-v1")
    state.profile.authorized_tools = [t for t in CALENDAR_TOOLS if t != "write_file"]
    store.save(state)

    mock_registry = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(
        spec=ProviderRegistry
    )
    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=__import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(
            _short_term=__import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
        ),
        tool_registry={"write_file": lambda **k: "ok"},
    )
    runtime._context_builder._short_term.push_message = __import__(
        "unittest.mock", fromlist=["MagicMock"]
    ).MagicMock()
    runtime.save_conversation_session = lambda *a, **k: None

    with patch(
        "core.agents.file_write_calendar_fusion.fetch_calendar_read_answer",
        return_value=calendar_text,
    ):
        answer, final = await runtime.run(q, "calendar-v1")

    assert final.pending_tool_name == "write_file"
    assert "Cumple Ximena" in final.pending_tool_args["content"]
    assert "aprobación" in answer.lower() or "aprobacion" in answer.lower()


@pytest.mark.asyncio
async def test_runtime_calendar_file_fusion_pending_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("CEREBRO_FILES_PATH", str(tmp_path))
    calendar_text = "- Cumple Test a las 2026-06-02\n"
    query = (
        "crea un archivo pruebacalendario.txt con contenido de los proximos "
        "3 cumpleaños en mi calendario"
    )

    store = AgentStateStore(state_dir=str(tmp_path / "state"))
    state = store.load("general-v1")
    state.profile.authorized_tools = ["write_file", "search_upcoming"]
    store.save(state)

    mock_registry = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(
        spec=ProviderRegistry
    )
    short_term = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=__import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(
            _short_term=short_term
        ),
        tool_registry={},
    )
    runtime._context_builder._short_term.push_message = __import__(
        "unittest.mock", fromlist=["MagicMock"]
    ).MagicMock()
    runtime.save_conversation_session = lambda *a, **k: None

    with patch(
        "core.agents.file_write_calendar_fusion.fetch_calendar_read_answer",
        return_value=calendar_text,
    ):
        answer, final = await runtime.run(query, "general-v1")

    assert final.pending_tool_name == "write_file"
    assert "Cumple Test" in final.pending_tool_args["content"]
    assert (
        "calendario" in answer.lower()
        or "aprobación" in answer.lower()
        or "aprobacion" in answer.lower()
    )

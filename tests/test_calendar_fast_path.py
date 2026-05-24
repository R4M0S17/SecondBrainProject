"""Tests for calendar fast path — birthdays and upcoming events without LLM JSON."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.calendar_fast_path import try_calendar_fast_path
from core.agents.calendar_reminder_fast_path import try_calendar_reminder_fast_path
from core.agents.runtime import AgentRuntime
from core.agents.specialized import CALENDAR_TOOLS, GENERAL_TOOLS
from core.agents.state_store import AgentStateStore
from core.inference.registry import ProviderRegistry
from tests.test_calendar import _make_ics, _vevent


@pytest.fixture(autouse=True)
def ics_only_calendar(monkeypatch):
    """Avoid slow/blocked osascript during unit tests."""
    monkeypatch.setattr("core.tools.handlers.calendar.platform.system", lambda: "Linux")


def _write_fixture_ics(path, *, meeting_hours: float = 3, birthday_days: float = 45) -> None:
    now = datetime.now(UTC)
    ics = _make_ics(
        [
            _vevent("Team Standup E2E", now + timedelta(hours=meeting_hours)),
            _vevent("Maria cumpleaños party", now + timedelta(days=birthday_days)),
        ]
    )
    path.write_bytes(ics)


def _write_many_birthdays_ics(path) -> None:
    now = datetime.now(UTC)
    base = 10
    events = [
        _vevent("Cumple Gemelo A", now + timedelta(days=base)),
        _vevent("Cumple Gemelo B", now + timedelta(days=base, hours=3)),
    ]
    events.extend(
        _vevent(f"Cumple Persona {i}", now + timedelta(days=base + i)) for i in range(1, 8)
    )
    path.write_bytes(_make_ics(events))


def test_calendar_fast_path_upcoming_events(tmp_path):
    ics = tmp_path / "cal.ics"
    _write_fixture_ics(ics, meeting_hours=2)
    result = try_calendar_fast_path(
        "¿Qué tengo en el calendario en las próximas 24 horas?",
        GENERAL_TOOLS,
        ics_path=str(ics),
    )
    assert result is not None
    assert "Team Standup E2E" in result


def test_calendar_fast_path_birthday_caps_at_three(tmp_path):
    ics = tmp_path / "cal.ics"
    now = datetime.now(UTC)
    events = [_vevent(f"Cumple Persona {i}", now + timedelta(days=10 + i)) for i in range(8)]
    ics.write_bytes(_make_ics(events))
    result = try_calendar_fast_path(
        "¿Cuál es mi próximo cumpleaños?",
        GENERAL_TOOLS,
        ics_path=str(ics),
    )
    assert result is not None
    assert result.count("\n- ") == 3
    assert "mostrando 3 de 8" in result


def test_calendar_fast_path_birthday_solo_uno(tmp_path):
    ics = tmp_path / "cal.ics"
    _write_many_birthdays_ics(ics)
    result = try_calendar_fast_path(
        "cual es el proximo cumpleaños en mi calendario? dime solo uno",
        GENERAL_TOOLS,
        ics_path=str(ics),
    )
    assert result is not None
    assert result.count("\n- ") == 1
    assert "Próximo evento" in result


def test_calendar_fast_path_birthday_same_day_bundle(tmp_path):
    ics = tmp_path / "cal.ics"
    _write_many_birthdays_ics(ics)
    result = try_calendar_fast_path(
        "¿Hay cumpleaños próximos?",
        GENERAL_TOOLS,
        ics_path=str(ics),
    )
    assert result is not None
    assert "Gemelo A" in result
    assert "Gemelo B" in result
    assert "Persona 1" not in result


def test_calendar_fast_path_birthday_search(tmp_path):
    ics = tmp_path / "cal.ics"
    _write_fixture_ics(ics, birthday_days=60)
    result = try_calendar_fast_path(
        "¿Hay algún cumpleaños próximo?",
        GENERAL_TOOLS,
        ics_path=str(ics),
    )
    assert result is not None
    assert "Maria cumpleaños" in result or "cumple" in result.lower()


def test_calendar_fast_path_english_next_event(tmp_path):
    ics = tmp_path / "cal.ics"
    _write_fixture_ics(ics)
    result = try_calendar_fast_path(
        "What do I have on my calendar today?",
        CALENDAR_TOOLS,
        ics_path=str(ics),
    )
    assert result is not None
    assert "Eventos" in result or "Standup" in result


def test_calendar_fast_path_skips_without_tools():
    assert try_calendar_fast_path("próximo evento", ["read_file"]) is None


def test_calendar_fast_path_next_event_single(tmp_path):
    ics = tmp_path / "cal.ics"
    now = datetime.now(UTC)
    ics.write_bytes(
        _make_ics(
            [
                _vevent("First meeting", now + timedelta(hours=3)),
                _vevent("Second meeting", now + timedelta(hours=12)),
            ]
        )
    )
    result = try_calendar_fast_path(
        "cual es el proximo evento en el calendario?",
        GENERAL_TOOLS,
        ics_path=str(ics),
    )
    assert result is not None
    assert "Próximo evento" in result
    assert "First meeting" in result
    assert "Second meeting" not in result


def test_calendar_fast_path_list_events_48h(tmp_path):
    ics = tmp_path / "cal.ics"
    _write_fixture_ics(ics, meeting_hours=12)
    result = try_calendar_fast_path(
        "Lista eventos próximas 48 horas",
        GENERAL_TOOLS,
        ics_path=str(ics),
    )
    assert result is not None
    assert "Standup" in result


@pytest.mark.asyncio
async def test_runtime_calendar_fast_path_bypasses_llm(tmp_path):
    ics = tmp_path / "cal.ics"
    _write_fixture_ics(ics)

    agent_id = "calendar-v1"
    store = AgentStateStore(state_dir=str(tmp_path / "state"))
    state = store.load(agent_id)
    state.profile.authorized_tools = CALENDAR_TOOLS
    store.save(state)

    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(return_value='{"action":"answer","answer":"parse fail"}')
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    mock_builder = MagicMock()
    mock_builder._short_term = MagicMock()
    mock_builder._short_term.push_message = MagicMock()

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=mock_builder,
        tool_registry={},
    )

    answer, _ = await runtime.run(
        "¿Cuál es el próximo cumpleaños?",
        agent_id,
    )
    mock_chat.complete.assert_not_called()
    assert "Maria cumpleaños" in answer or "cumple" in answer.lower() or "Sin eventos" in answer


@pytest.mark.asyncio
async def test_api_query_calendar_fast_path(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from core.agents.conversation_store import ConversationStore
    from core.observability.response_meta import MetricsCollector
    from ui.tray.server import app, app_state

    ics = tmp_path / "e2e.ics"
    _write_fixture_ics(ics)
    monkeypatch.setenv("CEREBRO_ICS", str(ics))

    store = AgentStateStore(state_dir=str(tmp_path / "agent_state"))
    state = store.load("general-v1")
    state.profile.authorized_tools = GENERAL_TOOLS
    store.save(state)

    mock_chat = MagicMock()
    mock_chat.model_id = MagicMock(return_value="test-model")
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)
    mock_registry.primary_name = "mock"

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=MagicMock(_short_term=MagicMock()),
        tool_registry={},
    )
    runtime._context_builder._short_term.push_message = MagicMock()
    runtime.save_conversation_session = MagicMock()

    app_state.runtime = runtime
    app_state.conv_store = ConversationStore(str(tmp_path / "convs"))
    app_state.metrics = MetricsCollector()
    app_state.provider_registry = mock_registry

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/query",
            json={
                "question": "Lista eventos próximas 48 horas",
                "agent": "general-v1",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "calendar_fast_path" in body.get("metadata", {}).get("warnings", [])
    assert "Standup" in body["answer"] or "Eventos" in body["answer"]
    mock_chat.complete.assert_not_called()


def test_calendar_reminder_fast_path_add(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_add(title: str, when: str, notes: str = "") -> str:
        calls.append((title, when))
        return f"ok:{title}"

    monkeypatch.setattr(
        "core.agents.calendar_reminder_fast_path.add_reminder",
        fake_add,
    )
    result = try_calendar_reminder_fast_path(
        'crea un recordatorio mañana a las 3pm con nombre "pruebaCalendario"',
        GENERAL_TOOLS,
    )
    assert result == "ok:pruebaCalendario"
    assert calls == [("pruebaCalendario", "mañana a las 3pm")]


def test_calendar_reminder_fast_path_delete(monkeypatch):
    monkeypatch.setattr(
        "core.agents.calendar_reminder_fast_path.delete_reminder",
        lambda title: f"deleted:{title}",
    )
    result = try_calendar_reminder_fast_path(
        "borra el recordatorio pruebaCalendario",
        GENERAL_TOOLS,
    )
    assert result == "deleted:pruebaCalendario"


@pytest.mark.asyncio
async def test_runtime_reminder_fast_path_bypasses_llm(tmp_path, monkeypatch):
    _write_fixture_ics(tmp_path / "cal.ics")

    monkeypatch.setattr(
        "core.agents.calendar_reminder_fast_path.add_reminder",
        lambda title, when, notes="": f"Added reminder '{title}' due {when}.",
    )

    agent_id = "general-v1"
    store = AgentStateStore(state_dir=str(tmp_path / "state"))
    state = store.load(agent_id)
    state.profile.authorized_tools = GENERAL_TOOLS
    store.save(state)

    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(return_value='{"action":"answer","answer":"parse fail"}')
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    mock_builder = MagicMock()
    mock_builder._short_term = MagicMock()
    mock_builder._short_term.push_message = MagicMock()

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=mock_builder,
        tool_registry={},
    )

    answer, _ = await runtime.run(
        'crea un recordatorio mañana a las 3pm con nombre "pruebaCalendario"',
        agent_id,
    )
    mock_chat.complete.assert_not_called()
    assert "pruebaCalendario" in answer

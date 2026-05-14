"""Phase 8.5 — Calendar query E2E via FastAPI."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from integrations.calendar_reader import BackendResult, CalendarEvent, CalendarReader
from tests.test_fix_cerebro.conftest import install_runtime_for_query_e2e, make_stub_chat_complete


def _fake_event() -> CalendarEvent:
    t0 = datetime(2026, 6, 15, 14, 0, tzinfo=UTC)
    return CalendarEvent(title="Fake Standup Phase8", start=t0, end=t0 + timedelta(hours=1))


def _patch_calendar_v2_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def _v2(self: CalendarReader, hours_ahead: int = 24) -> BackendResult:
        return BackendResult(events=[_fake_event()], status="ok")

    monkeypatch.setattr(CalendarReader, "get_upcoming_events_v2", _v2)


@pytest.mark.asyncio
async def test_query_calendar_tool_and_answer_mention_event(api_client, tmp_path, monkeypatch):
    _patch_calendar_v2_ok(monkeypatch)
    mock_chat = make_stub_chat_complete(
        [
            '{"action": "tool", "tool": "get_upcoming_events", "args": {"hours_ahead": 24}}',
            '{"action": "answer", "answer": "Tu próximo evento es Fake Standup Phase8."}',
        ]
    )
    install_runtime_for_query_e2e(tmp_path, mock_chat)

    async with api_client as c:
        resp = await c.post(
            "/api/query",
            json={"question": "¿Cuál es mi próximo evento?", "agent": "general-v1"},
        )
    assert resp.status_code == 200
    data = resp.json()
    names = [t["name"] for t in data["metadata"]["tools_called"]]
    assert "get_upcoming_events" in names
    assert "Fake Standup Phase8" in data["answer"]


@pytest.mark.asyncio
async def test_query_calendar_permission_denied_message(api_client, tmp_path, monkeypatch):
    def _v2_denied(self: CalendarReader, hours_ahead: int = 24) -> BackendResult:
        return BackendResult(events=[], status="permission_denied", detail="denied")

    monkeypatch.setattr(CalendarReader, "get_upcoming_events_v2", _v2_denied)

    mock_chat = make_stub_chat_complete(
        [
            '{"action": "tool", "tool": "get_upcoming_events", "args": {"hours_ahead": 24}}',
            (
                '{"action": "answer", "answer": "No tengo permiso para leer Apple Calendar. '
                'Abre Ajustes del sistema → Privacidad y seguridad → Automatización."}'
            ),
        ]
    )
    install_runtime_for_query_e2e(tmp_path, mock_chat)

    async with api_client as c:
        resp = await c.post(
            "/api/query",
            json={"question": "eventos", "agent": "general-v1"},
        )
    assert resp.status_code == 200
    answer = resp.json()["answer"]
    assert "Ajustes del sistema" in answer or "Automatización" in answer

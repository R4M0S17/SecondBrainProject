"""Tests for the dedicated fast-path router."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.agents.fast_path_router import FastPathRouter
from core.agents.file_write_fast_path import FileWriteIntent
from core.agents.reminder_intent_resolver import ReminderIntent
from core.agents.state_store import AgentProfile, AgentState


def _make_state(*, authorized_tools: list[str] | None = None) -> AgentState:
    now = "2026-05-26T22:59:26.552-04:00"
    return AgentState(
        profile=AgentProfile(
            id="general-v1",
            name="general-v1",
            domain_tags=["general"],
            authorized_tools=authorized_tools or [],
            preferences={},
            created_at=now,
            updated_at=now,
        ),
        session_summary="",
        working_memory={},
        tool_trace=[],
        semantic_memory_refs=[],
        execution_count=0,
        last_active=now,
    )


@pytest.mark.asyncio
async def test_router_uses_canonical_order_and_short_circuits(monkeypatch):
    from core.agents import fast_path_router as module

    calls: list[str] = []

    monkeypatch.setattr(FastPathRouter, "_try_time_date", lambda *a, **kw: None)
    monkeypatch.setattr(FastPathRouter, "_try_config_read", lambda *a, **kw: None)
    monkeypatch.setattr(FastPathRouter, "_try_url_open", lambda *a, **kw: None)
    monkeypatch.setattr(
        module,
        "try_pure_math_fast_path",
        lambda *args, **kwargs: calls.append("math") or None,
    )
    monkeypatch.setattr(
        module,
        "try_file_write_calendar_fusion",
        lambda *args, **kwargs: calls.append("file_write_fusion") or None,
    )
    monkeypatch.setattr(
        module,
        "try_file_write_fast_path",
        lambda *args, **kwargs: calls.append("file_write") or None,
    )
    monkeypatch.setattr(
        module, "is_reminder_write_query", lambda _query: calls.append("reminder_gate") or True
    )

    async def fake_extract(*args, **kwargs):
        calls.append("reminder_extract")
        return ReminderIntent(action="none")

    monkeypatch.setattr(module, "extract_reminder_intent", fake_extract)
    monkeypatch.setattr(
        module,
        "heuristic_parse_reminder",
        lambda *args, **kwargs: calls.append("reminder_heuristic") or None,
    )
    monkeypatch.setattr(
        module,
        "try_calendar_fast_path",
        lambda *args, **kwargs: calls.append("calendar") or "calendar-answer",
    )
    monkeypatch.setattr(
        module,
        "try_file_search_fast_path",
        lambda *args, **kwargs: calls.append("file_search") or "search-answer",
    )

    registry = MagicMock()
    router = FastPathRouter(registry, {})
    result = await router.try_all("cualquier cosa", _make_state())

    assert result is not None
    assert result.kind == "calendar_read"
    assert result.answer == "calendar-answer"
    assert calls == [
        "math",
        "file_write_fusion",
        "file_write",
        "reminder_gate",
        "reminder_extract",
        "reminder_heuristic",
        "calendar",
    ]


@pytest.mark.asyncio
async def test_router_generates_spec_file_content(monkeypatch):
    from core.agents import fast_path_router as module

    monkeypatch.setattr(module, "try_pure_math_fast_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "try_file_write_calendar_fusion", lambda *args, **kwargs: None)

    intent = FileWriteIntent(
        path="/tmp/report.txt",
        content="describe this",
        filename="report.txt",
        content_source="spec",
        content_spec="describe this",
    )
    monkeypatch.setattr(module, "try_file_write_fast_path", lambda *args, **kwargs: intent)
    monkeypatch.setattr(module, "try_calendar_fast_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "try_file_search_fast_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "is_reminder_write_query", lambda _query: False)

    async def fake_extract(*args, **kwargs):
        return None

    monkeypatch.setattr(module, "extract_reminder_intent", fake_extract)

    registry = MagicMock()
    registry.select_for_task.return_value = "primary"
    registry.get_chat.return_value = MagicMock()

    async def fake_generate_file_content(**kwargs):
        return "generated body"

    monkeypatch.setattr(module, "generate_file_content", fake_generate_file_content)

    router = FastPathRouter(registry, {"write_file": object()})
    result = await router.try_all("crea un archivo report.txt con una spec", _make_state())

    assert result is not None
    assert result.kind == "file_write"
    assert result.file_write_intent is not None
    assert result.file_write_intent.content == "generated body"
    assert "file_write_content_generated" in result.warnings
    registry.select_for_task.assert_called_once()
    registry.get_chat.assert_called_once_with("primary")


@pytest.mark.asyncio
async def test_router_intent_rag_query_runs_only_file_search(monkeypatch):
    """RAG_QUERY intent skips all routes except file search."""
    from core.agents import fast_path_router as module

    calls: list[str] = []

    monkeypatch.setattr(
        FastPathRouter, "_try_time_date", lambda *a, **kw: calls.append("time_date") or None
    )
    monkeypatch.setattr(
        FastPathRouter, "_try_config_read", lambda *a, **kw: calls.append("config_read") or None
    )
    monkeypatch.setattr(
        FastPathRouter, "_try_url_open", lambda *a, **kw: calls.append("url_open") or None
    )
    monkeypatch.setattr(
        module, "try_pure_math_fast_path", lambda *a, **kw: calls.append("math") or None
    )
    monkeypatch.setattr(module, "try_file_write_calendar_fusion", lambda *a, **kw: None)
    monkeypatch.setattr(module, "try_file_write_fast_path", lambda *a, **kw: None)
    monkeypatch.setattr(
        module, "is_reminder_write_query", lambda _q: calls.append("reminder") or False
    )
    monkeypatch.setattr(
        module, "try_calendar_fast_path", lambda *a, **kw: calls.append("calendar") or None
    )
    monkeypatch.setattr(
        module,
        "try_file_search_fast_path",
        lambda *a, **kw: calls.append("file_search") or "search-hit",
    )

    registry = MagicMock()
    router = FastPathRouter(registry, {})
    result = await router.try_all("cualquier consulta", _make_state(), intent="RAG_QUERY")

    assert result is not None
    assert result.kind == "file_search"
    assert result.answer == "search-hit"
    assert calls == ["file_search"], f"Expected only file_search, got {calls}"


@pytest.mark.asyncio
async def test_router_intent_agent_action_skips_time_and_config(monkeypatch):
    """AGENT_ACTION intent skips time/date and config read."""
    from core.agents import fast_path_router as module

    calls: list[str] = []

    monkeypatch.setattr(
        FastPathRouter, "_try_time_date", lambda *a, **kw: calls.append("time_date") or None
    )
    monkeypatch.setattr(
        FastPathRouter, "_try_config_read", lambda *a, **kw: calls.append("config_read") or None
    )
    monkeypatch.setattr(
        FastPathRouter, "_try_url_open", lambda *a, **kw: calls.append("url_open") or None
    )
    monkeypatch.setattr(
        module, "try_pure_math_fast_path", lambda *a, **kw: calls.append("math") or None
    )
    monkeypatch.setattr(module, "try_file_write_calendar_fusion", lambda *a, **kw: None)
    monkeypatch.setattr(
        module, "try_file_write_fast_path", lambda *a, **kw: calls.append("file_write") or None
    )
    monkeypatch.setattr(
        module, "is_reminder_write_query", lambda _q: calls.append("reminder_gate") or True
    )

    async def fake_extract(*a, **kw):
        calls.append("reminder_extract")
        from core.agents.reminder_intent_resolver import ReminderIntent

        return ReminderIntent(action="none")

    monkeypatch.setattr(module, "extract_reminder_intent", fake_extract)
    monkeypatch.setattr(
        module,
        "heuristic_parse_reminder",
        lambda *a, **kw: calls.append("reminder_heuristic") or None,
    )
    monkeypatch.setattr(
        module,
        "try_calendar_fast_path",
        lambda *a, **kw: calls.append("calendar") or "calendar-answer",
    )
    monkeypatch.setattr(FastPathRouter, "_try_calendar_write", lambda *a, **kw: None)
    monkeypatch.setattr(
        module, "try_file_search_fast_path", lambda *a, **kw: calls.append("file_search") or None
    )

    registry = MagicMock()
    router = FastPathRouter(registry, {})
    result = await router.try_all("cualquier consulta", _make_state(), intent="AGENT_ACTION")

    assert result is not None
    assert result.kind == "calendar_read"
    assert "time_date" not in calls, f"time_date should be skipped for AGENT_ACTION, got {calls}"
    assert (
        "config_read" not in calls
    ), f"config_read should be skipped for AGENT_ACTION, got {calls}"
    assert "math" not in calls, f"math should be skipped for AGENT_ACTION, got {calls}"
    assert "url_open" in calls, f"url_open should be in calls for AGENT_ACTION, got {calls}"
    assert "calendar" in calls, f"calendar should be in calls for AGENT_ACTION, got {calls}"


@pytest.mark.asyncio
async def test_router_intent_config_runs_only_config_read(monkeypatch):
    """CONFIG intent runs only config read route."""
    from core.agents import fast_path_router as module
    from core.agents.fast_path_router import FastPathResult

    calls: list[str] = []

    monkeypatch.setattr(
        FastPathRouter, "_try_time_date", lambda *a, **kw: calls.append("time_date") or None
    )
    monkeypatch.setattr(
        FastPathRouter,
        "_try_config_read",
        lambda *a, **kw: calls.append("config_read")
        or FastPathResult(kind="config_read", answer="config-hit"),
    )
    monkeypatch.setattr(
        FastPathRouter, "_try_url_open", lambda *a, **kw: calls.append("url_open") or None
    )
    monkeypatch.setattr(
        module, "try_pure_math_fast_path", lambda *a, **kw: calls.append("math") or None
    )

    registry = MagicMock()
    router = FastPathRouter(registry, {})
    result = await router.try_all("cualquier consulta", _make_state(), intent="CONFIG")

    assert result is not None
    assert result.kind == "config_read"
    assert result.answer == "config-hit"
    assert calls == ["config_read"], f"Expected only config_read, got {calls}"


@pytest.mark.asyncio
async def test_router_intent_none_runs_full_canonical_order(monkeypatch):
    """intent=None (default) preserves full canonical order."""
    from core.agents import fast_path_router as module

    calls: list[str] = []

    monkeypatch.setattr(
        FastPathRouter, "_try_time_date", lambda *a, **kw: calls.append("time_date") or None
    )
    monkeypatch.setattr(
        FastPathRouter, "_try_config_read", lambda *a, **kw: calls.append("config_read") or None
    )
    monkeypatch.setattr(
        FastPathRouter, "_try_url_open", lambda *a, **kw: calls.append("url_open") or None
    )
    monkeypatch.setattr(
        module, "try_pure_math_fast_path", lambda *a, **kw: calls.append("math") or "math-hit"
    )

    registry = MagicMock()
    router = FastPathRouter(registry, {})
    result = await router.try_all("cualquier consulta", _make_state(), intent=None)

    assert result is not None
    assert result.kind == "math"
    assert result.answer == "math-hit"
    assert calls[:4] == [
        "time_date",
        "config_read",
        "url_open",
        "math",
    ], f"Expected full canonical order, got {calls}"

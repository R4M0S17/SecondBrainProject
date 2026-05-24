"""Regression tests for Module 4 — date/time correctness in the agent runtime."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from core.agents.runtime import (
    _build_stream_system_prompt,
    _build_system_prompt,
    _date_preamble,
    _now_human,
)
from core.agents.state_store import AgentProfile, AgentState
from core.memory.context_builder import AssembledContext


def _empty_context() -> AssembledContext:
    return AssembledContext(
        session_history=[],
        retrieved_memory=[],
        retrieved_documents=[],
        agent_summary="",
        total_tokens_estimated=0,
        sources_used=[],
    )


def _minimal_state() -> AgentState:
    now = datetime.now(ZoneInfo("UTC")).isoformat()
    return AgentState(
        profile=AgentProfile(
            id="t",
            name="Test",
            domain_tags=[],
            authorized_tools=[],
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


def test_date_preamble_contains_current_year_and_both_time_forms() -> None:
    p = _date_preamble()
    assert str(datetime.now().year) in p
    t = _now_human()
    assert t["date"] in p
    assert t["time_12h"] in p
    assert f"({t['time_24h']})" in p
    assert t["tz"] in p
    assert "repeat this exact time" in p.lower()


def test_date_preamble_english_system_marker() -> None:
    p = _date_preamble()
    assert p.startswith("[System context:")
    assert "Today is" in p


def test_build_system_and_stream_prompts_share_same_datetime_line() -> None:
    state = _minimal_state()
    context = _empty_context()
    fixed = datetime(2026, 5, 19, 16, 7, 0, tzinfo=ZoneInfo("America/New_York"))

    with patch("core.agents.runtime._now_human") as mock_human:
        mock_human.return_value = _now_human(fixed)
        system = _build_system_prompt(state, context, [])
        stream = _build_stream_system_prompt(state, context)

    assert "Tuesday, May 19, 2026" in system
    assert "04:07 PM (16:07)" in system
    assert system.split("FECHA Y HORA ACTUAL: ", 1)[1].split(" — AÑO", 1)[0] == (
        stream.split("FECHA Y HORA ACTUAL: ", 1)[1].split(" — AÑO", 1)[0]
    )


def test_build_system_prompt_uses_local_timezone() -> None:
    """System prompt must include local %Z abbreviation, not a hardcoded UTC literal."""
    state = _minimal_state()
    context = _empty_context()
    local_dt = datetime(2026, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("America/Mexico_City"))
    mock_now = MagicMock()
    mock_now.astimezone.return_value = local_dt

    with patch("core.agents.runtime.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        prompt = _build_system_prompt(state, context, [])

    assert "CST" in prompt
    assert " UTC" not in prompt

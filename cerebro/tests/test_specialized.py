"""Tests for Module 8 — Specialized Agents."""

from __future__ import annotations

import tempfile

import pytest

from core.agents.specialized import (
    ACADEMIC_AGENT_ID,
    ACADEMIC_TOOLS,
    CALENDAR_AGENT_ID,
    CALENDAR_TOOLS,
    CODE_AGENT_ID,
    CODE_TOOLS,
    GENERAL_AGENT_ID,
    GENERAL_TOOLS,
    SpecializedAgentRouter,
    make_academic_profile,
    make_calendar_profile,
    make_code_profile,
    make_general_profile,
)
from core.agents.state_store import AgentStateStore

# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------


def test_academic_prefix_routes_correctly():
    router = SpecializedAgentRouter()
    result = router.route("/academic resume mi clase de física")
    assert result.agent_id == ACADEMIC_AGENT_ID
    assert result.query == "resume mi clase de física"


def test_code_prefix_routes_correctly():
    router = SpecializedAgentRouter()
    result = router.route("/code cómo funciona esta función?")
    assert result.agent_id == CODE_AGENT_ID
    assert result.query == "cómo funciona esta función?"


def test_no_prefix_routes_to_general():
    router = SpecializedAgentRouter()
    result = router.route("¿cuál es el clima hoy?")
    assert result.agent_id == GENERAL_AGENT_ID
    assert result.query == "¿cuál es el clima hoy?"


def test_academic_prefix_alone_routes_to_academic():
    router = SpecializedAgentRouter()
    result = router.route("/academic")
    assert result.agent_id == ACADEMIC_AGENT_ID


def test_code_prefix_leading_whitespace_ignored():
    router = SpecializedAgentRouter()
    result = router.route("  /code   refactoriza esto  ")
    assert result.agent_id == CODE_AGENT_ID
    assert result.query == "refactoriza esto"


def test_unknown_slash_prefix_uses_keyword_routing():
    # /foo is not a registered prefix — keyword "schedule" → calendar
    router = SpecializedAgentRouter()
    result = router.route("/schedule meeting")
    assert result.agent_id == CALENDAR_AGENT_ID


def test_unknown_slash_without_keywords_routes_to_general():
    router = SpecializedAgentRouter()
    result = router.route("/foo something random")
    assert result.agent_id == GENERAL_AGENT_ID


def test_keyword_routes_calendar_create_event():
    router = SpecializedAgentRouter()
    result = router.route(
        "Crea un evento llamado Cerebro smoke test mañana a las 4pm por 30 minutos"
    )
    assert result.agent_id == CALENDAR_AGENT_ID


def test_keyword_routes_code_write_file():
    router = SpecializedAgentRouter()
    result = router.route("escribe un archivo test.txt con la palabra hola")
    assert result.agent_id == CODE_AGENT_ID


def test_keyword_routes_academic_pdf():
    router = SpecializedAgentRouter()
    result = router.route("Resume este pdf de física")
    assert result.agent_id == ACADEMIC_AGENT_ID


# ---------------------------------------------------------------------------
# Profile factory tests
# ---------------------------------------------------------------------------


def test_academic_profile_has_correct_id_and_tools():
    profile = make_academic_profile()
    assert profile.id == ACADEMIC_AGENT_ID
    assert set(profile.authorized_tools) == set(ACADEMIC_TOOLS)
    assert "search_documents" in profile.authorized_tools
    assert "create_note" in profile.authorized_tools
    # code-only tool must NOT be in academic profile
    assert "execute_python" not in profile.authorized_tools


def test_code_profile_has_correct_id_and_tools():
    profile = make_code_profile()
    assert profile.id == CODE_AGENT_ID
    assert set(profile.authorized_tools) == set(CODE_TOOLS)
    assert "execute_python" in profile.authorized_tools
    assert "write_file" in profile.authorized_tools
    assert "create_note" not in profile.authorized_tools


def test_general_profile_has_expected_tools():
    profile = make_general_profile()
    assert profile.id == GENERAL_AGENT_ID
    assert set(profile.authorized_tools) == set(GENERAL_TOOLS)
    assert "get_upcoming_events" in profile.authorized_tools
    assert "execute_python" not in profile.authorized_tools
    assert "write_file" in profile.authorized_tools
    assert "read_file" in profile.authorized_tools


def test_general_profile_can_call_create_calendar_event():
    assert "create_calendar_event" in make_general_profile().authorized_tools


def test_general_can_write_file():
    assert "write_file" in make_general_profile().authorized_tools


def test_code_can_write_file():
    assert "write_file" in make_code_profile().authorized_tools


def test_profiles_have_non_empty_instructions():
    for factory in (make_academic_profile, make_code_profile, make_general_profile):
        profile = factory()
        assert "instructions" in profile.preferences
        assert len(profile.preferences["instructions"]) > 20


# ---------------------------------------------------------------------------
# ensure_profiles tests
# ---------------------------------------------------------------------------


def test_ensure_profiles_seeds_all_three_when_store_empty():
    with tempfile.TemporaryDirectory() as tmp:
        store = AgentStateStore(tmp)
        router = SpecializedAgentRouter()

        assert store.list_agents() == []
        router.ensure_profiles(store)

        ids = {p.id for p in store.list_agents()}
        assert ACADEMIC_AGENT_ID in ids
        assert CODE_AGENT_ID in ids
        assert GENERAL_AGENT_ID in ids


def test_ensure_profiles_does_not_overwrite_existing():
    with tempfile.TemporaryDirectory() as tmp:
        store = AgentStateStore(tmp)
        router = SpecializedAgentRouter()

        # Seed once, then modify the academic profile
        router.ensure_profiles(store)
        state = store.load(ACADEMIC_AGENT_ID)
        state.session_summary = "persisted summary"
        store.save(state)

        # Calling ensure_profiles again must not reset the existing profile
        router.ensure_profiles(store)
        reloaded = store.load(ACADEMIC_AGENT_ID)
        assert reloaded.session_summary == "persisted summary"


def test_ensure_profiles_partial_seeds_only_missing():
    with tempfile.TemporaryDirectory() as tmp:
        store = AgentStateStore(tmp)
        router = SpecializedAgentRouter()

        # Manually seed only the academic profile
        from core.agents.state_store import AgentState

        profile = make_academic_profile()
        store.save(
            AgentState(
                profile=profile,
                session_summary="already there",
                working_memory={},
                tool_trace=[],
                semantic_memory_refs=[],
                execution_count=0,
                last_active=profile.created_at,
            )
        )

        router.ensure_profiles(store)

        # All four profiles should now exist
        ids = {p.id for p in store.list_agents()}
        assert ids == {ACADEMIC_AGENT_ID, CALENDAR_AGENT_ID, CODE_AGENT_ID, GENERAL_AGENT_ID}

        # Academic profile must retain its original summary
        assert store.load(ACADEMIC_AGENT_ID).session_summary == "already there"


# ---------------------------------------------------------------------------
# Calendar profile tests (Module 7)
# ---------------------------------------------------------------------------


def test_calendar_profile_has_correct_id_and_tools():
    profile = make_calendar_profile()
    assert profile.id == CALENDAR_AGENT_ID
    assert set(profile.authorized_tools) == set(CALENDAR_TOOLS)
    assert "get_upcoming_events" in profile.authorized_tools
    assert "query_events" in profile.authorized_tools
    assert "search_documents" in profile.authorized_tools
    assert "execute_python" not in profile.authorized_tools


def test_calendar_profile_has_non_empty_instructions():
    profile = make_calendar_profile()
    assert "instructions" in profile.preferences
    assert len(profile.preferences["instructions"]) > 20


def test_calendar_instructions_under_prompt_budget():
    instructions = make_calendar_profile().preferences["instructions"]
    assert len(instructions) < 1500
    assert "get_upcoming_events" in instructions
    assert "create_calendar_event" in instructions
    assert instructions.count('{"action": "tool"') == 2


def test_calendar_prefix_routes_correctly():
    router = SpecializedAgentRouter()
    result = router.route("/calendar ¿qué tengo mañana?")
    assert result.agent_id == CALENDAR_AGENT_ID
    assert result.query == "¿qué tengo mañana?"


def test_calendar_prefix_alone_routes_to_calendar():
    router = SpecializedAgentRouter()
    result = router.route("/calendar")
    assert result.agent_id == CALENDAR_AGENT_ID


def test_ensure_profiles_seeds_all_four_when_store_empty():
    with tempfile.TemporaryDirectory() as tmp:
        store = AgentStateStore(tmp)
        router = SpecializedAgentRouter()

        assert store.list_agents() == []
        router.ensure_profiles(store)

        ids = {p.id for p in store.list_agents()}
        assert ACADEMIC_AGENT_ID in ids
        assert CALENDAR_AGENT_ID in ids
        assert CODE_AGENT_ID in ids
        assert GENERAL_AGENT_ID in ids


# ---------------------------------------------------------------------------
# route_with_llm tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_with_llm_prefix_wins_without_calling_llm():
    """Prefix match short-circuits — LLMRouter must not be called."""
    from unittest.mock import AsyncMock

    mock_llm = AsyncMock()
    router = SpecializedAgentRouter(llm_router=mock_llm)
    result = await router.route_with_llm("/code debug this")
    assert result.agent_id == CODE_AGENT_ID
    assert result.query == "debug this"
    mock_llm.classify.assert_not_called()


@pytest.mark.asyncio
async def test_route_with_llm_uses_llm_when_no_prefix():
    """No prefix → LLMRouter.classify is called and its category is used."""
    from unittest.mock import AsyncMock

    mock_llm = AsyncMock()
    mock_llm.classify = AsyncMock(return_value="academic")
    router = SpecializedAgentRouter(llm_router=mock_llm)
    result = await router.route_with_llm("explain quantum entanglement")
    assert result.agent_id == ACADEMIC_AGENT_ID
    mock_llm.classify.assert_called_once_with("explain quantum entanglement")


@pytest.mark.asyncio
async def test_route_with_llm_maps_all_categories():
    """Each category returned by the LLM maps to the correct agent."""
    from unittest.mock import AsyncMock

    expected = {
        "code": CODE_AGENT_ID,
        "calendar": CALENDAR_AGENT_ID,
        "academic": ACADEMIC_AGENT_ID,
        "general": GENERAL_AGENT_ID,
    }
    for category, agent_id in expected.items():
        mock_llm = AsyncMock()
        mock_llm.classify = AsyncMock(return_value=category)
        router = SpecializedAgentRouter(llm_router=mock_llm)
        result = await router.route_with_llm("some query")
        assert result.agent_id == agent_id, f"category={category!r} should map to {agent_id!r}"


@pytest.mark.asyncio
async def test_route_with_llm_falls_back_to_general_without_llm_router():
    """If no LLMRouter is provided, unrecognised input defaults to general."""
    router = SpecializedAgentRouter(llm_router=None)
    result = await router.route_with_llm("some random question")
    assert result.agent_id == GENERAL_AGENT_ID


@pytest.mark.asyncio
async def test_route_with_llm_keyword_skips_slow_llm():
    from unittest.mock import AsyncMock

    mock_llm = AsyncMock()
    router = SpecializedAgentRouter(llm_router=mock_llm)
    result = await router.route_with_llm("¿Qué tengo en el calendario mañana?")
    assert result.agent_id == CALENDAR_AGENT_ID
    mock_llm.classify.assert_not_called()


@pytest.mark.asyncio
async def test_route_with_llm_prefix_takes_priority_over_llm_calendar():
    """/calendar prefix wins even when the LLM would have said something different."""
    from unittest.mock import AsyncMock

    mock_llm = AsyncMock()
    mock_llm.classify = AsyncMock(return_value="code")
    router = SpecializedAgentRouter(llm_router=mock_llm)
    result = await router.route_with_llm("/calendar what's tomorrow?")
    assert result.agent_id == CALENDAR_AGENT_ID
    mock_llm.classify.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 4 — Updated tool authorization lists
# ---------------------------------------------------------------------------


def test_code_profile_includes_phase2_tools():
    profile = make_code_profile()
    assert "create_python_file" in profile.authorized_tools
    assert "run_script" in profile.authorized_tools
    assert "delete_file" in profile.authorized_tools
    assert "list_directory" in profile.authorized_tools
    assert "search_files" in profile.authorized_tools


def test_academic_profile_includes_phase3_tools():
    profile = make_academic_profile()
    assert "search_notes" in profile.authorized_tools
    assert "spotlight_search" in profile.authorized_tools
    assert "list_directory" in profile.authorized_tools
    assert "search_files" in profile.authorized_tools


def test_calendar_profile_includes_notification_tool():
    profile = make_calendar_profile()
    assert "send_notification" in profile.authorized_tools

"""Tests for A2 — Persistent Agent Runtime."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agents.runtime import AgentRuntime
from core.agents.state_store import (
    AgentProfile,
    AgentState,
    AgentStateStore,
    ToolCall,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(agent_id: str = "test-agent") -> AgentProfile:
    now = datetime.now(UTC).isoformat()
    return AgentProfile(
        id=agent_id,
        name=agent_id,
        domain_tags=["general"],
        authorized_tools=[],
        preferences={"instructions": "Sé conciso."},
        created_at=now,
        updated_at=now,
    )


def _make_state(agent_id: str = "test-agent", summary: str = "") -> AgentState:
    return AgentState(
        profile=_make_profile(agent_id),
        session_summary=summary,
        working_memory={"goal": "unit testing"},
        tool_trace=[ToolCall(tool_name="read_file", args={"path": "/tmp/x.txt"}, result="ok")],
        semantic_memory_refs=["chunk-abc"],
        execution_count=3,
        last_active=datetime.now(UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# Test 1: AgentStateStore persists and reloads state without data loss
# ---------------------------------------------------------------------------


def test_state_store_roundtrip(tmp_path):
    store = AgentStateStore(state_dir=str(tmp_path))
    original = _make_state(agent_id="agent-roundtrip", summary="Conversación de prueba")

    store.save(original)
    loaded = store.load("agent-roundtrip")

    assert loaded.profile.id == original.profile.id
    assert loaded.profile.name == original.profile.name
    assert loaded.session_summary == original.session_summary
    assert loaded.working_memory == original.working_memory
    assert loaded.execution_count == original.execution_count
    assert len(loaded.tool_trace) == len(original.tool_trace)
    assert loaded.tool_trace[0].tool_name == "read_file"
    assert loaded.semantic_memory_refs == original.semantic_memory_refs


def test_state_store_list_agents(tmp_path):
    store = AgentStateStore(state_dir=str(tmp_path))
    store.save(_make_state("agent-alpha"))
    store.save(_make_state("agent-beta"))

    profiles = store.list_agents()
    ids = {p.id for p in profiles}
    assert "agent-alpha" in ids
    assert "agent-beta" in ids


def test_state_store_delete(tmp_path):
    store = AgentStateStore(state_dir=str(tmp_path))
    store.save(_make_state("agent-to-delete"))
    assert (tmp_path / "agent-to-delete.json").exists()

    store.delete("agent-to-delete")
    assert not (tmp_path / "agent-to-delete.json").exists()


# ---------------------------------------------------------------------------
# Test 2: Atomic write — original file not corrupted on interrupted save
# ---------------------------------------------------------------------------


def test_atomic_write_leaves_no_tmp_file(tmp_path):
    """After a successful save, no .tmp file should remain."""
    store = AgentStateStore(state_dir=str(tmp_path))
    state = _make_state("agent-atomic")

    store.save(state)

    json_path = tmp_path / "agent-atomic.json"
    tmp_path_file = tmp_path / "agent-atomic.tmp"

    assert json_path.exists()
    assert not tmp_path_file.exists()


def test_atomic_write_original_intact_if_os_replace_fails(tmp_path):
    """If os.replace raises, the original file must be untouched."""
    store = AgentStateStore(state_dir=str(tmp_path))

    # Write initial state
    initial_state = _make_state("agent-safe", summary="original summary")
    store.save(initial_state)

    # Now attempt a save that fails during the atomic rename
    new_state = _make_state("agent-safe", summary="NEW summary — should not appear")
    with patch("os.replace", side_effect=OSError("simulated disk failure")):
        with pytest.raises(OSError):
            store.save(new_state)

    # Original file must still have old content
    current_content = (tmp_path / "agent-safe.json").read_text()
    data = json.loads(current_content)
    assert data["session_summary"] == "original summary"


# ---------------------------------------------------------------------------
# Test 3: update_state node updates session_summary after each interaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_updates_session_summary_after_run(tmp_path):
    """After run(), the saved AgentState must have session_summary updated."""
    from core.agents.runtime import AgentRuntime
    from core.inference.registry import ProviderRegistry

    agent_id = "agent-summary-test"
    store = AgentStateStore(state_dir=str(tmp_path))

    # Pre-condition: no session_summary
    initial = store.load(agent_id)
    assert initial.session_summary == ""

    # Mock ProviderRegistry
    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(
        return_value='{"action": "answer", "answer": "42 es la respuesta."}'
    )
    mock_chat.is_available = MagicMock(return_value=True)

    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    # Mock ContextBuilder
    mock_context = MagicMock()
    mock_context.retrieved_memory = []
    mock_context.session_history = []
    mock_context.retrieved_documents = []
    mock_context.agent_summary = ""
    mock_context.total_tokens_estimated = 50
    mock_context.sources_used = []

    mock_builder = MagicMock()
    mock_builder.maybe_consolidate = AsyncMock(return_value=False)
    mock_builder.build = AsyncMock(return_value=mock_context)

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=mock_builder,
        tool_registry={},
    )

    answer, final_state = await runtime.run("¿Cuál es la respuesta?", agent_id)

    assert "42" in answer
    # session_summary must now contain the exchange
    saved = store.load(agent_id)
    assert len(saved.session_summary) > 0
    assert "42" in saved.session_summary or "respuesta" in saved.session_summary.lower()


# ---------------------------------------------------------------------------
# Test 4: Agent without saved profile initializes empty state correctly
# ---------------------------------------------------------------------------


def test_load_nonexistent_agent_returns_empty_state(tmp_path):
    store = AgentStateStore(state_dir=str(tmp_path))

    state = store.load("brand-new-agent")

    assert state.profile.id == "brand-new-agent"
    assert state.session_summary == ""
    assert state.working_memory == {}
    assert state.tool_trace == []
    assert state.execution_count == 0
    assert state.semantic_memory_refs == []


def test_load_corrupted_file_returns_empty_state(tmp_path):
    """If the JSON file is corrupted, load() must not raise — return empty state."""
    store = AgentStateStore(state_dir=str(tmp_path))

    # Write garbage JSON
    (tmp_path / "broken-agent.json").write_text("{not valid json", encoding="utf-8")

    state = store.load("broken-agent")

    assert state.profile.id == "broken-agent"
    assert state.session_summary == ""


# ---------------------------------------------------------------------------
# Test: duplicate tool call detection aborts loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_aborts_on_duplicate_tool_call(tmp_path):
    """If the same tool+args are called twice, the runtime must not loop."""
    from core.agents.runtime import AgentRuntime
    from core.inference.registry import ProviderRegistry

    agent_id = "agent-dedup"
    store = AgentStateStore(state_dir=str(tmp_path))

    call_count = 0

    async def fake_complete(_messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: request a tool
            return '{"action": "tool", "tool": "read_file", "args": {"path": "/tmp/x"}}'
        if call_count == 2:
            # Second call (after observe): request the SAME tool again → should abort
            return '{"action": "tool", "tool": "read_file", "args": {"path": "/tmp/x"}}'
        # Should not reach here — dedup kicks in
        return '{"action": "answer", "answer": "final"}'

    mock_chat = MagicMock()
    mock_chat.complete = fake_complete
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    mock_context = MagicMock()
    mock_context.retrieved_memory = []
    mock_context.session_history = []
    mock_context.retrieved_documents = []
    mock_context.agent_summary = ""
    mock_context.total_tokens_estimated = 10
    mock_context.sources_used = []

    mock_builder = MagicMock()
    mock_builder.maybe_consolidate = AsyncMock(return_value=False)
    mock_builder.build = AsyncMock(return_value=mock_context)

    def fake_read_file(**_kwargs):
        return "contenido del archivo"

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=mock_builder,
        tool_registry={"read_file": fake_read_file},
    )

    answer, _ = await runtime.run("Lee el archivo", agent_id)

    # Must terminate (not hang) and return a graceful message
    assert isinstance(answer, str)
    assert len(answer) > 0


# ──────────────────────────────────────────────────────────────────────────────
# _parse_llm_response — robustness for small / Qwen3 models
# ──────────────────────────────────────────────────────────────────────────────

from core.agents.runtime import _parse_llm_response

_SAMPLE_TOOLS = frozenset(
    {
        "get_upcoming_events",
        "write_file",
        "create_python_file",
        "read_file",
    }
)


def test_parse_standard_tool_call():
    raw = '{"action": "tool", "tool": "get_upcoming_events", "args": {"hours_ahead": 24}}'
    action, tool, args = _parse_llm_response(raw)
    assert action == "tool"
    assert tool == "get_upcoming_events"
    assert args == {"hours_ahead": 24}


def test_parse_standard_answer():
    raw = '{"action": "answer", "answer": "Tienes una reunión mañana."}'
    action, tool, args = _parse_llm_response(raw)
    assert action == "answer"
    assert args["answer"] == "Tienes una reunión mañana."


def test_parse_qwen3_thinking_block_stripped():
    raw = (
        "<think>\nLet me call the calendar tool.\n</think>\n"
        '{"action": "tool", "tool": "get_upcoming_events", "args": {"hours_ahead": 24}}'
    )
    action, tool, args = _parse_llm_response(raw)
    assert action == "tool"
    assert tool == "get_upcoming_events"


def test_parse_action_is_tool_name_directly():
    # Small model outputs tool name in action field instead of "tool"
    raw = '{"action": "get_upcoming_events", "hours_ahead": 24}'
    action, tool, args = _parse_llm_response(raw)
    assert action == "tool"
    assert tool == "get_upcoming_events"
    assert args == {"hours_ahead": 24}


def test_parse_action_tool_name_with_wrong_args():
    # Model uses wrong arg name — parser still identifies it as a tool call
    raw = '{"action": "get_upcoming_events", "date": "tomorrow"}'
    action, tool, args = _parse_llm_response(raw)
    assert action == "tool"
    assert tool == "get_upcoming_events"
    assert "date" in args


def test_parse_json_embedded_in_prose():
    raw = 'Sure! Here is my response: {"action": "answer", "answer": "No events today."} Hope that helps.'
    action, tool, args = _parse_llm_response(raw)
    assert action == "answer"
    assert "No events today" in args["answer"]


def test_parse_markdown_fence_stripped():
    raw = '```json\n{"action": "answer", "answer": "All clear."}\n```'
    action, tool, args = _parse_llm_response(raw)
    assert action == "answer"
    assert "All clear" in args["answer"]


def test_parse_plain_text_fallback():
    raw = "Tienes una reunión mañana a las 10."
    action, tool, args = _parse_llm_response(raw)
    assert action == "answer"
    assert "reunión" in args["answer"]


def test_parse_answer_list_becomes_bulleted_text():
    action, tool, args = _parse_llm_response('{"action":"answer","answer":["a","b","c"]}')
    assert action == "answer"
    assert tool is None
    assert args["answer"] == "- a\n- b\n- c"


def test_parse_answer_dict_becomes_kv_text():
    action, _, args = _parse_llm_response('{"action":"answer","answer":{"k1":"v1","k2":2}}')
    assert action == "answer"
    assert args["answer"] == "k1: v1\nk2: 2"


def test_parse_answer_single_error_key():
    action, _, args = _parse_llm_response('{"action":"answer","answer":{"error":"Sin eventos"}}')
    assert action == "answer"
    assert args["answer"] == "Sin eventos"


def test_parse_answer_error_and_code():
    action, _, args = _parse_llm_response(
        '{"action":"answer","answer":{"error":"Sin eventos","code":404}}'
    )
    assert action == "answer"
    assert args["answer"] == "Sin eventos (404)"


def test_parse_invalid_tool_shortcut_falls_back_to_friendly_answer():
    raw = '{"action": "not_a_real_tool", "hours_ahead": 24}'
    action, tool, args = _parse_llm_response(raw, known_tools=_SAMPLE_TOOLS)
    assert action == "answer"
    assert tool is None
    assert "reformular" in args["answer"]


def test_parse_malformed_json_returns_friendly_fallback():
    raw = '{"action": "tool", "tool": create_python_file, "args": {"filename": "hello.py"}}'
    action, tool, args = _parse_llm_response(raw)
    assert action == "answer"
    assert tool is None
    assert not args["answer"].strip().startswith("{")


def test_parse_fence_with_trailing_whitespace_on_closing_line():
    raw = '```json\n{"action": "answer", "answer": "All clear."}\n```   \n'
    action, _, args = _parse_llm_response(raw)
    assert action == "answer"
    assert "All clear" in args["answer"]


def test_parse_answer_field_with_embedded_fence_stripped():
    raw = '{"action": "answer", "answer": "```json\\nHola\\n```"}'
    action, _, args = _parse_llm_response(raw)
    assert action == "answer"
    assert args["answer"] == "Hola"


def test_parse_unknown_tool_name_with_known_tools_set():
    raw = '{"action": "tool", "tool": "phantom_tool", "args": {}}'
    action, tool, args = _parse_llm_response(raw, known_tools=_SAMPLE_TOOLS)
    assert action == "answer"
    assert tool is None
    assert "phantom_tool" in args["answer"]


# ---------------------------------------------------------------------------
# Phase 4 — search_files reaches handler when authorized
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_files_tool_reached_when_authorized(tmp_path):
    """When authorized_tools=[] (all allowed), search_files handler must be called."""
    from core.agents.runtime import AgentRuntime
    from core.inference.registry import ProviderRegistry

    agent_id = "agent-search-files"
    store = AgentStateStore(state_dir=str(tmp_path))

    # Empty authorized_tools = all tools allowed per AgentRuntime contract
    initial = store.load(agent_id)
    assert initial.profile.authorized_tools == []

    handler_called = False

    def fake_search_files(**kwargs):
        nonlocal handler_called
        handler_called = True
        return "report.py, notes.md"

    call_count = 0

    async def fake_complete(_messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return '{"action": "tool", "tool": "search_files", "args": {"pattern": "*.py"}}'
        return '{"action": "answer", "answer": "Encontré 2 archivos."}'

    mock_chat = MagicMock()
    mock_chat.complete = fake_complete
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    mock_context = MagicMock()
    mock_context.retrieved_memory = []
    mock_context.session_history = []
    mock_context.retrieved_documents = []
    mock_context.agent_summary = ""
    mock_context.total_tokens_estimated = 10
    mock_context.sources_used = []

    mock_builder = MagicMock()
    mock_builder.maybe_consolidate = AsyncMock(return_value=False)
    mock_builder.build = AsyncMock(return_value=mock_context)

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=mock_builder,
        tool_registry={"search_files": fake_search_files},
    )

    answer, _ = await runtime.run("Busca archivos Python", agent_id)

    assert handler_called, "search_files handler was not called"
    assert isinstance(answer, str) and len(answer) > 0


# ---------------------------------------------------------------------------
# A1.3 — semantic history compression when context fill exceeds 85 %
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidation_triggers_above_85_percent_fill():
    from unittest.mock import AsyncMock

    from core.memory.context_builder import ContextBuilder
    from core.memory.short_term import ShortTermStore

    short_term = ShortTermStore()
    for _ in range(15):
        short_term.push_message({"role": "user", "content": "x" * 500})
        short_term.push_message({"role": "assistant", "content": "y" * 500})

    before_count = len(short_term.get_context().active_messages)
    assert before_count > 0

    long_term = AsyncMock()
    long_term.search = AsyncMock(return_value=[])
    builder = ContextBuilder(short_term=short_term, long_term=long_term)

    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value="Resumen técnico con archivo config.py y variable API_KEY."
    )

    agent_state = _make_state(summary="")
    context_window = 4096

    triggered = await builder.maybe_consolidate(agent_state, provider, context_window)

    assert triggered is True
    assert "Consolidación automática" in agent_state.session_summary
    assert len(short_term.get_context().active_messages) < before_count
    provider.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_reason_node_passes_grammar_to_complete(tmp_path):
    from core.agents.runtime import AgentRuntime
    from core.inference.registry import ProviderRegistry

    agent_id = "agent-grammar"
    store = AgentStateStore(state_dir=str(tmp_path))

    captured: dict = {}

    async def fake_complete(_messages, **kwargs):
        captured.update(kwargs)
        return '{"action": "answer", "answer": "respuesta con áéíóú ñ"}'

    mock_chat = MagicMock()
    mock_chat.complete = fake_complete
    mock_registry = MagicMock(spec=ProviderRegistry)
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    mock_context = MagicMock()
    mock_context.retrieved_memory = []
    mock_context.session_history = []
    mock_context.retrieved_documents = []
    mock_context.agent_summary = ""
    mock_context.total_tokens_estimated = 10
    mock_context.sources_used = []

    mock_builder = MagicMock()
    mock_builder.maybe_consolidate = AsyncMock(return_value=False)
    mock_builder.build = AsyncMock(return_value=mock_context)

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=mock_builder,
        tool_registry={},
    )

    await runtime.run("¿Qué hora es?", agent_id)

    assert "grammar" in captured
    assert "answer-response" in captured["grammar"]
    assert "json-string" in captured["grammar"]


@pytest.mark.asyncio
async def test_runtime_resumes_capped_conversation_history(tmp_path):
    from unittest.mock import AsyncMock, MagicMock

    from core.agents.conversation_store import ConversationStore
    from core.agents.session_policy import SESSION_RESUME_MAX_TURNS
    from core.agents.specialized import make_general_profile
    from core.memory.context_builder import ContextBuilder
    from core.memory.short_term import ShortTermStore

    conv_store = ConversationStore(str(tmp_path))
    conv_id = conv_store.create("general-v1")
    for i in range(12):
        conv_store.append(conv_id, f"q{i}", f"a{i}", {})

    store = AgentStateStore(str(tmp_path / "agents"))
    profile = make_general_profile()
    store.save(
        AgentState(
            profile=profile,
            session_summary="",
            working_memory={},
            tool_trace=[],
            semantic_memory_refs=[],
            execution_count=0,
            last_active=datetime.now(UTC).isoformat(),
        )
    )

    short_term = ShortTermStore()
    long_term = AsyncMock()
    long_term.search = AsyncMock(return_value=[])
    builder = ContextBuilder(short_term=short_term, long_term=long_term)

    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(return_value='{"action": "answer", "answer": "ok"}')
    mock_chat.context_window = MagicMock(return_value=4096)
    mock_registry = MagicMock()
    mock_registry.select_for_task = MagicMock(return_value="primary")
    mock_registry.get_chat = MagicMock(return_value=mock_chat)

    runtime = AgentRuntime(
        registry=mock_registry,
        state_store=store,
        context_builder=builder,
        tool_registry={},
        conversation_store=conv_store,
    )

    runtime.prepare_conversation(conv_id, "general-v1")

    messages = short_term.get_context().active_messages
    assert len(messages) == SESSION_RESUME_MAX_TURNS
    assert messages[0]["content"] == "q8"


@pytest.mark.asyncio
async def test_consolidation_skipped_below_threshold():
    from unittest.mock import AsyncMock

    from core.memory.context_builder import ContextBuilder
    from core.memory.short_term import ShortTermStore

    short_term = ShortTermStore()
    short_term.push_message({"role": "user", "content": "hola"})

    long_term = AsyncMock()
    long_term.search = AsyncMock(return_value=[])
    builder = ContextBuilder(short_term=short_term, long_term=long_term)

    provider = AsyncMock()
    provider.complete = AsyncMock(return_value="no debería llamarse")

    agent_state = _make_state(summary="")
    triggered = await builder.maybe_consolidate(agent_state, provider, context_window=4096)

    assert triggered is False
    provider.complete.assert_not_awaited()

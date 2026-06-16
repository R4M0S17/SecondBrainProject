"""Tests for A3 — Two-Level Memory Architecture."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.memory.short_term import ShortTermStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_state(summary: str = "", domain_tags: list[str] | None = None):
    """Build a minimal AgentState without importing the full state_store module."""
    from core.agents.state_store import AgentProfile, AgentState

    profile = AgentProfile(
        id="test-agent",
        name="TestAgent",
        domain_tags=domain_tags or [],
        authorized_tools=[],
        preferences={},
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
    )
    return AgentState(
        profile=profile,
        session_summary=summary,
        working_memory={},
        tool_trace=[],
        semantic_memory_refs=[],
        execution_count=0,
        last_active="2024-01-01T00:00:00",
    )


def _fake_embed(dim: int = 768):
    """Return a deterministic mock EmbeddingProvider."""
    embed = AsyncMock()
    embed.embed = AsyncMock(return_value=[0.1] * dim)
    embed.dimensions = MagicMock(return_value=dim)
    return embed


def _mock_vector_store(tmp_path):
    """Return a stub with db_path so LongTermStore can connect."""
    vs = MagicMock()
    vs.db_path = str(tmp_path / "testdb")
    return vs


# ---------------------------------------------------------------------------
# Test 1: ShortTermStore.to_summary() produces summary < 500 tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_to_summary_produces_short_text():
    store = ShortTermStore(max_messages=50)
    store.push_message({"role": "user", "content": "Explícame los transformers."})
    store.push_message(
        {"role": "assistant", "content": "Los transformers son arquitecturas de red neuronal..."}
    )
    store.push_message({"role": "user", "content": "¿Y la atención multi-cabeza?"})

    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(
        return_value="Resumen: el usuario preguntó sobre transformers y atención."
    )

    summary = await store.to_summary(mock_provider)

    # 500 tokens ≈ 2000 characters (1 token ~ 4 chars)
    assert len(summary) < 2000
    assert isinstance(summary, str)
    assert len(summary) > 0


@pytest.mark.asyncio
async def test_to_summary_empty_store_returns_empty_string():
    store = ShortTermStore()
    mock_provider = MagicMock()

    summary = await store.to_summary(mock_provider)

    assert summary == ""
    mock_provider.complete.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: LongTermStore.search() filters correctly by task_tags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_long_term_search_filters_by_task_tags(tmp_path):
    from core.memory.long_term import LongTermStore, RetrievalContext

    embed = _fake_embed()
    vs = _mock_vector_store(tmp_path)
    store = LongTermStore(vector_store=vs, agent_id="agent-1", embed=embed)

    # Store two episodes with different tags
    await store.store_episode("Resumen de física cuántica", tags=["academic", "physics"])
    await store.store_episode("Fragmento de código Python", tags=["code", "python"])

    # Search filtering only for "academic" tag
    ctx = RetrievalContext(
        query="física",
        task_tags=["academic"],
        date_range=None,
        source_filter=[],
        min_confidence=0.0,
    )
    results = await store.search("física cuántica", ctx)

    assert all("academic" in chunk.tags for chunk in results)
    # The code episode should be excluded
    assert not any("code" in chunk.tags for chunk in results)


@pytest.mark.asyncio
async def test_long_term_search_no_tag_filter_returns_all(tmp_path):
    from core.memory.long_term import LongTermStore, RetrievalContext

    embed = _fake_embed()
    vs = _mock_vector_store(tmp_path)
    store = LongTermStore(vector_store=vs, agent_id="agent-2", embed=embed)

    await store.store_episode("Episodio académico", tags=["academic"])
    await store.store_episode("Episodio de código", tags=["code"])

    ctx = RetrievalContext(
        query="episodio",
        task_tags=[],  # no filter
        date_range=None,
        source_filter=[],
        min_confidence=0.0,
    )
    results = await store.search("episodio", ctx)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# Test 3: ContextBuilder.build() respects the token budget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_builder_respects_token_budget(tmp_path):
    from core.memory.context_builder import ContextBuilder
    from core.memory.long_term import LongTermStore
    from core.memory.short_term import ShortTermStore

    # Fill short_term with a lot of content
    short_term = ShortTermStore(max_messages=50)
    for i in range(20):
        # Each message ~400 chars → ~100 tokens
        short_term.push_message({"role": "user", "content": "x" * 400})

    embed = _fake_embed()
    vs = _mock_vector_store(tmp_path)
    long_term = LongTermStore(vector_store=vs, agent_id="agent-3", embed=embed)

    builder = ContextBuilder(short_term=short_term, long_term=long_term, token_budget=500)
    agent_state = _make_agent_state()

    result = await builder.build("query", agent_state)

    assert result.total_tokens_estimated <= 500


# ---------------------------------------------------------------------------
# Test 4: Episode stored is retrievable by similarity
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Test 5: ContextBuilder._consolidation_params() responds to RAM pressure
# ---------------------------------------------------------------------------


def test_context_builder_consolidation_params_dynamic(mocker):
    from core.memory.context_builder import ContextBuilder

    short_term = MagicMock()
    long_term = MagicMock()
    builder = ContextBuilder(short_term=short_term, long_term=long_term)

    mocker.patch(
        "core.observability.ram_monitor.current_ram_pressure",
        return_value="ok",
    )
    threshold, target = builder._consolidation_params()
    assert threshold == 0.85
    assert target == 0.60

    mocker.patch(
        "core.observability.ram_monitor.current_ram_pressure",
        return_value="critical",
    )
    threshold, target = builder._consolidation_params()
    assert threshold == 0.60
    assert target == 0.40

    mocker.patch(
        "core.observability.ram_monitor.current_ram_pressure",
        return_value="warn",
    )
    threshold, target = builder._consolidation_params()
    assert threshold == 0.60
    assert target == 0.40


# ---------------------------------------------------------------------------
# Test 6: ContextBuilder.build() skips working_memory under RAM pressure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_builder_build_skips_working_memory_under_pressure(mocker, tmp_path):
    from core.memory.context_builder import ContextBuilder
    from core.memory.long_term import LongTermStore
    from core.memory.short_term import ShortTermStore

    short_term = ShortTermStore(max_messages=50)
    short_term.push_message({"role": "user", "content": "test query message"})

    embed = _fake_embed()
    vs = _mock_vector_store(tmp_path)
    long_term = LongTermStore(vector_store=vs, agent_id="agent-test", embed=embed)

    builder = ContextBuilder(short_term=short_term, long_term=long_term, token_budget=2000)
    agent_state = _make_agent_state()
    agent_state.working_memory = {"key": "x" * 800}

    # Under OK pressure: working_memory consumes budget
    mocker.patch(
        "core.observability.ram_monitor.current_ram_pressure",
        return_value="ok",
    )
    result_ok = await builder.build("query", agent_state)

    # Under CRITICAL pressure: working_memory is skipped, so more budget remains
    mocker.patch(
        "core.observability.ram_monitor.current_ram_pressure",
        return_value="critical",
    )
    result_critical = await builder.build("query", agent_state)
    agent_state_critical = _make_agent_state()
    agent_state_critical.working_memory = {"key": "x" * 800}
    result_critical = await builder.build("query", agent_state_critical)

    # With less budget consumed, total_tokens_estimated should be lower
    # (or equal, if no RAG docs are included)
    assert result_critical.total_tokens_estimated <= result_ok.total_tokens_estimated


# ---------------------------------------------------------------------------
# Test 7: ShortTermStore.distill_if_needed() uses lower threshold under pressure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_short_term_distill_if_needed_uses_lower_threshold_under_pressure(mocker):
    store = ShortTermStore(max_messages=50)
    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(return_value="Resumen bajo presión.")

    # Fill exactly 55% of 2000 ctx (1100 tokens) — above 50% threshold, below 75%
    # 1 token ≈ 4 chars, so 1100 tokens ≈ 4400 chars
    store.push_message({"role": "user", "content": "x" * 2200})
    store.push_message({"role": "assistant", "content": "y" * 2200})

    # Under OK pressure: 75% threshold → 1500 tokens needed, we have ~1100 → no distill
    mocker.patch(
        "core.observability.ram_monitor.current_ram_pressure",
        return_value="ok",
    )
    assert await store.distill_if_needed(mock_provider, 2000) is False

    # Same store, same content, but under CRITICAL pressure: 50% threshold → 1000 needed
    mocker.patch(
        "core.observability.ram_monitor.current_ram_pressure",
        return_value="critical",
    )
    assert await store.distill_if_needed(mock_provider, 2000) is True


# ---------------------------------------------------------------------------
# Test 8: ShortTermStore.distill_forced() always summarizes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_short_term_distill_forced_always_summarizes():
    store = ShortTermStore(max_messages=50)
    store.push_message({"role": "user", "content": "Mensaje de prueba."})

    mock_provider = MagicMock()
    mock_provider.complete = AsyncMock(return_value="Resumen forzado.")

    assert await store.distill_forced(mock_provider) is True
    messages = store.get_context().active_messages
    assert len(messages) == 1
    assert "resumido por presión de RAM" in messages[0]["content"]


@pytest.mark.asyncio
async def test_short_term_distill_forced_empty_store():
    store = ShortTermStore(max_messages=50)
    mock_provider = MagicMock()

    assert await store.distill_forced(mock_provider) is False
    mock_provider.complete.assert_not_called()


@pytest.mark.asyncio
async def test_stored_episode_is_retrievable(tmp_path):
    from core.memory.long_term import LongTermStore, RetrievalContext

    embed = _fake_embed()
    vs = _mock_vector_store(tmp_path)
    store = LongTermStore(vector_store=vs, agent_id="agent-4", embed=embed)

    chunk_id = await store.store_episode("Aprendizaje automático con redes neuronales", tags=["ml"])

    ctx = RetrievalContext(
        query="redes neuronales",
        task_tags=[],
        date_range=None,
        source_filter=[],
        min_confidence=0.0,
    )
    results = await store.search("redes neuronales", ctx)

    ids = [r.id for r in results]
    assert chunk_id in ids


@pytest.mark.asyncio
async def test_get_agent_episodes_returns_only_own_agent(tmp_path):
    from core.memory.long_term import LongTermStore

    embed = _fake_embed()

    vs_a = _mock_vector_store(tmp_path)
    vs_b = MagicMock()
    vs_b.db_path = vs_a.db_path  # share same DB

    store_a = LongTermStore(vector_store=vs_a, agent_id="agent-A", embed=embed)
    store_b = LongTermStore(vector_store=vs_b, agent_id="agent-B", embed=embed)

    await store_a.store_episode("Episodio del agente A", tags=[])
    await store_b.store_episode("Episodio del agente B", tags=[])

    episodes_a = store_a.get_agent_episodes("agent-A")
    assert all(e.agent_id == "agent-A" for e in episodes_a)
    assert len(episodes_a) == 1

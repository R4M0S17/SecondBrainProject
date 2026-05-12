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

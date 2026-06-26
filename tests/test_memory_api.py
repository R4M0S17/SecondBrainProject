"""REST API tests for agent memory browser endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.conversation_store import ConversationStore
from core.agents.specialized import GENERAL_AGENT_ID
from core.agents.state_store import AgentStateStore
from core.memory.long_term import LongTermStore
from core.memory.short_term import ShortTermStore
from core.memory.vector_store import VectorStore
from core.observability.ram_monitor import RamMonitor
from core.observability.response_meta import MetricsCollector
from ui.tray.server import app, app_state


def _fake_embed(dim: int = 384):
    embed = AsyncMock()
    embed.embed = AsyncMock(return_value=[0.1] * dim)
    embed.dimensions = MagicMock(return_value=dim)
    return embed


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    app_state.runtime = None
    app_state.router = MagicMock()
    app_state.active_agent_id = GENERAL_AGENT_ID
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    app_state.conv_store = ConversationStore(str(tmp_path / "conv"))
    app_state.ram_monitor = RamMonitor()
    app_state.short_term = ShortTermStore()
    app_state.state_store = AgentStateStore(str(tmp_path / "state"))
    app_state.vector_store = VectorStore(str(tmp_path / "db"), embedding_dim=384)
    app_state.embedding_provider = _fake_embed(384)
    yield
    app_state.short_term = None
    app_state.state_store = None
    app_state.vector_store = None
    app_state.embedding_provider = None


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_list_memory_episodes_empty(client):
    res = await client.get("/api/memory/episodes")
    assert res.status_code == 200
    data = res.json()
    assert data["episodes"] == []
    assert data["stats"]["episodes_stored"] == 0


@pytest.mark.asyncio
async def test_create_list_delete_memory_episode(client):
    create = await client.post(
        "/api/memory/episodes",
        json={"content": "Prefiere respuestas en español técnico.", "tags": ["preference"]},
    )
    assert create.status_code == 200
    created = create.json()
    assert created["content"].startswith("Prefiere")
    assert created["source"] == "manual"
    assert "manual" in created["tags"]
    episode_id = created["id"]

    listing = await client.get("/api/memory/episodes")
    assert listing.status_code == 200
    body = listing.json()
    assert body["stats"]["episodes_stored"] == 1
    assert len(body["episodes"]) == 1
    assert body["episodes"][0]["id"] == episode_id

    deleted = await client.delete(f"/api/memory/episodes/{episode_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    after = await client.get("/api/memory/episodes")
    assert after.json()["episodes"] == []


@pytest.mark.asyncio
async def test_patch_pin_memory_episode(client, tmp_path):
    store = LongTermStore(
        vector_store=app_state.vector_store,
        agent_id=GENERAL_AGENT_ID,
        embed=app_state.embedding_provider,
    )
    episode_id = await store.store_episode("Pinned candidate", ["session"], source="episode")

    patch = await client.patch(
        f"/api/memory/episodes/{episode_id}",
        json={"pinned": True},
    )
    assert patch.status_code == 200
    assert patch.json()["pinned"] is True

    listing = await client.get("/api/memory/episodes")
    assert listing.json()["episodes"][0]["pinned"] is True


@pytest.mark.asyncio
async def test_memory_session_reflects_agent_state(client):
    state = app_state.state_store.load(GENERAL_AGENT_ID)
    state.session_summary = "Resumen de prueba para API."
    state.working_memory = {"task": "memory-api-test"}
    app_state.state_store.save(state)
    app_state.short_term.push_message({"role": "user", "content": "hola"})
    app_state.short_term.push_message({"role": "assistant", "content": "hola"})

    res = await client.get("/api/memory/session")
    assert res.status_code == 200
    data = res.json()
    assert data["session_summary"] == "Resumen de prueba para API."
    assert data["working_memory"]["task"] == "memory-api-test"
    assert data["messages_in_short_term"] == 2


@pytest.mark.asyncio
async def test_memory_recall_returns_semantic_hits(client):
    store = LongTermStore(
        vector_store=app_state.vector_store,
        agent_id=GENERAL_AGENT_ID,
        embed=app_state.embedding_provider,
    )
    await store.store_episode("Graph theory in thesis chapter 2", ["academic"])
    await store.store_episode("Python asyncio patterns", ["code"])

    res = await client.post("/api/memory/recall", json={"query": "graph theory thesis"})
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) >= 1
    assert "graph" in results[0]["episode"]["content"].lower() or results[0]["relevance_score"] > 0


@pytest.mark.asyncio
async def test_patch_memory_episode_content(client):
    create = await client.post(
        "/api/memory/episodes",
        json={"content": "Original text", "tags": ["manual"]},
    )
    episode_id = create.json()["id"]

    patch = await client.patch(
        f"/api/memory/episodes/{episode_id}",
        json={"content": "Updated text", "tags": ["manual", "preference"]},
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["content"] == "Updated text"
    assert "preference" in body["tags"]


@pytest.mark.asyncio
async def test_memory_unavailable_returns_503(client):
    app_state.vector_store = None
    app_state.embedding_provider = None
    res = await client.get("/api/memory/episodes")
    assert res.status_code == 503

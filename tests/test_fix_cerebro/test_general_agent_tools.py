"""Phase 8.3 — General agent tool allowlist + runtime tool execution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.runtime import AgentRuntime
from core.agents.specialized import GENERAL_AGENT_ID, SpecializedAgentRouter, make_general_profile
from core.agents.state_store import AgentStateStore
from core.inference.registry import ProviderRegistry
from core.memory.context_builder import ContextBuilder
from core.memory.long_term import LongTermStore
from core.memory.short_term import ShortTermStore
from core.memory.vector_store import VectorStore
from core.tools.registry import ToolRegistry, register_calendar_tools


@pytest.mark.asyncio
async def test_general_profile_includes_calendar_read_tools():
    profile = make_general_profile()
    for name in ("get_upcoming_events", "query_events", "search_upcoming"):
        assert name in profile.authorized_tools


@pytest.mark.asyncio
async def test_runtime_invokes_get_upcoming_events_when_llm_requests_tool(tmp_path):
    calls: list[str] = []

    def fake_get_upcoming_events(**_kwargs: object) -> str:
        calls.append("get_upcoming_events")
        return "Evento de prueba: Reunión QA"

    store_dir = tmp_path / "state"
    store_dir.mkdir(parents=True, exist_ok=True)
    store = AgentStateStore(str(store_dir))

    router = SpecializedAgentRouter(llm_router=None)
    router.ensure_profiles(store)

    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    vector_store = VectorStore(db_path=str(db_dir), embedding_dim=768)
    embed = MagicMock()
    embed.embed = AsyncMock(return_value=[0.02] * 768)
    embed.dimensions = MagicMock(return_value=768)
    short_term = ShortTermStore()
    long_term = LongTermStore(vector_store=vector_store, agent_id=GENERAL_AGENT_ID, embed=embed)
    context_builder = ContextBuilder(short_term=short_term, long_term=long_term)

    reg = ToolRegistry()
    register_calendar_tools(reg)
    tools = reg.handlers()
    tools["get_upcoming_events"] = fake_get_upcoming_events

    seq = [
        '{"action": "tool", "tool": "get_upcoming_events", "args": {"hours_ahead": 24}}',
        '{"action": "answer", "answer": "Listo: usé el calendario."}',
    ]
    mock_chat = MagicMock()
    mock_chat.complete = AsyncMock(side_effect=seq)
    mock_chat.is_available = MagicMock(return_value=True)
    mock_chat.model_id = MagicMock(return_value="stub")
    mock_chat.context_window = MagicMock(return_value=4096)

    provider_registry = ProviderRegistry(
        ram_threshold_primary_gb=0.01,
        ram_threshold_fallback_gb=0.01,
    )
    provider_registry.register("llamacpp", mock_chat, embed)
    provider_registry.set_primary("llamacpp")

    runtime = AgentRuntime(
        registry=provider_registry,
        state_store=store,
        context_builder=context_builder,
        tool_registry=tools,
        tool_definitions=reg.definitions(),
        enricher=None,
    )

    answer, final = await runtime.run("¿Qué hay hoy en el calendario?", GENERAL_AGENT_ID)

    assert calls == ["get_upcoming_events"]
    assert "Listo" in answer or "calendario" in answer.lower()
    assert any(t.tool_name == "get_upcoming_events" for t in final.tool_trace)

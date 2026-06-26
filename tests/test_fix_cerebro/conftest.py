"""Shared fixtures for FIX_CEREBRO HTTP + runtime E2E tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.conversation_store import ConversationStore
from core.agents.runtime import AgentRuntime
from core.agents.specialized import GENERAL_AGENT_ID, SpecializedAgentRouter
from core.agents.state_store import AgentStateStore
from core.inference.registry import ProviderRegistry
from core.memory.context_builder import ContextBuilder
from core.memory.long_term import LongTermStore
from core.memory.short_term import ShortTermStore
from core.memory.vector_store import VectorStore
from core.observability.ram_monitor import RamMonitor
from core.observability.response_meta import MetricsCollector
from core.tools.registry import (
    ToolRegistry,
    register_calendar_tools,
    register_filesystem_tools,
    register_macos_tools,
)
from ui.tray.server import app, app_state


@pytest.fixture(autouse=True)
def _reset_app_state(tmp_path: Any) -> Any:
    """Baseline app_state so FIX_CEREBRO tests do not leak into each other."""
    conv_dir = tmp_path / "conv_store"
    conv_dir.mkdir(parents=True, exist_ok=True)
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.model_manager = None
    app_state.planner = None
    app_state.enricher = None
    app_state.embedding_provider = None
    app_state.fleet_orchestrator = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    app_state.conv_store = ConversationStore(str(conv_dir))
    app_state.ram_monitor = RamMonitor()
    yield
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.model_manager = None
    app_state.planner = None
    app_state.enricher = None
    app_state.embedding_provider = None
    app_state.fleet_orchestrator = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    app_state.conv_store = ConversationStore(str(conv_dir))
    app_state.ram_monitor = RamMonitor()


@pytest.fixture
def api_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def make_stub_chat_complete(
    side_effect: list[str] | Callable[..., Any],
) -> MagicMock:
    """Build mock chat with .complete returning JSON strings (or async callable)."""
    mock_chat = MagicMock()
    if isinstance(side_effect, list):
        responses = list(side_effect)

        async def _complete(_messages: Any, **_kwargs: Any) -> str:
            if not responses:
                return ""
            return responses.pop(0)

        mock_chat.complete = AsyncMock(side_effect=_complete)

        async def _stream(_messages: Any):
            if False:
                yield ""

        mock_chat.stream = _stream
    else:
        mock_chat.complete = AsyncMock(side_effect=side_effect)

        async def _empty_stream(_messages: Any, **_kwargs: Any):
            if False:
                yield ""

        mock_chat.stream = _empty_stream

    mock_chat.is_available = MagicMock(return_value=True)
    mock_chat.model_id = MagicMock(return_value="stub-model.gguf")
    mock_chat.context_window = MagicMock(return_value=4096)
    return mock_chat


def install_runtime_for_query_e2e(
    tmp_path: Any,
    mock_chat: MagicMock,
    *,
    authorized_read: list[str] | None = None,
) -> None:
    """Wire a real AgentRuntime + ProviderRegistry into app_state for POST /api/query."""
    read_paths = authorized_read or [str(tmp_path)]
    write_paths = [str(tmp_path)]

    db_dir = tmp_path / "lance"
    db_dir.mkdir(parents=True, exist_ok=True)
    vector_store = VectorStore(db_path=str(db_dir), embedding_dim=768)

    embed = MagicMock()
    embed.embed = AsyncMock(return_value=[0.01] * 768)
    embed.dimensions = MagicMock(return_value=768)

    short_term = ShortTermStore()
    long_term = LongTermStore(vector_store=vector_store, agent_id=GENERAL_AGENT_ID, embed=embed)
    context_builder = ContextBuilder(short_term=short_term, long_term=long_term)

    cal_registry = ToolRegistry()
    register_calendar_tools(cal_registry)
    register_filesystem_tools(
        cal_registry,
        authorized_read_paths=read_paths,
        authorized_write_paths=write_paths,
    )
    register_macos_tools(cal_registry)

    state_dir = tmp_path / "agent_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_store = AgentStateStore(str(state_dir))

    router = SpecializedAgentRouter(llm_router=None)
    router.ensure_profiles(state_store)

    registry = ProviderRegistry(
        ram_threshold_primary_gb=0.01,
        ram_threshold_fallback_gb=0.01,
    )
    registry.register("llamacpp", mock_chat, embed)
    registry.set_primary("llamacpp")

    runtime = AgentRuntime(
        registry=registry,
        state_store=state_store,
        context_builder=context_builder,
        tool_registry=cal_registry.handlers(),
        tool_definitions=cal_registry.definitions(),
        enricher=None,
    )

    app_state.runtime = runtime
    app_state.vector_store = vector_store
    app_state.provider_registry = registry
    app_state.router = router
    app_state.model_manager = None
    app_state.enricher = None

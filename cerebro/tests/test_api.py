"""Tests for Module 9 — REST API server (port 7842)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.conversation_store import ConversationStore
from core.observability.response_meta import MetricsCollector
from ui.tray.server import app, app_state

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    """Restore app_state to a clean baseline before every test."""
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    app_state.conv_store = ConversationStore(str(tmp_path))
    yield
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    app_state.conv_store = ConversationStore(str(tmp_path))


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def mock_runtime():
    rt = AsyncMock()
    rt.run.return_value = (
        "Respuesta de prueba.",
        MagicMock(tool_trace=[], pending_tool_name=None, pending_tool_args=None),
    )
    app_state.runtime = rt
    return rt


# ──────────────────────────────────────────────────────────────────────────────
# /status
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_returns_200(client):
    async with client as c:
        resp = await c.get("/api/status")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_status_responds_under_100ms(client):
    async with client as c:
        t0 = time.perf_counter()
        resp = await c.get("/api/status")
        elapsed_ms = (time.perf_counter() - t0) * 1000
    assert resp.status_code == 200
    assert elapsed_ms < 100, f"Status took {elapsed_ms:.1f}ms, expected < 100ms"


@pytest.mark.asyncio
async def test_status_has_required_fields(client):
    async with client as c:
        resp = await c.get("/api/status")
    data = resp.json()
    required = [
        "indexed_files",
        "engine_ok",
        "model",
        "provider",
        "active_agent",
        "ram_used_gb",
        "ram_available_gb",
        "queries_total",
        "avg_latency_ms",
        "p95_latency_ms",
        "tool_call_count",
        "memory_hits",
        "provider_fallbacks",
    ]
    for field in required:
        assert field in data, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_status_reports_engine_unavailable_when_no_registry(client):
    async with client as c:
        resp = await c.get("/api/status")
    assert resp.json()["engine_ok"] is False


@pytest.mark.asyncio
async def test_status_ram_fields_are_positive_numbers(client):
    async with client as c:
        resp = await c.get("/api/status")
    data = resp.json()
    assert data["ram_used_gb"] >= 0
    assert data["ram_available_gb"] > 0


# ──────────────────────────────────────────────────────────────────────────────
# /query
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_returns_valid_json(client, mock_runtime):
    async with client as c:
        resp = await c.post("/api/query", json={"question": "¿Qué es Python?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "metadata" in data
    assert isinstance(data["answer"], str)
    assert isinstance(data["metadata"], dict)


@pytest.mark.asyncio
async def test_query_returns_runtime_answer(client, mock_runtime):
    mock_runtime.run.return_value = (
        "La respuesta es 42.",
        MagicMock(tool_trace=[], pending_tool_name=None, pending_tool_args=None),
    )
    async with client as c:
        resp = await c.post("/api/query", json={"question": "¿Cuál es la respuesta?"})
    assert resp.json()["answer"] == "La respuesta es 42."


@pytest.mark.asyncio
async def test_query_empty_question_returns_422(client):
    async with client as c:
        resp = await c.post("/api/query", json={"question": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_query_missing_question_returns_422(client):
    async with client as c:
        resp = await c.post("/api/query", json={"agent": "general-v1"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_query_without_runtime_returns_503(client):
    async with client as c:
        resp = await c.post("/api/query", json={"question": "test"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_query_increments_queries_total(client, mock_runtime):
    async with client as c:
        await c.post("/api/query", json={"question": "pregunta 1"})
        await c.post("/api/query", json={"question": "pregunta 2"})
    assert app_state.queries_total == 2


# ──────────────────────────────────────────────────────────────────────────────
# /index
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_returns_started_status(client):
    async with client as c:
        resp = await c.post("/api/index", json={"paths": ["/some/path"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "started"
    assert "job_id" in data
    assert len(data["job_id"]) > 0


@pytest.mark.asyncio
async def test_index_empty_paths_returns_422(client):
    async with client as c:
        resp = await c.post("/api/index", json={"paths": []})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_index_missing_paths_returns_422(client):
    async with client as c:
        resp = await c.post("/api/index", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_index_each_call_returns_unique_job_id(client):
    async with client as c:
        r1 = await c.post("/api/index", json={"paths": ["/path/a"]})
        r2 = await c.post("/api/index", json={"paths": ["/path/b"]})
    assert r1.json()["job_id"] != r2.json()["job_id"]


# ──────────────────────────────────────────────────────────────────────────────
# /config
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_config_get_returns_empty_dict_by_default(client):
    async with client as c:
        resp = await c.get("/api/config")
    assert resp.status_code == 200
    assert resp.json() == {}


@pytest.mark.asyncio
async def test_config_put_updates_and_returns_settings(client):
    new_config = {"language": "es", "model": "phi3:mini"}
    async with client as c:
        put_resp = await c.patch("/api/config", json=new_config)
    assert put_resp.status_code == 200
    assert put_resp.json()["language"] == "es"
    assert put_resp.json()["model"] == "phi3:mini"


@pytest.mark.asyncio
async def test_config_get_reflects_previous_put(client):
    async with client as c:
        await c.patch("/api/config", json={"key": "value"})
        get_resp = await c.get("/api/config")
    assert get_resp.json()["key"] == "value"


@pytest.mark.asyncio
async def test_config_put_merges_settings(client):
    async with client as c:
        await c.patch("/api/config", json={"a": 1})
        await c.patch("/api/config", json={"b": 2})
        get_resp = await c.get("/api/config")
    data = get_resp.json()
    assert data["a"] == 1
    assert data["b"] == 2


@pytest.mark.asyncio
async def test_config_model_change_switches_llamacpp_provider(client):
    """Patching model with a llama.cpp model name updates the registry primary."""
    from core.inference.providers.llamacpp_provider import LlamaCppChatProvider
    from core.inference.registry import ProviderRegistry

    registry = ProviderRegistry()
    mlx_chat = MagicMock()
    mlx_chat.model_id.return_value = "mlx-community/Phi-4-mini-instruct-4bit"
    llamacpp_chat = LlamaCppChatProvider(model="phi3-mini.gguf")

    registry.register("mlx", mlx_chat, MagicMock())
    registry.register("llamacpp", llamacpp_chat, MagicMock())
    app_state.provider_registry = registry

    async with client as c:
        resp = await c.patch("/api/config", json={"model": "qwen3-4b.gguf"})

    assert resp.status_code == 200
    # Registry primary should now be llamacpp
    assert registry.get_chat().model_id() == "qwen3-4b.gguf"


# ──────────────────────────────────────────────────────────────────────────────
# /query — LLM routing (agent="auto") and ModelManager integration
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_auto_uses_route_with_llm(client, mock_runtime):
    """agent='auto' delegates routing to router.route_with_llm."""
    from core.agents.specialized import RouteResult

    app_state.router.route_with_llm = AsyncMock(
        return_value=RouteResult(agent_id="general-v1", query="¿Qué es Python?")
    )
    async with client as c:
        resp = await c.post("/api/query", json={"question": "¿Qué es Python?", "agent": "auto"})
    assert resp.status_code == 200
    app_state.router.route_with_llm.assert_awaited_once()


@pytest.mark.asyncio
async def test_query_auto_routes_to_code_agent(client, mock_runtime):
    """route_with_llm returning code-v1 sets active_agent_id to code-v1."""
    from core.agents.specialized import RouteResult

    app_state.router.route_with_llm = AsyncMock(
        return_value=RouteResult(agent_id="code-v1", query="/code fix this")
    )
    async with client as c:
        await c.post("/api/query", json={"question": "/code fix this", "agent": "auto"})
    assert app_state.active_agent_id == "code-v1"


@pytest.mark.asyncio
async def test_query_explicit_agent_skips_llm_router(client, mock_runtime):
    """Explicit agent= bypasses route_with_llm entirely."""
    app_state.router.route_with_llm = AsyncMock()
    async with client as c:
        await c.post("/api/query", json={"question": "test", "agent": "general-v1"})
    app_state.router.route_with_llm.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_with_model_manager_calls_get_chat_for_agent(client, mock_runtime):
    """When model_manager is set, get_chat_for_agent is called instead of get_chat."""
    from core.inference.registry import ProviderRegistry

    mock_chat = MagicMock()
    mock_chat.model_id.return_value = "Qwen-4B"

    registry = MagicMock(spec=ProviderRegistry)
    registry.get_chat_for_agent = AsyncMock(return_value=mock_chat)
    registry.primary_name = "llamacpp"

    mock_mm = MagicMock()
    app_state.provider_registry = registry
    app_state.model_manager = mock_mm

    async with client as c:
        resp = await c.post("/api/query", json={"question": "fix my code", "agent": "code-v1"})

    assert resp.status_code == 200
    registry.get_chat_for_agent.assert_awaited_once_with("code-v1", mock_mm)
    assert resp.json()["metadata"]["provider_used"] == "llamacpp"
    assert resp.json()["metadata"]["model_used"] == "Qwen-4B"

    app_state.model_manager = None


@pytest.mark.asyncio
async def test_query_without_model_manager_uses_get_chat(client, mock_runtime):
    """Without model_manager, plain get_chat() is used."""
    from core.inference.registry import ProviderRegistry

    mock_chat = MagicMock()
    mock_chat.model_id.return_value = "phi3:mini"

    registry = MagicMock(spec=ProviderRegistry)
    registry.get_chat.return_value = mock_chat
    registry.primary_name = "llamacpp"

    app_state.provider_registry = registry
    app_state.model_manager = None

    async with client as c:
        resp = await c.post("/api/query", json={"question": "hello", "agent": "general-v1"})

    assert resp.status_code == 200
    registry.get_chat.assert_called_once()
    assert resp.json()["metadata"]["model_used"] == "phi3:mini"


@pytest.mark.asyncio
async def test_config_model_change_switches_to_mlx(client):
    """Patching model with the MLX model ID switches primary to mlx."""
    from core.inference.providers.llamacpp_provider import LlamaCppChatProvider
    from core.inference.registry import ProviderRegistry

    registry = ProviderRegistry()
    mlx_chat = MagicMock()
    mlx_chat.model_id.return_value = "mlx-community/Phi-4-mini-instruct-4bit"
    llamacpp_chat = LlamaCppChatProvider(model="phi3-mini.gguf")

    registry.register("mlx", mlx_chat, MagicMock())
    registry.register("llamacpp", llamacpp_chat, MagicMock())
    # Start with llamacpp as primary
    registry.set_primary("llamacpp")
    app_state.provider_registry = registry

    async with client as c:
        await c.patch("/api/config", json={"model": "mlx-community/Phi-4-mini-instruct-4bit"})

    assert registry.get_chat() is mlx_chat

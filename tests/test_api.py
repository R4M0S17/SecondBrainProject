"""Tests for Module 9 — REST API server (port 7842)."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.conversation_store import ConversationStore
from core.agents.runtime import ContextSourcesEvent, StreamRunComplete
from core.observability.ram_monitor import RamMonitor
from core.observability.response_meta import MetricsCollector
from ui.tray.server import app, app_state

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


class _RunStreamingMock:
    """Async generator stand-in for ``AgentRuntime.run_streaming`` in API tests."""

    def __init__(self, answer: str, final_state: MagicMock) -> None:
        self.answer = answer
        self.final_state = final_state
        self.calls: list[tuple] = []

    async def __call__(
        self,
        query: str,
        agent_id: str,
        conversation_id: str | None = None,
        intent_query: str | None = None,
        slot_id: int | None = None,
        attachments: list[dict] | None = None,
    ):
        self.calls.append((query, agent_id, conversation_id, intent_query, attachments))
        yield self.answer
        yield StreamRunComplete(answer=self.answer, final_state=self.final_state)


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
    app_state.ram_monitor = RamMonitor()
    app_state.model_manager = None
    app_state.llama_health_monitor = None
    yield
    app_state.runtime = None
    app_state.vector_store = None
    app_state.provider_registry = None
    app_state.active_agent_id = "general-v1"
    app_state.metrics = MetricsCollector()
    app_state._config = {}
    app_state.conv_store = ConversationStore(str(tmp_path))
    app_state.ram_monitor = RamMonitor()
    app_state.model_manager = None
    app_state.llama_health_monitor = None


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def mock_runtime():
    rt = AsyncMock()
    final_state = MagicMock(tool_trace=[], pending_tool_name=None, pending_tool_args=None)
    answer = "Respuesta de prueba."
    rt.run.return_value = (answer, final_state)
    rt._run_streaming_mock = _RunStreamingMock(answer, final_state)
    rt.run_streaming = rt._run_streaming_mock
    app_state.runtime = rt
    return rt


@pytest.mark.asyncio
async def test_lifespan_does_not_block_on_model_manager_start(monkeypatch):
    monkeypatch.setattr(
        "core.observability.macos_perms.probe_calendar_permission",
        AsyncMock(return_value="unknown"),
    )

    started = asyncio.Event()

    class SlowModelManager:
        async def start(self):
            started.set()
            await asyncio.Event().wait()

        async def stop(self):
            return None

    app_state.model_manager = SlowModelManager()
    app_state.llama_health_monitor = None

    async def _enter_lifespan():
        async with app.router.lifespan_context(app):
            await asyncio.wait_for(started.wait(), timeout=0.2)

    await asyncio.wait_for(_enter_lifespan(), timeout=0.5)


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
        "context_window",
        "ram_pressure",
        "ram_total_gb",
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
    assert data["ram_pressure"] in ("ok", "warn", "critical")
    assert data["ram_total_gb"] > 0


@pytest.mark.asyncio
async def test_ram_pressure_critical_query_returns_warning_not_503(client, mock_runtime):
    mon = MagicMock()
    mon.snapshot.return_value = {
        "pressure": "critical",
        "used_gb": 14.0,
        "available_gb": 0.5,
        "total_gb": 16.0,
    }
    app_state.ram_monitor = mon
    mock_runtime.run = AsyncMock(
        return_value=("ok", MagicMock(tool_trace=[], pending_tool_name=None))
    )
    async with client as c:
        resp = await c.post("/api/query", json={"question": "hi", "agent": "general-v1"})
    assert resp.status_code == 200
    assert "ram_pressure_critical" in resp.json()["metadata"]["warnings"]
    mock_runtime.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_ram_pressure_critical_stream_returns_warning_not_503(client, mock_runtime):
    mon = MagicMock()
    mon.snapshot.return_value = {
        "pressure": "critical",
        "used_gb": 14.0,
        "available_gb": 0.5,
        "total_gb": 16.0,
    }
    app_state.ram_monitor = mon
    final_state = MagicMock(tool_trace=[], pending_tool_name=None)
    mock_runtime._run_streaming_mock = _RunStreamingMock("stream ok", final_state)
    mock_runtime.run_streaming = mock_runtime._run_streaming_mock

    async def _collect_stream():
        chunks = []
        async with client as c:
            async with c.stream(
                "POST",
                "/api/query/stream",
                json={"question": "hello", "agent": "general-v1"},
            ) as resp:
                assert resp.status_code == 200
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunks.append(line[6:])
        return chunks

    chunks = await _collect_stream()
    meta_chunks = [c for c in chunks if c.strip().startswith("{") and "metadata" in c]
    assert meta_chunks, "expected metadata SSE event"
    meta = json.loads(meta_chunks[-1])
    assert "ram_pressure_critical" in meta["metadata"]["warnings"]
    assert len(mock_runtime._run_streaming_mock.calls) == 1


@pytest.mark.asyncio
async def test_wizard_check_llamacpp_skipped_when_claude_backend(client, monkeypatch):
    monkeypatch.setenv("CEREBRO_INFERENCE_BACKEND", "claude")
    async with client as c:
        resp = await c.post("/api/wizard/check-llamacpp")
    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is True
    assert data["status"] == "skipped"
    assert "reason" in data


@pytest.mark.asyncio
async def test_wizard_check_models_skipped_reflects_api_key(client, monkeypatch):
    monkeypatch.setenv("CEREBRO_INFERENCE_BACKEND", "claude")
    async with client as c:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        resp = await c.post("/api/wizard/check-models")
        assert resp.json()["ok"] is False
        assert resp.json().get("status") == "skipped"

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        resp2 = await c.post("/api/wizard/check-models")
    body = resp2.json()
    assert body["ok"] is True
    assert body.get("status") == "skipped"


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
async def test_query_with_attachments_includes_attachment_text_in_runtime_query(
    client, mock_runtime
):
    attachment = {
        "filename": "notes.txt",
        "mime_type": "text/plain",
        "content": "El proyecto usa FastAPI para la API y React para el frontend.",
        "type": "text",
    }
    async with client as c:
        resp = await c.post(
            "/api/query",
            json={
                "question": "¿De qué trata el archivo?",
                "agent": "general-v1",
                "attachments": [attachment],
            },
        )

    assert resp.status_code == 200
    call_args = mock_runtime.run.call_args
    assert call_args is not None
    augmented_query = call_args.args[0]
    assert "FastAPI" in augmented_query
    assert "notes.txt" in augmented_query
    assert call_args.kwargs["intent_query"] == "¿De qué trata el archivo?"


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
async def test_patch_config_rebinds_read_handlers(client, tmp_path):
    from functools import partial

    from core.tools.handlers.filesystem import read_file

    extra = tmp_path / "new_watch"
    extra.mkdir()
    (extra / "hi.txt").write_text("hello")
    startup = tmp_path / "startup"
    startup.mkdir()
    app_state.authorized_read_paths = [str(startup)]

    tr = {"read_file": partial(read_file, authorized_paths=[str(startup)])}
    mock_rt = MagicMock()
    mock_rt._tool_registry = tr
    app_state.runtime = mock_rt

    async with client as c:
        resp = await c.patch("/api/config", json={"watched_folders": [str(extra)]})
    assert resp.status_code == 200
    body = tr["read_file"](path=str(extra / "hi.txt"))
    assert body == "hello"


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
async def test_query_stream_calls_runtime_run_streaming(client, mock_runtime):
    """B2: /api/query/stream uses runtime.run_streaming(), not legacy runtime.stream()."""
    mock_runtime.stream = MagicMock()
    async with client as c:
        resp = await c.post(
            "/api/query/stream",
            json={"question": "hello", "agent": "general-v1"},
        )
        assert resp.status_code == 200
        await resp.aread()
    assert len(mock_runtime._run_streaming_mock.calls) == 1
    mock_runtime.stream.assert_not_called()


@pytest.mark.asyncio
async def test_query_stream_semantic_chunking_event_count(client, mock_runtime):
    """SentenceBuffer flushes produce ≤10 SSE events for 50 single-word tokens with 2 sentences."""
    words = [
        "This ",
        "is ",
        "a ",
        "test ",
        "of ",
        "the ",
        "sentence ",
        "buffer. ",
        "It ",
        "should ",
        "flush ",
        "at ",
        "boundaries. ",
        "These ",
        "extra ",
        "words ",
        "just ",
        "add ",
        "bulk ",
        "to ",
        "reach ",
        "fifty ",
        "tokens ",
        "total ",
        "without ",
        "more ",
        "sentences. ",
        "Just ",
        "padding ",
        "here ",
        "and ",
        "more ",
        "padding ",
        "there ",
        "to ",
        "fill ",
        "the ",
        "count. ",
        "Almost ",
        "there ",
        "now ",
        "just ",
        "a ",
        "few ",
        "more ",
        "words ",
        "left ",
        "to ",
        "write ",
        "out. ",
    ]
    assert len(words) == 50, f"Expected 50 tokens, got {len(words)}"

    full_answer = "".join(words)
    final_state = MagicMock(tool_trace=[], pending_tool_name=None, pending_tool_args=None)

    async def _streaming_mock(*args, **kwargs):
        for w in words:
            yield w
        yield StreamRunComplete(answer=full_answer, final_state=final_state)

    app_state.runtime.run_streaming = _streaming_mock

    async with client as c:
        resp = await c.post(
            "/api/query/stream",
            json={"question": "test", "agent": "general-v1"},
        )
        assert resp.status_code == 200
        body = await resp.aread()

    body_text = body.decode()
    token_events = [
        line for line in body_text.split("\n") if line.startswith("data: ") and '"token"' in line
    ]
    token_count = len(token_events)
    assert token_count <= 10, f"SentenceBuffer produced {token_count} token events, expected ≤10"

    reconstructed = ""
    for line in token_events:
        payload = json.loads(line[6:])
        reconstructed += payload["token"]
    assert reconstructed == full_answer, (
        f"Reconstructed text does not match original.\n"
        f"Expected ({len(full_answer)} chars): {full_answer[:100]}...\n"
        f"Got ({len(reconstructed)} chars): {reconstructed[:100]}..."
    )


@pytest.mark.asyncio
async def test_query_stream_context_sources_event(client, mock_runtime):
    """SSE stream includes context_sources event before token events when available."""
    final_state = MagicMock(tool_trace=[], pending_tool_name=None, pending_tool_args=None)
    answer = "Respuesta de prueba."

    async def _streaming_with_sources(*args, **kwargs):
        yield ContextSourcesEvent(sources=["file1.pdf", "notes.md"], episode_count=2)
        yield answer
        yield StreamRunComplete(answer=answer, final_state=final_state)

    app_state.runtime.run_streaming = _streaming_with_sources

    async with client as c:
        resp = await c.post(
            "/api/query/stream",
            json={"question": "test", "agent": "general-v1"},
        )
        assert resp.status_code == 200
        body = await resp.aread()

    body_text = body.decode()
    events = [line for line in body_text.split("\n") if line.startswith("data: ")]
    assert len(events) >= 2

    first = json.loads(events[0][6:])
    assert first.get("type") == "context_sources"
    assert first.get("sources") == ["file1.pdf", "notes.md"]
    assert first.get("episode_count") == 2


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


# ──────────────────────────────────────────────────────────────────────────────
# /fleet/*
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fleet_orchestrator(tmp_path):
    from core.inference.fleet.hardware_monitor import HardwareSnapshot
    from core.inference.fleet.model_registry import ModelConfig
    from core.inference.fleet.orchestrator import FleetOrchestrator, ModelSelection

    model_path = tmp_path / "tiny.gguf"
    model_path.write_text("fake", encoding="utf-8")
    model = ModelConfig(
        id="tiny-q4",
        path=str(model_path),
        family="test",
        params_b=0.5,
        quant="Q4_K_M",
        ram_required_gb=1.0,
        vram_required_gb=0.5,
        gpu_layers=0,
        context_length=2048,
        capabilities=["chat"],
        speed_tokens_per_sec=100.0,
    )
    hw = HardwareSnapshot(
        ram_total_gb=16.0,
        ram_available_gb=8.0,
        cpu_count=8,
        cpu_percent=10.0,
        gpu_backend="metal",
        gpu_vram_total_gb=16.0,
        gpu_vram_available_gb=8.0,
        unified_memory=True,
    )
    fleet = FleetOrchestrator()
    fleet._hw_snapshot = hw
    fleet.current_selection = ModelSelection(
        model=model,
        gpu_layers=0,
        context_length=2048,
        rationale="test fixture",
    )
    app_state.fleet_orchestrator = fleet
    return fleet


@pytest.mark.asyncio
async def test_fleet_status_returns_200(client, fleet_orchestrator):
    async with client as c:
        resp = await c.get("/api/fleet/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "auto"
    assert body["current_model"]["id"] == "tiny-q4"
    assert body["hardware"]["ram_pressure_pct"] >= 0


@pytest.mark.asyncio
async def test_fleet_status_503_without_orchestrator(client):
    app_state.fleet_orchestrator = None
    async with client as c:
        resp = await c.get("/api/fleet/status")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_fleet_models_lists_registry(client, fleet_orchestrator, monkeypatch):
    model = fleet_orchestrator.current_selection.model
    monkeypatch.setattr(fleet_orchestrator, "list_models", lambda registry_path=None: [model])
    async with client as c:
        resp = await c.get("/api/fleet/models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_model_id"] == "tiny-q4"
    assert len(body["models"]) == 1
    assert body["models"][0]["available_on_disk"] is True


@pytest.mark.asyncio
async def test_fleet_config_pinned_persists(client, fleet_orchestrator, monkeypatch):
    model = fleet_orchestrator.current_selection.model
    monkeypatch.setattr(fleet_orchestrator, "list_models", lambda registry_path=None: [model])
    async with client as c:
        resp = await c.patch(
            "/api/fleet/config",
            json={"mode": "pinned", "pinned_model_id": "tiny-q4"},
        )
    assert resp.status_code == 200
    assert app_state._config["fleet_mode"] == "pinned"
    assert fleet_orchestrator.mode == "pinned"


@pytest.mark.asyncio
async def test_fleet_config_auto_restores_selection(client, fleet_orchestrator, monkeypatch):
    def _fake_startup(registry_path=None, default_task_complexity=None):
        sel = fleet_orchestrator.current_selection
        fleet_orchestrator._mode = "auto"
        fleet_orchestrator._pinned_model_id = None
        return sel

    model = fleet_orchestrator.current_selection.model
    monkeypatch.setattr(fleet_orchestrator, "list_models", lambda registry_path=None: [model])
    monkeypatch.setattr(fleet_orchestrator, "select_on_startup", _fake_startup)
    fleet_orchestrator.pin_model("tiny-q4")
    async with client as c:
        resp = await c.patch("/api/fleet/config", json={"mode": "auto"})
    assert resp.status_code == 200
    assert app_state._config["fleet_mode"] == "auto"
    assert fleet_orchestrator.mode == "auto"

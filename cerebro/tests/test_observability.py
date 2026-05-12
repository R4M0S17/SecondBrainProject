"""Tests for Module A6 — Observability."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.conversation_store import ConversationStore
from core.observability.response_meta import (
    MemoryRef,
    MetricsCollector,
    ResponseMetadata,
    ToolCallRecord,
)
from ui.tray.server import app, app_state

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
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
# ResponseMetadata always present in /query response
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_response_contains_metadata(client, mock_runtime):
    async with client as c:
        resp = await c.post("/api/query", json={"question": "¿Qué es Python?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "metadata" in data
    meta = data["metadata"]
    assert "sources_used" in meta
    assert "tools_called" in meta
    assert "memory_retrieved" in meta
    assert "inference_latency_ms" in meta
    assert "total_latency_ms" in meta
    assert "iterations" in meta
    assert "model_used" in meta
    assert "provider_used" in meta
    assert "warnings" in meta
    assert "pipeline_stages_ms" in meta


@pytest.mark.asyncio
async def test_query_metadata_latency_is_positive(client, mock_runtime):
    async with client as c:
        resp = await c.post("/api/query", json={"question": "test"})
    meta = resp.json()["metadata"]
    assert meta["total_latency_ms"] >= 0


@pytest.mark.asyncio
async def test_query_metadata_model_and_provider_present(client, mock_runtime):
    async with client as c:
        resp = await c.post("/api/query", json={"question": "test"})
    meta = resp.json()["metadata"]
    assert isinstance(meta["model_used"], str)
    assert isinstance(meta["provider_used"], str)


# ──────────────────────────────────────────────────────────────────────────────
# warnings includes "provider_fallback" when provider_registry raises
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_warnings_include_provider_fallback_on_registry_error(client, mock_runtime):
    broken_registry = MagicMock()
    broken_registry.get_chat.side_effect = RuntimeError("provider down")
    app_state.provider_registry = broken_registry

    async with client as c:
        resp = await c.post("/api/query", json={"question": "test"})

    meta = resp.json()["metadata"]
    assert "provider_fallback" in meta["warnings"]


# ──────────────────────────────────────────────────────────────────────────────
# MetricsCollector — unit tests
# ──────────────────────────────────────────────────────────────────────────────


def _meta(total_ms: float, warnings: list[str] | None = None) -> ResponseMetadata:
    return ResponseMetadata(
        total_latency_ms=total_ms,
        warnings=warnings or [],
    )


def test_metrics_collector_queries_total():
    mc = MetricsCollector()
    mc.record_query(_meta(100.0))
    mc.record_query(_meta(200.0))
    assert mc.get_stats().queries_total == 2


def test_metrics_collector_avg_latency():
    mc = MetricsCollector()
    mc.record_query(_meta(100.0))
    mc.record_query(_meta(300.0))
    assert mc.get_stats().avg_latency_ms == 200.0


def test_metrics_collector_p95_known_samples():
    mc = MetricsCollector()
    # 20 samples: 1..20 ms
    for i in range(1, 21):
        mc.record_query(_meta(float(i)))
    stats = mc.get_stats()
    # p95 of [1..20] → index = 0.95 * 19 = 18.05 → interpolate between 19 and 20
    expected = 19 * (1 - 0.05) + 20 * 0.05
    assert abs(stats.p95_latency_ms - expected) < 0.1


def test_metrics_collector_p95_single_sample():
    mc = MetricsCollector()
    mc.record_query(_meta(42.0))
    assert mc.get_stats().p95_latency_ms == 42.0


def test_metrics_collector_p95_two_samples():
    mc = MetricsCollector()
    mc.record_query(_meta(10.0))
    mc.record_query(_meta(20.0))
    stats = mc.get_stats()
    assert stats.p95_latency_ms == pytest.approx(19.5, abs=0.1)


def test_metrics_collector_provider_fallbacks():
    mc = MetricsCollector()
    mc.record_query(_meta(100.0, warnings=["provider_fallback"]))
    mc.record_query(_meta(100.0))
    assert mc.get_stats().provider_fallbacks == 1


def test_metrics_collector_tool_call_count():
    mc = MetricsCollector()
    meta = ResponseMetadata(
        total_latency_ms=50.0,
        tools_called=[
            ToolCallRecord(
                name="search",
                args_summary="q",
                result_summary="r",
                latency_ms=10.0,
                approved=True,
            ),
            ToolCallRecord(
                name="read_file",
                args_summary="p",
                result_summary="ok",
                latency_ms=5.0,
                approved=True,
            ),
        ],
    )
    mc.record_query(meta)
    assert mc.get_stats().tool_call_count == 2


def test_metrics_collector_memory_hits():
    mc = MetricsCollector()
    meta = ResponseMetadata(
        total_latency_ms=50.0,
        memory_retrieved=[
            MemoryRef(id="m1", summary_snippet="snippet", relevance_score=0.9),
        ],
    )
    mc.record_query(meta)
    assert mc.get_stats().memory_hits == 1


def test_metrics_collector_empty_stats():
    mc = MetricsCollector()
    stats = mc.get_stats()
    assert stats.queries_total == 0
    assert stats.avg_latency_ms == 0.0
    assert stats.p95_latency_ms == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# /status exposes enriched fields from MetricsCollector
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_has_p95_and_enriched_fields(client):
    async with client as c:
        resp = await c.get("/api/status")
    data = resp.json()
    for field in ("p95_latency_ms", "tool_call_count", "memory_hits", "provider_fallbacks"):
        assert field in data, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_status_reflects_recorded_queries(client, mock_runtime):
    async with client as c:
        await c.post("/api/query", json={"question": "pregunta 1"})
        await c.post("/api/query", json={"question": "pregunta 2"})
        status_resp = await c.get("/api/status")
    assert status_resp.json()["queries_total"] == 2

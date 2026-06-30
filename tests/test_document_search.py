"""Tests for core/tools/document_search.py and POST /api/documents/search."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.memory.vector_store import SearchResult
from core.tools.document_search import (
    DocumentChunkHit,
    filter_by_source_prefix,
    make_snippet,
    search_document_chunks,
)
from ui.tray.server import app, app_state

# ── Pure unit tests ──────────────────────────────────────────────


def test_make_snippet_truncates():
    short = "Hello world"
    assert make_snippet(short, max_len=100) == short

    long = "a " * 200
    result = make_snippet(long, max_len=50)
    assert len(result) <= 53
    assert result.endswith("…")

    exact = "x" * 300
    assert make_snippet(exact, max_len=300) == exact


def test_make_snippet_word_boundary():
    text = "word boundary test here please"
    result = make_snippet(text, max_len=12)
    assert not result.endswith(" ")
    assert result.endswith("…")


def test_filter_by_source_prefix():
    hits = [
        SearchResult(
            id="1", content="a", source_path="/docs/a.md", chunk_index=0, score=0.1, metadata={}
        ),
        SearchResult(
            id="2", content="b", source_path="/other/b.md", chunk_index=0, score=0.2, metadata={}
        ),
        SearchResult(
            id="3", content="c", source_path="/docs/sub/c.md", chunk_index=0, score=0.3, metadata={}
        ),
    ]

    filtered = filter_by_source_prefix(hits, "/docs")
    assert len(filtered) == 2
    assert all(h.source_path.startswith("/docs") for h in filtered)

    filtered_none = filter_by_source_prefix(hits, None)
    assert len(filtered_none) == 3


def test_filter_by_source_prefix_empty_prefix():
    hits = [
        SearchResult(
            id="1", content="a", source_path="/a.md", chunk_index=0, score=0.1, metadata={}
        )
    ]
    assert filter_by_source_prefix(hits, "") == hits


@pytest.mark.asyncio
async def test_search_document_chunks_empty_index():
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])

    async def fake_embed(_text: str) -> list[float]:
        return [0.1] * 384

    hits = await search_document_chunks(
        query="test",
        vector_store=store,
        embed_fn=fake_embed,
        top_k=5,
    )
    assert hits == []


@pytest.mark.asyncio
async def test_search_document_chunks_returns_hits():
    results = [
        SearchResult(
            id="1",
            content="Hello world content",
            source_path="/a.md",
            chunk_index=0,
            score=0.1,
            metadata={},
        ),
        SearchResult(
            id="2",
            content="Second chunk here",
            source_path="/b.md",
            chunk_index=1,
            score=0.2,
            metadata={},
        ),
    ]
    store = AsyncMock()
    store.search = AsyncMock(return_value=results)

    async def fake_embed(_text: str) -> list[float]:
        return [0.1] * 384

    hits = await search_document_chunks(
        query="test",
        vector_store=store,
        embed_fn=fake_embed,
        top_k=5,
    )
    assert len(hits) == 2
    assert isinstance(hits[0], DocumentChunkHit)
    assert hits[0].filename == "a.md"
    assert hits[0].score == 0.1
    assert hits[1].filename == "b.md"


@pytest.mark.asyncio
async def test_search_document_chunks_source_prefix():
    results = [
        SearchResult(
            id="1", content="a", source_path="/docs/a.md", chunk_index=0, score=0.1, metadata={}
        ),
        SearchResult(
            id="2", content="b", source_path="/other/b.md", chunk_index=0, score=0.2, metadata={}
        ),
    ]
    store = AsyncMock()
    store.search = AsyncMock(return_value=results)

    async def fake_embed(_text: str) -> list[float]:
        return [0.1] * 384

    hits = await search_document_chunks(
        query="test",
        vector_store=store,
        embed_fn=fake_embed,
        top_k=5,
        source_prefix="/docs",
    )
    assert len(hits) == 1
    assert hits[0].source_path == "/docs/a.md"


@pytest.mark.asyncio
async def test_search_document_chunks_overfetch_with_prefix():
    """When source_prefix is set, fetch top_k*3 then filter."""
    results = [
        SearchResult(
            id=str(i),
            content=f"c{i}",
            source_path=f"/other/f{i}.md",
            chunk_index=0,
            score=float(i) * 0.1,
            metadata={},
        )
        for i in range(10)
    ]
    store = AsyncMock()
    store.search = AsyncMock(return_value=results)

    async def fake_embed(_text: str) -> list[float]:
        return [0.1] * 384

    hits = await search_document_chunks(
        query="test",
        vector_store=store,
        embed_fn=fake_embed,
        top_k=3,
        source_prefix="/other",
    )
    assert len(hits) == 3
    assert store.search.call_args[1]["top_k"] == 9


# ── API integration tests ────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_state():
    app_state._config = {}
    app_state.authorized_read_paths = []
    app_state.vector_store = None
    app_state.embedding_provider = None
    app_state.rag_engine = None
    yield


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_api_documents_search_200(client):
    store = AsyncMock()
    store.search = AsyncMock(
        return_value=[
            SearchResult(
                id="1",
                content="presupuesto mensual",
                source_path="/docs/finanzas.md",
                chunk_index=0,
                score=0.1,
                metadata={},
            ),
        ]
    )
    app_state.vector_store = store

    embed = AsyncMock()
    embed.embed = AsyncMock(return_value=[0.1] * 384)
    app_state.embedding_provider = embed

    async with client as c:
        resp = await c.post(
            "/api/documents/search",
            json={"query": "presupuesto", "mode": "chunks", "top_k": 5},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "presupuesto"
    assert data["mode"] == "chunks"
    assert len(data["hits"]) == 1
    assert data["hits"][0]["filename"] == "finanzas.md"
    assert data["hits"][0]["snippet"] == "presupuesto mensual"
    assert data["latency_ms"] >= 0
    assert data["warnings"] == []


@pytest.mark.asyncio
async def test_api_documents_search_422_short_query(client):
    async with client as c:
        resp = await c.post(
            "/api/documents/search",
            json={"query": "a", "mode": "chunks"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_documents_search_503_no_store(client):
    async with client as c:
        resp = await c.post(
            "/api/documents/search",
            json={"query": "test", "mode": "chunks"},
        )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_api_documents_search_503_no_embed(client):
    app_state.vector_store = AsyncMock()
    async with client as c:
        resp = await c.post(
            "/api/documents/search",
            json={"query": "test", "mode": "chunks"},
        )
    assert resp.status_code == 503


# ── Fase 2: answer mode ─────────────────────────────────────────


def _setup_basic_search(store):
    store.search = AsyncMock(
        return_value=[
            SearchResult(
                id="1",
                content="presupuesto mensual",
                source_path="/docs/finanzas.md",
                chunk_index=0,
                score=0.1,
                metadata={},
            ),
        ]
    )


def _setup_embed():
    embed = AsyncMock()
    embed.embed = AsyncMock(return_value=[0.1] * 384)
    return embed


@pytest.mark.asyncio
async def test_api_documents_search_answer_mode_mock_rag(client):
    store = AsyncMock()
    _setup_basic_search(store)
    app_state.vector_store = store
    app_state.embedding_provider = _setup_embed()

    rag = AsyncMock()
    rag.query = AsyncMock(
        return_value=MagicMock(
            answer="El presupuesto mensual es de 500€.",
            sources=["/docs/finanzas.md"],
            chunks_used=1,
            latency_ms=50.0,
            compressed=False,
        )
    )
    app_state.rag_engine = rag

    registry = MagicMock()
    chat = MagicMock()
    chat.is_available = MagicMock(return_value=True)
    registry.get_chat = MagicMock(return_value=chat)
    app_state.provider_registry = registry

    async with client as c:
        resp = await c.post(
            "/api/documents/search",
            json={"query": "presupuesto", "mode": "answer", "top_k": 5},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "answer"
    assert data["answer"] == "El presupuesto mensual es de 500€."
    assert "/docs/finanzas.md" in data["sources"]
    assert data["hits"]  # chunks still returned
    assert data["warnings"] == []


@pytest.mark.asyncio
async def test_api_documents_search_answer_engine_off_degrades(client):
    store = AsyncMock()
    _setup_basic_search(store)
    app_state.vector_store = store
    app_state.embedding_provider = _setup_embed()

    app_state.rag_engine = AsyncMock()

    registry = MagicMock()
    chat = MagicMock()
    chat.is_available = MagicMock(return_value=False)
    registry.get_chat = MagicMock(return_value=chat)
    app_state.provider_registry = registry

    async with client as c:
        resp = await c.post(
            "/api/documents/search",
            json={"query": "presupuesto", "mode": "answer", "top_k": 5},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] is None
    assert data["hits"]  # chunks still returned
    assert "engine_off" in data["warnings"]


@pytest.mark.asyncio
async def test_api_documents_search_answer_no_rag_engine_fallback(client):
    store = AsyncMock()
    _setup_basic_search(store)
    app_state.vector_store = store
    app_state.embedding_provider = _setup_embed()
    app_state.rag_engine = None

    async with client as c:
        resp = await c.post(
            "/api/documents/search",
            json={"query": "presupuesto", "mode": "answer", "top_k": 5},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] is None
    assert "rag_unavailable" in data["warnings"]


@pytest.mark.asyncio
async def test_api_documents_search_source_prefix(client):
    store = AsyncMock()
    store.search = AsyncMock(
        return_value=[
            SearchResult(
                id="1",
                content="a",
                source_path="/docs/finanzas.md",
                chunk_index=0,
                score=0.1,
                metadata={},
            ),
            SearchResult(
                id="2",
                content="b",
                source_path="/other/notas.md",
                chunk_index=0,
                score=0.2,
                metadata={},
            ),
        ]
    )
    app_state.vector_store = store
    app_state.embedding_provider = _setup_embed()

    async with client as c:
        resp = await c.post(
            "/api/documents/search",
            json={"query": "test", "mode": "chunks", "source_prefix": "/docs"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["hits"]) == 1
    assert data["hits"][0]["source_path"] == "/docs/finanzas.md"
    assert len(data["sources"]) == 1

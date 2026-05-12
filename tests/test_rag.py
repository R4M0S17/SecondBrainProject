import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.inference.engine import InferenceEngine
from core.memory.vector_store import SearchResult, VectorStore
from core.rag.query_engine import NO_INFO_RESPONSE, RAGQueryEngine, RAGResponse


def _chunk(source: str, idx: int, content: str) -> SearchResult:
    return SearchResult(
        id=hashlib.sha256(content.encode()).hexdigest(),
        content=content,
        source_path=source,
        chunk_index=idx,
        score=0.9,
        metadata={},
    )


def _make(chunks: list[SearchResult], answer: str):
    store = AsyncMock(spec=VectorStore)
    store.search = AsyncMock(return_value=chunks)

    engine = AsyncMock(spec=InferenceEngine)
    engine.embed = AsyncMock(return_value=[0.1] * 768)
    engine.complete = AsyncMock(return_value=answer)

    return store, engine


@pytest.mark.asyncio
async def test_returns_answer_when_context_relevant():
    chunks = [_chunk("/docs/notes.txt", 0, "The capital of France is Paris.")]
    store, engine = _make(chunks, "Paris is the capital of France.")

    rag = RAGQueryEngine(store=store, engine=engine)
    response = await rag.query("What is the capital of France?")

    assert isinstance(response, RAGResponse)
    assert response.answer == "Paris is the capital of France."
    assert response.chunks_used == 1
    assert response.latency_ms >= 0


@pytest.mark.asyncio
async def test_returns_no_info_string_when_context_irrelevant():
    chunks = [_chunk("/docs/cooking.txt", 0, "Pasta is made from flour and water.")]
    store, engine = _make(chunks, NO_INFO_RESPONSE)

    rag = RAGQueryEngine(store=store, engine=engine)
    response = await rag.query("What is the speed of light?")

    assert response.answer == NO_INFO_RESPONSE


@pytest.mark.asyncio
async def test_sources_list_matches_chunks_used():
    chunks = [
        _chunk("/docs/a.txt", 0, "Content from A."),
        _chunk("/docs/b.txt", 1, "Content from B."),
        _chunk("/docs/a.txt", 2, "More content from A."),
    ]
    store, engine = _make(chunks, "Some answer.")

    rag = RAGQueryEngine(store=store, engine=engine)
    response = await rag.query("Tell me about A and B.")

    assert response.sources == ["/docs/a.txt", "/docs/b.txt"]
    assert response.chunks_used == 3


def test_build_prompt_includes_chunks_and_question():
    rag = RAGQueryEngine(store=MagicMock(), engine=MagicMock())
    chunks = [
        _chunk("/docs/notes.txt", 0, "First chunk content."),
        _chunk("/docs/notes.txt", 1, "Second chunk content."),
    ]
    prompt = rag.build_prompt("What is this about?", chunks)

    assert "First chunk content." in prompt
    assert "Second chunk content." in prompt
    assert "What is this about?" in prompt
    assert "Fuente: notes.txt" in prompt


def test_build_prompt_truncates_oversized_chunk():
    rag = RAGQueryEngine(store=MagicMock(), engine=MagicMock())
    huge_content = "word " * 30_000  # far exceeds budget
    chunks = [_chunk("/docs/big.txt", 0, huge_content)]
    prompt = rag.build_prompt("question?", chunks)

    assert "[truncado]" in prompt


def test_build_prompt_empty_chunks():
    rag = RAGQueryEngine(store=MagicMock(), engine=MagicMock())
    prompt = rag.build_prompt("Any question?", [])

    assert "Pregunta: Any question?" in prompt

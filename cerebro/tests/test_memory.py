import hashlib
from unittest.mock import AsyncMock

import pytest

from core.inference.engine import InferenceEngine
from core.ingestion.pipeline import Document
from core.memory.vector_store import SearchResult, VectorStore


def _doc(source: str, idx: int = 0, mtime: float = 1000.0) -> Document:
    content = f"chunk {idx} from {source}"
    return Document(
        id=hashlib.sha256(content.encode()).hexdigest(),
        content=content,
        source_path=source,
        chunk_index=idx,
        file_modified=mtime,
        metadata={"extension": ".txt"},
    )


def _engine() -> InferenceEngine:
    engine = AsyncMock(spec=InferenceEngine)
    engine.embed = AsyncMock(return_value=[0.1] * 768)
    return engine


@pytest.mark.asyncio
async def test_upsert_without_duplicates(tmp_path):
    store = VectorStore(str(tmp_path / "db"))
    engine = _engine()

    docs = [_doc("/a/file.txt", i) for i in range(3)]
    count = await store.upsert(docs, engine)
    assert count == 3

    # Same mtime → skip, no re-insert
    count2 = await store.upsert(docs, engine)
    assert count2 == 0


@pytest.mark.asyncio
async def test_search_returns_correct_top_k(tmp_path):
    store = VectorStore(str(tmp_path / "db"))
    engine = _engine()

    docs = [_doc("/a/file.txt", i) for i in range(10)]
    await store.upsert(docs, engine)

    results = await store.search("some query", engine, top_k=3)
    assert len(results) == 3
    assert all(isinstance(r, SearchResult) for r in results)


@pytest.mark.asyncio
async def test_delete_by_source_removes_all_chunks(tmp_path):
    store = VectorStore(str(tmp_path / "db"))
    engine = _engine()

    docs_a = [_doc("/a/file.txt", i) for i in range(5)]
    docs_b = [_doc("/b/other.txt", i) for i in range(3)]
    await store.upsert(docs_a + docs_b, engine)

    deleted = store.delete_by_source("/a/file.txt")
    assert deleted == 5

    indexed = store.get_indexed_files()
    assert "/a/file.txt" not in indexed
    assert "/b/other.txt" in indexed


@pytest.mark.asyncio
async def test_reindex_unchanged_file_is_noop(tmp_path):
    store = VectorStore(str(tmp_path / "db"))
    engine = _engine()

    docs = [_doc("/a/file.txt", i, mtime=9999.0) for i in range(3)]
    await store.upsert(docs, engine)
    embed_calls_after_first = engine.embed.call_count

    # Same docs, same mtime → no embed calls, no inserts
    count = await store.upsert(docs, engine)
    assert count == 0
    assert engine.embed.call_count == embed_calls_after_first


@pytest.mark.asyncio
async def test_changed_file_is_reindexed(tmp_path):
    store = VectorStore(str(tmp_path / "db"))
    engine = _engine()

    docs_v1 = [_doc("/a/file.txt", i, mtime=1000.0) for i in range(3)]
    await store.upsert(docs_v1, engine)

    # Same path, different mtime → delete old + insert new
    docs_v2 = [_doc("/a/file.txt", i, mtime=2000.0) for i in range(4)]
    count = await store.upsert(docs_v2, engine)
    assert count == 4

    indexed = store.get_indexed_files()
    assert indexed["/a/file.txt"] == 2000.0


@pytest.mark.asyncio
async def test_get_indexed_files_empty(tmp_path):
    store = VectorStore(str(tmp_path / "db"))
    assert store.get_indexed_files() == {}

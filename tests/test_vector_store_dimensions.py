from __future__ import annotations

import pytest

from core.memory.vector_store import (
    EmbeddingDimensionMismatchError,
    VectorStore,
    _check_vector_dim,
)


def test_check_vector_dim_mismatch():
    with pytest.raises(EmbeddingDimensionMismatchError, match="reindex_embeddings"):
        _check_vector_dim([0.1] * 768, 384)


@pytest.mark.asyncio
async def test_vector_store_rejects_wrong_dim_on_upsert(tmp_path):
    from unittest.mock import AsyncMock, MagicMock

    from core.ingestion.pipeline import Document

    store = VectorStore(str(tmp_path / "db"), embedding_dim=384)
    engine = MagicMock()
    engine.embed = AsyncMock(return_value=[0.1] * 768)
    doc = Document(
        id="1",
        content="hello",
        source_path="/tmp/a.txt",
        chunk_index=0,
        file_modified=1.0,
        metadata={},
    )
    with pytest.raises(EmbeddingDimensionMismatchError):
        await store.upsert([doc], engine)

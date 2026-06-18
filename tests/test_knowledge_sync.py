"""Tests for the Knowledge Sync Agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.knowledge_sync.chunking import ChunkingEngine
from core.knowledge_sync.content_filter import ContentFilter
from core.knowledge_sync.models import (
    FetchedItem,
    SourceType,
    SyncSourceConfig,
    SyncState,
    SyncStatus,
)
from core.knowledge_sync.orchestrator import KnowledgeSyncOrchestrator
from core.knowledge_sync.sources.github_source import GithubSyncSource
from core.knowledge_sync.sources.rss_source import RssSyncSource
from core.knowledge_sync.sources.web_source import WebSyncSource
from core.knowledge_sync.state_store import SyncStateStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_feed_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Test Blog</title>
  <link>https://example.com/blog</link>
  <item>
    <title>First Post</title>
    <link>https://example.com/blog/first</link>
    <description>This is the first post content.</description>
    <author>Author One</author>
    <pubDate>Mon, 01 Jan 2025 00:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Second Post</title>
    <link>https://example.com/blog/second</link>
    <description>This is the second post content.</description>
    <author>Author Two</author>
    <pubDate>Tue, 02 Jan 2025 00:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""


@pytest.fixture
def mock_embed_provider():
    """Return a callable that simulates an embedding provider."""

    async def embed(text: str) -> list[float]:
        return [hash(text) % 100 / 100.0] * 384

    return embed


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    store.upsert = AsyncMock(return_value=3)
    store.search_by_vector = AsyncMock(return_value=[])
    return store


@pytest.fixture
def rss_config() -> SyncSourceConfig:
    return SyncSourceConfig(
        id="rss:example.com/blog",
        source_type=SourceType.RSS,
        uri="https://example.com/blog/feed.xml",
        label="Test Blog",
        interval_minutes=60,
        max_items_per_sync=10,
    )


# ---------------------------------------------------------------------------
# RSS Source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rss_parse_sample(sample_feed_xml: str, rss_config: SyncSourceConfig) -> None:
    source = RssSyncSource(rss_config)
    state = SyncState(source_id=rss_config.id)

    with patch.object(source._client, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"etag": '"abc123"', "content-type": "application/rss+xml"}
        mock_resp.text = sample_feed_xml
        mock_get.return_value = mock_resp

        items = []
        async for item in source.fetch(state):
            items.append(item)

    assert len(items) == 2
    assert items[0].title == "First Post"
    assert items[0].url == "https://example.com/blog/first"
    assert items[0].author == "Author One"
    assert items[0].published_at > 0
    assert state.etag == '"abc123"'


@pytest.mark.asyncio
async def test_rss_304_no_content(rss_config: SyncSourceConfig) -> None:
    source = RssSyncSource(rss_config)
    state = SyncState(source_id=rss_config.id, etag='"old"')

    with patch.object(source._client, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 304
        mock_get.return_value = mock_resp

        items = []
        async for item in source.fetch(state):
            items.append(item)

    assert len(items) == 0


# ---------------------------------------------------------------------------
# GitHub Source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_github_fetch_file() -> None:
    config = SyncSourceConfig(
        id="github:psf/requests",
        source_type=SourceType.GITHUB,
        uri="psf/requests",
    )
    source = GithubSyncSource(config)
    state = SyncState(source_id=config.id)

    mock_contents = [
        {
            "name": "README.md",
            "path": "README.md",
            "type": "file",
            "download_url": "https://raw.githubusercontent.com/psf/requests/main/README.md",
            "sha": "abc123",
        }
    ]

    with patch.object(source._client, "get") as mock_get:

        def _side_effect(url, **kwargs):
            resp = MagicMock()
            if "contents" in url or "repos" in url:
                resp.json.return_value = mock_contents
                resp.status_code = 200
            if "raw.githubusercontent" in url:
                resp.status_code = 200
                resp.text = "# Requests\n\nA simple HTTP library for Python. " * 5
            return resp

        mock_get.side_effect = _side_effect

        items = []
        async for item in source.fetch(state):
            items.append(item)

    assert len(items) == 1
    assert items[0].title == "requests/README.md"
    assert "Requests" in items[0].content
    assert "psf/requests" in items[0].metadata["repo"]


@pytest.mark.asyncio
async def test_github_skip_binary() -> None:
    config = SyncSourceConfig(
        id="github:test/repo",
        source_type=SourceType.GITHUB,
        uri="test/repo",
    )
    source = GithubSyncSource(config)
    state = SyncState(source_id=config.id)

    mock_contents = [
        {
            "name": "logo.png",
            "path": "logo.png",
            "type": "file",
            "download_url": "https://raw.githubusercontent.com/test/repo/main/logo.png",
        },
        {
            "name": "app.exe",
            "path": "app.exe",
            "type": "file",
            "download_url": "https://raw.githubusercontent.com/test/repo/main/app.exe",
        },
    ]

    with patch.object(source._client, "get") as mock_get:
        resp = MagicMock()
        resp.json.return_value = mock_contents
        resp.status_code = 200
        mock_get.return_value = resp

        items = []
        async for item in source.fetch(state):
            items.append(item)

    assert len(items) == 0


# ---------------------------------------------------------------------------
# Web Source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_fetch_extract() -> None:
    config = SyncSourceConfig(
        id="web:example.com",
        source_type=SourceType.WEB,
        uri="https://example.com/article",
        label="Example Article",
    )
    source = WebSyncSource(config)
    state = SyncState(source_id=config.id)

    with (
        patch.object(source._client, "get") as mock_get,
        patch("core.knowledge_sync.sources.web_source.extract") as mock_extract,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><p>" + "Article content here. " * 10 + "</p></body></html>"
        mock_get.return_value = mock_resp
        mock_extract.return_value = "Article content here. " * 10

        items = []
        async for item in source.fetch(state):
            items.append(item)

    assert len(items) == 1
    assert items[0].title == "Example Article"
    assert "Article content" in items[0].content
    assert items[0].url == "https://example.com/article"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def test_chunking_basic() -> None:
    engine = ChunkingEngine(chunk_size=10, chunk_overlap=2, min_chunk=3)
    item = FetchedItem(
        url="https://example.com/post",
        title="Test",
        content="one two three four five six seven eight nine ten eleven twelve",
        published_at=1000.0,
    )
    docs = engine.chunk(item)
    assert len(docs) >= 2
    assert docs[0].source_path == item.url
    assert docs[0].metadata["source_type"] == "knowledge_sync"
    assert docs[0].metadata["title"] == "Test"
    assert docs[0].file_modified == 1000.0


def test_chunking_short_content() -> None:
    engine = ChunkingEngine(chunk_size=10, chunk_overlap=2, min_chunk=50)
    item = FetchedItem(
        url="https://example.com/short",
        title="Short",
        content="too short",
    )
    docs = engine.chunk(item)
    # Short content now creates a single document instead of returning empty
    assert len(docs) == 1
    assert docs[0].content == "too short"


# ---------------------------------------------------------------------------
# Content Filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_embedding_relevance(mock_embed_provider, mock_vector_store) -> None:
    filter_ = ContentFilter(
        embed_provider=mock_embed_provider,
        interest_tags=["AI", "machine learning"],
        relevance_threshold=0.5,
    )
    items = [
        FetchedItem(url="https://a.com/1", title="AI Advances", content="lorem ipsum"),
        FetchedItem(url="https://a.com/2", title="Cooking Recipe", content="lorem ipsum"),
    ]
    # Our mock embed returns hash-based vectors — ensure the first item passes
    first_vec = await mock_embed_provider("tag: AI")
    second_vec = await mock_embed_provider("tag: machine learning")
    tag_arr = np.array([first_vec, second_vec], dtype=np.float32)
    item_vecs = np.array(
        [
            await mock_embed_provider("AI Advances lorem ipsum"),
            await mock_embed_provider("Cooking Recipe lorem ipsum"),
        ],
        dtype=np.float32,
    )
    scores = item_vecs @ tag_arr.T
    max_scores = scores.max(axis=1)
    # At least one should be above 0.5 given same hash logic
    assert any(s >= 0.5 for s in max_scores), "Mock embed should produce some high scores"

    result = await filter_.filter(items, mock_vector_store)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_filter_dedup(mock_embed_provider) -> None:
    filter_ = ContentFilter(
        embed_provider=mock_embed_provider,
        interest_tags=None,
    )
    mock_store = MagicMock()
    mock_store.search_by_vector = AsyncMock(
        return_value=[MagicMock(score=0.3)]  # ≤ dedup_threshold of 0.4 → duplicate
    )

    items = [FetchedItem(url="https://a.com/dup", title="Duplicate Content", content="some text")]
    result = await filter_.filter(items, mock_store)
    assert len(result) == 0  # dedup should skip it


# ---------------------------------------------------------------------------
# State Store
# ---------------------------------------------------------------------------


def test_state_store_save_load(tmp_path: Path) -> None:
    store = SyncStateStore(state_dir=str(tmp_path))
    state = SyncState(
        source_id="rss:test",
        etag='"abc"',
        items_fetched_count=5,
        items_indexed_count=3,
        consecutive_errors=0,
    )
    store.save(state)

    loaded = store.load("rss:test")
    assert loaded.source_id == "rss:test"
    assert loaded.etag == '"abc"'
    assert loaded.items_fetched_count == 5
    assert loaded.items_indexed_count == 3
    assert loaded.status == SyncStatus.IDLE


def test_state_store_load_missing(tmp_path: Path) -> None:
    store = SyncStateStore(state_dir=str(tmp_path))
    state = store.load("nonexistent")
    assert state.source_id == "nonexistent"
    assert state.status == SyncStatus.IDLE


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_ram_gate(tmp_path: Path) -> None:
    registry = MagicMock()
    vector_store = MagicMock()
    engine = MagicMock()
    embed = MagicMock()
    embed.embed = AsyncMock(return_value=[0.1] * 384)

    orch = KnowledgeSyncOrchestrator(
        registry=registry,
        vector_store=vector_store,
        inference_engine=engine,
        embed_provider=embed.embed,
        state_dir=str(tmp_path),
    )

    with patch.object(orch._ram, "snapshot", return_value={"available_gb": 0.2}):
        result = await orch.trigger_sync(force=True)
    assert result["status"] == "error"
    assert "RAM" in result["reason"]


@pytest.mark.asyncio
async def test_orchestrator_full_cycle(tmp_path: Path) -> None:
    registry = MagicMock()
    vector_store = MagicMock()
    vector_store.upsert = AsyncMock(return_value=2)
    vector_store.search_by_vector = AsyncMock(return_value=[])
    engine = MagicMock()
    embed = MagicMock()
    embed.embed = AsyncMock(return_value=[0.1] * 384)

    orch = KnowledgeSyncOrchestrator(
        registry=registry,
        vector_store=vector_store,
        inference_engine=engine,
        embed_provider=embed.embed,
        state_dir=str(tmp_path),
    )

    source_id = "rss:test"
    config = SyncSourceConfig(
        id=source_id,
        source_type=SourceType.RSS,
        uri="https://example.com/feed",
        label="Test",
        interval_minutes=1,
    )
    orch.add_source(config)

    async def _fake_fetch(state):
        yield FetchedItem(url="https://example.com/1", title="Item 1", content="hello world " * 100)
        yield FetchedItem(url="https://example.com/2", title="Item 2", content="lorem ipsum " * 100)

    source = orch._sources[source_id]
    source.fetch = _fake_fetch

    with (
        patch.object(orch._ram, "snapshot", return_value={"available_gb": 4.0}),
        patch("core.knowledge_sync.content_filter._slm_complete", return_value="NOVEDAD_ALTA"),
    ):
        result = await orch.trigger_sync(source_id=source_id, force=True)
        assert result["status"] == "processing"

        if orch._running_pipeline:
            await orch._running_pipeline

    state = orch.get_state(source_id)
    assert state.status == SyncStatus.IDLE
    assert state.items_fetched_count == 2
    assert state.items_indexed_count == 2

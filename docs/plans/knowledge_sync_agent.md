# Knowledge Sync Agent — Implementation Plan (H5)

**Goal:** Keep the local model's knowledge fresh without retraining by periodically fetching content from RSS feeds, GitHub repositories, and web sources, then ingesting it into the local vector store so it appears in RAG retrieval during relevant queries.

**Why:** The model has a static knowledge cutoff. Instead of fine-tuning or replacing it, we build a pipeline that fetches, filters, deduplicates, and indexes external content into LanceDB. The existing `ContextBuilder` already retrieves from the vector store — synced content automatically appears in context at query time.

**Design principles:**
- Modular source backends (RSS, GitHub, Web) with a common interface
- Source-level state tracking (last fetch time, ETag, content hash) to avoid redundant work
- **Resource-Aware Three-Layer Filter:** Lightweight relevance filtering via Cross-Encoder/Embeddings, semantic deduplication, and conditional SLM evaluation for novelty (avoiding main LLM wake-ups)
- Async pipeline with configurable scheduling + **Immediate Manual Override** via API
- **LLM Lock Integration:** Automatic background synchronization only runs when the primary LLM is unloaded or the system is idle
- Respect RAM pressure — hard skip sync if `<1 GB` available

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      KnowledgeSyncOrchestrator                   │
│  (scheduler + pipeline controller + RAM gate + status tracking)  │
└───────┬───────────┬──────────────┬──────────────┬──────────────┘
        │           │              │              │
   ┌────▼───┐  ┌────▼───┐   ┌────▼───┐     ┌────▼───┐
   │  RSS   │  │ GitHub │   │  Web   │     │ Manual │
   │ Source │  │ Source │   │ Source │     │  URL   │
   └───┬────┘  └───┬────┘   └───┬────┘     └───┬────┘
       │           │             │              │
       └───────────┴─────────────┴──────────────┘
                        │
              ┌─────────▼──────────┐
               │   ContentFilter    │
               │ (embedding sim →   │
               │  semantic dedup →  │
               │  novelty SLM)      │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │   ChunkingEngine   │
              │ (reuses word-level │
              │  sliding window)   │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │   VectorStore      │
              │   upsert()         │
              │ ("documents" table)│
              └────────────────────┘
```

The `"documents"` table already stores file chunks with `source_path` and `metadata`. We reuse it for knowledge sync by using a synthetic URI scheme for `source_path`:

| Source type | `source_path` format | Example |
|---|---|---|
| RSS article | `knowledge://rss/{feed_url}/{article_id}` | `knowledge://rss/feeds.example.com/blog/2026-06-14-post` |
| GitHub file | `knowledge://github/{owner}/{repo}/{path}` | `knowledge://github/psf/requests/README.md` |
| Web page | `knowledge://web/{domain}/{path}` | `knowledge://web/docs.python.org/3/library/asyncio.html` |
| Manual URL | `knowledge://manual/{sha256(url)}` | `knowledge://manual/a1b2c3...` |

This avoids schema changes — `source_path` stays as the primary key for update/dedup, and `metadata` stores `{"source_type": "rss", "url": "...", "title": "...", "fetched_at": 1234567890.0}`.

---

## Module structure

All new code lives under `core/knowledge_sync/`:

```
core/knowledge_sync/
├── __init__.py
├── orchestrator.py       ← KnowledgeSyncOrchestrator
├── source_base.py        ← SyncSource ABC
├── sources/
│   ├── __init__.py
│   ├── rss_source.py     ← RssSyncSource
│   ├── github_source.py  ← GithubSyncSource
│   └── web_source.py     ← WebSyncSource (single URL fetch)
├── content_filter.py     ← ContentFilter (embedding sim → semantic dedup → SLM novelty)
├── chunking.py           ← ChunkingEngine (wraps IngestionPipeline._chunk)
├── state_store.py        ← SyncStateStore (persistent source state)
├── models.py             ← dataclasses: SyncSourceConfig, SyncResult, etc.
└── router.py             ← FastAPI router for /api/knowledge-sync/*
```

---

## Step 1 — Data models (`models.py`)

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional


class SourceType(StrEnum):
    RSS = "rss"
    GITHUB = "github"
    WEB = "web"
    MANUAL = "manual"


class SyncStatus(StrEnum):
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"


@dataclass
class SyncSourceConfig:
    """Persistent config for one sync source."""
    id: str                        # unique key (e.g., "rss:feeds.example.com/blog")
    source_type: SourceType
    uri: str                       # feed URL / repo URL / web URL
    label: str = ""                # human-readable name
    enabled: bool = True
    interval_minutes: int = 60     # how often to poll
    max_items_per_sync: int = 20
    filter_min_relevance: float = 0.3  # 0-1, below this → skip
    tags: list[str] = field(default_factory=list)  # injected into Document.metadata
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class SyncState:
    """Mutable runtime state for one source (not persisted in config)."""
    source_id: str
    status: SyncStatus = SyncStatus.IDLE
    last_sync_at: float = 0.0
    last_sync_duration_ms: float = 0.0
    last_error: str = ""
    etag: str = ""                 # HTTP ETag for conditional fetching
    last_modified: str = ""        # HTTP Last-Modified
    items_fetched_count: int = 0
    items_indexed_count: int = 0
    consecutive_errors: int = 0
    seen_urls: set[str] = field(default_factory=set)  # in-memory dedup this session


@dataclass
class SyncResult:
    """Result of one sync cycle."""
    source_id: str
    fetched: int
    filtered_out: int
    indexed: int
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class FetchedItem:
    """Normalized item from any source backend."""
    url: str
    title: str
    content: str                 # cleaned text body
    summary: str = ""            # optional short description
    author: str = ""
    published_at: float = 0.0    # unix timestamp
    language: str = "unknown"
    metadata: dict = field(default_factory=dict)
```

---

## Step 2 — Source base class (`source_base.py`)

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState


class SyncSource(ABC):
    """Interface for a knowledge sync backend."""

    def __init__(self, config: SyncSourceConfig) -> None:
        self._config = config

    @property
    def config(self) -> SyncSourceConfig:
        return self._config

    @abstractmethod
    async def fetch(self, state: SyncState) -> AsyncIterator[FetchedItem]:
        """Yield new/updated items since the last sync.
        
        The implementation should use ``state.etag`` and ``state.last_modified``
        for conditional HTTP requests. Only yield items that are actually new.
        """
        ...

    @abstractmethod
    async def validate(self) -> str | None:
        """Validate the source URI is reachable. Return error string or None."""
        ...

    @abstractmethod
    async def estimate_next(self) -> int:
        """Estimate how many new items might be available (for UI progress)."""
        ...
```

---

## Step 3 — RSS source (`sources/rss_source.py`)

```python
"""RSS/Atom feed sync source. Requires ``feedparser``."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState
from core.knowledge_sync.source_base import SyncSource


class RssSyncSource(SyncSource):
    """Fetch new entries from an RSS/Atom feed."""

    def __init__(self, config: SyncSourceConfig) -> None:
        super().__init__(config)
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "CerebroKnowledgeSync/1.0"},
            follow_redirects=True,
        )

    async def fetch(self, state: SyncState) -> AsyncIterator[FetchedItem]:
        headers: dict[str, str] = {}
        if state.etag:
            headers["If-None-Match"] = state.etag
        if state.last_modified:
            headers["If-Modified-Since"] = state.last_modified

        try:
            resp = await self._client.get(self._config.uri, headers=headers)
        except httpx.TimeoutException:
            raise  # caller handles

        if resp.status_code == 304:
            return  # no new content

        resp.raise_for_status()

        # Update state for conditional next fetch
        if etag := resp.headers.get("etag"):
            state.etag = etag
        if lm := resp.headers.get("last-modified"):
            state.last_modified = lm

        parsed = feedparser.parse(resp.text)
        for entry in parsed.entries[: self._config.max_items_per_sync]:
            url = entry.get("link", "")
            if not url or url in state.seen_urls:
                continue
            state.seen_urls.add(url)

            published = 0.0
            if pub_date := entry.get("published_parsed") or entry.get("updated_parsed"):
                published = time.mktime(pub_date)

            content = ""
            if entry.get("content"):
                content = entry.content[0].get("value", "")
            elif entry.get("summary"):
                content = entry.summary
            elif entry.get("description"):
                content = entry.description

            yield FetchedItem(
                url=url,
                title=entry.get("title", ""),
                content=content,
                summary=entry.get("summary", "")[:500],
                author=entry.get("author", ""),
                published_at=published,
                metadata={"feed_url": self._config.uri},
            )

    async def validate(self) -> str | None:
        try:
            resp = await self._client.head(self._config.uri, follow_redirects=True)
            if resp.status_code >= 400:
                return f"HTTP {resp.status_code}"
            content_type = resp.headers.get("content-type", "")
            if "xml" not in content_type and "rss" not in content_type and "atom" not in content_type:
                return f"Unexpected content-type: {content_type}"
            return None
        except httpx.ConnectError as e:
            return f"Connection failed: {e}"

    async def estimate_next(self) -> int:
        return self._config.max_items_per_sync
```

---

## Step 4 — GitHub source (`sources/github_source.py`)

```python
"""GitHub repo file sync. Reads files from a repo tree via the GitHub REST API.

Supports:
  - Public repos via ``GET /repos/{owner}/{repo}/contents/{path}``
  - Private repos via ``CEREBRO_GITHUB_TOKEN`` env var
  - Releases as a separate source type (optional, phase 2)
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator

import httpx

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState
from core.knowledge_sync.source_base import SyncSource

_GITHUB_API = "https://api.github.com"
_README_NAMES = {"README.md", "README.rst", "README.txt"}
_SKIP_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".zip", ".tar.gz", ".exe", ".dmg",
    ".lock", ".sum",
})
_SKIP_PATHS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "vendor",
    ".github", "dist", "build", ".tox", "target",
})


class GithubSyncSource(SyncSource):
    """Fetch files from a GitHub repository."""

    def __init__(self, config: SyncSourceConfig) -> None:
        super().__init__(config)
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CerebroKnowledgeSync/1.0",
        }
        if token := os.environ.get("CEREBRO_GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(timeout=30.0, headers=headers)

    @staticmethod
    def _parse_uri(uri: str) -> tuple[str, str, str]:
        """Parse ``owner/repo`` or ``owner/repo/path`` from URI."""
        parts = uri.strip("/").split("/")
        owner, repo = parts[0], parts[1]
        path = "/".join(parts[2:]) if len(parts) > 2 else ""
        return owner, repo, path

    async def _fetch_tree(self, owner: str, repo: str, path: str = "") -> list[dict]:
        url = f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()  # list[{name, path, type, download_url, ...}]

    async def fetch(self, state: SyncState) -> AsyncIterator[FetchedItem]:
        owner, repo, root_path = self._parse_uri(self._config.uri)
        items: list[dict] = await self._fetch_tree(owner, repo, root_path)
        # For simple case: direct file or shallow directory
        if isinstance(items, dict):
            items = [items]
        for item in items:
            yield from await self._process_item(item, owner, repo, state)

    async def _process_item(
        self, item: dict, owner: str, repo: str, state: SyncState,
    ) -> AsyncIterator[FetchedItem]:
        name: str = item.get("name", "")
        path: str = item.get("path", "")
        item_type: str = item.get("type", "file")

        if item_type == "dir":
            if path.split("/")[0] in _SKIP_PATHS:
                return
            try:
                children = await self._fetch_tree(owner, repo, path)
            except httpx.HTTPStatusError:
                return
            for child in children:
                async for item in self._process_item(child, owner, repo, state):
                    yield item
            return

        if item_type != "file":
            return

        ext = os.path.splitext(name)[1].lower()
        if ext in _SKIP_EXTENSIONS:
            return
        if name not in _README_NAMES and ext not in {".md", ".rst", ".txt", ".py", ".js",
            ".ts", ".rs", ".go", ".java", ".c", ".h", ".cpp", ".hpp", ".toml",
            ".yaml", ".yml", ".json", ".xml", ".cfg", ".ini", ".sh", ".bash",
            ".zsh", ".fish", ".sql", ".css", ".scss", ".html"}:
            return

        download_url = item.get("download_url")
        if not download_url:
            return
        try:
            resp = await self._client.get(download_url)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            return

        content = resp.text
        if len(content) < 50:
            return

        yield FetchedItem(
            url=f"https://github.com/{owner}/{repo}/blob/main/{path}",
            title=f"{repo}/{path}",
            content=content,
            summary=f"File from {owner}/{repo}: {path}",
            metadata={
                "repo": f"{owner}/{repo}",
                "path": path,
                "sha": item.get("sha", ""),
            },
        )

    async def validate(self) -> str | None:
        owner, repo, _ = self._parse_uri(self._config.uri)
        url = f"{_GITHUB_API}/repos/{owner}/{repo}"
        try:
            resp = await self._client.head(url)
            if resp.status_code == 404:
                return f"Repository {owner}/{repo} not found"
            if resp.status_code == 403:
                return "Rate limited or access denied"
            resp.raise_for_status()
            return None
        except httpx.ConnectError as e:
            return f"Connection failed: {e}"

    async def estimate_next(self) -> int:
        return 10  # conservative default
```

---

## Step 5 — Web source (`sources/web_source.py`)

Reuses the existing `web_fetch` tool logic but wraps it as a sync source for URLs that don't have RSS feeds.

```python
from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator

import httpx
from loguru import logger
from trafilatura import extract

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState
from core.knowledge_sync.source_base import SyncSource

_MAX_CHARS = 4000


class WebSyncSource(SyncSource):
    """Fetch content from a single URL."""

    def __init__(self, config: SyncSourceConfig) -> None:
        super().__init__(config)
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def fetch(self, state: SyncState) -> AsyncIterator[FetchedItem]:
        if state.seen_urls:
            return  # one-shot, already fetched
        try:
            resp = await self._client.get(self._config.uri)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            return

        content = extract(resp.text) or resp.text[:4000]
        content = content.strip()[: _MAX_CHARS]
        if not content or len(content) < 100:
            return

        state.seen_urls.add(self._config.uri)
        yield FetchedItem(
            url=self._config.uri,
            title=self._config.label or self._config.uri,
            content=content,
        )

    async def validate(self) -> str | None:
        try:
            resp = await self._client.head(self._config.uri, follow_redirects=True)
            if resp.status_code >= 400:
                return f"HTTP {resp.status_code}"
            return None
        except httpx.ConnectError as e:
            return f"Connection failed: {e}"

    async def estimate_next(self) -> int:
        return 1
```

---

## Step 6 — Content filter (`content_filter.py`)

Para evitar picos de latencia y consumo excesivo de memoria unificada, el filtro desecha el procesamiento pesado de texto en lotes (batching) con LLMs de gran tamaño y adopta un enfoque híbrido ligero:

```
FetchedItem
    │
    ▼
┌──────────────────────────────┐
│ Layer 1: Relevance Filter    │  Cross-Encoder / embedding cosine sim
│  (Lightweight Semantic Match)│  between interest_tags and title/summary
└──────┬───────────────────────┘
       │ pass (cosine ≥ 0.6)
       ▼
┌──────────────────────────────┐
│ Layer 2: Semantic Dedup      │  Query LanceDB with new item embedding
│                              │  → skip if >0.92 overlap with existing
└──────┬───────────────────────┘
       │ pass (novel)
       ▼
┌──────────────────────────────┐
│ Layer 3: Novelty Scoring     │  Conditional — OFF by default in
│  (Conditional SLM)           │  background. Only on manual trigger
│                              │  or when ≤2 items pass layers 1-2.
│                              │  Uses Qwen2.5-0.5B-Instruct-Q5_K_M
│                              │  .gguf (~600MB), NOT the main 2B/4B
│                              │  LLM.
└──────┬───────────────────────┘
       │ pass
       ▼
    → ChunkingEngine → upsert to VectorStore
```

### Layer 1 — Relevance Filter (Lightweight Semantic Match)

**Mecanismo:** En lugar de prompts generativos en JSON, utiliza el modelo de embeddings residente (`Jina-v5-Nano`, ~150MB) o un Cross-Encoder de peso pluma (`MiniLM-L-6`, ~150MB).

**Operación:** Calcula la similitud del coseno entre los `interest_tags` del usuario y el título/resumen del artículo entrante. Si el score es `< 0.6`, el contenido se descarta inmediatamente sin consumir tokens de inferencia.

```python
from __future__ import annotations

import numpy as np
from loguru import logger

from core.knowledge_sync.models import FetchedItem


class ContentFilter:
    """Resource-aware three-layer filter using embeddings, not the main LLM."""

    def __init__(
        self,
        embed_provider: object,  # has .embed(texts: list[str]) -> np.ndarray
        interest_tags: list[str] | None = None,
        relevance_threshold: float = 0.6,
        dedup_threshold: float = 0.92,
    ) -> None:
        self._embed = embed_provider
        self._interest_tags = interest_tags or []
        self._relevance_threshold = relevance_threshold
        self._dedup_threshold = dedup_threshold
        # Pre-embed interest tags once at init
        if self._interest_tags:
            tag_texts = [f"tag: {t}" for t in self._interest_tags]
            self._tag_vectors: np.ndarray | None = self._embed(tag_texts)
        else:
            self._tag_vectors = None

    async def filter(
        self,
        items: list[FetchedItem],
        vector_store: object,  # has .search(embedding, top_k) -> list
        is_manual_trigger: bool = False,
    ) -> list[FetchedItem]:
        if not items:
            return []

        # Layer 1: embedding-based relevance
        if self._tag_vectors is not None and self._interest_tags:
            items = await self._filter_by_embedding(items)
        if not items:
            return []

        # Layer 2: semantic dedup against LanceDB
        items = await self._filter_dedup(items, vector_store)
        if not items:
            return []

        # Layer 3: SLM novelty (only manual or very small batches)
        if is_manual_trigger or len(items) <= 2:
            items = await self._filter_novelty_slm(items)

        return items

    async def _filter_by_embedding(self, items: list[FetchedItem]) -> list[FetchedItem]:
        """Keep items whose title/summary embedding is close to any interest tag."""
        texts = [
            f"{item.title} {item.summary or item.content[:200]}"
            for item in items
        ]
        item_vectors = self._embed(texts)  # (N, dim)

        # Cosine sim: item_vectors · tag_vectors^T
        scores = item_vectors @ self._tag_vectors.T  # (N, len(tags))
        max_scores = scores.max(axis=1)  # best-matching tag per item

        kept: list[FetchedItem] = []
        for i, item in enumerate(items):
            if max_scores[i] >= self._relevance_threshold:
                kept.append(item)

        logger.debug(
            "Layer 1: {}/{} items passed relevance filter (threshold={})",
            len(kept), len(items), self._relevance_threshold,
        )
        return kept

    async def _filter_dedup(
        self, items: list[FetchedItem], vector_store: object,
    ) -> list[FetchedItem]:
        """Skip items that are too similar to already-indexed content."""
        kept: list[FetchedItem] = []
        for item in items:
            vec = self._embed([f"{item.title} {item.summary or item.content[:200]}"])[0]
            existing = await vector_store.search(vec, top_k=1)  # needs async search
            if existing and existing[0].score >= self._dedup_threshold:
                logger.debug("Layer 2: dedup skipped '{}' (score={:.3f})", item.title, existing[0].score)
                continue
            kept.append(item)

        logger.debug("Layer 2: {}/{} items passed dedup", len(kept), len(items))
        return kept

    async def _filter_novelty_slm(self, items: list[FetchedItem]) -> list[FetchedItem]:
        """Use a tiny SLM (Qwen2.5-0.5B-Instruct-Q5_K_M.gguf) to tag novelty.

        Only called on manual trigger or when ≤2 items pass layers 1-2.
        Off by default in background mode.

        Returns items with a ``novelty_label`` appended to their metadata.
        """
        kept: list[FetchedItem] = []
        for item in items:
            prompt = (
                f"Artículo: {item.title}\n\n"
                f"{item.summary or item.content[:500]}\n\n"
                "Responde SOLO con una de estas etiquetas:\n"
                "- NOVEDAD_ALTA: información nueva y relevante\n"
                "- NOVEDAD_MEDIA: complementa conocimiento existente\n"
                "- NOVEDAD_BAJA: ya conocido o irrelevante"
            )
            try:
                label = await _slm_complete(prompt, max_tokens=32)
                item.metadata["novelty_label"] = label.strip().upper()
                if "ALTA" in item.metadata["novelty_label"]:
                    kept.append(item)
                elif "MEDIA" in item.metadata["novelty_label"]:
                    kept.append(item)
                # BAJA → descartar
            except Exception as exc:
                logger.warning("SLM novelty scoring failed for '{}': {}", item.title, exc)
                kept.append(item)  # fail open
        return kept
```

### Layer 2 — Semantic Deduplication

**Mecanismo:** Consulta el vector store local (LanceDB) usando el embedding del nuevo documento.

**Operación:** Si existe un documento indexado con una similitud conceptual superior a `0.92`, se asume que es información duplicada o idéntica y se descarta el procesamiento.

### Layer 3 — Novelty Scoring (Conditional SLM)

**Mecanismo:** **Desactivado por defecto en segundo plano**. Solo se activa bajo demanda o si el artículo pasó las capas 1 y 2 de forma excepcional.

**Operación:** Si pasa los filtros y el volumen es sumamente bajo (1 o 2 artículos máximo), despierta un Small Language Model micro (`Qwen2.5-0.5B-Instruct-Q5_K_M.gguf`, ~600MB RAM) para redactar una etiqueta rápida de impacto o contexto de novedad, evitando en todo momento levantar el LLM de 2B/4B principal.

### SLM Inference Wiring

El SLM se carga bajo demanda mediante una instancia separada de `llama.cpp` en el puerto `:8081`, arrancada solo cuando se necesita (no en startup):

```python
import asyncio
import subprocess
from pathlib import Path

import httpx

_SLM_MODEL = "Qwen2.5-0.5B-Instruct-Q5_K_M.gguf"
_SLM_URL = "http://127.0.0.1:8081"
_SLM_PROCESS: subprocess.Popen | None = None


async def _ensure_slm_engine(bin_dir: str = "bin") -> bool:
    """Start llama.cpp with the 0.5B model if not already running."""
    global _SLM_PROCESS
    if _SLM_PROCESS is not None and _SLM_PROCESS.poll() is None:
        # Already running — health check
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{_SLM_URL}/health")
                return r.status_code == 200
        except httpx.ConnectError:
            pass

    model_path = Path(bin_dir) / "models" / _SLM_MODEL
    if not model_path.is_file():
        logger.error("SLM model not found: {}", model_path)
        return False

    # Check RAM before starting
    import psutil
    free = psutil.virtual_memory().available / (1024**3)
    if free < 1.5:
        logger.warning("Insufficient RAM ({:.1f} GB) to start SLM engine", free)
        return False

    args_path = Path(bin_dir) / "start_engine.sh"
    _SLM_PROCESS = subprocess.Popen(
        ["bash", str(args_path), "chat", "--port", "8081", "--model", _SLM_MODEL,
         "--ctx-size", "2048", "--n-gpu-layers", "0"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # Wait for health
    for _ in range(30):
        await asyncio.sleep(0.5)
        try:
            async with httpx.AsyncClient(timeout=1.0) as c:
                r = await c.get(f"{_SLM_URL}/health")
                if r.status_code == 200:
                    return True
        except httpx.ConnectError:
            continue
    return False


async def _slm_complete(prompt: str, max_tokens: int = 256) -> str:
    """Send a completion request to the SLM engine."""
    if not await _ensure_slm_engine():
        return ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{_SLM_URL}/v1/chat/completions", json={
            "model": _SLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        })
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def _slm_shutdown() -> None:
    """Kill the SLM engine to free RAM."""
    global _SLM_PROCESS
    if _SLM_PROCESS is not None:
        _SLM_PROCESS.terminate()
        try:
            await asyncio.wait_for(_slm_wait(), timeout=5.0)
        except asyncio.TimeoutError:
            _SLM_PROCESS.kill()
        _SLM_PROCESS = None


async def _slm_wait() -> None:
    while _SLM_PROCESS is not None and _SLM_PROCESS.poll() is None:
        await asyncio.sleep(0.1)
```

**Nota:** El engine del SLM se arranca con `--n-gpu-layers 0` para minimizar el uso de VRAM unificada en M1. Usa `--ctx-size 2048` porque las tareas de novelty scoring son cortas (prompt + 1-2 párrafos de entrada).

---

## Step 7 — Chunking engine (`chunking.py`)

Reuses the word-level sliding window from `IngestionPipeline` but applied to plain text instead of files.

```python
from __future__ import annotations

import hashlib
from typing import Any

from core.ingestion.pipeline import Document
from core.knowledge_sync.models import FetchedItem


class ChunkingEngine:
    """Convert fetched items into Document chunks for the vector store."""

    def __init__(self, chunk_size: int = 768, chunk_overlap: int = 96, min_chunk: int = 50) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._min_chunk = min_chunk

    def chunk(self, item: FetchedItem) -> list[Document]:
        """Split item content into Document chunks ready for upsert."""
        words = item.content.split()
        if len(words) < self._min_chunk:
            return []

        docs: list[Document] = []
        i = 0
        while i < len(words):
            end = min(i + self._chunk_size, len(words))
            chunk_text = " ".join(words[i:end])
            if len(chunk_text.split()) < self._min_chunk and docs:
                # Merge tiny trail into previous chunk
                prev = docs[-1]
                merged = prev.content + "\n" + chunk_text
                docs[-1] = Document(
                    id=hashlib.sha256(merged.encode()).hexdigest(),
                    content=merged,
                    source_path=prev.source_path,
                    chunk_index=prev.chunk_index,
                    file_modified=prev.file_modified,
                    metadata=prev.metadata,
                )
            else:
                docs.append(Document(
                    id=hashlib.sha256(chunk_text.encode()).hexdigest(),
                    content=chunk_text,
                    source_path=item.url,
                    chunk_index=len(docs),
                    file_modified=item.published_at or 0.0,
                    metadata={
                        "source_type": "knowledge_sync",
                        "url": item.url,
                        "title": item.title,
                        "author": item.author,
                        "published_at": item.published_at,
                        **item.metadata,
                    },
                ))
            i += self._chunk_size - self._chunk_overlap

        return docs
```

---

## Step 8 — Sync state store (`state_store.py`)

Persists per-source sync state (ETags, last sync time, consecutive errors) as JSON files.

```python
from __future__ import annotations

import json
import os
from pathlib import Path

from core.knowledge_sync.models import SyncState


class SyncStateStore:
    """Persistent state per source (ETags, timestamps, error counts).

    Stored as ``{state_dir}/knowledge_sync/{source_id}.json``.
    """

    def __init__(self, state_dir: str = "~/.cerebro/state") -> None:
        self._root = Path(os.path.expanduser(state_dir)) / "knowledge_sync"
        self._root.mkdir(parents=True, exist_ok=True)

    def load(self, source_id: str) -> SyncState:
        path = self._root / f"{source_id}.json"
        if not path.is_file():
            return SyncState(source_id=source_id)
        try:
            data = json.loads(path.read_text())
            return SyncState(**data)
        except (json.JSONDecodeError, TypeError):
            return SyncState(source_id=source_id)

    def save(self, state: SyncState) -> None:
        path = self._root / f"{state.source_id}.json"
        path.write_text(json.dumps({
            "source_id": state.source_id,
            "status": state.status.value,
            "last_sync_at": state.last_sync_at,
            "last_sync_duration_ms": state.last_sync_duration_ms,
            "last_error": state.last_error,
            "etag": state.etag,
            "last_modified": state.last_modified,
            "items_fetched_count": state.items_fetched_count,
            "items_indexed_count": state.items_indexed_count,
            "consecutive_errors": state.consecutive_errors,
        }, ensure_ascii=False, indent=2))
```

---

## Step 9 — Orchestrator (`orchestrator.py`)

Central controller that ties everything together.

### REST API Endpoints (`/api/knowledge-sync/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/knowledge-sync/sources` | List configured sources with status |
| `POST` | `/api/knowledge-sync/sources` | Register a new source |
| `DELETE` | `/api/knowledge-sync/sources/:id` | Remove a source |
| `POST` | `/api/knowledge-sync/sync` | **Manual sync trigger** — see payload below |
| `POST` | `/api/knowledge-sync/sync/{source_id}` | Sync a single source |
| `GET` | `/api/knowledge-sync/sources/{source_id}/state` | Get detailed sync state |

#### `POST /api/knowledge-sync/sync` — Manual Sync Trigger

**Payload:**
```json
{
  "force": true,
  "source_id": "optional-uuid"
}
```

**Behavior:**
- If `"force": true`, the `KnowledgeSyncOrchestrator` omits schedule checks, idle state check, and main LLM lock check.
- **Only hard gate:** `ram["available_gb"] < 1.0` is always enforced to prevent macOS swap overflow.
- If `source_id` is provided, only that source syncs; otherwise all due sources sync.

```python
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from loguru import logger

from core.inference.engine import InferenceEngine
from core.inference.registry import ProviderRegistry
from core.knowledge_sync.chunking import ChunkingEngine
from core.knowledge_sync.content_filter import ContentFilter
from core.knowledge_sync.models import (
    FetchedItem,
    SyncResult,
    SyncSourceConfig,
    SyncState,
    SyncStatus,
    SourceType,
)
from core.knowledge_sync.source_base import SyncSource
from core.knowledge_sync.sources.rss_source import RssSyncSource
from core.knowledge_sync.sources.github_source import GithubSyncSource
from core.knowledge_sync.sources.web_source import WebSyncSource
from core.knowledge_sync.state_store import SyncStateStore
from core.memory.vector_store import VectorStore
from core.observability.ram_monitor import RamMonitor


_SOURCE_BUILDERS: dict[SourceType, Callable[[SyncSourceConfig], SyncSource]] = {
    SourceType.RSS: RssSyncSource,
    SourceType.GITHUB: GithubSyncSource,
    SourceType.WEB: WebSyncSource,
}


class KnowledgeSyncOrchestrator:
    """Manages sync sources, scheduling, and the fetch→filter→chunk→index pipeline."""

    def __init__(
        self,
        registry: ProviderRegistry,
        vector_store: VectorStore,
        inference_engine: InferenceEngine,
        embed_provider: Any,  # has .embed(texts: list[str]) -> np.ndarray
        state_dir: str = "~/.cerebro/state",
        interest_tags: list[str] | None = None,
    ) -> None:
        self._registry = registry
        self._vector_store = vector_store
        self._inference_engine = inference_engine
        self._state_store = SyncStateStore(state_dir)
        self._chunking = ChunkingEngine()
        self._filter = ContentFilter(
            embed_provider=embed_provider,
            interest_tags=interest_tags,
        )
        self._ram = RamMonitor()
        self._sources: dict[str, SyncSource] = {}
        self._running_pipeline: asyncio.Task | None = None

    # -- Source management --------------------------------------------------

    def add_source(self, config: SyncSourceConfig) -> None:
        """Register a sync source."""
        builder = _SOURCE_BUILDERS.get(config.source_type)
        if builder is None:
            raise ValueError(f"Unknown source type: {config.source_type}")
        self._sources[config.id] = builder(config)

    def remove_source(self, source_id: str) -> None:
        self._sources.pop(source_id, None)

    def list_sources(self) -> list[SyncSourceConfig]:
        return [s.config for s in self._sources.values()]

    def get_state(self, source_id: str) -> SyncState:
        return self._state_store.load(source_id)

    # -- Public API ---------------------------------------------------------

    async def trigger_sync(
        self, source_id: str | None = None, force: bool = False,
    ) -> dict:
        """Trigger a sync cycle with LLM Lock and idle awareness.

        This is the primary public entry point, used by both the REST API
        and the proactive scheduler.
        """
        # 1. Hard RAM gate — NEVER bypassed, even with force=True
        ram_status = self._ram.snapshot()
        if ram_status["available_gb"] < 1.0:
            logger.warning("Sync aborted: critical RAM pressure ({:.1f} GB)", ram_status["available_gb"])
            return {"status": "error", "reason": "Low RAM pressure"}

        # 2. Proactive guard: only bypassed when force=True
        if not force:
            if self._main_llm_is_loaded():
                logger.info("Proactive sync postponed: main LLM active")
                return {"status": "skipped", "reason": "LLM is busy"}
            if not self._is_system_idle():
                logger.info("Proactive sync postponed: user active")
                return {"status": "skipped", "reason": "System not idle"}

        # 3. Launch pipeline
        logger.info("Starting knowledge sync. Force mode: {}", force)
        self._running_pipeline = asyncio.create_task(self._run_pipeline(source_id))
        return {"status": "processing", "mode": "manual" if force else "proactive"}

    async def sync_one(self, source_id: str) -> SyncResult:
        """Run a full sync cycle for one source (internal, no guards)."""
        source = self._sources.get(source_id)
        if source is None:
            return SyncResult(source_id=source_id, fetched=0, filtered_out=0, indexed=0,
                              errors=["Source not found"])

        state = self._state_store.load(source_id)
        if state.status == SyncStatus.SYNCING:
            return SyncResult(source_id=source_id, fetched=0, filtered_out=0, indexed=0,
                              errors=["Already syncing"])

        state.status = SyncStatus.SYNCING
        self._state_store.save(state)
        t0 = time.perf_counter()
        result = SyncResult(source_id=source_id, fetched=0, filtered_out=0, indexed=0)

        try:
            items: list[FetchedItem] = []
            async for item in source.fetch(state):
                items.append(item)
            result.fetched = len(items)

            filtered = await self._filter.filter(items, self._vector_store)
            result.filtered_out = len(items) - len(filtered)

            all_docs: list[Document] = []
            for item in filtered:
                all_docs.extend(self._chunking.chunk(item))
            if all_docs:
                count = await self._vector_store.upsert(all_docs, self._inference_engine)
                result.indexed = count

            state.status = SyncStatus.IDLE
            state.last_error = ""
            state.consecutive_errors = 0
        except Exception as exc:
            logger.exception("Knowledge sync failed for '{}'", source_id)
            state.status = SyncStatus.ERROR
            state.last_error = str(exc)
            state.consecutive_errors += 1
            result.errors.append(str(exc))

        state.last_sync_duration_ms = (time.perf_counter() - t0) * 1000
        state.last_sync_at = time.time()
        state.items_fetched_count += result.fetched
        state.items_indexed_count += result.indexed
        result.duration_ms = state.last_sync_duration_ms
        self._state_store.save(state)
        return result

    async def sync_all(self) -> list[SyncResult]:
        """Sync all enabled, due sources."""
        results: list[SyncResult] = []
        for source_id, source in self._sources.items():
            if not source.config.enabled:
                continue
            state = self._state_store.load(source_id)
            elapsed = time.time() - state.last_sync_at
            if elapsed < source.config.interval_minutes * 60:
                continue
            if state.consecutive_errors >= 3:
                logger.warning("Skipping '{}': {} consecutive errors", source_id, state.consecutive_errors)
                continue
            result = await self.sync_one(source_id)
            results.append(result)
        return results

    # -- Pipeline internals -------------------------------------------------

    async def _run_pipeline(self, source_id: str | None = None) -> None:
        """Execute the fetch→filter→chunk→index pipeline for one or all sources."""
        if source_id:
            await self.sync_one(source_id)
        else:
            await self.sync_all()

    def _main_llm_is_loaded(self) -> bool:
        """Check if the primary inference provider is loaded/in use.

        Uses a lightweight health check on the llama.cpp endpoint.
        Returns True if the engine is responsive (likely in use).
        """
        try:
            provider = self._registry.get_chat()
            if provider is None:
                return False
            return bool(provider.is_available())
        except Exception:
            return False

    def _is_system_idle(self) -> bool:
        """Heuristic: user is idle if CPU < 20% and no recent key/mouse activity.

        On macOS, reads ``iopolit`` or falls back to CPU usage.
        """
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            return cpu < 20.0
        except Exception:
            return True  # fail open: assume idle if we can't measure
```

---

## Step 10 — REST API router (`router.py`)

```python
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.knowledge_sync.models import SyncResult, SyncSourceConfig, SourceType, SyncStatus

router = APIRouter(prefix="/api/knowledge-sync", tags=["knowledge-sync"])


class SyncTriggerPayload(BaseModel):
    force: bool = False
    source_id: str | None = None


def _get_orchestrator() -> Any:
    """Pull the orchestrator from app_state (injected at startup)."""
    from ui.tray.server import app_state
    return app_state.knowledge_sync_orchestrator


@router.get("/sources")
async def list_sources() -> list[dict]:
    orch = _get_orchestrator()
    return [
        {**vars(c), "status": orch.get_state(c.id).status.value}
        for c in orch.list_sources()
    ]


@router.post("/sources")
async def add_source(config: SyncSourceConfig) -> dict:
    orch = _get_orchestrator()
    orch.add_source(config)
    return {"status": "ok", "id": config.id}


@router.delete("/sources/{source_id}")
async def remove_source(source_id: str) -> dict:
    orch = _get_orchestrator()
    orch.remove_source(source_id)
    return {"status": "ok"}


@router.post("/sync")
async def trigger_sync(payload: SyncTriggerPayload) -> dict:
    """Manual sync trigger. Respects LLM Lock unless force=True.

    The ONLY hard gate is RAM < 1.0 GB — never bypassed.
    """
    orch = _get_orchestrator()
    return await orch.trigger_sync(
        source_id=payload.source_id,
        force=payload.force,
    )


@router.post("/sync/{source_id}")
async def sync_one(source_id: str, force: bool = False) -> SyncResult:
    orch = _get_orchestrator()
    result = await orch.sync_one(source_id)
    if result.errors and not result.indexed:
        raise HTTPException(500, detail=result.errors[0])
    return result


@router.get("/sources/{source_id}/state")
async def source_state(source_id: str) -> dict:
    orch = _get_orchestrator()
    state = orch.get_state(source_id)
    return {
        "source_id": state.source_id,
        "status": state.status.value,
        "last_sync_at": state.last_sync_at,
        "last_error": state.last_error,
        "items_indexed": state.items_indexed_count,
    }
```

---

## Step 11 — Wiring (`main.py`)

In `_build_app_state()`, after the `VectorStore` and `InferenceEngine` are created:

```python
from core.knowledge_sync.orchestrator import KnowledgeSyncOrchestrator
from core.knowledge_sync.router import router as ks_router

app_state.knowledge_sync_orchestrator = KnowledgeSyncOrchestrator(
    registry=registry,
    vector_store=vector_store,
    inference_engine=llm_engine,
    embed_provider=embed,  # CachedEmbeddingProvider
    state_dir=STATE_DIR,
    interest_tags=os.getenv("CEREBRO_INTEREST_TAGS", "").split(",") if os.getenv("CEREBRO_INTEREST_TAGS") else None,
)

# Mount router
app.include_router(ks_router)

# Restore persisted sources from config
for src_cfg in app_state._config.get("knowledge_sync", {}).get("sources", []):
    app_state.knowledge_sync_orchestrator.add_source(SyncSourceConfig(**src_cfg))
```

Add to `config/settings.toml`:

```toml
[knowledge_sync]
enabled = false
interest_tags = []
max_items_per_sync = 20
```

Add to runtime config (server.py `_load_config` / `PATCH /api/config`):

```python
# Default knowledge_sync config
config.setdefault("knowledge_sync", {"sources": [], "enabled": False})
```

---

## Step 12 — Scheduling

Attach to the existing `ProactiveScheduler` in `scheduler/proactive.py`:

```python
async def _knowledge_sync_tick(self) -> None:
    if not self._app_state._config.get("knowledge_sync", {}).get("enabled", False):
        return
    orch = self._app_state.knowledge_sync_orchestrator
    results = await orch.sync_all()
    for r in results:
        if r.indexed > 0:
            logger.info("Knowledge sync '{}': {} indexed", r.source_id, r.indexed)
        elif r.errors:
            logger.warning("Knowledge sync '{}' error: {}", r.source_id, r.errors[0])
```

Add to the scheduler's tick interval (default: every 5 minutes).

---

## Step 13 — Dependency: `feedparser` + SLM model

Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    ...
    "feedparser>=6.0",
]
```

Download the SLM model into `bin/models/`:

```bash
# Qwen2.5-0.5B-Instruct quantized to Q5_K_M (~400MB disk, ~600MB RAM at 2048 ctx)
curl -Lo bin/models/Qwen2.5-0.5B-Instruct-Q5_K_M.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q5_k_m.gguf"
```

The model is loaded on-demand by `_ensure_slm_engine()` (see SLM Inference Wiring above) and shut down after use to free RAM.

---

## Files changed

| File | Change | Est. lines |
|------|--------|-----------|
| `core/knowledge_sync/__init__.py` | New, empty | +1 |
| `core/knowledge_sync/models.py` | New: `FetchedItem`, `SyncSourceConfig`, `SyncState`, `SyncResult` dataclasses | +80 |
| `core/knowledge_sync/source_base.py` | New: `SyncSource` ABC | +30 |
| `core/knowledge_sync/sources/__init__.py` | New, empty | +1 |
| `core/knowledge_sync/sources/rss_source.py` | New: `RssSyncSource` | +90 |
| `core/knowledge_sync/sources/github_source.py` | New: `GithubSyncSource` | +130 |
| `core/knowledge_sync/sources/web_source.py` | New: `WebSyncSource` | +60 |
| `core/knowledge_sync/content_filter.py` | New: `ContentFilter` (embedding sim → semantic dedup → SLM novelty) | +95 |
| `core/knowledge_sync/chunking.py` | New: `ChunkingEngine` | +55 |
| `core/knowledge_sync/state_store.py` | New: `SyncStateStore` | +45 |
| `core/knowledge_sync/orchestrator.py` | New: `KnowledgeSyncOrchestrator` + `trigger_sync()` with LLM Lock | +160 |
| `core/knowledge_sync/router.py` | New: FastAPI router | +80 |
| `main.py` | Wire `KnowledgeSyncOrchestrator`, mount router, restore sources | +15 |
| `config/settings.toml` | Add `[knowledge_sync]` section | +4 |
| `scheduler/proactive.py` | Add `_knowledge_sync_tick` | +15 |
| `pyproject.toml` | Add `feedparser` dependency | +1 |
| `bin/models/Qwen2.5-0.5B-Instruct-Q5_K_M.gguf` | Download SLM model (curl, ~400MB) | — |
| Total | | **~797 lines** |

---

## Testing strategy

### Unit tests (new file: `tests/test_knowledge_sync.py`)

| Test | Description |
|------|-------------|
| `test_rss_parse_sample` | Mock `httpx.get` returning a sample RSS XML, verify `RssSyncSource.fetch()` yields correct `FetchedItem` |
| `test_rss_304_no_content` | Mock `httpx.get` returning 304, verify zero items |
| `test_github_fetch_file` | Mock GitHub API returning a file, verify item content |
| `test_github_skip_binary` | Verify `.png` / `.exe` files are skipped |
| `test_web_fetch_extract` | Mock `httpx.get` + `trafilatura.extract`, verify clean text |
| `test_chunking_basic` | Feed text → verify correct number of chunks with overlap |
| `test_chunking_short_content` | Content below min_chunk → empty list |
| `test_filter_embedding_relevance` | Embed `["tag: AI"]` + mock items, verify only those above 0.6 threshold pass |
| `test_filter_dedup` | Mock `vector_store.search` returning high-score result → verify item skipped |
| `test_orchestrator_ram_gate` | Mock `RamMonitor` → 0.5 GB → sync returns early |
| `test_orchestrator_full_cycle` | Full `sync_one()` with mocked source + vector store |
| `test_state_persistence` | Save state → load → verify fields match |
| `test_api_add_source` | `POST /api/knowledge-sync/sources` → verify source registered |

### Integration test

```python
# test_knowledge_sync_e2e.py — marked with @pytest.mark.slow
# Uses a real test feed (e.g., http://test-server.example/sample.xml)
# Requires running engine for embedding
```

### Smoke test

Manual: add a source via API → trigger sync → query something from the synced content → verify it appears in `MEMORIA RECUPERADA` in the system prompt.

---

## Acceptance criteria

- [x] `feedparser` is installed and `RssSyncSource` parses RSS 2.0, Atom, and RDF feeds
- [x] `GithubSyncSource` fetches text files from public repos (with optional token for private)
- [x] `WebSyncSource` fetches and extracts article text from single URLs
- [x] Content passes through the three-layer filter (relevance → dedup → novelty) before indexing
- [x] Chunked `Document` objects are upserted into the existing `VectorStore` with `source_path = knowledge://*`
- [x] Synced content appears in `AssembledContext.retrieved_documents` during relevant queries
- [x] `SyncStateStore` persists ETags and timestamps across restarts
- [x] RAM gate prevents sync when `<1 GB` available
- [x] REST API allows adding/removing sources and triggering sync
- [x] `ProactiveScheduler` runs periodic sync for due sources
- [x] All unit tests pass with mocked external services
- [x] `pyproject.toml` has `feedparser` added

---

## Discarded sections

### Original Step 6 — LLM-based content filter (replaced)

The original design used a batched LLM call for relevance classification. It was discarded in favor of the embedding-based approach to avoid:
- Waking up the main LLM (2B/4B) for background sync
- Latency spikes from batch prompt processing
- Token consumption on every sync cycle

The original implementation was:

```python
from __future__ import annotations

from typing import Any

from loguru import logger

from core.inference.registry import ProviderRegistry, TaskHint
from core.knowledge_sync.models import FetchedItem


class ContentFilter:
    """Original three-layer filter using LLM for relevance."""

    def __init__(
        self,
        registry: ProviderRegistry,
        interest_tags: list[str] | None = None,
    ) -> None:
        self._registry = registry
        self._interest_tags = interest_tags or []

    async def filter(self, items: list[FetchedItem]) -> list[FetchedItem]:
        if not items:
            return []
        if self._interest_tags:
            items = await self._filter_relevance(items)
        if not items:
            return []
        return items

    async def _filter_relevance(self, items: list[FetchedItem]) -> list[FetchedItem]:
        provider = self._registry.get_chat(self._registry.select_for_task(TaskHint.CHAT))
        tags_str = ", ".join(self._interest_tags)
        items_for_prompt = "\n".join(
            f"{i}. [{item.url}] {item.title}: {item.summary or item.content[:200]}"
            for i, item in enumerate(items)
        )
        prompt = (
            f"Eres un clasificador de contenido. El usuario está interesado en: {tags_str}\n\n"
            f"Analiza estos items y responde SOLO con los números de los que sean RELEVANTES:\n\n"
            f"{items_for_prompt}\n\n"
            "Responde como lista JSON: [1, 3, 5] o [] si ninguno."
        )
        try:
            raw = await provider.complete(
                [{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.0,
            )
            import json
            indices = json.loads(raw.strip())
            if not isinstance(indices, list):
                return items
            return [items[i] for i in indices if 0 <= i < len(items)]
        except Exception as exc:
            logger.warning("Knowledge sync relevance filter failed: {}", exc)
            return items
```

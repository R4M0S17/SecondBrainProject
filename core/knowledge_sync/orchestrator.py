from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from loguru import logger

from core.inference.engine import InferenceEngine
from core.inference.registry import ProviderRegistry
from core.ingestion.pipeline import Document
from core.knowledge_sync.chunking import ChunkingEngine
from core.knowledge_sync.content_filter import ContentFilter
from core.knowledge_sync.models import (
    FetchedItem,
    SourceType,
    SyncResult,
    SyncSourceConfig,
    SyncState,
    SyncStatus,
)
from core.knowledge_sync.source_base import SyncSource
from core.knowledge_sync.sources.arxiv_source import ArxivSyncSource
from core.knowledge_sync.sources.github_source import GithubSyncSource
from core.knowledge_sync.sources.pubmed_source import PubMedSyncSource
from core.knowledge_sync.sources.rss_source import RssSyncSource
from core.knowledge_sync.sources.web_source import WebSyncSource
from core.knowledge_sync.sources.youtube_source import YoutubeSyncSource
from core.knowledge_sync.state_store import SyncStateStore
from core.memory.vector_store import VectorStore
from core.observability.ram_monitor import RamMonitor

# Progress callback type: stage name -> data dict
ProgressCallback = Callable[[str, dict], Awaitable[None]]

_SOURCE_BUILDERS: dict[SourceType, Callable[[SyncSourceConfig], SyncSource]] = {
    SourceType.RSS: RssSyncSource,
    SourceType.GITHUB: GithubSyncSource,
    SourceType.WEB: WebSyncSource,
    SourceType.ARXIV: ArxivSyncSource,
    SourceType.YOUTUBE: YoutubeSyncSource,
    SourceType.PUBMED: PubMedSyncSource,
}


class KnowledgeSyncOrchestrator:
    def __init__(
        self,
        registry: ProviderRegistry,
        vector_store: VectorStore,
        inference_engine: InferenceEngine,
        embed_provider: Any,
        state_dir: str = "~/.cerebro/state",
        interest_tags: list[str] | None = None,
    ) -> None:
        self._registry = registry
        self._vector_store = vector_store
        self._inference_engine = inference_engine
        self._embed_provider = embed_provider
        self._state_store = SyncStateStore(state_dir)
        self._chunking = ChunkingEngine()
        self._filter = ContentFilter(
            embed_provider=embed_provider,
            interest_tags=interest_tags,
        )
        self._ram = RamMonitor()
        self._sources: dict[str, SyncSource] = {}
        self._running_pipeline: asyncio.Task | None = None

    def add_source(self, config: SyncSourceConfig) -> None:
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

    async def trigger_sync(
        self,
        source_id: str | None = None,
        force: bool = False,
    ) -> dict:
        ram_status = self._ram.snapshot()
        if ram_status["available_gb"] < 0.3:
            logger.warning(
                "Sync aborted: critical RAM pressure ({:.1f} GB)", ram_status["available_gb"]
            )
            return {"status": "error", "reason": "Low RAM pressure"}

        if not force:
            if self._main_llm_is_loaded():
                logger.info("Proactive sync postponed: main LLM active")
                return {"status": "skipped", "reason": "LLM is busy"}
            if not self._is_system_idle():
                logger.info("Proactive sync postponed: user active")
                return {"status": "skipped", "reason": "System not idle"}

        logger.info("Starting knowledge sync. Force mode: {}", force)

        if source_id:
            # Direct sync (no background task for single source)
            result = await self.sync_one(source_id)
            return {
                "status": "processing",
                "result": {
                    "fetched": result.fetched,
                    "filtered_out": result.filtered_out,
                    "indexed": result.indexed,
                    "errors": result.errors,
                },
                "mode": "manual" if force else "proactive",
            }
        else:
            self._running_pipeline = asyncio.create_task(
                self._sync_all_forced() if force else self._run_pipeline(None)
            )

            return {"status": "processing", "mode": "manual" if force else "proactive"}

    async def sync_one(
        self,
        source_id: str,
        force: bool = False,
        progress_cb: ProgressCallback | None = None,
    ) -> SyncResult:
        source = self._sources.get(source_id)
        if source is None:
            return SyncResult(
                source_id=source_id,
                fetched=0,
                filtered_out=0,
                indexed=0,
                errors=["Source not found"],
            )

        state = self._state_store.load(source_id)
        if state.status == SyncStatus.SYNCING:
            return SyncResult(
                source_id=source_id,
                fetched=0,
                filtered_out=0,
                indexed=0,
                errors=["Already syncing"],
            )

        state.status = SyncStatus.SYNCING
        self._state_store.save(state)
        t0 = time.perf_counter()
        result = SyncResult(source_id=source_id, fetched=0, filtered_out=0, indexed=0)

        try:
            if progress_cb:
                await progress_cb(
                    "fetch", {"source": source_id, "label": source.config.label or source_id}
                )
            items: list[FetchedItem] = []
            async for item in source.fetch(state):
                items.append(item)
            result.fetched = len(items)

            if progress_cb:
                await progress_cb("filter", {"source": source_id, "items": result.fetched})
            filtered = await self._filter.filter(items, self._vector_store, is_manual_trigger=force)
            result.filtered_out = len(items) - len(filtered)

            if progress_cb:
                await progress_cb(
                    "chunk",
                    {"source": source_id, "passed": len(filtered), "filtered": result.filtered_out},
                )
            all_docs: list[Document] = []
            for item in filtered:
                all_docs.extend(self._chunking.chunk(item))

            if progress_cb:
                await progress_cb("index", {"source": source_id, "chunks": len(all_docs)})
            if all_docs:
                count = await self._vector_store.upsert(all_docs, self._embed_provider)
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
        if progress_cb:
            await progress_cb(
                "complete",
                {"source_id": source_id, "indexed": result.indexed, "errors": result.errors},
            )
        return result

    async def sync_all(self) -> list[SyncResult]:
        results: list[SyncResult] = []
        for source_id, source in self._sources.items():
            if not source.config.enabled:
                continue
            state = self._state_store.load(source_id)
            if not self._should_sync_now(source.config, state):
                continue
            if state.consecutive_errors >= 3:
                logger.warning(
                    "Skipping '{}': {} consecutive errors", source_id, state.consecutive_errors
                )
                continue
            result = await self.sync_one(source_id)
            results.append(result)
        return results

    @staticmethod
    def _should_sync_now(config: SyncSourceConfig, state: SyncState) -> bool:
        if config.schedule_cron:
            try:
                from croniter import croniter

                base = (
                    datetime.fromtimestamp(state.last_sync_at)
                    if state.last_sync_at > 0
                    else datetime.now()
                )
                next_sync = croniter(config.schedule_cron, base).get_next(datetime)
                return datetime.now() >= next_sync
            except (ValueError, KeyError):
                logger.warning(
                    "Invalid cron expression '{}', falling back to interval", config.schedule_cron
                )
                pass
        elapsed = time.time() - state.last_sync_at
        if elapsed < config.interval_minutes * 60:
            return False
        return True

    async def _sync_all_forced(self) -> list[SyncResult]:
        results: list[SyncResult] = []
        for source_id in list(self._sources.keys()):
            result = await self.sync_one(source_id)
            results.append(result)
        return results

    async def _run_pipeline(self, source_id: str | None = None) -> None:
        if source_id:
            await self.sync_one(source_id)
        else:
            await self.sync_all()

    def _main_llm_is_loaded(self) -> bool:
        try:
            provider = self._registry.get_chat()
            if provider is None:
                return False
            return bool(provider.is_available())
        except Exception:
            return False

    def _is_system_idle(self) -> bool:
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=0.1)
            return cpu < 20.0
        except Exception:
            return True

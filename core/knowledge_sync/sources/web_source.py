from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from trafilatura import extract

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState
from core.knowledge_sync.source_base import SyncSource

_MAX_CHARS = 4000


class WebSyncSource(SyncSource):
    def __init__(self, config: SyncSourceConfig) -> None:
        super().__init__(config)
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def fetch(self, state: SyncState) -> AsyncIterator[FetchedItem]:
        if state.seen_urls:
            return
        try:
            resp = await self._client.get(self._config.uri)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            return

        content = extract(resp.text) or resp.text[:4000]
        content = content.strip()[:_MAX_CHARS]
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

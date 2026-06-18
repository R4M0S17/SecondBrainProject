from __future__ import annotations

import time
from collections.abc import AsyncIterator

import feedparser
import httpx

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState
from core.knowledge_sync.source_base import SyncSource


class RssSyncSource(SyncSource):
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
            raise

        if resp.status_code == 304:
            return

        resp.raise_for_status()

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
            if (
                "xml" not in content_type
                and "rss" not in content_type
                and "atom" not in content_type
            ):
                return f"Unexpected content-type: {content_type}"
            return None
        except httpx.ConnectError as e:
            return f"Connection failed: {e}"

    async def estimate_next(self) -> int:
        return self._config.max_items_per_sync

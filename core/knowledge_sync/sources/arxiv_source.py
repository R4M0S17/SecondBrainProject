from __future__ import annotations

import time
import urllib.parse
from collections.abc import AsyncIterator
from xml.etree import ElementTree

import httpx

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState
from core.knowledge_sync.source_base import SyncSource

_ARXIV_API = "http://export.arxiv.org/api/query"
_MAX_PAGE_CHARS = 20_000


class ArxivSyncSource(SyncSource):
    def __init__(self, config: SyncSourceConfig) -> None:
        super().__init__(config)
        self._client = httpx.AsyncClient(timeout=60.0)

    async def _search_query(self) -> str:
        tags = self._config.tags or ["cs", "ai"]
        return "+OR+".join(f"cat:{t}" for t in tags)

    async def fetch(self, state: SyncState) -> AsyncIterator[FetchedItem]:
        query = await self._search_query()
        max_results = min(self._config.max_items_per_sync, 30)
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": str(max_results),
        }
        try:
            resp = await self._client.get(f"{_ARXIV_API}?{urllib.parse.urlencode(params)}")
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            return

        root = ElementTree.fromstring(resp.text)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns):
            arxiv_id = entry.find("a:id", ns)
            if arxiv_id is None:
                continue
            url = arxiv_id.text.strip()
            if url in state.seen_urls:
                continue
            state.seen_urls.add(url)

            title_el = entry.find("a:title", ns)
            title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""

            summary_el = entry.find("a:summary", ns)
            summary = (
                (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""
            )
            summary = summary[:_MAX_PAGE_CHARS]

            published_el = entry.find("a:published", ns)
            published = 0.0
            if published_el is not None and published_el.text:
                try:
                    published = time.mktime(time.strptime(published_el.text[:10], "%Y-%m-%d"))
                except (ValueError, OSError):
                    pass

            authors: list[str] = []
            for author_el in entry.findall("a:author", ns):
                name_el = author_el.find("a:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())

            content = f"Title: {title}\n\nAuthors: {', '.join(authors)}\n\nAbstract: {summary}"

            yield FetchedItem(
                url=url,
                title=title,
                content=content,
                summary=summary[:500],
                author=", ".join(authors),
                published_at=published,
                metadata={"source": "arxiv", "arxiv_id": url.split("/")[-1]},
            )

    async def validate(self) -> str | None:
        try:
            resp = await self._client.get(f"{_ARXIV_API}?search_query=cat:cs&max_results=1")
            if resp.status_code >= 400:
                return f"arXiv API returned HTTP {resp.status_code}"
            return None
        except httpx.ConnectError as e:
            return f"Connection failed: {e}"

    async def estimate_next(self) -> int:
        return self._config.max_items_per_sync

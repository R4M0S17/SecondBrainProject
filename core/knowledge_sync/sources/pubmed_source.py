from __future__ import annotations

import time
import urllib.parse
from collections.abc import AsyncIterator
from xml.etree import ElementTree

import httpx

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState
from core.knowledge_sync.source_base import SyncSource

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_MAX_ABSTRACT_CHARS = 20_000


class PubMedSyncSource(SyncSource):
    def __init__(self, config: SyncSourceConfig) -> None:
        super().__init__(config)
        self._client = httpx.AsyncClient(timeout=60.0)

    async def _esearch(self, term: str, retmax: int = 10) -> list[str]:
        params = {
            "db": "pubmed",
            "term": term,
            "retmax": str(retmax),
            "retmode": "json",
        }
        try:
            resp = await self._client.get(
                f"{_EUTILS_BASE}/esearch.fcgi?{urllib.parse.urlencode(params)}"
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("esearchresult", {}).get("idlist", [])
        except (httpx.HTTPStatusError, ValueError):
            return []

    async def _efetch(self, pmid: str) -> FetchedItem | None:
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
            "rettype": "abstract",
        }
        try:
            resp = await self._client.get(
                f"{_EUTILS_BASE}/efetch.fcgi?{urllib.parse.urlencode(params)}"
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            return None

        root = ElementTree.fromstring(resp.text)
        article = root.find(".//PubmedArticle")
        if article is None:
            return None

        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else ""

        abstract_el = article.find(".//AbstractText")
        abstract = "".join(abstract_el.itertext()) if abstract_el is not None else ""
        abstract = abstract[:_MAX_ABSTRACT_CHARS]

        authors: list[str] = []
        for author_el in article.findall(".//Author"):
            last = author_el.find("LastName")
            fore = author_el.find("ForeName")
            if last is not None and last.text:
                name = last.text
                if fore is not None and fore.text:
                    name = f"{fore.text} {name}"
                authors.append(name)

        pub_date_el = article.find(".//PubDate/Year")
        published = 0.0
        if pub_date_el is not None and pub_date_el.text:
            try:
                published = time.mktime(time.strptime(pub_date_el.text, "%Y"))
            except (ValueError, OSError):
                pass

        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        content = f"Title: {title}\n\nAuthors: {', '.join(authors)}\n\nAbstract: {abstract}"

        return FetchedItem(
            url=url,
            title=title,
            content=content,
            summary=abstract[:500],
            author=", ".join(authors),
            published_at=published,
            metadata={"source": "pubmed", "pmid": pmid},
        )

    async def fetch(self, state: SyncState) -> AsyncIterator[FetchedItem]:
        term = self._config.uri.strip() or "artificial intelligence[Title]"
        retmax = min(self._config.max_items_per_sync, 30)
        pmids = await self._esearch(term, retmax=retmax)
        for pmid in pmids:
            if pmid in state.seen_urls:
                continue
            state.seen_urls.add(pmid)
            item = await self._efetch(pmid)
            if item is not None:
                yield item

    async def validate(self) -> str | None:
        try:
            resp = await self._client.get(
                f"{_EUTILS_BASE}/esearch.fcgi?db=pubmed&term=test&retmax=1&retmode=json",
                timeout=15.0,
            )
            if resp.status_code >= 400:
                return f"PubMed API returned HTTP {resp.status_code}"
            return None
        except httpx.ConnectError as e:
            return f"Connection failed: {e}"

    async def estimate_next(self) -> int:
        return self._config.max_items_per_sync

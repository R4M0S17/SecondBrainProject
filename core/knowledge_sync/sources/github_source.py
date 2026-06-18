from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState
from core.knowledge_sync.source_base import SyncSource

_GITHUB_API = "https://api.github.com"
_README_NAMES = {"README.md", "README.rst", "README.txt"}
_SKIP_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".mp4",
        ".mp3",
        ".zip",
        ".tar.gz",
        ".exe",
        ".dmg",
        ".lock",
        ".sum",
    }
)
_SKIP_PATHS = frozenset(
    {
        "node_modules",
        ".git",
        "__pycache__",
        ".venv",
        "vendor",
        ".github",
        "dist",
        "build",
        ".tox",
        "target",
    }
)


class GithubSyncSource(SyncSource):
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
        parts = uri.strip("/").split("/")
        owner, repo = parts[0], parts[1]
        path = "/".join(parts[2:]) if len(parts) > 2 else ""
        return owner, repo, path

    async def _fetch_tree(self, owner: str, repo: str, path: str = "") -> list[dict]:
        url = f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def fetch(self, state: SyncState) -> AsyncIterator[FetchedItem]:
        owner, repo, root_path = self._parse_uri(self._config.uri)
        items: list[dict] = await self._fetch_tree(owner, repo, root_path)
        if isinstance(items, dict):
            items = [items]
        for item in items:
            for fetched in await self._process_item(item, owner, repo, state):
                yield fetched

    async def _process_item(
        self,
        item: dict,
        owner: str,
        repo: str,
        state: SyncState,
    ) -> list[FetchedItem]:
        name: str = item.get("name", "")
        path: str = item.get("path", "")
        item_type: str = item.get("type", "file")

        if item_type == "dir":
            if path.split("/")[0] in _SKIP_PATHS:
                return []
            try:
                children = await self._fetch_tree(owner, repo, path)
            except httpx.HTTPStatusError:
                return []
            results = []
            for child in children:
                results.extend(await self._process_item(child, owner, repo, state))
            return results

        if item_type != "file":
            return []

        ext = os.path.splitext(name)[1].lower()
        if ext in _SKIP_EXTENSIONS:
            return []
        if name not in _README_NAMES and ext not in {
            ".md",
            ".rst",
            ".txt",
            ".py",
            ".js",
            ".ts",
            ".rs",
            ".go",
            ".java",
            ".c",
            ".h",
            ".cpp",
            ".hpp",
            ".toml",
            ".yaml",
            ".yml",
            ".json",
            ".xml",
            ".cfg",
            ".ini",
            ".sh",
            ".bash",
            ".zsh",
            ".fish",
            ".sql",
            ".css",
            ".scss",
            ".html",
        }:
            return []

        download_url = item.get("download_url")
        if not download_url:
            return []
        try:
            resp = await self._client.get(download_url)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            return []

        content = resp.text
        if len(content) < 50:
            return []

        return [
            FetchedItem(
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
        ]

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
        return 10

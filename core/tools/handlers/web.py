from __future__ import annotations

import os
from typing import Final

_MAX_CHARS: Final = int(os.environ.get("CEREBRO_WEB_MAX_CHARS", "4000"))
_TIMEOUT: Final = int(os.environ.get("CEREBRO_WEB_TIMEOUT", "15"))
_MAX_RESULTS: Final = int(os.environ.get("CEREBRO_WEB_MAX_RESULTS", "5"))
_BACKEND: Final = os.environ.get("CEREBRO_WEB_BACKEND", "duckduckgo")
_TAVILY_KEY: Final = os.environ.get("TAVILY_API_KEY", "")

_TRUNC_SUFFIX: Final = "\n[... Texto truncado por límite de contexto]"


def web_search(query: str, max_results: int = _MAX_RESULTS) -> str:
    backend = _BACKEND
    if backend == "tavily" and _TAVILY_KEY:
        return _search_tavily(query, max_results)
    return _search_duckduckgo(query, max_results)


def _search_duckduckgo(query: str, max_results: int) -> str:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS  # type: ignore[assignment]

    try:
        results = list(DDGS().text(query, max_results=max_results))
    except Exception as exc:
        exc_name = type(exc).__name__
        return f"Error en búsqueda DuckDuckGo: {exc_name} — {exc}"

    if not results:
        return "No se encontraron resultados."

    lines: list[str] = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip()
        href = r.get("href", "")
        snippet = r.get("body", "").strip()
        lines.append(f"{i}. {title}")
        if href:
            lines.append(f"   URL: {href}")
        if snippet:
            lines.append(f"   {snippet}")
        lines.append("---")
    return "\n".join(lines)


def _search_tavily(query: str, max_results: int) -> str:
    from tavily import TavilyClient

    try:
        client = TavilyClient(api_key=_TAVILY_KEY)
        resp = client.search(query=query, max_results=max_results)
    except Exception as exc:
        exc_name = type(exc).__name__
        return f"Error en búsqueda Tavily: {exc_name} — {exc}"

    results = resp.get("results", [])
    if not results:
        return "No se encontraron resultados."

    lines: list[str] = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip()
        url = r.get("url", "")
        content = r.get("content", "").strip()
        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   URL: {url}")
        if content:
            lines.append(f"   {content}")
        lines.append("---")
    return "\n".join(lines)


def web_fetch(url: str) -> str:
    import httpx
    import trafilatura

    headers = {"User-Agent": "Mozilla/5.0 (compatible; Cerebro/1.0)"}
    try:
        resp = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True, headers=headers)
        resp.raise_for_status()
    except httpx.TimeoutException:
        return f"Error: Timeout al acceder a {url} (límite: {_TIMEOUT}s)"
    except httpx.HTTPStatusError as exc:
        return f"Error: HTTP {exc.response.status_code} al acceder a {url}"
    except httpx.RequestError as exc:
        return f"Error de conexión: {exc}"

    text = trafilatura.extract(resp.text, no_labels=True, include_tables=False)
    if not text:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(" ", strip=True)

    if text and len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS] + _TRUNC_SUFFIX

    return text or "(no se pudo extraer contenido de la página)"

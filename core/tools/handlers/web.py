from __future__ import annotations

import ipaddress
import os
import socket
from typing import Final
from urllib.parse import urlparse

from core.i18n.messages import _L

_MAX_CHARS: Final = int(os.environ.get("CEREBRO_WEB_MAX_CHARS", "4000"))
_TIMEOUT: Final = int(os.environ.get("CEREBRO_WEB_TIMEOUT", "15"))
_MAX_RESULTS: Final = int(os.environ.get("CEREBRO_WEB_MAX_RESULTS", "5"))
_BACKEND: Final = os.environ.get("CEREBRO_WEB_BACKEND", "duckduckgo")
_TAVILY_KEY: Final = os.environ.get("TAVILY_API_KEY", "")

_TRUNC_SUFFIX: Final = _L("web.truncated")

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS  # type: ignore[assignment,no-redef]


def _check_blocked(hostname: str) -> None:
    addrs = socket.getaddrinfo(hostname, None)
    for _, _, _, _, sockaddr in addrs:
        ip = ipaddress.ip_address(sockaddr[0])
        for blocked in _BLOCKED_NETWORKS:
            if ip in blocked:
                raise ValueError(f"Blocked network: {ip} is in {blocked}")


def web_search(query: str, max_results: int = _MAX_RESULTS) -> str:
    backend = _BACKEND
    if backend == "tavily" and _TAVILY_KEY:
        return _search_tavily(query, max_results)
    return _search_duckduckgo(query, max_results)


def _search_duckduckgo(query: str, max_results: int) -> str:
    try:
        results = list(DDGS().text(query, max_results=max_results))
    except Exception as exc:
        exc_name = type(exc).__name__
        return _L("web.search_error", backend="DuckDuckGo", exc_name=exc_name, exc=exc)

    if not results:
        return _L("web.no_results")

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
        return _L("web.search_error", backend="Tavily", exc_name=exc_name, exc=exc)

    results = resp.get("results", [])
    if not results:
        return _L("web.no_results")

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

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"Error: Scheme '{parsed.scheme}' not allowed"

    hostname = parsed.hostname or ""
    if not hostname:
        return "Error: No hostname in URL"

    try:
        _check_blocked(hostname)
    except ValueError as e:
        return str(e)
    except socket.gaierror as e:
        return f"Error: DNS resolution failed for {hostname}: {e}"

    headers = {"User-Agent": "Mozilla/5.0 (compatible; Cerebro/1.0)"}
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=False) as client:
            resp = client.get(url, headers=headers)
            hops = 0
            while resp.status_code in (301, 302, 307, 308) and hops < 5:
                redirect_url = resp.headers.get("Location")
                if not redirect_url:
                    break
                parsed_redirect = urlparse(redirect_url)
                redirect_host = parsed_redirect.hostname or ""
                if redirect_host:
                    try:
                        _check_blocked(redirect_host)
                    except ValueError as e:
                        return str(e)
                resp = client.get(redirect_url, headers=headers)
                hops += 1
            resp.raise_for_status()
    except httpx.TimeoutException:
        return _L("web.fetch_timeout", url=url, timeout=_TIMEOUT)
    except httpx.HTTPStatusError as exc:
        return _L("web.fetch_http_error", code=exc.response.status_code, url=url)
    except httpx.RequestError as exc:
        return _L("web.fetch_connection_error", exc=exc)

    text = trafilatura.extract(resp.text, include_tables=False)
    if not text:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(" ", strip=True)

    if text and len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS] + _TRUNC_SUFFIX

    return text or _L("web.no_content")

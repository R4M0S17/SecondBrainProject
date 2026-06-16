"""Tests for web_search and web_fetch tools — all mocks, no network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.agents.specialized import GENERAL_TOOLS
from core.tools.registry import ToolRegistry, ToolScope


def _make_web_registry() -> ToolRegistry:
    from core.tools.registry import register_web_tools

    r = ToolRegistry()
    register_web_tools(r)
    return r


# ── web_search (DuckDuckGo backend) ─────────────────────────────────────────


@patch("duckduckgo_search.DDGS")
def test_web_search_duckduckgo_returns_results(mock_ddgs: MagicMock) -> None:
    from core.tools.handlers.web import web_search

    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text.return_value = [
        {
            "title": "Resultado Uno",
            "href": "https://ejemplo.com/1",
            "body": "Este es el primer resultado.",
        },
        {
            "title": "Resultado Dos",
            "href": "https://ejemplo.com/2",
            "body": "Este es el segundo resultado.",
        },
    ]
    mock_ddgs.return_value = mock_ddgs_instance

    result = web_search("test query", max_results=2)

    assert "Resultado Uno" in result
    assert "https://ejemplo.com/1" in result
    assert "Resultado Dos" in result
    assert "---" in result


@patch("duckduckgo_search.DDGS")
def test_web_search_duckduckgo_no_results(mock_ddgs: MagicMock) -> None:
    from core.tools.handlers.web import web_search

    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text.return_value = []
    mock_ddgs.return_value = mock_ddgs_instance

    result = web_search("asdfgh12345nonexistent")

    assert "No se encontraron resultados" in result


@patch("duckduckgo_search.DDGS")
def test_web_search_duckduckgo_error(mock_ddgs: MagicMock) -> None:
    from core.tools.handlers.web import web_search

    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text.side_effect = Exception("Rate limit exceeded")
    mock_ddgs.return_value = mock_ddgs_instance

    result = web_search("test query")

    assert "Error" in result
    assert "Rate limit" in result


# ── web_search (Tavily backend) ──────────────────────────────────────────────


@patch("tavily.TavilyClient")
def test_web_search_tavily_returns_results(mock_client: MagicMock) -> None:
    from core.tools.handlers import web as web_mod

    web_mod._BACKEND = "tavily"
    web_mod._TAVILY_KEY = "test_key"

    mock_instance = MagicMock()
    mock_instance.search.return_value = {
        "results": [
            {
                "title": "Tavily Result",
                "url": "https://tavily.com/1",
                "content": "Tavily content here.",
            },
        ]
    }
    mock_client.return_value = mock_instance

    try:
        result = web_mod.web_search("test query")
        assert "Tavily Result" in result
        assert "https://tavily.com/1" in result
        assert "Tavily content" in result
    finally:
        web_mod._BACKEND = "duckduckgo"
        web_mod._TAVILY_KEY = ""


@patch("tavily.TavilyClient")
def test_web_search_tavily_no_results(mock_client: MagicMock) -> None:
    from core.tools.handlers import web as web_mod

    web_mod._BACKEND = "tavily"
    web_mod._TAVILY_KEY = "test_key"

    mock_instance = MagicMock()
    mock_instance.search.return_value = {"results": []}
    mock_client.return_value = mock_instance

    try:
        result = web_mod.web_search("asdfgh")
        assert "No se encontraron resultados" in result
    finally:
        web_mod._BACKEND = "duckduckgo"
        web_mod._TAVILY_KEY = ""


# ── web_fetch ────────────────────────────────────────────────────────────────


@patch("trafilatura.extract", return_value="Texto limpio extraído por trafilatura.")
@patch("httpx.get")
def test_web_fetch_success(mock_get: MagicMock, mock_extract: MagicMock) -> None:
    from core.tools.handlers.web import web_fetch

    mock_response = MagicMock()
    mock_response.text = "<html><body><p>Hello</p></body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = web_fetch("https://ejemplo.com/articulo")

    assert "Texto limpio" in result
    mock_extract.assert_called_once()


@patch("httpx.get")
def test_web_fetch_timeout(mock_get: MagicMock) -> None:
    import httpx

    from core.tools.handlers.web import web_fetch

    mock_get.side_effect = httpx.TimeoutException("timed out")

    result = web_fetch("https://ejemplo.com")

    assert "Error" in result
    assert "Timeout" in result


@patch("httpx.get")
def test_web_fetch_404(mock_get: MagicMock) -> None:
    import httpx

    from core.tools.handlers.web import web_fetch

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=mock_response
    )
    mock_get.return_value = mock_response

    result = web_fetch("https://ejemplo.com/notfound")

    assert "Error" in result
    assert "404" in result


@patch("trafilatura.extract", return_value="A" * 200)
@patch("httpx.get")
def test_web_fetch_truncation(mock_get: MagicMock, mock_extract: MagicMock) -> None:
    from core.tools.handlers import web as web_mod

    web_mod._MAX_CHARS = 50

    mock_response = MagicMock()
    mock_response.text = "<html><body><p>ok</p></body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    try:
        result = web_mod.web_fetch("https://ejemplo.com")
        assert "Texto truncado" in result
        assert len(result) < 200  # original was 200 chars, now truncated
    finally:
        web_mod._MAX_CHARS = 4000


@patch("bs4.BeautifulSoup")
@patch("trafilatura.extract", return_value=None)
@patch("httpx.get")
def test_web_fetch_fallback_bs4(
    mock_get: MagicMock, mock_extract: MagicMock, mock_bs4: MagicMock
) -> None:
    from core.tools.handlers.web import web_fetch

    mock_response = MagicMock()
    mock_response.text = "<html><body><p>fallback content</p></body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    mock_soup = MagicMock()
    mock_soup.get_text.return_value = "fallback content"
    mock_bs4.return_value = mock_soup

    result = web_fetch("https://ejemplo.com")

    assert "fallback content" in result


# ── Registration ─────────────────────────────────────────────────────────────


def test_web_search_tool_registered() -> None:
    r = _make_web_registry()
    td = r.get("web_search")
    assert td.name == "web_search"
    assert td.required_permission == "tools.web.read"
    assert td.scope == ToolScope.SANDBOXED
    assert not td.requires_confirmation
    assert "query" in td.parameters


def test_web_fetch_tool_registered() -> None:
    r = _make_web_registry()
    td = r.get("web_fetch")
    assert td.name == "web_fetch"
    assert td.required_permission == "tools.web.read"
    assert td.scope == ToolScope.SANDBOXED
    assert not td.requires_confirmation
    assert "url" in td.parameters


def test_web_search_in_general_tools() -> None:
    assert "web_search" in GENERAL_TOOLS


def test_web_fetch_in_general_tools() -> None:
    assert "web_fetch" in GENERAL_TOOLS


def test_web_search_authorized_for_profile() -> None:
    from core.agents.state_store import AgentProfile

    profile = AgentProfile(
        id="test-agent",
        name="TestAgent",
        domain_tags=["test"],
        authorized_tools=GENERAL_TOOLS,
        preferences={},
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )
    r = _make_web_registry()
    assert r.is_authorized("web_search", profile)
    assert r.is_authorized("web_fetch", profile)

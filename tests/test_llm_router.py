from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.agents.llm_router import LLMRouter


def _mock_response(content: str, status: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def _patch_post(content: str, status: int = 200):
    return patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(return_value=_mock_response(content, status)),
    )


# ---------------------------------------------------------------------------
# test_classify_returns_code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_returns_code():
    router = LLMRouter()
    with _patch_post("code"):
        result = await router.classify("Fix this Python bug")
    assert result == "code"


@pytest.mark.asyncio
async def test_classify_returns_calendar():
    router = LLMRouter()
    with _patch_post("calendar"):
        result = await router.classify("Schedule a meeting for Monday")
    assert result == "calendar"


@pytest.mark.asyncio
async def test_classify_returns_academic():
    router = LLMRouter()
    with _patch_post("academic"):
        result = await router.classify("Summarise this PDF")
    assert result == "academic"


@pytest.mark.asyncio
async def test_classify_returns_general():
    router = LLMRouter()
    with _patch_post("general"):
        result = await router.classify("What is the weather like?")
    assert result == "general"


# ---------------------------------------------------------------------------
# test_classify_returns_general_on_http_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_returns_general_on_http_error():
    router = LLMRouter()
    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.ConnectError("refused")),
    ):
        result = await router.classify("anything")
    assert result == "general"


@pytest.mark.asyncio
async def test_classify_returns_general_on_timeout():
    router = LLMRouter()
    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.TimeoutException("timed out")),
    ):
        result = await router.classify("anything")
    assert result == "general"


# ---------------------------------------------------------------------------
# test_classify_truncates_long_query
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_truncates_long_query():
    router = LLMRouter()
    long_query = "x" * 1000

    captured_payload: dict = {}

    async def capture_post(url, json=None, **kwargs):
        captured_payload.update(json or {})
        return _mock_response("general")

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=capture_post)):
        await router.classify(long_query)

    user_content = captured_payload["messages"][0]["content"]
    # The prompt template wraps the query — verify the raw query portion is capped at 300 chars
    assert "x" * 301 not in user_content


# ---------------------------------------------------------------------------
# test_classify_extracts_category_from_noisy_response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_extracts_category_from_noisy_response():
    router = LLMRouter()
    with _patch_post("  The category is: CODE "):
        result = await router.classify("write a script")
    assert result == "code"


# ---------------------------------------------------------------------------
# test_classify_falls_back_on_unrecognised_response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_falls_back_on_unrecognised_response():
    router = LLMRouter()
    with _patch_post("I don't know"):
        result = await router.classify("something weird")
    assert result == "general"


# ---------------------------------------------------------------------------
# test_custom_base_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_base_url():
    router = LLMRouter(base_url="http://127.0.0.1:9090")

    captured_url: list[str] = []

    async def capture_post(url, json=None, **kwargs):
        captured_url.append(url)
        return _mock_response("general")

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=capture_post)):
        await router.classify("test")

    assert captured_url[0].startswith("http://127.0.0.1:9090")

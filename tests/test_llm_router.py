"""Tests for LLMRouter intent prefilter and slow classify path."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.agents.intent_keywords import classify_intent_fast
from core.agents.llm_router import LLMRouter


def test_classify_intent_fast_calendar_spanish():
    assert classify_intent_fast("Crea un evento mañana a las 4pm") == "calendar"


def test_classify_intent_fast_code_file():
    assert classify_intent_fast("escribe un archivo hola.txt") == "code"


@pytest.mark.asyncio
async def test_classify_regex_routes_before_llm() -> None:
    r = LLMRouter()
    cases = [
        ("¿Cuál es mi próximo cumpleaños?", "calendar"),
        ("¿Qué día es hoy?", "calendar"),
        ("Arregla este bug en typescript", "code"),
        ("Resume este pdf", "academic"),
    ]
    for q, want in cases:
        assert await r.classify(q) == want, q


@pytest.mark.asyncio
async def test_classify_slow_path_uses_chat_model_not_router_name() -> None:
    router = LLMRouter(base_url="http://127.0.0.1:8080", model="my-chat.gguf")
    captured: dict = {}

    async def capture_post(url, json=None, **kwargs):
        captured.update(json or {})
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"choices": [{"message": {"content": "general"}}]}
        return resp

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=capture_post)):
        result = await router.classify("totally ambiguous xyz qwerty")

    assert result == "general"
    assert captured["model"] == "my-chat.gguf"
    assert captured["max_tokens"] == 5


@pytest.mark.asyncio
async def test_classify_returns_general_on_http_error() -> None:
    router = LLMRouter()
    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.ConnectError("refused")),
    ):
        result = await router.classify("ambiguous query with no keywords")
    assert result == "general"

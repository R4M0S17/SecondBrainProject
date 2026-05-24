from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from core.inference.context_usage import format_context_usage, resolve_token_usage
from core.inference.engine import InferenceTimeoutError, ModelNotFoundError
from core.inference.providers.llamacpp_provider import (
    LlamaCppChatProvider,
    LlamaCppUnavailableError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _provider(profile: str = "chat") -> LlamaCppChatProvider:
    return LlamaCppChatProvider(
        model="Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        base_url="http://127.0.0.1:8080",
        profile=profile,
    )


def _mock_response(body: dict, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    r.raise_for_status = MagicMock()
    return r


def _chat_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


def test_resolve_token_usage_prefers_total_tokens():
    data = {"usage": {"total_tokens": 321, "prompt_tokens": 100, "completion_tokens": 50}}
    tokens, source = resolve_token_usage(data, [])
    assert tokens == 321
    assert source == "usage.total_tokens"


def test_format_context_usage_line():
    assert format_context_usage(150, 4096, "usage.prompt+completion") == (
        "Context usage: 150/4096 (source=usage.prompt+completion)"
    )


@pytest.mark.asyncio
async def test_complete_logs_context_usage_with_usage_block(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        return_value=_mock_response(
            {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }
        )
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)
    mock_log = mocker.patch("core.inference.providers.llamacpp_provider.log_context_usage")

    await provider.complete([{"role": "user", "content": "hi"}])

    mock_log.assert_called_once_with(150, 4096, "usage.prompt+completion")


@pytest.mark.asyncio
async def test_complete_forwards_grammar_in_payload(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(_chat_response("ok")))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    sample_grammar = "root ::= answer-response"
    await provider.complete([{"role": "user", "content": "hi"}], grammar=sample_grammar)

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["grammar"] == sample_grammar


@pytest.mark.asyncio
async def test_complete_omits_grammar_when_not_supplied(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(_chat_response("ok")))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    await provider.complete([{"role": "user", "content": "hi"}])

    payload = mock_client.post.call_args.kwargs["json"]
    assert "grammar" not in payload


@pytest.mark.asyncio
async def test_complete_returns_stripped_string(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(_chat_response("  hello  ")))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    result = await provider.complete([{"role": "user", "content": "hi"}])
    assert result == "hello"


@pytest.mark.asyncio
async def test_complete_raises_model_not_found_on_404(mocker):
    provider = _provider()
    mock_response = _mock_response({}, status=404)
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    with pytest.raises(ModelNotFoundError):
        await provider.complete([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_complete_raises_unavailable_on_connect_error(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    with pytest.raises(LlamaCppUnavailableError):
        await provider.complete([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_complete_raises_timeout_error(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    with pytest.raises(InferenceTimeoutError):
        await provider.complete([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_complete_forwards_temperature_kwarg(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(_chat_response("ok")))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    await provider.complete([{"role": "user", "content": "hi"}], temperature=0.5)

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["temperature"] == 0.5


@pytest.mark.asyncio
async def test_stream_forwards_grammar_in_payload(mocker):
    provider = _provider()

    async def _lines():
        yield 'data: {"choices":[{"delta":{"content":"x"}}]}'
        yield "data: [DONE]"

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = _lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    sample_grammar = "root ::= answer-response"
    tokens = []
    async for token in provider.stream([{"role": "user", "content": "hi"}], grammar=sample_grammar):
        tokens.append(token)

    assert tokens == ["x"]
    payload = mock_client.stream.call_args.kwargs["json"]
    assert payload["grammar"] == sample_grammar


@pytest.mark.asyncio
async def test_complete_omits_none_temperature(mocker):
    provider = _provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_mock_response(_chat_response("ok")))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    await provider.complete([{"role": "user", "content": "hi"}])

    payload = mock_client.post.call_args.kwargs["json"]
    assert "temperature" not in payload


# ---------------------------------------------------------------------------
# is_available()
# ---------------------------------------------------------------------------


def test_is_available_returns_true_when_health_200(mocker):
    provider = _provider()
    mock_client = MagicMock()
    mock_client.get = MagicMock(return_value=MagicMock(status_code=200))
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)
    mocker.patch("httpx.Client", return_value=mock_client)

    assert provider.is_available() is True


def test_is_available_returns_false_when_server_down(mocker):
    provider = _provider()
    mock_client = MagicMock()
    mock_client.get = MagicMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)
    mocker.patch("httpx.Client", return_value=mock_client)

    assert provider.is_available() is False


def test_is_available_returns_false_on_any_exception(mocker):
    provider = _provider()
    mock_client = MagicMock()
    mock_client.get = MagicMock(side_effect=Exception("unexpected"))
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)
    mocker.patch("httpx.Client", return_value=mock_client)

    assert provider.is_available() is False


# ---------------------------------------------------------------------------
# Profile → context_window
# ---------------------------------------------------------------------------


def test_context_window_chat():
    assert _provider("chat").context_window() == 4096


def test_context_window_coding():
    assert _provider("coding").context_window() == 8192


def test_context_window_deep():
    assert _provider("deep").context_window() == 6144


def test_context_window_unknown_profile_defaults_to_2048():
    assert _provider("unknown").context_window() == 2048


# ---------------------------------------------------------------------------
# model_id / set_model
# ---------------------------------------------------------------------------


def test_model_id_returns_model_name():
    p = _provider()
    assert p.model_id() == "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf"


def test_set_model_changes_model_id():
    p = _provider()
    p.set_model("other-model.gguf")
    assert p.model_id() == "other-model.gguf"


# ---------------------------------------------------------------------------
# Registry integration: llamacpp registered as primary, mlx as fallback
# ---------------------------------------------------------------------------


def test_registry_llamacpp_primary_mlx_fallback():
    from unittest.mock import MagicMock

    from core.inference.registry import ProviderRegistry

    registry = ProviderRegistry()
    llamacpp = _provider("chat")
    mlx_chat = MagicMock()
    mlx_chat.model_id.return_value = "mlx-community/Phi-4-mini-instruct-4bit"

    registry.register("llamacpp", llamacpp, MagicMock())
    registry.register("mlx", mlx_chat, MagicMock())

    assert registry.get_chat().model_id() == "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
    assert registry.get_chat("mlx").model_id() == "mlx-community/Phi-4-mini-instruct-4bit"
    assert registry.available_providers() == ["llamacpp", "mlx"]

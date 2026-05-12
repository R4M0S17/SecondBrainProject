from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

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
    assert _provider("chat").context_window() == 2048


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

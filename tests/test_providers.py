from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from core.inference.providers.llamacpp_embedding_provider import LlamaCppEmbeddingProvider
from core.inference.providers.llamacpp_provider import LlamaCppChatProvider
from core.inference.registry import (
    InsufficientResourcesError,
    ProviderRegistry,
    TaskHint,
)

# ---------------------------------------------------------------------------
# Helpers: minimal stub providers for registry tests
# ---------------------------------------------------------------------------


def _make_chat_provider(model: str = "phi3-mini.gguf") -> LlamaCppChatProvider:
    return LlamaCppChatProvider(model=model, base_url="http://127.0.0.1:8080")


def _make_embed_provider(model: str = "jina-embeddings") -> LlamaCppEmbeddingProvider:
    return LlamaCppEmbeddingProvider(model=model, base_url="http://127.0.0.1:8082")


# ---------------------------------------------------------------------------
# Test 1: ProviderRegistry returns the correct provider by name
# ---------------------------------------------------------------------------


def test_registry_returns_correct_provider_by_name():
    registry = ProviderRegistry()

    chat_primary = _make_chat_provider("phi3-mini.gguf")
    embed_primary = _make_embed_provider()
    chat_fallback = _make_chat_provider("qwen2-1.5b.gguf")
    embed_fallback = _make_embed_provider()

    registry.register("primary", chat_primary, embed_primary)
    registry.register("fallback", chat_fallback, embed_fallback)

    assert registry.get_chat("primary") is chat_primary
    assert registry.get_embed("primary") is embed_primary
    assert registry.get_chat("fallback") is chat_fallback
    assert registry.get_embed("fallback") is embed_fallback
    assert registry.available_providers() == ["primary", "fallback"]


# ---------------------------------------------------------------------------
# Test 2: select_for_task picks fallback when RAM < primary threshold
# ---------------------------------------------------------------------------


def test_select_for_task_uses_fallback_when_low_ram(mocker):
    registry = ProviderRegistry(
        ram_threshold_primary_gb=4.0,
        ram_threshold_fallback_gb=2.0,
    )
    registry.register("primary", _make_chat_provider("phi3-mini.gguf"), _make_embed_provider())
    registry.register("fallback", _make_chat_provider("qwen2-1.5b.gguf"), _make_embed_provider())

    # Simulate 3 GB available — below primary threshold, above fallback threshold
    mock_mem = MagicMock()
    mock_mem.available = int(3.0 * 1024**3)
    mocker.patch("psutil.virtual_memory", return_value=mock_mem)

    chosen = registry.select_for_task(TaskHint.CHAT)
    assert chosen == "fallback"


def test_select_for_task_uses_primary_when_enough_ram(mocker):
    registry = ProviderRegistry(
        ram_threshold_primary_gb=4.0,
        ram_threshold_fallback_gb=2.0,
    )
    registry.register("primary", _make_chat_provider("phi3-mini.gguf"), _make_embed_provider())
    registry.register("fallback", _make_chat_provider("qwen2-1.5b.gguf"), _make_embed_provider())

    mock_mem = MagicMock()
    mock_mem.available = int(5.0 * 1024**3)
    mocker.patch("psutil.virtual_memory", return_value=mock_mem)

    chosen = registry.select_for_task(TaskHint.CHAT)
    assert chosen == "primary"


def test_select_for_task_raises_when_ram_critically_low(mocker):
    registry = ProviderRegistry(
        ram_threshold_primary_gb=4.0,
        ram_threshold_fallback_gb=2.0,
    )
    registry.register("primary", _make_chat_provider(), _make_embed_provider())

    mock_mem = MagicMock()
    mock_mem.available = int(1.0 * 1024**3)
    mocker.patch("psutil.virtual_memory", return_value=mock_mem)

    with pytest.raises(InsufficientResourcesError):
        registry.select_for_task(TaskHint.CHAT)


# ---------------------------------------------------------------------------
# Test 3: Embedding never uses the chat model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embedding_provider_never_uses_chat_model(mocker):
    embed_provider = _make_embed_provider()

    fake_embedding = [0.1] * 1024
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"embedding": fake_embedding}]}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    result = await embed_provider.embed("test text")

    # Verify the request used the embedding model, not a chat model
    call_kwargs = mock_client.post.call_args
    payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs.kwargs["json"]
    assert payload["model"] == "jina-embeddings"
    assert "phi3" not in payload["model"]
    assert len(result) == 1024


def test_select_for_task_embedding_always_returns_primary(mocker):
    """Embedding ignores RAM and always returns the primary (embedding) provider."""
    registry = ProviderRegistry()
    registry.register("primary", _make_chat_provider(), _make_embed_provider())
    registry.register("fallback", _make_chat_provider("qwen2-1.5b.gguf"), _make_embed_provider())

    # Even with very low RAM, embedding task must not raise and must return primary
    mock_mem = MagicMock()
    mock_mem.available = int(0.5 * 1024**3)
    mocker.patch("psutil.virtual_memory", return_value=mock_mem)

    chosen = registry.select_for_task(TaskHint.EMBEDDING)
    assert chosen == "primary"


# ---------------------------------------------------------------------------
# Test 4: is_available() returns False without exception when llama.cpp is down
# ---------------------------------------------------------------------------


def test_is_available_returns_false_when_llamacpp_down(mocker):
    provider = _make_chat_provider()

    mock_client = MagicMock()
    mock_client.get = MagicMock(side_effect=httpx.ConnectError("connection refused"))
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)

    mocker.patch("httpx.Client", return_value=mock_client)

    result = provider.is_available()
    assert result is False


def test_is_available_returns_false_on_any_exception(mocker):
    provider = _make_chat_provider()

    mock_client = MagicMock()
    mock_client.get = MagicMock(side_effect=Exception("unexpected error"))
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=None)

    mocker.patch("httpx.Client", return_value=mock_client)

    result = provider.is_available()
    assert result is False


# ---------------------------------------------------------------------------
# Test: ProviderRegistry.set_primary() swaps the active provider
# ---------------------------------------------------------------------------


def test_set_primary_swaps_primary_and_fallback():
    registry = ProviderRegistry()
    registry.register("mlx", _make_chat_provider("mlx-model"), _make_embed_provider())
    registry.register("llamacpp", _make_chat_provider("phi3-mini.gguf"), _make_embed_provider())

    assert registry.get_chat().model_id() == "mlx-model"

    registry.set_primary("llamacpp")

    assert registry.get_chat().model_id() == "phi3-mini.gguf"
    assert registry.get_chat("mlx").model_id() == "mlx-model"


def test_set_primary_raises_for_unknown_provider():
    registry = ProviderRegistry()
    registry.register("llamacpp", _make_chat_provider(), _make_embed_provider())

    with pytest.raises(KeyError):
        registry.set_primary("nonexistent")


def test_set_primary_is_idempotent():
    registry = ProviderRegistry()
    registry.register("llamacpp", _make_chat_provider("phi3-mini.gguf"), _make_embed_provider())
    registry.set_primary("llamacpp")
    assert registry.get_chat().model_id() == "phi3-mini.gguf"


# ---------------------------------------------------------------------------
# Test: LlamaCppChatProvider.set_model() changes model used for requests
# ---------------------------------------------------------------------------


def test_llamacpp_set_model_changes_model_id():
    provider = _make_chat_provider("phi3-mini.gguf")
    assert provider.model_id() == "phi3-mini.gguf"
    provider.set_model("qwen3-4b.gguf")
    assert provider.model_id() == "qwen3-4b.gguf"


# ---------------------------------------------------------------------------
# Test: ProviderRegistry.get_chat_for_agent()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_chat_for_agent_code_uses_coding_profile():
    from unittest.mock import AsyncMock

    from core.inference.providers.llamacpp_provider import LlamaCppChatProvider

    mock_mm = AsyncMock()
    mock_mm.ensure_specialist = AsyncMock(return_value=8081)

    registry = ProviderRegistry()
    provider = await registry.get_chat_for_agent("code-v1", mock_mm)

    mock_mm.ensure_specialist.assert_called_once_with("code")
    assert isinstance(provider, LlamaCppChatProvider)
    assert provider.model_id() == "code-v1"
    assert provider.context_window() == 8192  # "coding" profile


@pytest.mark.asyncio
async def test_get_chat_for_agent_general_uses_chat_profile():
    from unittest.mock import AsyncMock

    from core.inference.providers.llamacpp_provider import LlamaCppChatProvider

    mock_mm = AsyncMock()
    mock_mm.ensure_specialist = AsyncMock(return_value=8081)

    registry = ProviderRegistry()
    provider = await registry.get_chat_for_agent("general-v1", mock_mm)

    mock_mm.ensure_specialist.assert_called_once_with("general")
    assert isinstance(provider, LlamaCppChatProvider)
    assert provider.model_id() == "general-v1"
    assert provider.context_window() == 2048  # "chat" profile


@pytest.mark.asyncio
async def test_get_chat_for_agent_unknown_agent_falls_back_to_general_role():
    from unittest.mock import AsyncMock

    mock_mm = AsyncMock()
    mock_mm.ensure_specialist = AsyncMock(return_value=8081)

    registry = ProviderRegistry()
    await registry.get_chat_for_agent("calendar-v1", mock_mm)

    mock_mm.ensure_specialist.assert_called_once_with("general")


# ---------------------------------------------------------------------------
# Test: ProviderRegistry.get_embedding_provider()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_embedding_provider_returns_llamacpp_when_model_manager_set():
    from core.inference.providers.llamacpp_embedding_provider import LlamaCppEmbeddingProvider

    mock_mm = MagicMock()
    mock_mm.embed_url = "http://127.0.0.1:8082"

    registry = ProviderRegistry()
    provider = await registry.get_embedding_provider(mock_mm)

    assert isinstance(provider, LlamaCppEmbeddingProvider)


@pytest.mark.asyncio
async def test_get_embedding_provider_returns_registered_when_no_model_manager():
    registry = ProviderRegistry()
    llamacpp_embed = _make_embed_provider()
    registry.register("llamacpp", _make_chat_provider(), llamacpp_embed)

    provider = await registry.get_embedding_provider(None)

    assert isinstance(provider, LlamaCppEmbeddingProvider)

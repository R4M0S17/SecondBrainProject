from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Inject a minimal mlx_lm stub so imports inside the provider don't fail
# ---------------------------------------------------------------------------


class _FakeGenerationResponse:
    """Mirrors the real mlx_lm.GenerationResponse so tests exercise the .text path."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.token = 0
        self.logprobs = []


def _make_mlx_stub() -> None:
    mlx_core = ModuleType("mlx")
    mlx_core.core = ModuleType("mlx.core")
    sys.modules.setdefault("mlx", mlx_core)
    sys.modules.setdefault("mlx.core", mlx_core.core)

    mlx_lm = ModuleType("mlx_lm")
    mlx_lm.load = MagicMock(return_value=(MagicMock(), MagicMock()))
    mlx_lm.generate = MagicMock(return_value="Hello from MLX")
    mlx_lm.stream_generate = MagicMock(
        return_value=iter([_FakeGenerationResponse("Hello"), _FakeGenerationResponse(" world")])
    )
    sys.modules.setdefault("mlx_lm", mlx_lm)


_make_mlx_stub()

from core.inference.providers.mlx_provider import (
    MlxChatProvider,
    MlxEmbeddingProviderStub,
)

# ---------------------------------------------------------------------------
# Helper: create a provider whose worker thread uses a specific fake model/tokenizer.
# The provider must be constructed INSIDE the patch("mlx_lm.load", ...) context
# because the worker thread calls load() eagerly at __init__ time.
# ---------------------------------------------------------------------------


async def _make_provider(
    model: MagicMock, tokenizer: MagicMock, repo: str = "mlx-community/test"
) -> MlxChatProvider:
    with patch("mlx_lm.load", return_value=(model, tokenizer)):
        provider = MlxChatProvider(model_repo=repo)
        await asyncio.to_thread(provider._ready.wait)
    return provider


# ---------------------------------------------------------------------------
# MlxChatProvider — unit tests
# ---------------------------------------------------------------------------


def test_model_id_returns_repo_name():
    provider = MlxChatProvider(model_repo="mlx-community/Phi-4-mini-instruct-4bit")
    assert provider.model_id() == "mlx-community/Phi-4-mini-instruct-4bit"


def test_context_window_returns_int():
    provider = MlxChatProvider(model_repo="mlx-community/Phi-4-mini-instruct-4bit")
    assert isinstance(provider.context_window(), int)
    assert provider.context_window() > 0


def test_is_available_returns_bool():
    provider = MlxChatProvider(model_repo="mlx-community/Phi-4-mini-instruct-4bit")
    with patch("core.inference.platform.mlx_available", return_value=True):
        assert provider.is_available() is True
    with patch("core.inference.platform.mlx_available", return_value=False):
        assert provider.is_available() is False


@pytest.mark.asyncio
async def test_complete_returns_string():
    fake_model = MagicMock()
    fake_tokenizer = MagicMock()
    fake_tokenizer.apply_chat_template = MagicMock(return_value="<prompt>")

    provider = await _make_provider(fake_model, fake_tokenizer)

    with patch("mlx_lm.generate", return_value="Hello from MLX") as mock_gen:
        messages = [{"role": "user", "content": "Hello"}]
        result = await provider.complete(messages)

    assert isinstance(result, str)
    assert result == "Hello from MLX"
    mock_gen.assert_called_once()


@pytest.mark.asyncio
async def test_stream_yields_tokens():
    """stream_generate returns GenerationResponse objects; provider must yield .text strings."""
    fake_model = MagicMock()
    fake_tokenizer = MagicMock()
    fake_tokenizer.apply_chat_template = MagicMock(return_value="<prompt>")

    provider = await _make_provider(fake_model, fake_tokenizer)

    responses = [_FakeGenerationResponse(t) for t in ["Hello", " world", "!"]]
    with patch("mlx_lm.stream_generate", return_value=iter(responses)):
        messages = [{"role": "user", "content": "Hi"}]
        collected = []
        async for token in provider.stream(messages):
            collected.append(token)

    assert collected == ["Hello", " world", "!"]


@pytest.mark.asyncio
async def test_stream_handles_plain_string_tokens():
    """Fallback: if stream_generate ever yields plain strings, provider passes them through."""
    fake_model = MagicMock()
    fake_tokenizer = MagicMock()
    fake_tokenizer.apply_chat_template = MagicMock(return_value="<prompt>")

    provider = await _make_provider(fake_model, fake_tokenizer)

    with patch("mlx_lm.stream_generate", return_value=iter(["a", "b"])):
        collected = []
        async for token in provider.stream([{"role": "user", "content": "Hi"}]):
            collected.append(token)

    assert collected == ["a", "b"]


@pytest.mark.asyncio
async def test_complete_uses_chat_template_when_available():
    fake_model = MagicMock()
    fake_tokenizer = MagicMock()
    fake_tokenizer.apply_chat_template = MagicMock(return_value="<formatted>")

    provider = await _make_provider(fake_model, fake_tokenizer)

    with patch("mlx_lm.generate", return_value="ok") as mock_gen:
        await provider.complete([{"role": "user", "content": "test"}])

    fake_tokenizer.apply_chat_template.assert_called_once()
    call_kwargs = mock_gen.call_args
    assert "<formatted>" in call_kwargs.args or call_kwargs.kwargs.get("prompt") == "<formatted>"


@pytest.mark.asyncio
async def test_complete_fallback_template_when_no_apply_chat_template():
    fake_model = MagicMock()
    fake_tokenizer = MagicMock(spec=[])  # no apply_chat_template attribute

    provider = await _make_provider(fake_model, fake_tokenizer)

    with patch("mlx_lm.generate", return_value="ok"):
        result = await provider.complete([{"role": "user", "content": "hello"}])

    assert result == "ok"


# ---------------------------------------------------------------------------
# MlxEmbeddingProviderStub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stub_embed_raises():
    stub = MlxEmbeddingProviderStub()
    with pytest.raises(NotImplementedError):
        await stub.embed("text")


def test_stub_dimensions():
    stub = MlxEmbeddingProviderStub()
    assert stub.dimensions() == 768


# ---------------------------------------------------------------------------
# platform helpers
# ---------------------------------------------------------------------------


def test_is_apple_silicon_detects_arm64(mocker):
    mocker.patch("sys.platform", "darwin")
    mocker.patch("platform.machine", return_value="arm64")
    from core.inference.platform import is_apple_silicon

    assert is_apple_silicon() is True


def test_is_apple_silicon_false_on_non_darwin(mocker):
    mocker.patch("sys.platform", "linux")
    from core.inference.platform import is_apple_silicon

    assert is_apple_silicon() is False


def test_mlx_available_false_when_import_fails(mocker):
    mocker.patch("sys.platform", "darwin")
    mocker.patch("platform.machine", return_value="arm64")
    mocker.patch(
        "core.inference.platform.psutil.virtual_memory",
        return_value=mocker.Mock(total=16 * 1024**3),
    )
    with patch.dict(sys.modules, {"mlx": None, "mlx.core": None, "mlx_lm": None}):
        from importlib import reload

        import core.inference.platform as plat

        reload(plat)
        assert plat.mlx_available() is False


def test_mlx_available_false_when_insufficient_ram(mocker):
    mocker.patch("sys.platform", "darwin")
    mocker.patch("platform.machine", return_value="arm64")
    mocker.patch(
        "core.inference.platform.psutil.virtual_memory",
        return_value=mocker.Mock(total=8 * 1024**3),
    )
    import core.inference.platform as plat

    assert plat.mlx_available() is False

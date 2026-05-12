# MLX Provider Implementation Guide

Adds Apple Silicon–native inference to Cerebro as an optional primary provider.
MLX runs models in-process (no HTTP daemon), exploiting unified memory for lower
latency. Ollama stays registered as the fallback provider for chat and remains
the sole embedding provider (nomic-embed-text via Ollama is fast and stable).

Architecture: new files only, one small edit to `main.py`, one to `settings.toml`,
one to `pyproject.toml`. No existing files are refactored. All changes slot into
the existing `ChatProvider` / `EmbeddingProvider` protocol + `ProviderRegistry`.

---

## Step 0 — Add optional dependency in `pyproject.toml`

Add an `mlx` extras group inside `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
mlx = [
    "mlx>=0.16",
    "mlx-lm>=0.19",
]
dev = [
    # existing dev deps unchanged
    "black>=24.0",
    "ruff>=0.4",
    "mypy>=1.10",
    "pre-commit>=3.7",
]
build = [
    "pyinstaller>=6.0",
]
```

Install on Apple Silicon: `pip install -e ".[mlx]"`

---

## Step 1 — Add `[mlx]` section to `config/settings.toml`

Append at the end of the file (after `[security]`):

```toml
[mlx]
enabled = "auto"
chat_model = "mlx-community/Phi-4-mini-instruct-4bit"
max_tokens = 2048
```

`enabled` values:
- `"auto"` — activate if running on Apple Silicon and `mlx-lm` is installed
- `"true"` — force-enable (raises at startup if MLX unavailable)
- `"false"` — disable even on Apple Silicon (use Ollama only)

---

## Step 2 — Create `core/inference/platform.py`

New file. No imports from the rest of the codebase.

```python
from __future__ import annotations

import platform
import sys


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def mlx_available() -> bool:
    if not is_apple_silicon():
        return False
    try:
        import mlx.core  # noqa: F401
        import mlx_lm    # noqa: F401
        return True
    except ImportError:
        return False
```

---

## Step 3 — Create `core/inference/providers/mlx_provider.py`

New file. Implements both `ChatProvider` and a stub `EmbeddingProvider` (not
used at runtime — embeddings stay on Ollama, but the stub satisfies the registry
`register()` signature which requires both).

```python
from __future__ import annotations

import asyncio
import threading
from typing import AsyncIterator

from loguru import logger

from core.inference.registry import Message


class MlxChatProvider:
    """In-process LLM inference via mlx-lm on Apple Silicon."""

    def __init__(self, model_repo: str, max_tokens: int = 2048) -> None:
        self._model_repo = model_repo
        self._max_tokens = max_tokens
        self._model = None
        self._tokenizer = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lazy loader — called once on first inference request
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            from mlx_lm import load  # type: ignore[import]
            logger.info("Loading MLX model: {}", self._model_repo)
            self._model, self._tokenizer = load(self._model_repo)
            logger.info("MLX model loaded.")

    def _apply_template(self, messages: list[Message]) -> str:
        self._ensure_loaded()
        if hasattr(self._tokenizer, "apply_chat_template"):
            return self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        # Fallback: plain concatenation for tokenizers without a chat template
        return "\n".join(f"{m['role']}: {m['content']}" for m in messages)

    # ------------------------------------------------------------------
    # ChatProvider protocol
    # ------------------------------------------------------------------

    async def complete(self, messages: list[Message], **kwargs) -> str:
        from mlx_lm import generate  # type: ignore[import]

        prompt = self._apply_template(messages)

        def _run() -> str:
            self._ensure_loaded()
            return generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=self._max_tokens,
                verbose=False,
            )

        return await asyncio.to_thread(_run)

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        from mlx_lm import stream_generate  # type: ignore[import]

        prompt = self._apply_template(messages)
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def _run() -> None:
            self._ensure_loaded()
            try:
                for token in stream_generate(
                    self._model,
                    self._tokenizer,
                    prompt=prompt,
                    max_tokens=self._max_tokens,
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, token)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        while True:
            token = await queue.get()
            if token is None:
                break
            yield token

    def model_id(self) -> str:
        return self._model_repo

    def context_window(self) -> int:
        return 4096

    def is_available(self) -> bool:
        from core.inference.platform import mlx_available
        return mlx_available()


class MlxEmbeddingProviderStub:
    """Stub — satisfies ProviderRegistry.register() signature.

    MLX embeddings are not used at runtime; the Ollama embed provider is
    always passed to LongTermStore directly. This stub exists only so that
    the MLX entry can be registered without a real embed implementation.
    """

    async def embed(self, text: str) -> list[float]:  # pragma: no cover
        raise NotImplementedError("Use OllamaEmbeddingProvider for embeddings")

    def dimensions(self) -> int:
        return 768
```

---

## Step 4 — Update `main.py`

Replace the `_build_app_state` function with the version below. The only
meaningful changes are: import the new helpers, detect MLX at startup, and
register MLX as `"mlx"` (primary) when available with `"ollama"` as fallback.
Everything else — memory, state store, runtime, router — is untouched.

```python
"""Cerebro — entry point."""
from __future__ import annotations

import os

import uvicorn

from core.agents.runtime import AgentRuntime
from core.agents.specialized import GENERAL_AGENT_ID, SpecializedAgentRouter
from core.tools.handlers.calendar import get_upcoming_events, query_events
from core.agents.state_store import AgentStateStore
from core.inference.platform import mlx_available
from core.inference.providers.ollama_provider import OllamaChatProvider, OllamaEmbeddingProvider
from core.inference.registry import ProviderRegistry
from core.memory.context_builder import ContextBuilder
from core.memory.long_term import LongTermStore
from core.memory.short_term import ShortTermStore
from core.memory.vector_store import VectorStore
from ui.tray.server import app, app_state

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("CEREBRO_MODEL", "phi4-mini:latest")
EMBED_MODEL = os.getenv("CEREBRO_EMBED_MODEL", "nomic-embed-text")
DB_PATH = os.path.expanduser(os.getenv("CEREBRO_DB", "~/.cerebro/db"))
STATE_DIR = os.path.expanduser(os.getenv("CEREBRO_STATE", "~/.cerebro/state"))
PORT = int(os.getenv("CEREBRO_PORT", "7842"))
RAM_PRIMARY_GB = float(os.getenv("CEREBRO_RAM_PRIMARY_GB", "1.0"))
RAM_FALLBACK_GB = float(os.getenv("CEREBRO_RAM_FALLBACK_GB", "0.3"))
MLX_MODEL = os.getenv("CEREBRO_MLX_MODEL", "mlx-community/Phi-4-mini-instruct-4bit")
MLX_ENABLED = os.getenv("CEREBRO_MLX_ENABLED", "auto")  # "auto" | "true" | "false"


def _build_app_state() -> None:
    from loguru import logger

    embed = OllamaEmbeddingProvider(model=EMBED_MODEL, base_url=OLLAMA_URL)
    ollama_chat = OllamaChatProvider(model=CHAT_MODEL, base_url=OLLAMA_URL)

    registry = ProviderRegistry(
        ram_threshold_primary_gb=RAM_PRIMARY_GB,
        ram_threshold_fallback_gb=RAM_FALLBACK_GB,
    )

    use_mlx = (MLX_ENABLED == "true") or (MLX_ENABLED == "auto" and mlx_available())

    if use_mlx:
        from core.inference.providers.mlx_provider import (
            MlxChatProvider,
            MlxEmbeddingProviderStub,
        )
        mlx_chat = MlxChatProvider(model_repo=MLX_MODEL)
        registry.register("mlx", mlx_chat, MlxEmbeddingProviderStub())
        registry.register("ollama", ollama_chat, embed)
        logger.info("Inference: MLX primary, Ollama fallback")
    else:
        registry.register("ollama", ollama_chat, embed)
        logger.info("Inference: Ollama only")

    vector_store = VectorStore(db_path=DB_PATH)
    state_store = AgentStateStore(state_dir=STATE_DIR)

    short_term = ShortTermStore()
    long_term = LongTermStore(vector_store=vector_store, agent_id=GENERAL_AGENT_ID, embed=embed)
    context_builder = ContextBuilder(short_term=short_term, long_term=long_term)

    runtime = AgentRuntime(
        registry=registry,
        state_store=state_store,
        context_builder=context_builder,
        tool_registry={
            "get_upcoming_events": get_upcoming_events,
            "query_events": query_events,
        },
    )

    router = SpecializedAgentRouter()
    router.ensure_profiles(state_store)

    app_state.runtime = runtime
    app_state.vector_store = vector_store
    app_state.provider_registry = registry
    app_state.router = router


if __name__ == "__main__":
    _build_app_state()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
```

---

## Step 5 — Create `tests/test_mlx_provider.py`

New test file. All tests mock `mlx_lm` so they run on any machine (CI, Linux,
machines without MLX installed). The provider's lazy-load path is tested without
actually loading a model.

```python
from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Inject a minimal mlx_lm stub so imports inside the provider don't fail
# ---------------------------------------------------------------------------

def _make_mlx_stub() -> None:
    mlx_core = ModuleType("mlx")
    mlx_core.core = ModuleType("mlx.core")
    sys.modules.setdefault("mlx", mlx_core)
    sys.modules.setdefault("mlx.core", mlx_core.core)

    mlx_lm = ModuleType("mlx_lm")
    mlx_lm.load = MagicMock(return_value=(MagicMock(), MagicMock()))
    mlx_lm.generate = MagicMock(return_value="Hello from MLX")
    mlx_lm.stream_generate = MagicMock(return_value=iter(["Hello", " world"]))
    sys.modules.setdefault("mlx_lm", mlx_lm)

_make_mlx_stub()

from core.inference.providers.mlx_provider import MlxChatProvider, MlxEmbeddingProviderStub  # noqa: E402


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
    provider = MlxChatProvider(model_repo="mlx-community/Phi-4-mini-instruct-4bit")

    fake_model = MagicMock()
    fake_tokenizer = MagicMock()
    fake_tokenizer.apply_chat_template = MagicMock(return_value="<prompt>")

    with patch("mlx_lm.load", return_value=(fake_model, fake_tokenizer)):
        with patch("mlx_lm.generate", return_value="Hello from MLX") as mock_gen:
            messages = [{"role": "user", "content": "Hello"}]
            result = await provider.complete(messages)

    assert isinstance(result, str)
    assert result == "Hello from MLX"
    mock_gen.assert_called_once()


@pytest.mark.asyncio
async def test_stream_yields_tokens():
    provider = MlxChatProvider(model_repo="mlx-community/Phi-4-mini-instruct-4bit")

    fake_model = MagicMock()
    fake_tokenizer = MagicMock()
    fake_tokenizer.apply_chat_template = MagicMock(return_value="<prompt>")

    tokens = ["Hello", " world", "!"]

    with patch("mlx_lm.load", return_value=(fake_model, fake_tokenizer)):
        with patch("mlx_lm.stream_generate", return_value=iter(tokens)):
            messages = [{"role": "user", "content": "Hi"}]
            collected = []
            async for token in provider.stream(messages):
                collected.append(token)

    assert collected == tokens


@pytest.mark.asyncio
async def test_complete_uses_chat_template_when_available():
    provider = MlxChatProvider(model_repo="mlx-community/test-model")

    fake_model = MagicMock()
    fake_tokenizer = MagicMock()
    fake_tokenizer.apply_chat_template = MagicMock(return_value="<formatted>")

    with patch("mlx_lm.load", return_value=(fake_model, fake_tokenizer)):
        with patch("mlx_lm.generate", return_value="ok") as mock_gen:
            await provider.complete([{"role": "user", "content": "test"}])

    fake_tokenizer.apply_chat_template.assert_called_once()
    call_kwargs = mock_gen.call_args
    assert "<formatted>" in call_kwargs.args or call_kwargs.kwargs.get("prompt") == "<formatted>"


@pytest.mark.asyncio
async def test_complete_fallback_template_when_no_apply_chat_template():
    provider = MlxChatProvider(model_repo="mlx-community/test-model")

    fake_model = MagicMock()
    fake_tokenizer = MagicMock(spec=[])  # no apply_chat_template attribute

    with patch("mlx_lm.load", return_value=(fake_model, fake_tokenizer)):
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
    # Remove mlx stubs temporarily to simulate missing package
    with patch.dict(sys.modules, {"mlx": None, "mlx.core": None, "mlx_lm": None}):
        from importlib import reload
        import core.inference.platform as plat
        reload(plat)
        assert plat.mlx_available() is False
```

---

## Implementation checklist

Work through these in order. Run `pytest` after each step to confirm nothing regresses.

- [x] **Step 0** — edit `pyproject.toml`, add `[mlx]` extras group
- [x] **Step 1** — append `[mlx]` section to `config/settings.toml`
- [x] **Step 2** — create `core/inference/platform.py`
- [x] **Step 3** — create `core/inference/providers/mlx_provider.py`
- [x] **Step 4** — replace `_build_app_state` in `main.py`
- [x] **Step 5** — create `tests/test_mlx_provider.py`
- [x] Run `pip install -e ".[mlx]"` on the target Apple Silicon machine
- [x] Smoke-test: `python main.py` — confirm log line says `Inference: MLX primary, Ollama fallback`
- [x] Verify the first `/query` call triggers `Loading MLX model` in logs, subsequent calls do not (lazy-load cache working)

---

## Notes for the implementer

**Model choice.** `mlx-community/Phi-4-mini-instruct-4bit` is the MLX-quantized
equivalent of `phi4-mini:latest` used by Ollama today — same model family, same
behaviour, ~2.3 GB on disk.

**Embeddings stay on Ollama.** `LongTermStore` receives `embed` (an
`OllamaEmbeddingProvider`) directly, bypassing the registry. Do not change this
path. The `MlxEmbeddingProviderStub` is only there to satisfy the `register()`
call signature.

**Thread safety.** The `_lock` in `MlxChatProvider` prevents double-loading when
two async tasks both trigger the lazy load simultaneously. Do not remove it.

**Env-var override.** Set `CEREBRO_MLX_ENABLED=false` to fall back to Ollama-only
mode without changing `settings.toml`. Useful for debugging regressions.

**No streaming from `mlx_lm.stream_generate` in older versions.** If
`stream_generate` is not present in the installed version, the stream method will
raise `ImportError`. The fix is to upgrade: `pip install --upgrade mlx-lm`.

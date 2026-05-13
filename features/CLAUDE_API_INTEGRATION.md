# Claude API Integration — Cerebro

This document defines what Claude API adds to Cerebro and the full modular implementation path so Claude Code can execute it step by step.

---

## What Claude API Does in This Project

Cerebro already runs inference **locally** via llama.cpp (primary) and MLX (secondary). Claude API is a **third, cloud-based option** that sits in the same `ProviderRegistry` slot.

When `CEREBRO_INFERENCE_BACKEND=claude` is set:

| Capability | Local mode (llamacpp/MLX) | Claude API mode |
|---|---|---|
| Chat inference | llama.cpp subprocess on port 8080 | Anthropic SDK → `claude-sonnet-4-6` (or configured model) |
| Embeddings | llamacpp embedding server on port 8081 | **Still local** (LanceDB still needs nomic-embed-text; Claude API has no embeddings endpoint) |
| Context window | 2 048–8 192 tokens (GGUF model) | 200 000 tokens |
| RAM requirement | 4–8 GB for inference | None (cloud) |
| Cost | Free (local) | Per-token billing |
| Streaming | SSE via httpx | `anthropic.AsyncAnthropic` streaming |
| Tool use | Mapped through ToolRegistry | Native `tools=` param in Anthropic SDK (can map ToolRegistry definitions) |
| Prompt caching | Not applicable | `cache_control` on system prompt blocks → cuts cost on repeated queries |
| Vision | Not supported | Supported (future — attach images to `content` array) |

**When to use Claude API mode:**
- Laptop RAM is limited and local inference is too slow/impossible.
- You need a 200K-token context for large document analysis.
- You want to test responses against a frontier model before shipping a feature.

**Embeddings always stay local.** The embedding server (`make engine-embed`) must run in both modes so RAG and memory search continue to work.

---

## Environment Variables Added

```
CEREBRO_INFERENCE_BACKEND   claude          # triggers Claude API mode (existing var, new value)
CEREBRO_CLAUDE_MODEL        claude-sonnet-4-6   # which Claude model to use
ANTHROPIC_API_KEY           sk-ant-...      # required; loaded from env or .env file
```

Existing `llamacpp` vars are ignored when `CEREBRO_INFERENCE_BACKEND=claude`. The embed URL (`CEREBRO_LLAMACPP_EMBED_URL`) is still read to start the embedding provider.

---

## Implementation Path (Ordered Modules)

### Module C1 — Dependency

**File:** `cerebro/pyproject.toml`

Add to `[project.dependencies]`:
```toml
anthropic>=0.40.0
```

Then run `make install` to update `.venv`.

---

### Module C2 — Claude API Chat Provider

**New file:** `cerebro/core/inference/providers/claude_api_provider.py`

Implements the existing `ChatProvider` protocol from `registry.py`. No changes to the protocol needed.

```python
from __future__ import annotations

import os
from typing import AsyncIterator

import anthropic
from loguru import logger

from core.inference.registry import Message

_DEFAULT_MODEL = "claude-sonnet-4-6"
_CONTEXT_WINDOWS = {
    "claude-opus-4-7": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
}


class ClaudeApiUnavailableError(Exception):
    pass


class ClaudeApiChatProvider:
    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        timeout: int = 120,
        max_tokens: int = 4096,
    ) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ClaudeApiUnavailableError("ANTHROPIC_API_KEY is not set")
        self._model = model
        self._max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)

    async def complete(self, messages: list[Message], **kwargs) -> str:
        system, user_messages = _split_system(messages)
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},  # prompt caching
                    }
                ] if system else anthropic.NOT_GIVEN,
                messages=user_messages,
                temperature=kwargs.get("temperature", 0.7),
            )
            return response.content[0].text.strip()
        except anthropic.AuthenticationError as e:
            raise ClaudeApiUnavailableError("Invalid ANTHROPIC_API_KEY") from e
        except anthropic.APIConnectionError as e:
            raise ClaudeApiUnavailableError("Cannot reach Anthropic API") from e

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        system, user_messages = _split_system(messages)
        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=self._max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ] if system else anthropic.NOT_GIVEN,
                messages=user_messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIConnectionError as e:
            raise ClaudeApiUnavailableError("Cannot reach Anthropic API") from e

    def model_id(self) -> str:
        return self._model

    def context_window(self) -> int:
        return _CONTEXT_WINDOWS.get(self._model, 200_000)

    def is_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _split_system(messages: list[Message]) -> tuple[str, list[dict]]:
    """Separate the first system message from the rest for the Anthropic API format."""
    system = ""
    rest: list[dict] = []
    for m in messages:
        if m["role"] == "system" and not system:
            system = m["content"]
        else:
            rest.append({"role": m["role"], "content": m["content"]})
    return system, rest
```

**Key design choices:**
- `cache_control: ephemeral` on the system prompt activates prompt caching — Anthropic caches system prompt tokens across calls, reducing cost on repeated queries.
- Embeddings are **not** implemented here. Claude API has no embeddings endpoint. The existing `LlamaCppEmbeddingProvider` handles all embedding calls in both modes.
- `_split_system` converts Cerebro's flat `Message` list (which includes a `role=system` entry) into the format Anthropic's API expects (`system=` param + `messages=` list).

---

### Module C3 — Wire Into main.py

**File:** `cerebro/main.py`

In the section that builds the `ProviderRegistry`, add a branch for the `claude` backend. The embedding provider registration stays unchanged.

Locate the existing block that checks `CEREBRO_INFERENCE_BACKEND`:

```python
# EXISTING pattern (simplified):
if backend == "llamacpp":
    chat_provider = LlamaCppChatProvider(...)
    registry.register("llamacpp", chat=chat_provider, embed=embed_provider)
```

Add after the existing `elif mlx` branch:

```python
elif backend == "claude":
    from core.inference.providers.claude_api_provider import ClaudeApiChatProvider
    claude_model = os.environ.get("CEREBRO_CLAUDE_MODEL", "claude-sonnet-4-6")
    chat_provider = ClaudeApiChatProvider(model=claude_model)
    # Embeddings stay local — LancDB needs them; Claude API has no embed endpoint
    registry.register("claude", chat=chat_provider, embed=embed_provider)
    logger.info("Inference: Claude API ({})", claude_model)
```

`embed_provider` is whatever was already constructed (the llamacpp embedding provider). This means **the embedding server must still be started** (`make engine-embed`) even in Claude mode.

---

### Module C4 — Config: settings.toml & CLAUDE.md

**File:** `cerebro/settings.toml`

Add a `[claude]` section:

```toml
[claude]
model = "claude-sonnet-4-6"   # override with CEREBRO_CLAUDE_MODEL or ANTHROPIC env var
max_tokens = 4096
```

**File:** `cerebro/CLAUDE.md`

In the **Config** table, add two new rows:

```
CEREBRO_INFERENCE_BACKEND   claude              # new: routes inference to Anthropic API
CEREBRO_CLAUDE_MODEL        claude-sonnet-4-6   # which Claude model; default is sonnet-4-6
ANTHROPIC_API_KEY           sk-ant-...          # required when backend=claude
```

Also update the **Inference backends** section to add:

```
- `claude` + `ANTHROPIC_API_KEY`: routes all chat inference to Anthropic API.
  Embeddings still require the local llamacpp embed server (`make engine-embed`).
  Set CEREBRO_CLAUDE_MODEL to override the model (default: claude-sonnet-4-6).
```

---

### Module C5 — Surface Provider in /api/status

**File:** `cerebro/ui/tray/server.py`

The existing `/api/status` endpoint already returns `provider: str`. No structural change needed — when `claude` is registered as primary in `ProviderRegistry`, `registry.primary_name` already returns `"claude"`. The status response will automatically reflect `"provider": "claude"`.

Verify the `model` field also works: `registry.get_chat().model_id()` returns `"claude-sonnet-4-6"` from the new provider.

If the status response also returns `context_window`, it will correctly show `200000` from `ClaudeApiChatProvider.context_window()`.

---

### Module C6 — Frontend: Engine Indicator

**File:** `cerebro/ui/tray/src/components/status/EngineIndicator.tsx`

The `EngineIndicator` component reads `provider` from the status store. Add a display branch for Claude:

```tsx
// In the provider label map or switch:
case "claude":
  return <span className="engine-badge engine-claude">Claude API</span>;
```

Add a CSS class `engine-claude` with a purple/violet color to visually distinguish it from the local (green) indicator.

**File:** `cerebro/ui/tray/src/components/settings/ModelSelector.tsx`

When the status store reports `provider === "claude"`, show a static label ("Claude API — model managed by env var") instead of the local model picker dropdown, since model selection happens via `CEREBRO_CLAUDE_MODEL`, not the UI.

---

### Module C7 — Wizard Skip Logic

**File:** `cerebro/ui/tray/wizard.py` and `wizard_router.py`

The wizard's `check-llamacpp` step verifies that llama.cpp is installed. When `CEREBRO_INFERENCE_BACKEND=claude`, this check should be skipped (or show a "Using Claude API — llama.cpp not required for inference" message).

In `WizardSession`:

```python
@property
def skip_llamacpp_check(self) -> bool:
    return os.environ.get("CEREBRO_INFERENCE_BACKEND") == "claude"
```

In `wizard_router.py`, on the `check-llamacpp` route:

```python
if wizard.skip_llamacpp_check:
    return {"status": "skipped", "reason": "Claude API mode — llama.cpp not needed for inference"}
```

The `check-models` step should similarly be skipped or report Claude model availability based on `ANTHROPIC_API_KEY` presence instead.

---

### Module C8 — Tests

**New file:** `cerebro/tests/test_claude_api_provider.py`

Mock the `anthropic.AsyncAnthropic` client at the constructor level (same pattern as existing provider tests).

Tests to write:

```python
# test_complete_returns_text
# test_stream_yields_tokens
# test_is_available_false_when_no_api_key
# test_is_available_true_when_key_set
# test_complete_raises_on_auth_error
# test_complete_raises_on_connection_error
# test_split_system_separates_system_message
# test_split_system_no_system_message
# test_model_id_returns_configured_model
# test_context_window_200k
```

All tests mock `anthropic.AsyncAnthropic` — no live API calls. Follow the existing pattern from `tests/test_llamacpp_provider.py` using `unittest.mock.AsyncMock`.

---

## Dependency Summary

| What | How |
|---|---|
| Python package | `anthropic>=0.40.0` in `pyproject.toml` |
| API key | `ANTHROPIC_API_KEY` env var (never in settings.toml) |
| Embedding server | Still required in Claude mode (`make engine-embed`) |
| Inference server | **Not required** in Claude mode (`make engine` optional) |
| Switch | `CEREBRO_INFERENCE_BACKEND=claude make run` |

---

## Quick Start (After Implementation)

```bash
# 1. Install updated deps
make install

# 2. Set your API key (add to .env or shell profile)
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Start embedding server (still needed for RAG / memory)
make engine-embed

# 4. Run Cerebro in Claude API mode
CEREBRO_INFERENCE_BACKEND=claude make run

# 5. (Optional) Use a different Claude model
CEREBRO_INFERENCE_BACKEND=claude CEREBRO_CLAUDE_MODEL=claude-opus-4-7 make run
```

---

## Switching Between Modes

```bash
# Local mode (default)
make run

# Claude API mode
CEREBRO_INFERENCE_BACKEND=claude make run

# Local mode with MLX (Apple Silicon)
CEREBRO_MLX_ENABLED=true make run
```

No code changes are needed to switch — it's purely an environment variable.

---

## Files Changed / Created

| File | Action |
|---|---|
| `cerebro/pyproject.toml` | Add `anthropic>=0.40.0` dependency |
| `cerebro/core/inference/providers/claude_api_provider.py` | **Create** — new provider |
| `cerebro/main.py` | Add `elif backend == "claude"` branch |
| `cerebro/settings.toml` | Add `[claude]` section |
| `cerebro/CLAUDE.md` | Document new env vars and backend option |
| `cerebro/ui/tray/server.py` | Verify (likely no change needed) |
| `cerebro/ui/tray/src/components/status/EngineIndicator.tsx` | Add Claude badge |
| `cerebro/ui/tray/src/components/settings/ModelSelector.tsx` | Hide picker in Claude mode |
| `cerebro/ui/tray/wizard.py` | Add `skip_llamacpp_check` property |
| `cerebro/ui/tray/wizard_router.py` | Skip llama.cpp check when in Claude mode |
| `cerebro/tests/test_claude_api_provider.py` | **Create** — 10 unit tests |

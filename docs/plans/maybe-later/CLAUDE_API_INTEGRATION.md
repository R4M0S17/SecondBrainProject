> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


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

### Module C1 — Dependency ✅ DONE

**File:** `cerebro/pyproject.toml`

Add to `[project.dependencies]`:
```toml
anthropic>=0.40.0
```

Added `anthropic>=0.40.0` to both tracked `pyproject.toml` copies. Then run `make install` to update `.venv`.

---

### Module C2 — Claude API Chat Provider ✅ DONE

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
- Provider implementation added in both tracked code trees: `core/inference/providers/claude_api_provider.py` and `cerebro/core/inference/providers/claude_api_provider.py`.

---

### Module C3 — Wire Into main.py ✅ DONE

**Files:** `main.py` (repo root) and `cerebro/main.py`

When `CEREBRO_INFERENCE_BACKEND=claude`, the app registers `ClaudeApiChatProvider` with the existing local `LlamaCppEmbeddingProvider` (from `CEREBRO_LLAMACPP_EMBED_URL`), calls `registry.set_primary("claude")`, and skips llama.cpp chat / MLX-only setup.

---

### Module C4 — Config: settings.toml & CLAUDE.md ✅ DONE

**Files:** `config/settings.toml`, `cerebro/config/settings.toml`, `CLAUDE.md`, `cerebro/CLAUDE.md`

Added a `[claude]` table (`model`, `max_tokens`) to both settings files. Agent docs now list `CEREBRO_INFERENCE_BACKEND` values including `claude`, `CEREBRO_CLAUDE_MODEL`, `ANTHROPIC_API_KEY`, and an **Inference backends** bullet for Claude + local embeddings.

---

### Module C5 — Surface Provider in /api/status ✅ DONE

**Files:** `ui/tray/server.py`, `cerebro/ui/tray/server.py`

`/api/status` already exposed `provider` and `model` from the primary chat provider. Added **`context_window`** (from `chat.context_window()`) so Claude mode surfaces **200000** alongside `provider: "claude"` and the configured model id.

---

### Module C6 — Frontend: Engine Indicator ✅ DONE

**Files:** `ui/tray/src/components/status/EngineIndicator.tsx`, `cerebro/ui/tray/src/components/status/EngineIndicator.tsx`, `ui/tray/src/components/settings/ModelSelector.tsx`, `cerebro/ui/tray/src/components/settings/ModelSelector.tsx`, `ui/tray/src/api/types.ts`, `cerebro/ui/tray/src/api/types.ts`

- **EngineIndicator:** `provider === "claude"` shows the purple “Claude API” badge; root container includes the **`engine-claude`** class for styling hooks.
- **ModelSelector:** When `selectIsClaudeMode(status)` is true, shows the cloud panel plus the explicit line **“Claude API — model managed by env var”** (catalog rows remain informational only).
- **Types:** `StatusResponse` includes optional **`context_window`**.

---

### Module C7 — Wizard Skip Logic ✅ DONE

**Files:** `ui/tray/wizard.py`, `cerebro/ui/tray/wizard.py`, `ui/tray/wizard_router.py`, `cerebro/ui/tray/wizard_router.py`, `ui/tray/server.py`, `cerebro/ui/tray/server.py`, `ui/tray/src/api/client.ts`, `cerebro/ui/tray/src/api/client.ts`, `ui/tray/src/components/wizard/StepLlamaCpp.tsx`, `cerebro/ui/tray/src/components/wizard/StepLlamaCpp.tsx`, `ui/tray/src/components/wizard/StepModel.tsx`, `cerebro/ui/tray/src/components/wizard/StepModel.tsx`

- **`WizardSession`:** `skip_llamacpp_check` and `skip_models_check` when `CEREBRO_INFERENCE_BACKEND=claude` (case-insensitive).
- **`wizard_router`:** `POST .../step/llamacpp` and `.../step/model` return skip payloads with `ok` / `message` as appropriate.
- **`/api/wizard/*` in `server.py`:** `_wizard_claude_mode()` gates `GET /status`, `POST /check-llamacpp`, and `POST /check-models` so Claude mode skips llama health and uses `ANTHROPIC_API_KEY` for the models step.
- **Frontend:** Wizard steps read `status: "skipped"` from the tray API and show Claude-specific copy; `wizardCheckModels` / `wizardCheckLlamaCpp` typings extended.

---

### Module C8 — Tests ✅ DONE

**Files:** `tests/test_claude_api_provider.py`, `tests/test_api.py` (wizard skip coverage)

- **`tests/test_claude_api_provider.py`:** Mocks `anthropic.AsyncAnthropic`; covers `complete`, `stream`, availability, auth/connection errors, `_split_system`, `model_id`, and `context_window`. Runs even when the `anthropic` package is not installed (minimal stub in the test module).
- **`tests/test_api.py`:** `POST /api/wizard/check-llamacpp` and `check-models` behavior under `CEREBRO_INFERENCE_BACKEND=claude`.

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
| `pyproject.toml` | Add `anthropic>=0.40.0` dependency (root copy) |
| `cerebro/pyproject.toml` | Add `anthropic>=0.40.0` dependency |
| `core/inference/providers/claude_api_provider.py` | **Create** — new provider |
| `cerebro/core/inference/providers/claude_api_provider.py` | **Create** — mirrored provider copy |
| `main.py` | Add `claude` inference branch |
| `cerebro/main.py` | Add `claude` inference branch |
| `config/settings.toml` | Add `[claude]` section |
| `cerebro/config/settings.toml` | Add `[claude]` section |
| `CLAUDE.md` | Document new env vars and backend option |
| `cerebro/CLAUDE.md` | Document new env vars and backend option |
| `ui/tray/server.py` | `/api/status` `context_window`; `/api/wizard/*` Claude mode (C5/C7) |
| `cerebro/ui/tray/server.py` | Same as root `server.py` |
| `ui/tray/src/api/types.ts` | `StatusResponse.context_window` |
| `cerebro/ui/tray/src/api/types.ts` | Same |
| `ui/tray/src/components/status/EngineIndicator.tsx` | Claude branch + `engine-claude` class |
| `cerebro/ui/tray/src/components/status/EngineIndicator.tsx` | Same |
| `ui/tray/src/components/settings/ModelSelector.tsx` | Cloud panel + env-var line |
| `cerebro/ui/tray/src/components/settings/ModelSelector.tsx` | Same |
| `tests/test_api.py` | `/api/status` + wizard Claude-mode API tests |
| `tests/test_claude_api_provider.py` | **Create** — Claude provider unit tests (mocked SDK) |
| `ui/tray/wizard.py` | `skip_llamacpp_check` / `skip_models_check` |
| `cerebro/ui/tray/wizard.py` | Same |
| `ui/tray/wizard_router.py` | Skip llama + model steps in Claude mode |
| `cerebro/ui/tray/wizard_router.py` | Same |
| `ui/tray/src/api/client.ts` | Wizard check response typings |
| `cerebro/ui/tray/src/api/client.ts` | Same |
| `ui/tray/src/components/wizard/StepLlamaCpp.tsx` | Skipped-check UI |
| `cerebro/ui/tray/src/components/wizard/StepLlamaCpp.tsx` | Same |
| `ui/tray/src/components/wizard/StepModel.tsx` | Skipped models check + `detail` fallback |
| `cerebro/ui/tray/src/components/wizard/StepModel.tsx` | Same |

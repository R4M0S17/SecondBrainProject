# llama.cpp + Model Swapping — Implementation Plan

## Context
- `LlamaCppChatProvider` already exists at `core/inference/providers/llamacpp_provider.py`
- It talks to `llama-server` (OpenAI-compatible HTTP) at `http://127.0.0.1:8080`
- Current router: prefix-only (`/code`, `/academic`) — no AI classification
- `ProviderRegistry` does RAM-based fallback but does not manage processes

## Architecture
```
User input
    │
    ▼
SmolLM2-135M  port 8080  ← always on (~100MB RAM)
    │ classifies intent
    ├── general / calendar → Llama-3.2-3B  port 8081  (load on demand)
    └── code / academic   → Qwen-4B        port 8081  (load on demand)
                                           ↑ unloaded after 60s idle
```

---

## Phase 1 — Prerequisites ✅ COMPLETE

- [x] `SmolLM2-135M-Instruct-Q4_K_M.gguf` downloaded to `cerebro/bin/models/` (101 MB)
- [x] `Llama-3.2-3B-Instruct-Q4_K_M.gguf` downloaded to `cerebro/bin/models/` (1.9 GB)
- [x] `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` already in `cerebro/bin/models/` (2.3 GB)
- [x] `llama-server` installed at `/opt/homebrew/bin/llama-server`

---

## Phase 2 — ModelManager ✅ COMPLETE

**Goal:** Create the process manager that starts/stops `llama-server` instances and implements model swapping with an inactivity watchdog.

**File to create:** `core/inference/model_manager.py`

### Checklist
- [x] Create `core/inference/model_manager.py` with `ModelManager` class
- [x] Implement `start()` — launches SmolLM2 router on port 8080
- [x] Implement `stop()` — kills all llama-server processes on shutdown
- [x] Implement `ensure_specialist(role)` — loads Llama-3B or Qwen-4B on port 8081 on demand; swaps if different model needed
- [x] Implement `_watchdog()` — async loop that unloads specialist after 60s idle
- [x] Implement `_wait_healthy(port)` — polls `/health` until server is ready
- [x] Implement `router_url` property — returns `http://127.0.0.1:8080`
- [x] Implement `specialist_url` property — returns `http://127.0.0.1:8081`

### Key constants / env vars used
```
CEREBRO_MODELS_DIR   = cerebro/bin/models/
CEREBRO_ROUTER_MODEL = SmolLM2-135M-Instruct-Q4_K_M.gguf     port 8080  ctx 1024
CEREBRO_GENERAL_MODEL= Llama-3.2-3B-Instruct-Q4_K_M.gguf     port 8081  ctx 4096
CEREBRO_CODE_MODEL   = Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf port 8081 ctx 4096
CEREBRO_SWAP_TIMEOUT = 60   (seconds idle before unloading specialist)
```

### llama-server command template
```bash
llama-server \
  --model <path> \
  --port <port> \
  --ctx-size <ctx> \
  --n-gpu-layers 99 \
  --chat-template chatml \
  --log-disable
```

### Verify
```bash
cd cerebro
python -c "from core.inference.model_manager import ModelManager; print('OK')"
```

---

## Phase 3 — LLMRouter ✅ COMPLETE

**Goal:** Create an async intent classifier that calls SmolLM2 (port 8080) to decide which agent handles a query.

**File to create:** `core/agents/llm_router.py`

### Checklist
- [x] Create `core/agents/llm_router.py` with `LLMRouter` class
- [x] `__init__(base_url)` — default `http://127.0.0.1:8080`
- [x] `classify(query: str) -> str` — posts to `/v1/chat/completions`, returns one of: `"code"` `"calendar"` `"academic"` `"general"`
- [x] Use `max_tokens=5`, `temperature=0.0` (deterministic, fast)
- [x] Extract category with regex from response — fallback to `"general"` on any error
- [x] Truncate query to 300 chars before sending to router

### Classify prompt
```
Classify the user's request into ONE category:
- code: programming, debugging, scripts, technical problems
- calendar: scheduling, events, reminders, dates
- academic: notes, summaries, study, documents, PDFs
- general: everything else

Respond with ONLY the category word.

User: {query}
Category:
```

### Verify
```bash
cd cerebro
python -c "from core.agents.llm_router import LLMRouter; print('OK')"
```

---

## Phase 4 — Update SpecializedAgentRouter ✅ COMPLETE

**Goal:** Add LLM-based routing to `SpecializedAgentRouter` while keeping prefix routing as the fast path.

**File to modify:** `core/agents/specialized.py`

### Checklist
- [x] Add module-level `_LLM_CATEGORY_MAP` dict mapping `"code"→CODE_AGENT_ID`, `"calendar"→CALENDAR_AGENT_ID`, `"academic"→ACADEMIC_AGENT_ID`, `"general"→GENERAL_AGENT_ID`
- [x] Add `LLMRouter` import at top of file (TYPE_CHECKING guard)
- [x] Update `SpecializedAgentRouter.__init__` to accept optional `llm_router: LLMRouter | None = None`
- [x] Add `route_with_llm(raw_input: str) -> RouteResult` async method:
  - First checks prefixes (same logic as `route()`) — returns immediately if matched
  - If no prefix and `self._llm_router` is set: calls `await self._llm_router.classify()`
  - Maps category to agent_id via `_LLM_CATEGORY_MAP`
  - Falls back to `GENERAL_AGENT_ID` if llm_router is None
- [x] Keep existing `route()` sync method unchanged (no regression)

### Verify
```bash
cd cerebro
python -c "from core.agents.specialized import SpecializedAgentRouter; print('OK')"
make test tests/test_specialized_agents.py
```

---

## Phase 5 — Update ProviderRegistry ✅ COMPLETE

**Goal:** Add a method that coordinates with `ModelManager` to return the right `LlamaCppChatProvider` for a given agent.

**File to modify:** `core/inference/registry.py`

### Checklist
- [x] Add module-level `_AGENT_TO_ROLE` dict: `"code-v1"→"code"`, everything else → `"general"`
- [x] Add async method `get_chat_for_agent(agent_id, model_manager) -> ChatProvider`:
  - Looks up role from `_AGENT_TO_ROLE`
  - Calls `await model_manager.ensure_specialist(role)` to get port
  - Returns `LlamaCppChatProvider(model=agent_id, base_url=f"http://127.0.0.1:{port}", profile="coding" if role=="code" else "chat")`
- [x] Import `ModelManager` via TYPE_CHECKING guard + local import inside method (avoid circular import)

### Verify
```bash
cd cerebro
python -c "from core.inference.registry import ProviderRegistry; print('OK')"
make test tests/test_providers.py
```

---

## Phase 6 — Wire up main.py + env vars ✅ COMPLETE

**Goal:** Start `ModelManager` on FastAPI startup, shut it down cleanly, and use `route_with_llm` in the `/query` endpoint.

**Files to modify:** `main.py`, `.env.example`

### Checklist — main.py
- [x] Import `ModelManager` from `core.inference.model_manager`
- [x] Import `LLMRouter` from `core.agents.llm_router`
- [x] Create `model_manager = ModelManager()` inside `_build_app_state()` (conditional on `INFERENCE_BACKEND == "llamacpp"`)
- [x] Create `llm_router = LLMRouter()` inside `_build_app_state()` (conditional on `INFERENCE_BACKEND == "llamacpp"`)
- [x] Add `@asynccontextmanager async def lifespan(app)` in `server.py`: call `await model_manager.start()` before yield, `await model_manager.stop()` after (guarded by `app_state.model_manager is not None`)
- [x] Pass `lifespan=lifespan` to `FastAPI()` in `server.py`
- [x] In `SpecializedAgentRouter` instantiation: pass `llm_router=llm_router`
- [x] In `/query` handler: replace `router.route(...)` with `await router.route_with_llm(...)` (also in `/query/stream`)
- [x] In `/query` handler: use `await registry.get_chat_for_agent(agent_id, model_manager)` when `model_manager` is set (also in `/query/stream`)

### Checklist — .env.example
- [x] Add block at end of file:
```bash
# llama.cpp / Model Swapping
CEREBRO_MODELS_DIR=cerebro/bin/models
CEREBRO_ROUTER_MODEL=SmolLM2-135M-Instruct-Q4_K_M.gguf
CEREBRO_GENERAL_MODEL=Llama-3.2-3B-Instruct-Q4_K_M.gguf
CEREBRO_CODE_MODEL=Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf
CEREBRO_ROUTER_PORT=8080
CEREBRO_SPECIALIST_PORT=8081
CEREBRO_ROUTER_CTX=1024
CEREBRO_SPECIALIST_CTX=4096
CEREBRO_SWAP_TIMEOUT=60
```

### Verify
```bash
cd cerebro
python -c "import main; print('OK')"
```

---

## Phase 7 — Tests 🔲 TODO

**Goal:** Cover the two new modules and update existing tests that now need `ModelManager` mocked.

### Checklist — new files
- [x] Create `tests/test_model_manager.py`:
  - [x] `test_start_launches_router` — mock `subprocess.Popen`, verify called with SmolLM2 path and port 8080
  - [x] `test_ensure_specialist_general` — verify Llama-3B path and port 8081
  - [x] `test_ensure_specialist_code` — verify Qwen-4B path and port 8081
  - [x] `test_swap_kills_old_before_loading_new` — call `ensure_specialist("general")` then `ensure_specialist("code")`, verify first process terminated
  - [x] `test_watchdog_unloads_after_timeout` — mock `time.monotonic`, verify specialist proc killed after idle
  - [x] `test_stop_kills_all` — verify both router and specialist terminated on `stop()`

- [x] Create `tests/test_llm_router.py`:
  - [x] `test_classify_returns_code` — mock httpx to return `"code"`, assert result is `"code"`
  - [x] `test_classify_returns_general_on_http_error` — mock httpx to raise, assert fallback `"general"`
  - [x] `test_classify_truncates_long_query` — verify payload `content` never exceeds 300 chars + prompt

### Checklist — existing tests to update
- [ ] `tests/test_api.py` — mock `ModelManager.ensure_specialist` and `SpecializedAgentRouter.route_with_llm` where `/query` is tested
- [x] `tests/test_specialized.py` — added 5 tests for `route_with_llm` with mocked `LLMRouter`

### Verify
```bash
cd cerebro
make test
# Expected: all existing 111+ tests pass + new tests green
make lint
```

---

## Recommendations

1. **Keep Ollama as fallback** — `OllamaChatProvider` stays registered in `ProviderRegistry`. If `llama-server` fails to start, the registry falls back automatically.

2. **Prefix routing stays as fast path** — SmolLM2 is only called when there is no `/code`, `/academic`, `/calendar` prefix. This ensures reliability even if the router model misbehaves.

3. **60s idle timeout, not 30s** — 30s causes repeated 10–15s reload delays in normal usage. Start at 60s.

4. **`--n-gpu-layers 99` always** — M1 unified memory means all layers on Metal GPU at no extra cost. Never run on CPU.

5. **Show loading state in the UI** — model swapping takes 10–15s. The frontend should show "Cargando especialista..." during `ensure_specialist`. Add a `/status` field to the `/query` response or use an SSE event.

6. **SmolLM2 context = 1024 max** — the router only sees the current query, never history. Keeps RAM footprint at ~100MB instead of ~250MB.

7. **Qwen-4B is code-only** — resist loading it for general tasks. The specialization is the whole point.

---

## Phase 8 — UI Loading State for Model Swapping ✅ COMPLETE

**Goal:** Surface specialist loading state to the frontend so it can show "Cargando especialista…" during the 10–15 s cold load of a specialist model. Uses SSE events in the streaming path and a new field in `/status`.

**Files modified:** `core/inference/model_manager.py`, `ui/tray/server.py`

### Checklist — model_manager.py
- [x] Add `specialist_status` property returning `{"role": str | None, "loaded": bool}`

### Checklist — server.py
- [x] Add `specialist_role: str | None` and `specialist_loaded: bool` to `StatusResponse`
- [x] Populate specialist fields in `status_endpoint()` from `app_state.model_manager.specialist_status`
- [x] In `query_stream_endpoint`: skip outer `get_chat_for_agent` call when `model_manager` is set — resolve model identity inside each generator instead
- [x] In `event_generator_tools`: declare `nonlocal model_name, provider_name, warnings`; emit `{"event": "specialist_loading"}` SSE before calling `get_chat_for_agent`; update `model_name` / `provider_name` from the returned chat provider
- [x] In `event_generator`: same pattern — emit loading event before blocking `get_chat_for_agent`, update metadata vars via `nonlocal`

### SSE protocol — what the frontend receives
```
data: {"event": "specialist_loading"}   ← emitted immediately; show spinner
... 10–15 s silence while llama-server loads ...
data: {"token": "Hola"}                 ← first token; hide spinner
data: {"token": " mundo"}
...
data: {"metadata": {...}, "conversation_id": "..."}
data: [DONE]
```

### /status response additions
```json
{
  "specialist_role": "code",   // null when no specialist is loaded
  "specialist_loaded": true    // false while loading or after idle unload
}
```

### Verify
```bash
cd cerebro
make test tests/test_api.py tests/test_model_manager.py
# Expected: 34 tests pass, 0 failures
```


---

## Phase 9 — Replace Ollama with llama.cpp for Embeddings (Full llama.cpp Stack) ✅ COMPLETE

**Goal:** Eliminate the Ollama dependency entirely. Serve embeddings through `llama-server` on port 8082 using `jina-embeddings-v5-text-nano-retrieval-GGUF`, making `llama-server` the single inference backend for routing, chat, and embeddings.

**Why:** Architecturally consistent — all inference flows through `llama-server`. No Ollama process required at all when `INFERENCE_BACKEND=llamacpp`.

---

### Phase 9a — Prerequisites

- [x] Download `jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF` from HuggingFace into `cerebro/bin/models/`:
  ```bash
  .venv/bin/hf download jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF \
    --include "*.gguf" \
    --local-dir bin/models/
  ```
  Downloaded all quantizations. Using `v5-nano-retrieval-Q4_K_M.gguf` (150 MB) as default — best balance for M1 Metal GPU.

- [ ] Confirm `llama-server` supports `--embedding` flag:
  ```bash
  llama-server --help | grep embedding
  ```

---

### Phase 9b — Extend ModelManager (`core/inference/model_manager.py`)

**Goal:** Launch and manage a third `llama-server` instance on port 8082 for embeddings. This server is always-on (like the router on 8080), never swapped.

#### Checklist
- [ ] Add env var constants at the top of the file:
  ```python
  CEREBRO_EMBED_MODEL = os.getenv("CEREBRO_EMBED_MODEL", "jina-embeddings-v5-text-nano-retrieval-f16.gguf")
  CEREBRO_EMBED_PORT  = int(os.getenv("CEREBRO_EMBED_PORT", "8082"))
  CEREBRO_EMBED_CTX   = int(os.getenv("CEREBRO_EMBED_CTX", "512"))
  ```
- [ ] Add `self._embed_proc: subprocess.Popen | None = None` to `__init__`
- [ ] In `start()`: after launching the router, also launch the embedding server:
  ```bash
  llama-server \
    --model <embed_model_path> \
    --port 8082 \
    --ctx-size 512 \
    --n-gpu-layers 99 \
    --embedding \
    --log-disable
  ```
  Assign result to `self._embed_proc`. Then call `await self._wait_healthy(8082)`.
- [ ] In `stop()`: terminate `self._embed_proc` (same pattern as router — `proc.terminate(); proc.wait(timeout=5)`)
- [ ] Add `embed_url` property returning `"http://127.0.0.1:8082"`
- [ ] Add `specialist_status` dict update: include `"embed_loaded": self._embed_proc is not None`

#### llama-server command for embeddings
```bash
llama-server \
  --model <path/to/jina-embeddings-v5-text-nano-retrieval-f16.gguf> \
  --port 8082 \
  --ctx-size 512 \
  --n-gpu-layers 99 \
  --embedding \
  --log-disable
```

Note: `--embedding` enables the `/v1/embeddings` endpoint and disables the chat completion endpoint on that port. Do NOT use `--chat-template` here.

#### Verify
```bash
cd cerebro
python -c "from core.inference.model_manager import ModelManager; print('OK')"
```

---

### Phase 9c — Create LlamaCppEmbeddingProvider (`core/inference/providers/llamacpp_embedding_provider.py`)

**Goal:** An `EmbeddingProvider` implementation that POSTs to `llama-server`'s `/v1/embeddings` endpoint.

**File to create:** `core/inference/providers/llamacpp_embedding_provider.py`

#### Checklist
- [ ] Create class `LlamaCppEmbeddingProvider` implementing the same interface as `OllamaEmbeddingProvider`
- [ ] `__init__(base_url: str = "http://127.0.0.1:8082", model: str = "jina-embeddings")`:
  - Store `self._base_url` and `self._model`
- [ ] Implement `embed(texts: list[str]) -> list[list[float]]`:
  - POST to `{base_url}/v1/embeddings` with body `{"model": self._model, "input": texts}`
  - Use `httpx.AsyncClient` (same pattern as `LlamaCppChatProvider`)
  - Parse response: `[item["embedding"] for item in response_json["data"]]`
  - Raise `RuntimeError` on HTTP error with status + body in message
- [ ] Implement `embed_one(text: str) -> list[float]` as `(await self.embed([text]))[0]`
- [ ] Add `@property name(self) -> str` returning `"llamacpp-embed"`

#### Interface contract (match OllamaEmbeddingProvider)
```python
class LlamaCppEmbeddingProvider:
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_one(self, text: str) -> list[float]: ...
    @property
    def name(self) -> str: ...
```

#### Verify
```bash
cd cerebro
python -c "from core.inference.providers.llamacpp_embedding_provider import LlamaCppEmbeddingProvider; print('OK')"
```

---

### Phase 9d — Update ProviderRegistry (`core/inference/registry.py`)

**Goal:** When `INFERENCE_BACKEND == "llamacpp"`, return `LlamaCppEmbeddingProvider` instead of `OllamaEmbeddingProvider` from the registry. Ollama is not required at all in this mode.

#### Checklist
- [ ] Add import (TYPE_CHECKING guard):
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from core.inference.providers.llamacpp_embedding_provider import LlamaCppEmbeddingProvider
  ```
- [ ] Add async method `get_embedding_provider(model_manager=None) -> EmbeddingProvider`:
  - If `model_manager` is not None (i.e., llamacpp mode): local import `LlamaCppEmbeddingProvider`, return `LlamaCppEmbeddingProvider(base_url=model_manager.embed_url)`
  - Otherwise: return existing `OllamaEmbeddingProvider` (unchanged fallback)
- [ ] Do NOT remove `OllamaEmbeddingProvider` — it stays as the fallback when `model_manager` is None

#### Verify
```bash
cd cerebro
python -c "from core.inference.registry import ProviderRegistry; print('OK')"
make test tests/test_providers.py
```

---

### Phase 9e — Wire into server.py and main.py

**Goal:** Use `LlamaCppEmbeddingProvider` in all places that currently call `OllamaEmbeddingProvider` when running in llamacpp mode.

**Files to modify:** `ui/tray/server.py` (or `main.py` — wherever embedding provider is instantiated)

#### Checklist
- [ ] Find all call sites of `OllamaEmbeddingProvider(...)` in `main.py` / `server.py`
- [ ] In `_build_app_state()` (or equivalent): replace direct `OllamaEmbeddingProvider()` instantiation with `await registry.get_embedding_provider(model_manager)` — use `model_manager` if it exists, else None
- [ ] The `ContextBuilder`, `VectorStore`, and RAG pipeline receive the provider via dependency injection — no changes needed there if the interface matches

#### Verify
```bash
cd cerebro
python -c "import main; print('OK')"
```

---

### Phase 9f — Update .env.example

- [ ] Add to the `# llama.cpp / Model Swapping` block:
  ```bash
  CEREBRO_EMBED_MODEL=jina-embeddings-v5-text-nano-retrieval-f16.gguf
  CEREBRO_EMBED_PORT=8082
  CEREBRO_EMBED_CTX=512
  ```

---

### Phase 9g — Tests

#### New test file: `tests/test_llamacpp_embedding_provider.py`
- [ ] `test_embed_returns_vectors` — mock `httpx.AsyncClient.post` to return `{"data": [{"embedding": [0.1, 0.2]}]}`, assert result equals `[[0.1, 0.2]]`
- [ ] `test_embed_one_returns_single_vector` — same mock, assert single list returned
- [ ] `test_embed_raises_on_http_error` — mock post to raise `httpx.HTTPStatusError`, assert `RuntimeError` raised

#### Updates to existing tests
- [ ] `tests/test_model_manager.py` — add `test_start_launches_embed_server`: verify `subprocess.Popen` called with embed model path and `--embedding` flag on port 8082
- [ ] `tests/test_model_manager.py` — add `test_stop_kills_embed_server`: verify `self._embed_proc.terminate()` called in `stop()`
- [ ] `tests/test_providers.py` — add `test_get_embedding_provider_llamacpp`: mock `ModelManager`, assert returns `LlamaCppEmbeddingProvider`
- [ ] `tests/test_providers.py` — add `test_get_embedding_provider_fallback`: pass `model_manager=None`, assert returns `OllamaEmbeddingProvider`
- [ ] `tests/test_api.py` — where embedding provider is mocked, update mock target to `LlamaCppEmbeddingProvider` when `model_manager` fixture is active

#### Verify
```bash
cd cerebro
make test
# Expected: all tests pass, no Ollama calls when INFERENCE_BACKEND=llamacpp
make lint
```

---

### Final Architecture (after Phase 9)

```
llama-server port 8080  ← SmolLM2-135M router     (always on, ~100 MB)
llama-server port 8081  ← Llama-3B or Qwen-4B     (load on demand, unload after 60s)
llama-server port 8082  ← Jina Embeddings v5 nano  (always on, ~270 MB)

Ollama: NOT required when INFERENCE_BACKEND=llamacpp
```

Total always-on RAM footprint: ~370 MB (100 MB router + 270 MB embeddings)
Specialist RAM (on demand): ~1.9 GB (Llama-3B) or ~2.3 GB (Qwen-4B)
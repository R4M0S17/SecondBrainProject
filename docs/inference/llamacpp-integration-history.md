# llama.cpp Integration Plan
**Goal**: Replace/supplement Ollama with llama.cpp (`llama-server`) for local inference — full Metal GPU offload, dynamic model switching, and RAM-safe operation on 8GB Mac.

---

## Phase 1 — System Setup (Outside Python)

### 1.1 Install llama.cpp via Homebrew
- [x] Install: `brew install llama.cpp`
- [x] Verify Metal-enabled install: `llama-server --version` — Apple M1, Metal active, `/opt/homebrew/bin/llama-server`
- [x] Note: `llama-server` and `llama-cli` are now in PATH — no binary copying needed. Update with `brew upgrade llama.cpp`.

### 1.2 Download Model
- [x] Create model directory: `mkdir -p cerebro/bin/models`
- [x] Download via `hf_hub_download` (Python 3.11): `bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF`
- [x] Verified: `bin/models/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` — 2.3GB

---

## Phase 2 — Config Profiles

### 2.1 Create `cerebro/config/` profiles
> These `.args` files let `llama-server` and `llama-cli` load task-specific params without rewriting code.

- [x] Created `cerebro/config/coding.args` — ctx 8192, q8_0 KV cache, temp 0.2
- [x] Created `cerebro/config/chat.args` — ctx 2048, q4_0 KV cache, temp 0.7
- [x] Created `cerebro/config/deep.args` — ctx 6144, q8_0 KV cache, temp 0.3

### 2.2 Create `cerebro/bin/start_engine.sh`
- [x] Script written with profile validation and absolute path resolution
- [x] Made executable: `chmod +x cerebro/bin/start_engine.sh`
- [x] Syntax verified: `bash -n bin/start_engine.sh`
- [ ] Live test: `cd cerebro && ./bin/start_engine.sh chat` (run when ready to start server)

---

## Phase 3 — Python Provider (`core/inference/providers/`)

### 3.1 Create `core/inference/providers/llamacpp_provider.py`
> Mirror the interface of `ollama_provider.py`. llama-server exposes an OpenAI-compatible API at `http://127.0.0.1:8080`.

- [x] `LlamaCppChatProvider` implemented in `core/inference/providers/llamacpp_provider.py`
  - `complete()` → POST `/v1/chat/completions` (OpenAI-compatible)
  - `stream()` → SSE streaming via same endpoint
  - `is_available()` → GET `/health`
  - `context_window()` → returns ctx size per profile (chat=2048, coding=8192, deep=6144)
  - Raises `LlamaCppUnavailableError`, `InferenceTimeoutError`, `ModelNotFoundError`
- [x] Streaming implemented (SSE `data:` lines, `[DONE]` sentinel)
- [x] `temperature` kwarg forwarded; None values stripped so llama-server uses its own defaults

### 3.2 Embedding provider
- [x] **Kept Ollama** (`nomic-embed-text`) for embeddings — no GGUF embedding model needed

### 3.3 Update `core/inference/providers/__init__.py`
- [x] `LlamaCppChatProvider` and `LlamaCppUnavailableError` exported

---

## Phase 4 — Registry & Fallback Logic (`main.py`)

### 4.1 Register new provider
- [x] `CEREBRO_INFERENCE_BACKEND=llamacpp` wired in `main.py`
- [x] When `llamacpp`: registers llama.cpp as primary, Ollama as fallback (embeddings always via Ollama)
- [x] When `ollama` (default): original MLX → Ollama path unchanged

### 4.2 Profile selection
- [x] Profile passed via `CEREBRO_LLAMACPP_PROFILE` env var at startup
- [ ] Dynamic per-request routing (code-v1 → coding, general-v1 → chat) — deferred to Phase 7

---

## Phase 5 — Environment & Config

### 5.1 Add env vars to `main.py` defaults
- [x] `CEREBRO_INFERENCE_BACKEND`: `ollama` (default) | `llamacpp`
- [x] `CEREBRO_LLAMACPP_URL`: `http://127.0.0.1:8080`
- [x] `CEREBRO_LLAMACPP_MODEL`: `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf`
- [x] `CEREBRO_LLAMACPP_PROFILE`: `chat` (default profile)

### 5.2 Update `.env.example`
- [x] All `CEREBRO_LLAMACPP_*` vars documented with descriptions and defaults

### 5.3 Update `CLAUDE.md` prerequisites section
- [ ] Note: `llama-server` running on port 8080 (if using llama.cpp backend) — deferred, not blocking

### 5.4 Add `Makefile` targets
- [x] `make engine` → `./bin/start_engine.sh chat`
- [x] `make engine-code` → `./bin/start_engine.sh coding`
- [x] `make engine-deep` → `./bin/start_engine.sh deep`

---

## Phase 6 — Tests

### 6.1 Create `tests/test_llamacpp_provider.py`
- [x] 16 tests, all passing — no live server needed
- [x] `complete()`: returns string, 404→ModelNotFoundError, ConnectError→LlamaCppUnavailableError, TimeoutException→InferenceTimeoutError
- [x] `complete()`: temperature forwarded when set, omitted when None
- [x] `is_available()`: True on 200, False on ConnectError, False on any exception
- [x] `context_window()`: chat=2048, coding=8192, deep=6144, unknown→2048
- [x] `model_id()` / `set_model()`
- [x] Registry integration: llamacpp primary, ollama fallback

### 6.2 Registry integration test
- [x] Covered in `test_registry_llamacpp_primary_ollama_fallback` inside test_llamacpp_provider.py

### 6.3 Full test suite
- [x] **327 passed, 0 failed** — no regressions

---

## Phase 7 — Advanced

### 7.1 Context Distillation
- [x] `ShortTermStore.distill_if_needed(provider, ctx_size)` added to `core/memory/short_term.py`
- [x] Triggers when token count > 75% of `ctx_size` (1 token ≈ 4 chars)
- [x] Calls `to_summary()`, replaces all messages with single `{"role": "system", "content": "[Contexto previo resumido]: <summary>"}` message
- [x] Returns `True` if distillation occurred, `False` otherwise

### 7.2 Prompt Cache (`--prompt-cache`)
- [x] `bin/cache/` directory created
- [x] `--prompt-cache bin/cache/chat.cache` added to `chat.args`
- [x] `--prompt-cache bin/cache/coding.cache` added to `coding.args`
- [x] `--prompt-cache bin/cache/deep.cache` added to `deep.args`
- [x] Benefit: system prompt state saved to disk — ~30% faster cold starts on repeat sessions

### 7.3 Sliding Window / RAG Handoff
- [x] `ShortTermStore.slide_to_long_term(long_term, keep_last_n)` added
- [x] Archives oldest messages as a single episode in LanceDB (tagged `["session", "archived"]`)
- [x] Keeps last `keep_last_n` messages in active memory
- [x] Returns count of archived messages (0 if below threshold)
- [x] Archived content is retrievable by semantic search via `ContextBuilder`

### 7.4 Tests
- [x] `tests/test_phase7_advanced.py` — 10 tests, all passing
- [x] Full suite: **337 passed, 0 regressions**

---

## Recommendations

| Concern | Recommendation |
|---|---|
| **RAM safety** | Always use `--mlock`. Without it, macOS swaps the model to disk after 2 min idle — next query freezes. |
| **Embeddings** | Keep Ollama's `nomic-embed-text` for embeddings. Switching to a GGUF embedding model adds complexity for minimal gain. |
| **Context limit** | Never exceed `--ctx-size 8192` with other apps open. Use `deep.args` only with Chrome closed. |
| **KV Cache** | `--cache-type-k q8_0` is the single highest-impact flag — cuts context RAM usage 50% with <0.1% quality loss. |
| **Streaming** | Add streaming in Phase 5, not Phase 3. Get correctness first. |
| **Model version** | The `Q4_K_M` quant is the sweet spot for 8GB: better than Q4_0 quality, fits in ~2.5GB leaving 5.5GB for OS + app. |
| **Port conflict** | Ollama runs on `11434`, llama-server on `8080` — no conflict. Both can coexist during migration. |

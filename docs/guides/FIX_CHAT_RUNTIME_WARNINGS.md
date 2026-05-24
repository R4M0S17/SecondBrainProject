# Fix: Chat runtime warnings (embeddings, memory, context enricher)

> **Status: DONE** — 8 GB profile uses **one** `llama-server` on `:8080` (Qwen2.5-Coder-3B) + **local** embeddings (no `:8082` during chat). Backend on `:7842`.

## What changed (ImplemeFIX modules)

| Module | Summary |
|--------|---------|
| **4 — Temporal** | Single `_now_human()` source; English date/time in system + user preamble |
| **5 — Parser** | Balanced JSON extraction, fence stripping, friendly fallback on parse failure |
| **1 — Prompt cache** | `--cache-prompt` / `--cache-ram` in `config/chat.args`; `sync_prompt_cache()` on boot |
| **6 — Filesystem** | `CEREBRO_AUTHORIZED_*_PATHS`; `PathNotAuthorizedError` surfaced to chat |
| **3 — Embeddings** | `CEREBRO_EMBEDDINGS_BACKEND=local` → `sentence-transformers` (~120 MB), no embed server |
| **2 — Model** | Default chat GGUF → `Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf`, `--temp 0.5` |
| **7 — Smoke** | `make smoke` + [`manual_tests/post_implemefix_smoke.md`](../../manual_tests/post_implemefix_smoke.md) |

If you see logs like this when sending a message in Cerebro:

```
WARNING  | core.cache.embedding_cache - Embedding provider error ...
ERROR    | core.cache.embedding_cache - Cannot connect to llama-server (embeddings) at http://127.0.0.1:8082
WARNING  | core.memory.long_term - Embedding unavailable, skipping long-term memory search
WARNING  | core.agents.context_enricher - ContextEnricher.enrich timed out after 3s
DEBUG    | core.inference.registry - RAM available: 1.08 GB
```

this guide explains what is wrong and how to fix it.

**Related runbooks:** [`howToRun.md`](howToRun.md) · [`8gb-mac-quickstart.md`](8gb-mac-quickstart.md) · [`llamacpp-run-guide.md`](llamacpp-run-guide.md)

---

## Is chat broken?

**Not necessarily.** These are mostly **non-fatal** warnings:

| Log | Meaning | Chat still works? |
|-----|---------|-------------------|
| `Cannot connect ... :8082` | No **embedding** server | Yes, but **no RAG / long-term memory** over your documents |
| `skipping long-term memory search` | LanceDB search skipped | Yes for plain Q&A |
| `ContextEnricher ... timed out` | Calendar/file “ambient context” skipped | Yes |
| `RAM available: 1.08 GB` | Mac is memory-tight | Slower; risk of OOM if you load more models |

**Minimum for basic chat:** Terminal 1 (`make engine` on `:8080`) + Terminal 3 (`make run` on `:7842`).

**Full memory / RAG / indexing (8 GB):** use in-process embeddings (no second terminal) — see **Fix C** below. Legacy setups still use Terminal 2 (`make engine-embed` on `:8082`).

---

## Fix C — In-process embeddings (8 GB, Module 3)

On machines with ≤10 GB RAM, Cerebro defaults to **local** embeddings (`sentence-transformers/all-MiniLM-L6-v2`, ~120 MB) instead of a second `llama-server` on `:8082`.

```bash
pip install -e ".[embeddings]"
# Optional explicit override (also set in config/profiles/lite-8gb.env):
export CEREBRO_EMBEDDINGS_BACKEND=local
make run   # only make engine needed for chat — not make engine-embed
```

After switching from `llamacpp` to `local`, re-embed existing LanceDB data once:

```bash
.venv/bin/python scripts/reindex_embeddings.py
```

| Env | Values |
|-----|--------|
| `CEREBRO_EMBEDDINGS_BACKEND` | `local` (default ≤10 GB) \| `llamacpp` (legacy HTTP server) |
| `CEREBRO_LOCAL_EMBED_MODEL` | HuggingFace model id (default: `sentence-transformers/all-MiniLM-L6-v2`) |

---

## Root cause 1: Missing embedding server (main error)

Cerebro uses **two** llama-server processes in simple mode (`CEREBRO_LLAMACPP_SIMPLE=true`, the default):

| Port | Role | Started with | Config |
|------|------|--------------|--------|
| **8080** | Chat (`llama-3.2-3b-instruct-...`) | `make engine` | `config/chat.args` |
| **8082** | Embeddings (`v5-nano-retrieval-...`) | `make engine-embed` | `config/embed.args` |

`make engine` alone only starts chat. When `CEREBRO_EMBEDDINGS_BACKEND=llamacpp` (legacy), the backend calls `http://127.0.0.1:8082/v1/embeddings` (override with `CEREBRO_LLAMACPP_EMBED_URL`) for memory search and document indexing — hence the connection error if `make engine-embed` is not running.

`bin/start_engine.sh embed` checks that the GGUF exists before launch; if it is missing, the script prints a pointer to this guide.

### Fix A — Download the embedding model (one-time)

Your `bin/models/` folder must contain **both** GGUF files. Many setups only have the chat model.

From the **repository root** (where `Makefile` and `bin/` live):

```bash
cd /path/to/SecondBrain

# Requires huggingface-cli (installed with: make install → huggingface_hub)
.venv/bin/hf download jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF \
  v5-nano-retrieval-Q4_K_M.gguf \
  --local-dir bin/models
```

Expected file:

`bin/models/v5-nano-retrieval-Q4_K_M.gguf` (~150 MB)

Verify:

```bash
ls -lh bin/models/
# llama-3.2-3b-instruct-q4_k_m.gguf
# v5-nano-retrieval-Q4_K_M.gguf
```

Or run the model checker:

```bash
.venv/bin/python scripts/diag/check_models.py
```

### Fix B — Start the embedding server (second engine terminal)

```bash
cd /path/to/SecondBrain
make engine-embed
```

Wait for:

`main: server is listening on http://127.0.0.1:8082`

Verify health and a real embedding response:

```bash
curl -sf http://127.0.0.1:8082/health

curl -s http://127.0.0.1:8082/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"jina-embeddings","input":"hello"}' | head -c 200
```

You should see JSON with an `embedding` array (1024 floats for the Jina nano model).

### Full terminal layout (recommended)

| # | Directory | Command | Port |
|---|-----------|---------|------|
| 1 | repo root | `make engine` | 8080 chat |
| 2 | repo root | `make engine-embed` | 8082 embed |
| 3 | repo root | `source .venv/bin/activate && CEREBRO_INFERENCE_BACKEND=llamacpp make run` | 7842 API |
| 4 | `ui/tray` | `npx tauri dev` | UI (optional) |

On **8 GB Macs**, prefer the lite profile instead of raw `make engine` / `make run` — see [Root cause 3](#root-cause-3-low-free-ram-1-gb) and [`8gb-mac-quickstart.md`](8gb-mac-quickstart.md).

---

## Root cause 2: Context enricher timeout (optional)

`ContextEnricher.enrich timed out after 3s` means macOS calendar/file lookups (AppleScript) did not finish in time. Common on **8 GB RAM** when the chat model is already loaded.

When RAM is **critical**, the backend also **skips** the enricher automatically (`run_ram_preflight` → `should_skip_context_enricher()`), even if `CEREBRO_PROACTIVE_CONTEXT=true`.

**Disable proactive context** (recommended on M1 8 GB if you still see timeouts):

```bash
export CEREBRO_PROACTIVE_CONTEXT=false
source .venv/bin/activate
CEREBRO_INFERENCE_BACKEND=llamacpp make run
```

Or add to `.env` in the repo root (loaded by `main.py` if present):

```
CEREBRO_PROACTIVE_CONTEXT=false
```

Default is `true` (`main.py`). The bundled `config/profiles/lite-8gb.env` still sets `true`; override in `.env` if calendar/file ambient context is not worth the RAM cost.

Chat works without this; you only lose automatic “upcoming events / recent files” injection.

**Calendar tools** (separate from the enricher) need **Automation → Calendar** for Terminal/Python — see [`8gb-mac-quickstart.md`](8gb-mac-quickstart.md#3-calendar-automation-macos).

---

## Root cause 3: Low free RAM (~1 GB)

`RAM available: 1.08 GB` with chat + macOS is normal on an **8 GB M1** after loading ~2 GB for Llama 3.2 3B.

**Tips:**

1. Quit heavy apps (Chrome, Xcode) before `make engine`.
2. Run **only** `make engine` + `make engine-embed` + backend — avoid duplicate `llama-server` processes.
3. Do **not** use `CEREBRO_LLAMACPP_SIMPLE=false` unless you have all router/specialist/embed GGUFs and ≥16 GB RAM.
4. Use the **chat** profile only (`make engine` or `make engine-lite`), not `engine-code` / `engine-deep`, on 8 GB machines.
5. Prefer **`make engine-lite`** + **`make lite`** (loads `config/profiles/lite-8gb.env`: MLX off, conservative RAM thresholds).

If the Mac swaps heavily, chat becomes slow or freezes — free RAM first.

### API and UI signals (not only logs)

| Signal | Where | Meaning |
|--------|-------|---------|
| `ram_pressure` | `GET /api/status` | `ok` / `warn` / `critical` from `RamMonitor` |
| `ram_pressure_critical` | `metadata.warnings` on each reply | Shown as an amber toast in the chat UI |
| `ram_pressure_warn` | same | Elevated pressure; chat may still proceed |
| `llama_server` | `GET /api/health` | `up` / `restarting` / `down`; background monitor can restart chat engine after crashes |

Example:

```bash
curl -s http://127.0.0.1:7842/api/status | python3 -m json.tool
curl -s http://127.0.0.1:7842/api/health | python3 -m json.tool
```

Under critical RAM, preflight may **purge the prompt cache** and **clear the embedding cache** to avoid swap thrash — another reason to fix embed connectivity separately.

---

## Prompt cache (chat latency)

The chat profile (`config/chat.args`) enables llama.cpp **KV prompt reuse**:

- `--cache-prompt` — reuse prefix KV across turns (default on recent builds; set explicitly in chat profile).
- `--cache-ram 2048` — cap in-RAM prompt cache on 8 GB Macs (MiB).

The Python backend keeps a **fingerprint sidecar** at `bin/cache/chat.cache.sha256`. When the stable system prompt or registered tool set changes, `sync_prompt_cache()` deletes `bin/cache/chat.cache` so the next engine session does not reuse a stale prefix.

**Clear manually when debugging odd agent behaviour:**

```bash
rm -f bin/cache/chat.cache bin/cache/chat.cache.sha256
make engine   # restart chat llama-server
```

Env override: `CEREBRO_PROMPT_CACHE_PATH` (see `core/inference/prompt_cache.py`).

> **Note:** Current Homebrew `llama-server` builds use `--cache-prompt` / `--cache-ram`, not the older `--prompt-cache` on-disk file flags. Fingerprint invalidation is still required so tool/prompt changes do not silently reuse the wrong KV prefix.

---

## Quick checklist

Use this after any setup change:

- [ ] `curl -sf http://127.0.0.1:8080/health` → OK (chat)
- [ ] `curl -sf http://127.0.0.1:8082/health` → OK (embeddings)
- [ ] `bin/models/v5-nano-retrieval-Q4_K_M.gguf` exists
- [ ] Embed smoke: `curl` to `/v1/embeddings` with `"model":"jina-embeddings"` returns data
- [ ] Backend running: `curl -sf http://127.0.0.1:7842/api/status`
- [ ] (8 GB Mac) `make engine-lite` + `make lite`, or `CEREBRO_PROACTIVE_CONTEXT=false`
- [ ] (Optional) `bash scripts/diag/doctor.sh` exits 0

After embeddings are up, `Cannot connect to llama-server (embeddings)` should stop on the **next** message (embedding errors are not cached).

---

## Automated verification

With chat + backend running (embed optional for smoke):

```bash
make smoke
```

Requires `CEREBRO_BASE_URL=http://127.0.0.1:7842` and a healthy chat engine on `:8080`.

Full environment doctor (models, RAM, calendar permission):

```bash
bash scripts/diag/doctor.sh
echo "exit=$?"
```

---

## Still failing?

1. **Port 8082 in use:** `kill $(lsof -t -i :8082)` then `make engine-embed` again.
2. **Wrong embed model name in API:** backend sends model id `jina-embeddings` in the JSON payload (`LlamaCppEmbeddingProvider`). Do not change unless you know the server’s model alias from `llama-server` logs.
3. **Ollama:** Older docs mention `ollama serve` + `nomic-embed-text`. Current code uses **llama.cpp on 8082**, not Ollama, when `CEREBRO_INFERENCE_BACKEND=llamacpp`. Update [`howToRun.md`](howToRun.md) if it still mentions Ollama for embeddings.
4. **Indexing stuck / no memory hits:** indexing and `POST /api/index` also need the embed server on `:8082`.
5. **Chat engine died silently:** check `GET /api/health`; the health monitor may restart `make engine` up to a rate limit when RAM allows.

For engine/port issues, see also [`howToRun.md`](howToRun.md) and the port-8080 bind error fix (kill stale `llama-server` with `lsof`).

---

## Document history

| Date | Change |
|------|--------|
| 2026-05 | Initial guide: embed server on 8082, proactive context, RAM notes |
| 2026-05 | Completed: status DONE, API warnings, lite profile, doctor/smoke, terminal layout fix |

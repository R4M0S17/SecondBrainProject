# Cerebro — Agentic Personal OS

Local AI desktop app. Python backend + React/Tauri frontend communicating over HTTP on port 7842.

## Commands
```bash
make install          # venv + deps + pre-commit
make run              # python main.py → FastAPI on :7842
make test             # pytest (all tests mock inference backend, no live service needed)
make test tests/test_api.py::fn  # single test
make lint             # black + ruff + mypy
make engine           # start llama.cpp server (port 8080)

cd ui/tray && npm install && npm run dev   # frontend dev server (Vite + Tauri)
cd ui/tray && npm run build               # production desktop build
```

## Architecture

### Entry point
`main.py` wires everything together: builds inference providers, memory stores, agent runtime, and injects them into `app_state` in `ui/tray/server.py`. Then starts Uvicorn.

### Backend (`core/`)
| Module | Key files | Purpose |
|---|---|---|
| `agents/` | `runtime.py`, `specialized.py`, `llm_router.py` | LangGraph agent execution; router picks general/academic/code agent; `llm_router.py` uses LLM to classify query type |
| `agents/` | `conversation_store.py`, `state_store.py` | Persist conversation turns and agent state to `~/.cerebro/state/` |
| `inference/` | `registry.py`, `engine.py` | ProviderRegistry holds primary+fallback providers; auto-switches on OOM |
| `inference/providers/` | `llamacpp_provider.py`, `mlx_provider.py`, `claude_api_provider.py` | Chat + embedding provider implementations |
| `inference/` | `model_manager.py` | Manages llama.cpp subprocess servers (specialist + embed) for model-swapping mode |
| `memory/` | `short_term.py`, `long_term.py`, `context_builder.py` | Short-term = in-session messages; long-term = LanceDB vector search; context_builder assembles both for the prompt |
| `memory/` | `vector_store.py` | LanceDB wrapper |
| `tools/` | `registry.py`, `handlers/` | Tools agents can call (calendar, filesystem, search, shell execution); `policy.py` governs which tools need confirmation |
| `ingestion/` | `pipeline.py` | PDF/DOCX parse → chunk → embed → LanceDB |
| `pipeline/stages/` | `intent.py`, `context.py`, `prompt.py`, etc. | Per-request pipeline stages (intent detection, context injection, policy, audit) |
| `rag/` | `query_engine.py` | Vector similarity search for RAG |
| `watcher/` | `file_watcher.py` | Watchdog-based FS monitoring; triggers re-index |
| `scheduler/` | `proactive.py` | APScheduler for periodic proactive tasks |
| `observability/` | `response_meta.py` | MetricsCollector + ResponseMetadata attached to every query response |

### REST API (`ui/tray/server.py`)
All routes under `/api`. `app_state` (singleton `AppState`) is the injection point — tests replace components here.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/query` | POST | Synchronous query → `QueryResponse` (answer + metadata + conversation_id) |
| `/api/query/stream` | POST | SSE streaming: `{token}` chunks, then `{metadata, conversation_id}`, then `[DONE]` |
| `/api/tool-confirm` | POST | Approve/deny a pending tool call paused mid-run |
| `/api/index` | POST | Start async indexing job → `{job_id}` |
| `/api/index/status` | GET | Poll index job status |
| `/api/status` | GET | RAM, latency, model, provider, metrics |
| `/api/conversations` | GET | List all conversation summaries |
| `/api/conversations/{id}` | GET | Full conversation with messages + metadata |
| `/api/config` | GET/PATCH | Persistent config (model, watched_folders, etc.) |
| `/api/models` | GET | Available GGUF + MLX models |
| `/api/llama-cpp/models` | GET | Available GGUF models in `bin/models/` |
| `/api/wizard/*` | GET/POST | First-launch wizard (status, check-llamacpp, check-models, set-folders, complete) |

**Tool confirmation flow**: if agent hits a `CONFIRMATION_REQUIRED_TOOLS` tool, it pauses and returns `metadata.pending_tool`. Frontend shows `ConfirmModal`; user decision goes to `POST /api/tool-confirm`.

### Frontend (`ui/tray/src/`)
React 18 + TypeScript + Zustand + Tauri. Connects to backend via `api/client.ts` at `http://localhost:7842`.

```
src/
  main.tsx                  # entry
  App.tsx                   # root: wizard → main layout
  api/
    client.ts               # all fetch calls (queryAgent, queryAgentStream, confirmTool, …)
    types.ts                # shared TS types mirroring backend Pydantic models
    errors.ts               # ApiError
  stores/
    chat.ts                 # active chat state, streaming, pending tool
    history.ts              # conversation list + selected conversation
    settings.ts             # config, model selection
    system.ts               # status polling (RAM, latency, provider)
    wizard.ts               # onboarding wizard state
  components/
    chat/                   # ChatWindow, InputArea, MessageBubble, HistoryPanel,
                            # MemoryPanel, SourcesPanel, ToolHistoryPanel, ConfirmModal
    settings/               # SettingsPanel, ModelSelector, FolderManager, ToolPermissions
    status/                 # StatusBar, RamGauge, LatencyBadge, EngineIndicator
    wizard/                 # WizardShell, StepLlamaCpp, StepModel, StepFolders
    shared/                 # AgentSelectorDropdown, ConfirmModal
  layouts/
    MainLayout.tsx, Header.tsx
```

**State flow**: `stores/chat.ts` calls `queryAgentStream` → accumulates tokens → on `[DONE]` stores metadata. If `metadata.pending_tool` is set, shows `ConfirmModal` which calls `confirmTool()`.

### Inference backends
Controlled by `CEREBRO_INFERENCE_BACKEND` env var (default: `llamacpp`):
- `llamacpp` + `CEREBRO_LLAMACPP_SIMPLE=true` (**default**): single llama.cpp server at `CEREBRO_LLAMACPP_URL` (port 8080). Start with `make engine`.
- `llamacpp` + `CEREBRO_LLAMACPP_SIMPLE=false`: `ModelManager` spawns multiple llama.cpp subprocess servers for model-swapping (requires all GGUF paths under `bin/models/`); if files are missing, startup falls back to simple mode with a log warning.
- MLX as secondary provider: only when `CEREBRO_MLX_ENABLED=auto` and the machine reports **≥ 12 GB** RAM, Apple Silicon, and `mlx` / `mlx_lm` import. On 8 GB Macs `auto` skips MLX to save memory; set `CEREBRO_MLX_ENABLED=true` to force MLX anyway.
- `claude` + `ANTHROPIC_API_KEY`: routes chat inference to Anthropic. Embeddings still use the local llama.cpp embed server (`CEREBRO_LLAMACPP_EMBED_URL`, e.g. `make engine-embed`). Override model with `CEREBRO_CLAUDE_MODEL` (default: `claude-sonnet-4-6`).

### Config
```
CEREBRO_MODEL               phi4-mini:latest
CEREBRO_EMBED_MODEL         nomic-embed-text
CEREBRO_DB                  ~/.cerebro/db
CEREBRO_STATE               ~/.cerebro/state
CEREBRO_PORT                7842
CEREBRO_INFERENCE_BACKEND   llamacpp | mlx | claude
CEREBRO_CLAUDE_MODEL        claude-sonnet-4-6
ANTHROPIC_API_KEY           sk-ant-...          # required when backend=claude
CEREBRO_LLAMACPP_URL        http://127.0.0.1:8080
CEREBRO_LLAMACPP_EMBED_URL  http://127.0.0.1:8081
CEREBRO_LLAMACPP_MODEL      llama-3.2-3b-instruct-q4_k_m.gguf   # default simple-mode GGUF name
CEREBRO_LLAMACPP_SIMPLE     true   # false = ModelManager multi-server swapping
CEREBRO_PROACTIVE_CONTEXT   false  # true = ContextEnricher (osascript) on every query
CEREBRO_MLX_ENABLED         auto | true | false
```

## Testing
- One test file per module in `tests/`. Tests mock at the `AppState` injection level; no live service needed.
- `asyncio_mode = auto` in pytest config.
- `AppState` is injectable — tests set `app_state.runtime`, `app_state.vector_store`, etc. directly.

## Code style
- Black: 100ch, py3.11
- Ruff: rules E,F,I,UP (ignore E501)
- Mypy: warn_return_any=true, strict=false
- Pre-commit runs black + ruff + mypy on every commit

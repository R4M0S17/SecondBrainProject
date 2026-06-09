# Cerebro2 — Agentic Personal OS

Local AI desktop app. Python backend + React/Tauri frontend communicating over HTTP on port 7842.

## Commands
```bash
make install          # venv + deps + pre-commit
make run              # python main.py → FastAPI on :7842
make test             # pytest (all tests mock inference backend)
make test tests/test_api.py::fn  # single test
make lint             # black + ruff + mypy
make engine           # start llama.cpp server (port 8080)

cd ui/tray && npm install && npm run dev   # frontend dev server
cd ui/tray && npm run build               # production desktop build
```

## Entry Point (`main.py`)
`_build_app_state()` wiring order:
1. FleetOrchestrator selects startup model
2. ProviderRegistry created with RAM thresholds
3. Inference backend setup (llamacpp/mlx/claude), optionally registers MLX secondary
4. VectorStore (LanceDB), AgentStateStore (JSON), memory stack (ShortTerm → LongTerm → ContextBuilder)
5. InferenceEngine (raw llama.cpp), SemanticCompressor, RAGQueryEngine
6. ToolRegistry (21 tools), PromptCache, ContextEnricher, AgentRuntime
7. TaskPlanner, SpecializedAgentRouter, LlamaServerHealthMonitor
8. All assigned to app_state.*

## Computer
- Macbook pro m1 with 8gb ram

## Backend (`core/`)

### Agent Runtime (`core/agents/runtime.py`, 1418 lines)
- `AgentRuntime.__init__(registry, state_store, context_builder, tool_registry, tool_definitions, enricher, conversation_store)`
- Creates FastPathRouter + compiles LangGraph StateGraph
- **Hard Limits**: `MAX_ITERATIONS=10`, `MAX_TOOL_CALLS=5`, `TIMEOUT_SECONDS=120`
- `CONFIRMATION_REQUIRED_TOOLS`: write_file, execute_python, delete_file, run_script, create_calendar_event, add_reminder

**LangGraph State** (`_RunState` TypedDict): agent_state, query, context, messages, iterations, tool_calls_count, final_answer, next_tool_name, next_tool_args, seen_tool_calls, needs_confirmation, pending_tool_name, pending_tool_args, ambient_context

**Entry Points**:
- `async run(query, agent_id, conversation_id, intent_query) → (str, AgentState)` — hydrates history, checks fast path, then invokes LangGraph graph
- `async run_streaming(query, agent_id, conversation_id, intent_query, slot_id) → AsyncIterator[str|StreamRunComplete]` — manually loops graph nodes yielding tokens live
- `async stream(query, agent_id, conversation_id) → AsyncIterator[str]` — simplified, no tool loop

**Fast Path Router** (`core/agents/fast_path_router.py`): `try_all(query, agent_state) → FastPathResult|None`
Canonical order: Time/Date → Config Read → URL Open → Math → File write → Reminder → Calendar read → Calendar write → File search

**LangGraph Nodes** (5): context_assembly → reason_node → tool_node → observe_node → update_state → END
- Routing: reason_node → tool_node (if tool call) or update_state (if answer)
- tool_node → observe_node (normal) or update_state (if confirmation needed)
- observe_node → reason_node (loop back)

**Key Helpers**: `_parse_llm_response()` handles Qwen3 `<think>` blocks, markdown fences, JSON, action-shortcut format. `_normalize_tool_args()` for alias resolution. `_build_system_prompt()` templates.

### Memory & RAG
- **VectorStore** (`core/memory/vector_store.py`, 179 lines): LanceDB, schema `(id, content, vector, source_path, chunk_index, file_modified, metadata)`. Default dim 768, production uses 384/1024. Methods: upsert, search (top_k=5), delete_by_source, get_indexed_files.
- **LongTermStore** (`core/memory/long_term.py`, 182 lines): LanceDB table "agent_memory", schema `(id, agent_id, content, vector, tags, created_at, confidence, source)`. Methods: search (filters by agent_id/confidence/source/date_range + tag matching), store_episode, get_agent_episodes.
- **ShortTermStore** (`core/memory/short_term.py`, 119 lines): In-memory, max_messages=35. Methods: push_message, get_context (→ ShortTermMemory), distill_if_needed (summarizes at 75% context), slide_to_long_term (archives to vector store).
- **ContextBuilder** (`core/memory/context_builder.py`, 180 lines): `build(query, agent_state) → AssembledContext`. Priority budget: instructions+working_memory → session_summary → memory episodes → recent messages. `maybe_consolidate()` at 85% fill → targets 60%.
- **RAGQueryEngine** (`core/rag/query_engine.py`, 94 lines): `query(question, top_k=5) → RAGResponse`. Searches VectorStore, optionally compresses via SemanticCompressor, calls engine.complete().

**Embeddings** (`core/inference/embedding_factory.py`):
- `LocalEmbeddingProvider`: sentence-transformers all-MiniLM-L6-v2, 384d, CPU/MPS
- `LlamaCppEmbeddingProvider`: HTTP to /v1/embeddings, 1024d (jina-embeddings)
- `CachedEmbeddingProvider`: LRU (max 200), timeout 10s, retry 3x, optional SQLite persist
- Auto-select: "local" on ≤10GB RAM, "llamacpp" otherwise (override via CEREBRO_EMBEDDINGS_BACKEND)

### Inference Providers (`core/inference/`)
- **ProviderRegistry** (`core/inference/registry.py`, 155 lines): register(name, chat, embed). First→primary, second→fallback. `select_for_task(task_hint) → str`: RAM-based selection (thresholds: primary 1.0GB, fallback 0.3GB). `get_chat_for_agent()` creates per-agent LlamaCppChatProvider.
- **LlamaCppChatProvider**: HTTP to /v1/chat/completions, profiles (chat 4096, coding 8192, deep 6144), grammar support, RAM preflight.
- **MlxChatProvider**: In-process MLX on Apple Silicon via mlx_lm, persistent worker thread (thread-local GPU streams).
- **ClaudeApiChatProvider**: Anthropic SDK, models claude-sonnet-4-6/claude-opus-4-7, 200K context, cache_control on system messages.
- **InferenceEngine** (`core/inference/engine.py`): Lower-level llama.cpp client via /api/generate and /api/embeddings, used by VectorStore and RAGQueryEngine.

### Tools (`core/tools/`)
**Registry** (21 tools): 6 calendar, 10 filesystem, 4 macOS, 1 math. `ToolDefinition` dataclass: name, description, handler, required_permission, requires_confirmation, scope (LOCAL/SANDBOXED/RESTRICTED), audit_level, parameters.

**PolicyEngine**: validates agent auth, path scoping for read/write, sanitizes code args.

**Tools requiring confirmation**: execute_python, write_file, run_script, delete_file, create_calendar_event, add_reminder, delete_reminder

**Agents**: academic-v1, calendar-v1, code-v1, general-v1 (each with distinct authorized_tools, domain_tags, instructions). Profiles are defined in `specialized.py`. `SpecializedAgentRouter` uses prefix routing + keyword + LLM classification.

## REST API (`ui/tray/server.py`)
All routes under `/api`. `app_state` (singleton `AppState`) is the injection point — tests replace components here.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/query` | POST | Synchronous → QueryResponse |
| `/api/query/stream` | POST | SSE streaming: `{token}` chunks → `{metadata, conversation_id}` → `[DONE]` |
| `/api/tool-confirm` | POST | Approve/deny pending tool call |
| `/api/index` | POST | Start async indexing → `{job_id}` |
| `/api/index/status` | GET | Poll index job status |
| `/api/status` | GET | RAM, latency, model, provider, metrics |
| `/api/conversations` | GET | List conversation summaries |
| `/api/conversations/{id}` | GET | Full conversation with messages |
| `/api/config` | GET/PATCH | Persistent config |
| `/api/models` | GET | Available GGUF + MLX models |
| `/api/llama-cpp/models` | GET | GGUFs in `bin/models/` |
| `/api/wizard/*` | GET/POST | First-launch wizard |

## Frontend (`ui/tray/src/`)
React 18 + TypeScript + Zustand + Tauri.

```
src/
  main.tsx, App.tsx
  api/      client.ts, types.ts, errors.ts
  stores/   chat.ts, history.ts, settings.ts, system.ts, wizard.ts
  components/  chat/, settings/, status/, wizard/, shared/
  layouts/     MainLayout.tsx, Header.tsx
```

**State flow**: `stores/chat.ts` calls `queryAgentStream` → accumulates tokens → on `[DONE]` stores metadata. If `metadata.pending_tool`, shows `ConfirmModal` which calls `confirmTool()`.

## Config & Feature Flags
### Env Vars
| Variable | Default | Values |
|---|---|---|
| CEREBRO_INFERENCE_BACKEND | llamacpp | llamacpp / mlx / claude |
| CEREBRO_LLAMACPP_SIMPLE | true | true / false (ModelManager multi-server) |
| CEREBRO_MLX_ENABLED | auto | auto / true / false |
| CEREBRO_PROACTIVE_CONTEXT | true | true / false (ContextEnricher on every query) |
| CEREBRO_EMBEDDINGS_BACKEND | auto-select | local / llamacpp |
| CEREBRO_MODEL | Qwen_Qwen3.5-2B-Q4_K_M.gguf | |
| CEREBRO_CLAUDE_MODEL | claude-sonnet-4-6 | |
| CEREBRO_MLX_MODEL | mlx-community/Phi-4-mini-instruct-4bit | |
| CEREBRO_LLAMACPP_URL | http://127.0.0.1:8080 | |
| CEREBRO_LLAMACPP_EMBED_URL | http://127.0.0.1:8081 | |
| CEREBRO_DB | ~/.cerebro/db | |
| CEREBRO_STATE | ~/.cerebro/state | |
| CEREBRO_PORT | 7842 | |
| ANTHROPIC_API_KEY | — | required for claude backend |

### TOML Config (`config/settings.toml`)
Sections: general, providers, inference, ingestion, memory, tools, files, ui, scheduler, calendar, security, mlx, claude

### Runtime Config (`~/.cerebro/state/config.json`)
Managed via AppState._load_config()/_save_config(), exposed at /api/config.

## Testing
- Shared fixtures in `tests/conftest.py` (mock_provider, mock_registry, tmp_app_state).
- One test file per module in `tests/`. Mock at AppState injection level; no live service.
- `asyncio_mode = auto` in pytest config.
- **"Test-Stable"** (`tests/test_stable_fast_paths.py`, 552 lines): deterministic, no llama.cpp/network/embeddings. Uses pure Python + mocked LLM + fixtures from `tests/fixtures/stable_fast_path_prompts.yaml`.
- **Mocking patterns**: Mock ProviderRegistry (select_for_task, get_chat), Mock ChatProvider (complete=AsyncMock), Mock ContextBuilder, app_state reset fixture with tmp_path, monkeypatch for module-level functions, calendar tests patch platform.system()→"Linux".

### Key Test Files
| File | Tests |
|---|---|
| test_agent_runtime.py | State store, parsing (20+), consolidation, grammar, resume |
| test_api.py | REST endpoints via httpx ASGITransport, streaming, tool confirm |
| test_stable_fast_paths.py | Math/file/calendar/search fast paths, fusion |
| test_fast_path_router.py | Router order, spec content generation |
| test_calendar*.py (8 files) | Calendar fast path, AppleScript, datetime |
| test_inference.py, test_providers.py | Registry, RAM selection |
| test_memory.py, test_memory_levels.py | Short/long term, context builder |
| test_rag.py | RAG query engine |
| test_tool_*.py | Governance, confirmation, execution |
| conftest.py | Shared fixtures (mock_provider, mock_registry, tmp_app_state) |

## Code Style
- Black: 100ch, py3.11
- Ruff: rules E,F,I,UP (ignore E501)
- Mypy: warn_return_any=true, strict=false
- Pre-commit runs black + ruff + mypy

## Additional Components
- **ConversationStore** (`core/agents/conversation_store.py`): JSON files, atomic writes via .tmp+os.replace
- **SessionPolicy** (`core/agents/session_policy.py`): SESSION_RESUME_MAX_TURNS=8, hydrates short-term from conversation tail
- **ContextEnricher** (`core/agents/context_enricher.py`): Proactive ambient (calendar + recent files), 3s timeout
- **TaskPlanner** (`core/agents/planner.py`): Multi-step decomposition, max 20 steps/300s/5 failures
- **FleetOrchestration** (`core/inference/fleet/`): HardwareMonitor, ModelRegistry, ScriptWriter, TaskClassifier
- **Observability** (`core/observability/`): RamMonitor, MetricsCollector, ResponseMetadata
- **HealthMonitor** (`core/inference/health_monitor.py`): LlamaServerHealthMonitor — background liveness watchdog
- **InferenceWarnings** (`core/inference/inference_warnings.py`): ContextVar per-request flags for fast paths

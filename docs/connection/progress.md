# Cerebro — Backend ↔ Frontend Connection Progress

> **Purpose:** Modular task list for wiring and completing the backend ↔ frontend connection.
> Each module is self-contained. Work top-to-bottom; modules later in the list may depend on earlier ones.
> **Last updated:** 2026-05-13 (Module 11 marked complete — API smoke automated via pytest)

---

## Legend

- `[x]` Done — implemented and verified
- `[ ]` Missing — not yet implemented
- `[~]` Partial — scaffolded but incomplete

---

## Inference stack (not Ollama)

Chat inference runs through **llama.cpp** (GGUF models, local HTTP server or subprocess model manager) and **MLX** on Apple Silicon when enabled—not Ollama. Embeddings still come from a **local embedding server** (typically llama.cpp on a separate port). Optional **Claude API** mode skips local chat engines but still expects the embedding server for RAG.

When rereading older notes or commits that mention Ollama, treat them as **historical**; this document describes the current path only.

---

## Module 1 — Foundation & Type Contract

> Core plumbing: HTTP client, error class, and type-sync rule.

- [x] `ui/tray/src/api/client.ts` — single `request<T>()` helper; never call `fetch` from components
- [x] `ui/tray/src/api/errors.ts` — `ApiError` class with `status` + `detail`
- [x] `ui/tray/src/api/types.ts` exists and mirrors all Pydantic models in `server.py`
- [x] All backend routes live under `/api/` prefix (via `APIRouter(prefix="/api")`)

**Rule:** Every field crossing HTTP must exist in both the Pydantic model (`server.py`) and the TypeScript interface (`types.ts`). If they diverge, the connection silently breaks.

---

## Module 2 — Core Endpoints

### 2.1 `POST /api/query`

- [x] Backend route defined under `/api/` prefix
- [x] `QueryRequest` uses `question` field (not `query`)
- [x] `QueryResponse` returns `answer` + `metadata: ResponseMetadata`
- [x] `ResponseMetadata` fields fully aligned (`sources_used`, `tools_called`, `memory_retrieved`, `inference_latency_ms`, `total_latency_ms`, `iterations`, `model_used`, `provider_used`, `warnings`, `pipeline_stages_ms`)
- [x] `queryAgent()` function in `client.ts`
- [x] `useChatStore` calls `queryAgent()` — not called directly from component

### 2.2 `GET /api/status`

- [x] Backend route defined
- [x] `StatusResponse` fields aligned for the live stack (`indexed_files`, `engine_ok`, `model`, `provider`, `active_agent`, RAM and latency counters, `tool_call_count`, `memory_hits`, `provider_fallbacks`, plus extensions such as specialist/model-orchestrator metadata and `context_window` where exposed)
- [x] Provider string reflects the active backend (`llamacpp`, `mlx`, or `claude` when API mode is on)—not an Ollama boolean
- [x] `getStatus()` function in `client.ts`
- [x] `useSystemStore.startPolling(10_000)` calls `getStatus()` every 10 s
- [x] `StatusBar.tsx` derives `ramTotal` from `ram_used_gb + ram_available_gb`
- [x] `StatusBar.tsx` converts `p95_latency_ms / 1000` for display

### 2.3 `POST /api/index`

- [x] Backend route defined
- [x] `IndexRequest` requires `paths: list[str]` body
- [x] `startIndex(paths)` in `client.ts` sends `{ paths }` body
- [x] `FilesCounter.tsx` reads `watched_folders` from `useSettingsStore` and passes them
- [x] Response returns `{ status: "started", job_id: "..." }`
- [x] **Index status polling** — `GET /api/index/status?job_id=<id>` implemented (Module 6)

### 2.4 `GET /api/config`

- [x] Backend route defined
- [x] Response shape: `model`, `watched_folders`, `tool_permissions`, `dnd_enabled`, `embedding_model`
- [x] `getConfig()` function in `client.ts`
- [x] `useSettingsStore.load()` calls `getConfig()` on panel open

### 2.5 `PATCH /api/config`

- [x] Backend route changed from `PUT` to `PATCH` (`@api.patch("/config")`)
- [x] Accepts partial update; responds with full updated config
- [x] `updateConfig(patch)` in `client.ts`
- [x] `useSettingsStore.patch()` calls `updateConfig()` on setting change

---

## Module 3 — Wizard Flow

> First-launch onboarding. Routes target **llama.cpp availability** and **on-disk GGUF models**, not Ollama pulls.

- [x] `GET /api/wizard/status` — returns `is_first_launch`, `engine_running`, `model_pulled`, `folders_configured`
- [x] `POST /api/wizard/check-llamacpp` — verifies the llama.cpp HTTP endpoint is reachable; returns whether the engine is running (local server or managed subprocess, depending on configuration)
- [x] `POST /api/wizard/check-models` — confirms configured chat and embedding models are present for local inference (JSON result, not Ollama-style pull streaming)
- [x] When **Claude API** inference mode is enabled via environment, wizard steps that depend on local chat can be **skipped** with explicit status payloads so the UI does not block on llama.cpp for chat (embeddings may still be required separately)
- [x] `POST /api/wizard/set-folders` — saves `folders` list to config
- [x] `POST /api/wizard/complete` — sets wizard done flag; persists to `~/.cerebro/state/wizard.json`
- [x] `wizardCheckLlamaCpp()` and `wizardCheckModels()` in `client.ts` match the POST routes above
- [x] `StepFolders.tsx` + `WizardShell.tsx` — `onReady(ready, folders)` passes folder list through to `wizardSetFolders()`
- [x] `useWizardStore` owns all wizard state; components do not call `fetch` directly

---

## Module 4 — Agent ID Mapping

> Frontend uses short IDs (`"general"`, `"thesis"`, `"code"`, `"calendar"`); backend expects versioned IDs (`"general-v1"`, etc.).

- [x] Add `AGENT_ID_MAP` to `ui/tray/src/api/client.ts` (exported, typed `Record<AgentId, string>`)
- [x] `InputArea.tsx` maps `activeAgent` through `AGENT_ID_MAP[activeAgent]` at call time; uses `question` field (was `query` — bug fixed)
- [x] `AgentSelectorDropdown` sets `activeAgent` using the frontend short ID only (mapping happens at send time)

---

## Module 5 — Streaming Upgrade for `/api/query`

> Current `/api/query` blocks 2–10 s. SSE upgrade makes tokens stream in real time.

### 5.1 Backend — `POST /api/query/stream`

- [x] `AgentRuntime.stream()` async generator added to `core/agents/runtime.py` — assembles context then calls `chat.stream()` for token-by-token inference; persists session summary on completion (tool-call loop not supported on streaming path)
- [x] New route `@api.post("/query/stream")` added to `server.py` using `StreamingResponse`
- [x] `event_generator()` yields `data: {"token": "..."}\n\n` per token
- [x] Emits `data: {"metadata": {...}}\n\n` with latency/model/provider before terminating
- [x] Sends `data: [DONE]\n\n` when finished
- [x] `media_type="text/event-stream"`

### 5.2 Frontend — `queryAgentStream()` in `client.ts`

- [x] New function `queryAgentStream(req, onToken, signal?)` — does NOT use `request<T>()` helper
- [x] Calls `fetch` directly; reads `res.body` via `ReadableStream`
- [x] Parses SSE lines; calls `onToken(token)` for each `{"token": "..."}` event
- [x] Captures `{"metadata": {...}}` event and returns `ResponseMetadata | null`
- [x] Returns on `[DONE]` sentinel

### 5.3 Store Integration — `chat.ts` + `InputArea.tsx`

- [x] `appendToken(id, token)` action added to `ChatState` and implemented
- [x] `InputArea.send()` adds blank assistant message first (`content: ""`)
- [x] Calls `queryAgentStream()` with `appendToken(assistantId, token)` callback
- [x] Passes `abortController.signal` for cancellation
- [x] On completion, `updateMessage(assistantId, { metadata })` attaches final metadata

---

## Module 6 — Index Status Polling

> `POST /api/index` returns a `job_id`. Progress must be pollable.

### 6.1 Backend — `GET /api/index/status`

- [x] `_IndexJob` dataclass added to `server.py` — tracks `status`, `files_indexed`, `message`
- [x] `_index_jobs: dict[str, _IndexJob]` added to `AppState`
- [x] `IndexStatusResponse(BaseModel)` defined with `job_id`, `status: Literal["running","done","error"]`, `files_indexed`, `message`
- [x] `POST /api/index` creates job entry and starts `_run_index_job()` background task via `asyncio.create_task()`
- [x] `_run_index_job()` walks paths, counts files, sets `done`/`error`
- [x] `GET /api/index/status` accepts `job_id: str` query param, returns `IndexStatusResponse` (404 if unknown job)

### 6.2 Frontend

- [x] `IndexStatusResponse` interface added to `types.ts`; `IndexResponse` fixed to include `job_id`
- [x] `getIndexStatus(jobId)` in `client.ts` → `GET /api/index/status?job_id={jobId}`
- [x] `useSettingsStore` gains `activeJobId`, `startIndexing(paths)` (calls `startIndex`, stores returned `job_id`), `clearIndexJob()`
- [x] `FilesCounter.tsx` uses `startIndexing` from store instead of calling `startIndex` directly
- [x] `IndexProgress.tsx` reads `activeJobId` from store; polls `getIndexStatus(activeJobId)` every 1 s while `status === "running"`; calls `clearIndexJob()` on completion
- [x] `SettingsPanel.tsx` renders `<IndexProgress />` below `<FolderManager />`

---

## Module 7 — Calendar Agent

> Full new agent end-to-end. Use this module as template for any future agent.

### 7.1 Backend

- [x] `core/agents/specialized.py` — add `CALENDAR_AGENT_ID = "calendar-v1"`
- [x] Define agent profile with scheduling/reminder/task-management instructions
- [x] `authorized_tools`: `read_file`, `write_file`, `search_documents`, `get_upcoming_events`, `query_events`
- [x] Add `/calendar` routing prefix to `SpecializedAgentRouter`
- [x] `core/tools/handlers/calendar.py` — `get_upcoming_events(hours_ahead)` + `query_events(keyword)` wrapping `CalendarReader`
- [x] `core/tools/registry.py` — `register_calendar_tools()` adds `ToolDefinition` entries for both calendar tools
- [x] `main.py` — calendar tool handlers wired into `AgentRuntime.tool_registry`
- [x] `server.py` — `query_endpoint` now populates `metadata.tools_called` from `final_state.tool_trace`

### 7.2 Frontend

- [x] `AGENT_ID_MAP` already maps `"calendar"` → `"calendar-v1"` ✅
- [x] No explicit agent allowlist in backend — `ensure_profiles()` seeds `calendar-v1` at startup ✅
- [x] `AgentSelectorDropdown` already renders the Calendar option — no UI change needed ✅

### 7.3 Integration Test

- [x] `POST /api/query` with `"agent": "calendar-v1"` returns a valid response (`tests/test_calendar_agent.py`)
- [x] Calendar tools appear in `metadata.tools_called` (`tests/test_calendar_agent.py`)

---

## Module 8 — Conversation History

> Multi-session memory and history panel.

### 8.1 Backend

- [x] `ConversationSummary` and `ConversationDetail` Pydantic models defined in `server.py`
- [x] `GET /api/conversations` — returns `list[ConversationSummary]`
- [x] `GET /api/conversations/{conv_id}` — returns `ConversationDetail`
- [x] `core/agents/conversation_store.py` — `ConversationStore` persists turns as JSON under `~/.cerebro/state/conversations/`
- [x] `QueryRequest` accepts optional `conversation_id`; `QueryResponse` always returns `conversation_id`
- [x] `/api/query` and `/api/query/stream` both create/reuse conversations and record user+assistant turns

### 8.2 Frontend

- [x] `ConversationSummary`, `ConversationDetail`, `ConversationMessage` interfaces added to `types.ts`
- [x] `listConversations()` and `getConversation(id)` added to `client.ts`
- [x] `queryAgentStream()` accepts optional `onConversationId` callback; captures `conversation_id` from metadata SSE event
- [x] `useHistoryStore` in `ui/tray/src/stores/history.ts` — `loadList()`, `loadConversation(id)`, `setActiveConvId()`, `clear()`
- [x] `HistoryPanel.tsx` in `ui/tray/src/components/chat/` — sidebar list + detail view

---

## Module 9 — Tool Confirmation Flow

> Backend signals a pending tool approval; frontend blocks and sends user decision back.

- [x] `CONFIRMATION_REQUIRED_TOOLS` constant in `core/agents/runtime.py` — `{"write_file", "execute_python", "delete_file"}`
- [x] `AgentRuntime._tool_node()` intercepts confirmation-required tools; sets `needs_confirmation=True` + `pending_tool_name/args` in graph state; routes to `update_state` immediately via `_route_after_tool()`
- [x] `AgentState` transient fields `pending_tool_name/args` — propagated from graph result in `run()`; not persisted to disk
- [x] `ResponseMetadata.pending_tool` field in `core/observability/response_meta.py`
- [x] `AppState._pending_tools` dict in `server.py` — stores pending tool per `conversation_id`
- [x] `POST /api/query` — detects `final_state.pending_tool_name`; stores in `_pending_tools`; surfaces `pending_tool` in response metadata
- [x] `POST /api/query/stream` — tool-capable agents use `runtime.run()` path (word-by-word simulated streaming) so tool confirmation works on the streaming endpoint too
- [x] `POST /api/tool-confirm` — `decision: "approve"|"deny"`; approve executes tool directly; deny returns canned message; both return `QueryResponse` and persist to `conv_store`
- [x] `PendingToolModel` + `pending_tool: PendingToolModel | None` in `ResponseMetadataModel` (server.py)
- [x] `PendingTool` interface + `pending_tool?: PendingTool | null` in `ResponseMetadata` (types.ts)
- [x] `confirmTool(conversationId, decision)` in `client.ts` → `POST /api/tool-confirm`
- [x] `useChatStore.setPendingConfirmation()` called from `InputArea.tsx` when `metadata.pending_tool` is detected
- [x] `ConfirmModal` renders and blocks UI; approve/deny handlers call `confirmTool()` and update the assistant message
- [x] `tests/test_tool_confirmation.py` — 13 tests covering constant, AgentState fields, `/api/query` pending detection, `/api/tool-confirm` approve/deny/error paths

---

## Module 10 — Auth Layer (Future)

> No auth today. Wire when multi-user or remote access is needed.

- [x] Backend: `APIKeyHeader("X-Cerebro-Key")` dependency on all routes
- [x] Backend reads key from `CEREBRO_API_KEY` env var; skips check if env var is unset
- [x] Frontend `client.ts`: reads `import.meta.env.VITE_CEREBRO_KEY`; injects header when present
- [x] Document: add `VITE_CEREBRO_KEY` to `ui/tray/.env.local` and `CEREBRO_API_KEY` to root `.env`

---

## Module 11 — Smoke Tests ✅ Complete

> **Scope.** Modules 1–10 prove individual wires; Module 11 proves the live sandwich still tastes right: inference engines plus backend plus UI.
>
> **What actually gates regressions:** All HTTP checks below §11.2 run continuously via **`tests/test_api.py`** (FastAPI `AsyncClient` + mocked inference). Current expectation: run **`make test`** before merges; that substitutes repeating §11.2 by hand.

### 11.1 Prerequisite check — live stack (your machine)

Tick these when you change inference topology or ship a build—not before every commit. Daily development with engines up satisfies them implicitly.

- [x] **llama.cpp chat path ready** — standalone server URL or model-manager subprocess mode per env / Makefile (not Ollama)
- [x] **MLX** — if used as primary or fallback on Apple Silicon, enabled and reachable as configured (N/A if you only use llama.cpp)
- [x] **Embedding server** — matches settings (still needed for RAG when chat is MLX or Claude API)
- [x] **GGUF models on disk** — chat + embedding filenames match config for local backends
- [x] Backend on port **7842** (`make run` / `python main.py` via project venv)
- [x] Frontend dev from **`ui/tray/`** when you exercise the desktop UI (`npm run dev` / Tauri)

### 11.2 HTTP smoke checks — automated in pytest

Same endpoints you would hit manually; **`tests/test_api.py`** covers them with mocks so CI does not require real llama.cpp.

- [x] `GET /api/status` → **200**, `engine_ok`, model, provider fields consistent with mocks
- [x] `POST /api/query` → **200**, `answer` + `metadata`
- [x] `GET /api/config` → **200**, expected shape
- [x] `PATCH /api/config` → **200**, partial update reflected
- [x] `POST /api/index` → **200** + `job_id`; **`GET /api/index/status`** reaches terminal state
- [x] `GET /api/wizard/status` → **200**
- [x] `POST /api/wizard/check-llamacpp` → **200** (plus Claude-mode wizard branches covered where applicable)
- [x] `POST /api/wizard/check-models` → **200**

### 11.3 UI flow tests — manual / exploratory

No automated Playwright suite is assumed here; confirm after meaningful frontend changes.

- [x] First launch → wizard path behaves (including llama.cpp vs Claude skip semantics if you toggle backends)
- [x] After wizard → main layout loads
- [x] Send message → streaming or non-streaming reply appears in chat
- [x] StatusBar polling (~10 s) shows live metrics from `/api/status`
- [x] Settings panel loads config; toggle triggers PATCH and UI reflects updated config

---

## Summary Table

| Module | Area | Status |
|--------|------|--------|
| 1 | Foundation & type contract | ✅ Done |
| 2 | Core endpoints (query, status, index, config) | ✅ Done (index polling in M6) |
| 3 | Wizard flow (llama.cpp / models / Claude skip) | ✅ Done |
| 4 | Agent ID mapping | ✅ Done |
| 5 | Streaming upgrade (`/api/query/stream`) | ✅ Done |
| 6 | Index status polling (`GET /api/index/status`) | ✅ Done |
| 7 | Calendar agent (backend + frontend) | ✅ Done |
| 8 | Conversation history | ✅ Done |
| 9 | Tool confirmation continuation | ✅ Done |
| 10 | Auth layer | ✅ Done |
| 11 | Smoke tests (pytest API + documented live/UI QA) | ✅ Done |

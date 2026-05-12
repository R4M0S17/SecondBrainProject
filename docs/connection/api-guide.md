# Cerebro — Backend ↔ Frontend Connection Guide

> **Audience:** A developer wiring or extending the connection between the Python backend and the React/Tauri frontend.
> **Last updated:** 2026-05-07

---

## Connection Progress

### Mismatches resolved (Section 4)

- [x] **4.1** URL prefix — backend now uses `APIRouter(prefix="/api")`; all routes live under `/api/`
- [x] **4.2** Query field name — `QueryRequest.query` renamed to `question` in `types.ts`; aligns with backend Pydantic model
- [x] **4.3** StatusResponse fields — `types.ts` fully aligned to backend field names; `StatusBar.tsx` updated to derive `ramTotal` from `ram_used_gb + ram_available_gb` and convert `p95_latency_ms → s` for display
- [x] **4.3 (bonus)** ResponseMetadata / sub-types — `SourceRef`, `ToolCallRecord`, `MemoryRef`, `ResponseMetadata` in `types.ts` fully aligned to backend Pydantic models; `MessageFooter.tsx`, `MessageBubble.tsx`, `ToolHistoryPanel.tsx`, `MemoryPanel.tsx`, `ChatWindow.tsx` updated accordingly
- [x] **4.6** Config method — backend `PUT /config` changed to `PATCH /api/config`
- [x] **4.4** IndexRequest missing body — `startIndex(paths)` now sends `{ paths }` body; `FilesCounter.tsx` reads `watched_folders` from the settings store and passes them
- [x] **4.5** Wizard routes — all five `/api/wizard/*` routes implemented in `server.py` via `APIRouter(prefix="/api/wizard")`; wizard done flag persisted to `~/.cerebro/state/wizard.json`

### All Section 4 mismatches resolved

### Next steps

1. Run full stack and smoke-test each endpoint with `curl` (see Section 12 checklist)
2. Streaming upgrade for `/api/query` — see Section 9
3. Index status polling — `GET /api/index/status` — see Section 10.2

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Dev Setup — Running the Full Stack](#2-dev-setup--running-the-full-stack)
3. [Connection Layer](#3-connection-layer)
4. [Known Mismatches (Fix These First)](#4-known-mismatches-fix-these-first)
5. [API Contracts — Current Endpoints](#5-api-contracts--current-endpoints)
6. [Data Flow Diagrams](#6-data-flow-diagrams)
7. [Agent System](#7-agent-system)
8. [State Management Map](#8-state-management-map)
9. [Streaming Upgrade Path (Recommended)](#9-streaming-upgrade-path-recommended)
10. [Planned Extensions](#10-planned-extensions)
11. [Auth Layer (Future)](#11-auth-layer-future)
12. [Coder Checklist](#12-coder-checklist)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  macOS Tray App  (Tauri 2.0 native shell)                        │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  React 18 + Vite  (port 1420 in dev)                     │   │
│  │                                                          │   │
│  │  Zustand stores ──► api/client.ts ──► HTTP fetch         │   │
│  │  chat.ts / system.ts / settings.ts / wizard.ts           │   │
│  └──────────────────────────────┬───────────────────────────┘   │
└─────────────────────────────────┼───────────────────────────────┘
                                  │  HTTP  (localhost:7842)
                    ┌─────────────▼──────────────────┐
                    │  FastAPI  (uvicorn, port 7842)  │
                    │  ui/tray/server.py              │
                    │                                │
                    │  AppState ──► AgentRuntime      │
                    │             ├── AgentStateStore │
                    │             ├── ContextBuilder  │
                    │             └── ProviderRegistry│
                    │                      │          │
                    │               OllamaChat        │
                    └──────────────────┬─────────────┘
                                       │  HTTP  (localhost:11434)
                         ┌─────────────▼────────────┐
                         │  Ollama daemon            │
                         │  phi3:mini / qwen2:1.5b  │
                         └──────────────────────────┘
```

**Key facts:**
- No WebSocket, no Tauri IPC bridge — everything is plain HTTP REST.
- The Tauri shell is a native window host only; all logic is in the Python process or React.
- Ollama runs as a separate local daemon; the backend talks to it, the frontend never does.

---

## 2. Dev Setup — Running the Full Stack

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| Rust + Cargo | stable | Tauri CLI |
| Ollama | latest | Local LLM daemon |

### Start order (matters)

```bash
# 1. Start Ollama
ollama serve

# 2. Pull the default model (first time only)
ollama pull phi3:mini
ollama pull nomic-embed-text

# 3. Start the Python backend
cd /path/to/cerebro
pip install -e ".[dev]"
python main.py
# → listening on http://0.0.0.0:7842

# 4. Start the frontend (separate terminal)
cd ui/tray
npm install
npm run dev
# → Vite on http://localhost:1420
# → Tauri window opens automatically in dev mode
```

### Environment variables (override defaults)

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API base |
| `CEREBRO_MODEL` | `phi3:mini` | Chat model |
| `CEREBRO_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `CEREBRO_DB` | `~/.cerebro/db` | LanceDB vector store path |
| `CEREBRO_STATE` | `~/.cerebro/state` | Agent state directory |
| `CEREBRO_PORT` | `7842` | FastAPI server port |

Copy `.env.example` to `.env` and set values there; `main.py` reads them with `os.getenv`.

---

## 3. Connection Layer

### 3.1 HTTP Client — `ui/tray/src/api/client.ts`

All API calls go through a single `request<T>()` helper:

```ts
const BASE = "http://localhost:7842";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}
```

**Rules for adding new endpoints:**
- Add a typed wrapper function in `client.ts` that calls `request<YourResponseType>()`.
- Add the matching TypeScript interfaces to `api/types.ts`.
- Never call `fetch` directly from components — always go through `client.ts`.

### 3.2 Error Handling — `ui/tray/src/api/errors.ts`

```ts
export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`API ${status}: ${detail}`);
  }
}
```

- 503 → runtime not initialized (backend started but Ollama not running).
- 500 → unhandled backend exception (check Python logs).
- Network error (fetch throws) → Ollama or backend process is down.

### 3.3 Type Contract

TypeScript interfaces in `api/types.ts` must mirror Pydantic models in `server.py`. When you add a field on either side, update both files together.

```
server.py (Pydantic)  ←→  api/types.ts (TypeScript interface)
```

---

## 4. Known Mismatches (Fix These First)

> These are real divergences found between `server.py` and `client.ts` / `types.ts`.
> A connection will not work until they are resolved.

### 4.1 URL prefix mismatch — ✅ FIXED

**Was:** Backend routes were `/query`, `/status`, `/index`, `/config` (no prefix). Frontend called `/api/*`.

**Fix applied (`server.py`):** Replaced bare `@app.post(...)` decorators with an `APIRouter(prefix="/api")`. All routes now live under `/api/`.

```python
api = APIRouter(prefix="/api")

@api.post("/query", ...)
@api.get("/status", ...)
@api.post("/index", ...)
@api.get("/config")
@api.patch("/config")

app.include_router(api)
```

### 4.2 Query field name mismatch — ✅ FIXED

**Was:** Backend `QueryRequest` used `question`; frontend interface used `query`.

**Fix applied (`api/types.ts`):**

```ts
export interface QueryRequest {
  question: string;   // was: query
  agent?: string;
  conversation_id?: string;
}
```

### 4.3 StatusResponse + ResponseMetadata field differences — ✅ FIXED

**Was:** Multiple field name mismatches between backend Pydantic models and frontend TypeScript interfaces.

**Fix applied (`api/types.ts`)** — all interfaces now mirror the backend exactly:

```ts
export interface StatusResponse {
  indexed_files: number;
  ollama_ok: boolean;
  model: string;
  provider: string;
  active_agent: string;
  ram_used_gb: number;
  ram_available_gb: number;
  queries_total: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  tool_call_count: number;
  memory_hits: number;
  provider_fallbacks: number;
}

export interface SourceRef {
  path: string;
  chunk_index: number;   // was: missing
  score: number;
  // removed: snippet
}

export interface ToolCallRecord {
  name: string;
  args_summary: string;    // was: args (object)
  result_summary: string;  // was: result (string)
  latency_ms: number;      // was: duration_ms
  approved: boolean;       // was: success
}

export interface MemoryRef {
  id: string;
  summary_snippet: string;   // was: content
  relevance_score: number;   // was: score
}

export interface ResponseMetadata {
  sources_used: SourceRef[];       // was: sources
  tools_called: ToolCallRecord[];  // was: tools
  memory_retrieved: MemoryRef[];   // was: memory
  inference_latency_ms: number;    // was: missing
  total_latency_ms: number;        // was: duration_s (seconds)
  iterations: number;              // was: missing
  model_used: string;              // was: model
  provider_used: string;           // was: missing
  warnings: string[];              // was: warning (single string)
  pipeline_stages_ms: Record<string, number>;  // was: missing
}
```

**Components updated** to use new field names:
- `StatusBar.tsx` — `indexed_files`, `queries_total`, `p95_latency_ms / 1000`, `ram_used_gb + ram_available_gb`
- `MessageFooter.tsx` — `model_used`, `total_latency_ms / 1000`, `sources_used`, `tools_called`, `memory_retrieved`
- `MessageBubble.tsx` — `sources_used`, `tools_called`, `memory_retrieved`
- `ToolHistoryPanel.tsx` — `approved`, `latency_ms`
- `MemoryPanel.tsx` — `summary_snippet`, `relevance_score`
- `ChatWindow.tsx` — `model_used`, `warnings[0]`

### 4.4 IndexRequest missing body — ✅ FIXED

**Was:** `startIndex()` sent `POST /api/index` with no body; backend `IndexRequest` requires `paths: list[str]`.

**Fix applied (`api/client.ts`):**
```ts
export async function startIndex(paths: string[]): Promise<IndexResponse> {
  return request<IndexResponse>("/api/index", {
    method: "POST",
    body: JSON.stringify({ paths }),
  });
}
```

**Fix applied (`components/status/FilesCounter.tsx`):** reads `watched_folders` from `useSettingsStore` and passes them as the `paths` argument. If no folders are configured, the click is a no-op.

### 4.5 Wizard routes not in backend — ✅ FIXED

**Was:** Five `/api/wizard/*` routes called by the frontend did not exist in `server.py`.

**Fix applied (`server.py`):** Added `APIRouter(prefix="/api/wizard")` with all five routes. Wizard done state is persisted to `~/.cerebro/state/wizard.json` (path controlled by `CEREBRO_STATE` env var).

| Route | Method | Notes |
|-------|--------|-------|
| `/api/wizard/status` | GET | Returns `is_first_launch`, `ollama_running`, `model_pulled`, `folders_configured` |
| `/api/wizard/check-ollama` | POST | Direct httpx ping to `OLLAMA_URL/api/tags` |
| `/api/wizard/pull-models` | POST | Streams Ollama pull progress as NDJSON (`event`, `model`, `percent`) |
| `/api/wizard/set-folders` | POST | Writes `folders` list into `app_state._config["watched_folders"]` |
| `/api/wizard/complete` | POST | Sets `_wizard_done = True`, persists to disk |

**Also fixed:** `wizardCheckOllama()` in `client.ts` was sending GET (no options); updated to send POST to match the backend route.

**Also fixed (`StepFolders.tsx` + `WizardShell.tsx`):** `onReady` callback now passes `(ready: boolean, folders: string[])` so `WizardShell` always has the current folder list when calling `wizardSetFolders()` on step completion.

### 4.6 Config endpoint method mismatch — ✅ FIXED

**Was:** Backend had `PUT /config`. Frontend calls `PATCH /api/config`.

**Fix applied (`server.py`):** Route changed to `@api.patch("/config")` and handler renamed to `patch_config`. Also gained the `/api` prefix from fix 4.1.

---

## 5. API Contracts — Current Endpoints

> After fixing mismatches in Section 4, all routes will live under `/api/`.

### `POST /api/query`

Send a message to an agent.

**Request:**
```json
{
  "question": "Summarize my thesis notes",
  "agent": "academic-v1",
  "conversation_id": "optional-uuid"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `question` | string (min 1) | yes | User message |
| `agent` | string | no | Agent ID or `"auto"`. Defaults to `"general-v1"` |
| `conversation_id` | string | no | Reserved for future multi-turn sessions |

**Response:**
```json
{
  "answer": "Your thesis notes cover three main themes...",
  "metadata": {
    "sources_used": [{ "path": "~/thesis/ch2.pdf", "chunk_index": 3, "score": 0.91 }],
    "tools_called": [{ "name": "search_documents", "args_summary": "...", "result_summary": "...", "latency_ms": 120.5, "approved": true }],
    "memory_retrieved": [],
    "inference_latency_ms": 2100.0,
    "total_latency_ms": 2340.0,
    "iterations": 2,
    "model_used": "phi3:mini",
    "provider_used": "ollama",
    "warnings": [],
    "pipeline_stages_ms": { "context_build": 45.2, "inference": 2100.0 }
  }
}
```

**Errors:**
- `503` — runtime not initialized
- `500` — LangGraph / Ollama error (detail in response body)

---

### `GET /api/status`

System health and metrics. Polled every 10 seconds by the frontend.

**Response:**
```json
{
  "indexed_files": 142,
  "ollama_ok": true,
  "model": "phi3:mini",
  "provider": "ollama",
  "active_agent": "general-v1",
  "ram_used_gb": 6.2,
  "ram_available_gb": 9.8,
  "queries_total": 37,
  "avg_latency_ms": 1840.5,
  "p95_latency_ms": 3200.0,
  "tool_call_count": 12,
  "memory_hits": 28,
  "provider_fallbacks": 0
}
```

---

### `POST /api/index`

Trigger document indexing for a list of file/folder paths.

**Request:**
```json
{
  "paths": ["/Users/mb/thesis", "/Users/mb/notes"]
}
```

**Response:**
```json
{
  "status": "started",
  "job_id": "a3f8c2d1-..."
}
```

Poll `GET /api/index/status?job_id=<id>` for progress (endpoint to be implemented — see Section 10).

---

### `GET /api/config`

Load current app configuration.

**Response:**
```json
{
  "model": "phi3:mini",
  "watched_folders": ["/Users/mb/thesis"],
  "tool_permissions": {
    "execute_python": false,
    "write_file": false,
    "read_file": true,
    "search_web": false
  },
  "dnd_enabled": false,
  "embedding_model": "nomic-embed-text"
}
```

---

### `PATCH /api/config`

Partially update app configuration. Send only the keys you want to change.

**Request:**
```json
{ "dnd_enabled": true }
```

**Response:** Full updated config (same shape as GET).

---

### `GET /api/wizard/status`

Check first-launch state.

**Response:**
```json
{
  "is_first_launch": true,
  "ollama_running": false,
  "model_pulled": false,
  "folders_configured": false
}
```

---

### `POST /api/wizard/check-ollama`

Verify the Ollama daemon is running.

**Response:**
```json
{ "running": true }
```

---

### `POST /api/wizard/pull-models`

Download default models. Returns a **streaming** response (newline-delimited JSON progress events).

**Streaming response format (one JSON object per line):**
```
{"event": "progress", "model": "phi3:mini", "percent": 42}
{"event": "progress", "model": "phi3:mini", "percent": 100}
{"event": "done", "models": ["phi3:mini", "nomic-embed-text"]}
```

Frontend reads this via `res.body` (ReadableStream) — see Section 9 for the pattern.

---

### `POST /api/wizard/set-folders`

Save the list of watched folders.

**Request:**
```json
{ "folders": ["/Users/mb/Desktop/thesis"] }
```

**Response:**
```json
{ "ok": true }
```

---

### `POST /api/wizard/complete`

Mark wizard as complete. Persists a flag so the wizard does not show again.

**Response:**
```json
{ "ok": true }
```

---

## 6. Data Flow Diagrams

### 6.1 Chat Message Flow

```
User types message
       │
InputArea.tsx
       │ useChatStore.sendMessage(text)
       ▼
chat.ts (Zustand)
       │ queryAgent({ question, agent }, abortSignal)
       ▼
api/client.ts  ──── POST /api/query ──────────────────►  server.py
                                                              │
                                              SpecializedAgentRouter.route()
                                                              │
                                                      AgentRuntime.run()
                                                              │
                                              ┌───────────── loop (max 10) ──┐
                                              │ ContextBuilder.build()        │
                                              │ OllamaChatProvider.complete() │
                                              │ ToolHandler.execute()         │
                                              └──────────────────────────────┘
                                                              │
                    ◄─── QueryResponse (answer + metadata) ──┘
       │
chat.ts addMessage({ role: "assistant", content, metadata })
       │
MessageBubble.tsx renders answer
LatencyBadge / SourceList renders metadata
```

### 6.2 Status Polling Flow

```
App.tsx mounts
       │
useSystemStore.startPolling(10_000)
       │
       ├── getStatus()  ──── GET /api/status ──► server.py
       │                                              │ psutil + metrics
       │                   ◄─── StatusResponse ───────┘
       │
       │ repeat every 10 s
       │
StatusBar.tsx reads useSystemStore.status
  ├── OllamaIndicator  ← ollama_ok
  ├── RamGauge         ← ram_used_gb / ram_available_gb
  └── LatencyBadge     ← p95_latency_ms
```

### 6.3 Config Load / Save Flow

```
SettingsPanel mounts
       │
useSettingsStore.load()  ──── GET /api/config ──► server.py
                         ◄─── AppConfig ───────────┘

User changes a setting
       │
useSettingsStore.patch({ key: value })
       │ updateConfig(patch)  ──── PATCH /api/config ──► server.py
                              ◄─── AppConfig (full) ──────┘
```

### 6.4 Wizard Flow

```
App.tsx checks useWizardStore.step
       │
       ├── Step 1: wizardCheckOllama()  ──── POST /api/wizard/check-ollama
       │                               ◄─── { running: bool }
       │
       ├── Step 2: wizardPullModels()   ──── POST /api/wizard/pull-models
       │           ReadableStream        ◄── streaming progress events
       │           progress bar renders
       │
       ├── Step 3: wizardSetFolders()   ──── POST /api/wizard/set-folders
       │                               ◄─── { ok: true }
       │
       └── Step 4: wizardComplete()     ──── POST /api/wizard/complete
                                        ◄─── { ok: true }
                                             App.tsx → show MainLayout
```

### 6.5 Tool Confirmation Flow

```
AgentRuntime detects tool needs approval
       │
backend sets pending_tool in response metadata
       │
useChatStore sets pendingConfirmation
       │
ConfirmModal renders (blocks UI)
       │
User approves ──► POST /api/query (continued execution — to be implemented)
User denies  ──► tool skipped
```

---

## 7. Agent System

### 7.1 Current Agents

| Agent ID (backend) | Frontend ID | Trigger | Authorized Tools |
|--------------------|-------------|---------|-----------------|
| `general-v1` | `general` | default / no prefix | all |
| `academic-v1` | `thesis` | `/academic` prefix or auto-route | `search_documents`, `read_file`, `write_file`, `create_note` |
| `code-v1` | `code` | `/code` prefix or auto-route | `search_documents`, `read_file`, `execute_python` |
| `calendar-v1` | `calendar` | `/calendar` prefix | _(planned — see Section 10)_ |

### 7.2 Agent Routing Logic (backend)

```python
# SpecializedAgentRouter.route(question)
if question.startswith("/academic"):   → academic-v1
elif question.startswith("/code"):     → code-v1
elif agent == "auto":                  → router classifies automatically
else:                                  → use req.agent value directly
```

### 7.3 How Frontend Passes the Agent

`AgentSelectorDropdown` reads `activeAgent` from `useChatStore` (Zustand).
When the user sends a message, `InputArea` reads `activeAgent` and passes it as the `agent` field in `QueryRequest`.

**Current ID mapping needed** (frontend ID → backend agent ID):

| Frontend `AgentId` | Backend agent ID to send |
|--------------------|--------------------------|
| `"general"` | `"general-v1"` |
| `"thesis"` | `"academic-v1"` |
| `"code"` | `"code-v1"` |
| `"calendar"` | `"calendar-v1"` _(planned)_ |

Add this mapping in `api/client.ts` or `chat.ts`:
```ts
const AGENT_ID_MAP: Record<AgentId, string> = {
  general:  "general-v1",
  thesis:   "academic-v1",
  code:     "code-v1",
  calendar: "calendar-v1",
};
```

---

## 8. State Management Map

Each Zustand store owns one area of backend state.

| Store | File | Backend endpoints touched | Trigger |
|-------|------|--------------------------|---------|
| `useChatStore` | `stores/chat.ts` | `POST /api/query` | User sends message |
| `useSystemStore` | `stores/system.ts` | `GET /api/status` | Every 10 s (polling) |
| `useSettingsStore` | `stores/settings.ts` | `GET /api/config`, `PATCH /api/config` | Panel open / setting change |
| `useWizardStore` | `stores/wizard.ts` | All `/api/wizard/*` routes | First-launch only |

**Adding a new store:** create `stores/yourFeature.ts`, import the needed `client.ts` functions, and call them from Zustand actions. Do not call `fetch` directly inside components.

---

## 9. Streaming Upgrade Path (Recommended)

The current `/api/query` blocks until the full answer is ready (can be 2–10 seconds). The recommended upgrade is **Server-Sent Events (SSE)**, which lets tokens stream to the frontend as they are produced.

### 9.1 Backend — FastAPI SSE

```python
from fastapi.responses import StreamingResponse
import json

@app.post("/api/query/stream")
async def query_stream_endpoint(req: QueryRequest):
    async def event_generator():
        async for token in app_state.runtime.stream(req.question, req.agent):
            data = json.dumps({"token": token})
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 9.2 Frontend — Reading SSE with fetch

```ts
// api/client.ts
export async function queryAgentStream(
  req: QueryRequest,
  onToken: (token: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/api/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, res.statusText);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6);
      if (payload === "[DONE]") return;
      const { token } = JSON.parse(payload);
      onToken(token);
    }
  }
}
```

### 9.3 Store Integration

```ts
// stores/chat.ts — inside sendMessage action
addMessage({ role: "assistant", content: "", id: msgId });

await queryAgentStream(
  { question, agent: AGENT_ID_MAP[activeAgent] },
  (token) => appendToken(msgId, token),  // updates message in place
  abortController.signal,
);
```

**Wizard model pull already uses streaming** — follow the same `ReadableStream` pattern already in `wizardPullModels()`.

---

## 10. Planned Extensions

### 10.1 Calendar Agent — Implementation Checklist

**Backend tasks:**
- [ ] Create `core/agents/specialized.py` entry: `CALENDAR_AGENT_ID = "calendar-v1"`
- [ ] Define agent profile with instructions focused on scheduling, reminders, and task management
- [ ] Add `authorized_tools`: `read_file`, `write_file`, `search_documents` (and future `create_event`)
- [ ] Add routing prefix `/calendar` to `SpecializedAgentRouter`
- [ ] Add calendar-specific tools in `core/tools/handlers/calendar.py` (read/write `.ics`, query events)
- [ ] Register calendar tools in `core/tools/registry.py`

**Frontend tasks:**
- [ ] `AGENT_ID_MAP` already maps `"calendar"` → `"calendar-v1"` (add the mapping as per Section 7.3)
- [ ] `AgentSelectorDropdown` already shows the Calendar option — no UI change needed
- [ ] Add `"calendar"` to backend's agent validation once implemented

**Integration test:**
- [ ] `POST /api/query` with `"agent": "calendar-v1"` returns a valid response
- [ ] Calendar tools appear in `metadata.tools_called`

### 10.2 Index Status Polling — `GET /api/index/status`

Currently missing. Needed for the settings panel to show indexing progress.

**Backend:**
```python
class IndexStatusResponse(BaseModel):
    job_id: str
    status: Literal["running", "done", "error"]
    files_indexed: int
    message: str = ""

@app.get("/api/index/status")
async def index_status(job_id: str) -> IndexStatusResponse: ...
```

**Frontend:**
```ts
export async function getIndexStatus(jobId: string): Promise<IndexResponse> {
  return request<IndexResponse>(`/api/index/status?job_id=${jobId}`);
}
```

### 10.3 Conversation History — `GET /api/conversations`

To support multi-session memory and history panel.

**Backend:**
```python
@app.get("/api/conversations")
async def list_conversations() -> list[ConversationSummary]: ...

@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str) -> ConversationDetail: ...
```

---

## 11. Auth Layer (Future)

No auth is implemented today. When needed, the recommended approach is **API key via HTTP header**.

### Pattern (when implementing)

**Backend — `server.py`:**
```python
from fastapi import Header, Security
from fastapi.security.api_key import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-Cerebro-Key", auto_error=False)
VALID_KEY = os.getenv("CEREBRO_API_KEY", "")

async def verify_key(key: str = Security(API_KEY_HEADER)):
    if VALID_KEY and key != VALID_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

# Apply to all routes:
app = FastAPI(dependencies=[Depends(verify_key)])
```

**Frontend — `client.ts`:**
```ts
const API_KEY = import.meta.env.VITE_CEREBRO_KEY ?? "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY ? { "X-Cerebro-Key": API_KEY } : {}),
    },
    ...options,
  });
  // ...
}
```

Add `VITE_CEREBRO_KEY=your-key` to `ui/tray/.env.local`.
Add `CEREBRO_API_KEY=your-key` to the root `.env`.

---

## 12. Coder Checklist

Use this when adding any new feature that involves a backend ↔ frontend connection.

### Before you start
- [ ] Both backend (`python main.py`) and frontend (`npm run dev`) are running
- [ ] Ollama is running (`ollama serve`) and model is pulled (`ollama pull phi3:mini`)
- [ ] All mismatches in Section 4 are resolved in the branch you are working on

### Adding a new endpoint
- [ ] Define a Pydantic request model and response model in `server.py`
- [ ] Write the FastAPI route handler under the `/api/` prefix
- [ ] Add the matching TypeScript interface to `ui/tray/src/api/types.ts`
- [ ] Add the typed wrapper function to `ui/tray/src/api/client.ts`
- [ ] Call the function only from a Zustand store action, not directly from a component
- [ ] Test with `curl` before wiring the frontend:
  ```bash
  curl -s -X POST http://localhost:7842/api/query \
    -H "Content-Type: application/json" \
    -d '{"question": "hello", "agent": "general-v1"}' | python -m json.tool
  ```

### Adding a new agent
- [ ] Follow the calendar checklist in Section 10.1 as a template
- [ ] Add agent ID to `AGENT_ID_MAP` in the frontend
- [ ] Add agent profile to `core/agents/specialized.py`
- [ ] Add routing prefix to `SpecializedAgentRouter`
- [ ] Test: select agent in dropdown → send message → verify `metadata.model_used` is set

### Adding streaming to an endpoint
- [ ] Use `StreamingResponse` with `media_type="text/event-stream"` on the backend
- [ ] Use the fetch + ReadableStream pattern from Section 9.2 on the frontend
- [ ] Never use `request<T>()` helper for streaming — call `fetch` directly in `client.ts`

### Type safety rule
Every field that crosses the HTTP boundary must exist in both:
1. The Pydantic model in `server.py`
2. The TypeScript interface in `api/types.ts`

If they diverge, the connection silently breaks. Keep them in sync.

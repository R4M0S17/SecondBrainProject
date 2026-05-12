# Agentic Personal OS — Cerebro Digital Local
## Development Plan v1.0

> **Spec ref:** `agentic_personal_os_spec copy.docx` — do not change architecture decisions without consulting the spec.

---

## Architecture Overview

```
Capa 4 — UX Layer       │ System Tray (Tauri) · CLI · REST API :7842
Capa 3 — Agentic Kernel │ LangGraph agents · Tool execution
Capa 2 — Memory Layer   │ LanceDB vector store · Semantic search
Capa 1 — Ingestion      │ File watcher · Parser · Chunker
```

**Non-negotiable principles:** Privacy-first (zero external APIs), memory-first (state on disk), serial LLM execution (asyncio.Queue), graceful timeouts (30s), modular contracts (no cross-module internals).

---

## Module Roadmap

| ID | Module | Week | Category | Status |
|----|--------|------|----------|--------|
| 0 | Scaffolding & DevEnv | 1 | Foundation | ✅ |
| 1 | Inference Engine (Ollama) | 1 | Core | ✅ |
| 2 | Document Ingestion Pipeline | 2 | Core | ✅ |
| 3 | Vector Memory (LanceDB) | 2 | Core | ✅ |
| 4 | RAG Query Engine | 3 | Core | ✅ |
| 5 | File Watcher (Watchdog) | 3 | Automation | ✅ |
| 6 | Tool Use & Action Layer | 4–5 | Agent | ✅ |
| 7 | Agent Orchestration (LangGraph) | 5–6 | Agent | ✅ |
| 8 | Specialized Agents | 6–7 | Agent | ✅ |
| 9 | System Tray UI (Tauri) | 7–8 | UI | ✅ |
| 10 | Proactive Scheduler | 9–10 | Awareness | ✅ |
| 11 | Calendar Integration | 10 | Awareness | ✅ |
| 12 | Config & Security Layer | 11 | Security | ✅ |
| 13 | Packaging & Distribution | 12 | Release | ✅ |

---

## Module 0 — Scaffolding & DevEnv
**Week 1 · Foundation**

### Tasks
- [x] Init Git repo with `.gitignore` (exclude `__pycache__`, `.env`, `*.lance`, model files)
- [x] Create Python venv: `python -m venv .venv && source .venv/bin/activate`
- [x] Init `pyproject.toml` with all dependencies from stack below
- [x] Create full folder tree with `__init__.py` in each `core/` subfolder
- [x] Create `config/settings.toml` with default values (see Module 12 schema)
- [x] Create `.env.example` documenting all env vars
- [x] Write `Makefile` with targets: `install`, `test`, `run`, `lint`
- [x] Configure pre-commit hooks: `black` + `ruff` + `mypy`

### Folder Structure
```
cerebro/
  core/
    inference/      # Module 1
    ingestion/      # Module 2
    memory/         # Module 3
    rag/            # Module 4
    watcher/        # Module 5
    tools/          # Module 6
    agents/         # Modules 7–8
  ui/
    tray/           # Module 9
  scheduler/        # Module 10
  integrations/     # Module 11
  config/           # Module 12
  tests/
  dist/             # Module 13 output
```

### Acceptance Criteria
- `make install` runs without errors on macOS 14+ and Ubuntu 22.04+
- All `core/` subfolders have `__init__.py`
- `make lint` reports no errors on scaffolding files

---

## Module 1 — Inference Engine
**Week 1 · Core**

**File:** `core/inference/engine.py`

### Interface
```python
class InferenceEngine:
    def __init__(self, model: str, base_url: str = "http://localhost:11434"): ...
    async def complete(self, prompt: str, system: str = "") -> str: ...
    async def embed(self, text: str) -> list[float]: ...          # nomic-embed-text, 768d
    async def stream(self, prompt: str) -> AsyncIterator[str]: ...
    def is_available(self) -> bool: ...
```

### Method Contracts
| Method | Behavior |
|--------|----------|
| `complete()` | POST `/api/generate`. Timeout 30s → `InferenceTimeoutError`. Returns clean str. |
| `embed()` | POST `/api/embeddings` with `nomic-embed-text`. Returns 768 floats. Never uses chat model. |
| `stream()` | POST with `stream=True`, yields each token. |
| `is_available()` | GET `/api/tags`, returns `False` (no exception) if Ollama is down. |

### Custom Exceptions
- `InferenceTimeoutError`
- `ModelNotFoundError`
- `OllamaUnavailableError`

### Tests — `tests/test_inference.py`
- [x] `test_complete_returns_string`
- [x] `test_embed_returns_768_floats`
- [x] `test_timeout_raises` (mock Ollama to not respond)
- [x] `test_unavailable_returns_false`

---

## Module 2 — Document Ingestion Pipeline
**Week 2 · Core**

**File:** `core/ingestion/pipeline.py`

### Supported Formats
| Format | Library | Notes |
|--------|---------|-------|
| `.pdf` | PyMuPDF (`fitz`) | Text only, skip scanned PDFs with warning |
| `.txt` | built-in | UTF-8, latin-1 fallback |
| `.md` | built-in | Plain text, ignore markdown syntax |
| `.py` | built-in | Plain text, no AST parsing in v1.0 |
| `.docx` | python-docx | Paragraphs only, ignore tables/images |

### Chunking Config (`settings.toml`)
```toml
[ingestion]
chunk_size = 512
chunk_overlap = 64
min_chunk_size = 50
```

### Document Dataclass
```python
@dataclass
class Document:
    id: str              # SHA256 of chunk content (dedup key)
    content: str
    source_path: str     # absolute path
    chunk_index: int
    file_modified: float # os.path.getmtime()
    metadata: dict       # extension, size, PDF page if applicable
```

### Acceptance Criteria
- 10-page PDF → 15–40 chunks depending on density
- No chunk produced below `min_chunk_size` tokens
- Unsupported formats return `[]` and log a warning (no exception)

### Tests — `tests/test_ingestion.py`
- [x] Parse each supported format
- [x] Correct chunking boundaries and overlap
- [x] Handle empty/corrupt files gracefully

---

## Module 3 — Vector Memory (LanceDB)
**Week 2 · Core**

**File:** `core/memory/vector_store.py`

### Interface
```python
class VectorStore:
    def __init__(self, db_path: str, table_name: str = "documents"): ...
    async def upsert(self, documents: list[Document], engine: InferenceEngine) -> int: ...
    async def search(self, query: str, engine: InferenceEngine, top_k: int = 5) -> list[SearchResult]: ...
    def delete_by_source(self, source_path: str) -> int: ...
    def get_indexed_files(self) -> dict[str, float]: ...  # {path: mtime}
```

### LanceDB Table Schema
| Field | Type | Description |
|-------|------|-------------|
| `id` | str (PK) | SHA256 of chunk |
| `content` | str | Chunk text |
| `vector` | list[float] (768d) | nomic-embed-text embedding |
| `source_path` | str | Absolute file path |
| `chunk_index` | int | Position within document |
| `file_modified` | float | mtime at indexing time |
| `metadata` | str (JSON) | Serialized metadata dict |

### Upsert Logic (Anti-Duplication — Critical)
1. Call `get_indexed_files()` for existing timestamps
2. Same file, same `file_modified` → **skip entirely**
3. Same file, different `file_modified` → `delete_by_source()` + re-insert
4. New file → insert directly

### Tests — `tests/test_memory.py`
- [x] Upsert without duplicates
- [x] Search returns correct `top_k`
- [x] `delete_by_source` removes all chunks for a file
- [x] Re-indexing unchanged file is a no-op

---

## Module 4 — RAG Query Engine
**Week 3 · Core**

**File:** `core/rag/query_engine.py`

### Interface
```python
class RAGQueryEngine:
    def __init__(self, store: VectorStore, engine: InferenceEngine): ...
    async def query(self, question: str, top_k: int = 5) -> RAGResponse: ...
    def build_prompt(self, question: str, chunks: list[SearchResult]) -> str: ...

@dataclass
class RAGResponse:
    answer: str
    sources: list[str]   # source_paths of used chunks
    chunks_used: int
    latency_ms: float
```

### Prompt Template (Do Not Modify Without Approval)
```
SYSTEM:
Eres un asistente personal que responde ÚNICAMENTE basándose en el contexto
provisto. Si la información no está en el contexto, responde exactamente:
"No encontré información sobre eso en tus documentos."
No inventes datos. No uses conocimiento externo.

USER:
Contexto de tus documentos:
---
[Fuente: archivo.pdf, chunk 3]
<contenido>
---
Pregunta: {question}
```

### Context Window Budget
- Reserve 512 tokens → system prompt + question
- Reserve 1024 tokens → expected response
- Fill remainder with chunks in similarity order up to `top_k`
- Truncate oversized chunks and append `[truncado]`

### Tests — `tests/test_rag.py`
- [x] Returns coherent answer when context is relevant
- [x] Returns the "no information" string when context is irrelevant
- [x] Sources list matches chunks used

---

## Module 5 — File System Watcher
**Week 3 · Automation**

**File:** `core/watcher/file_watcher.py`

### Interface
```python
class FileWatcher:
    def __init__(self, paths: list[str], ingestion_queue: asyncio.Queue): ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def _on_modified(self, event: FileModifiedEvent) -> None: ...
```

### Debounce Logic
- Maintain `dict[filepath → asyncio.TimerHandle]`
- On each event: cancel previous timer, set new 3-second timer
- On expiry: enqueue filepath into `ingestion_queue`
- Only process: `.pdf`, `.txt`, `.md`, `.py`, `.docx`

### Always Ignore
- Dotfiles (start with `.`)
- `.git/`, `node_modules/`, `__pycache__/`, `.venv/`
- `*.swp`, `*.tmp`, `*~`, `.DS_Store`

### Tests — `tests/test_watcher.py`
- [x] Debounce groups rapid events into single queue entry
- [x] Ignored files never reach the queue
- [x] Start/stop cycle is clean

---

## Module 6 — Tool Use & Action Layer
**Week 4–5 · Agent**

**File:** `core/tools/`

### Tools v1.0
| Tool | Signature | Notes |
|------|-----------|-------|
| `read_file` | `(path: str) -> str` | Only within `watched_paths` |
| `write_file` | `(path: str, content: str) -> bool` | Requires user confirmation if file exists |
| `create_directory` | `(path: str) -> bool` | Recursive mkdir |
| `list_directory` | `(path: str) -> list[str]` | Non-recursive |
| `execute_python` | `(code: str) -> str` | Sandboxed, 10s timeout, 64MB limit |
| `search_documents` | `(query: str) -> str` | Wraps `RAGQueryEngine.query()` |
| `get_current_datetime` | `() -> str` | ISO 8601 |
| `create_note` | `(title: str, content: str) -> str` | Creates `.md` in `notes/` dir |

### Sandbox Rules for `execute_python`
- **Allowed modules:** `math`, `datetime`, `json`, `re`, `collections`, `itertools`
- **Blocked:** `os`, `sys`, `subprocess`, `socket`, `importlib`, `builtins.__import__`
- No network, no filesystem outside sandbox
- Max output: 4000 characters of stdout

### Tests — `tests/test_tools.py`
- [x] `read_file` rejects paths outside `authorized_paths`
- [x] `execute_python` blocks `import os`, `__import__`, `os as _os` escape attempts
- [x] `execute_python` enforces 10s timeout
- [x] All tools return structured errors on failure

---

## Module 7 — Agent Orchestration (LangGraph)
**Week 5–6 · Agent**

**File:** `core/agents/kernel.py`

### Agent State
```python
@dataclass
class AgentState:
    messages: list[BaseMessage]
    tools_called: list[str]
    iterations: int       # max 10
    final_answer: str | None
```

### Graph Nodes
```
reason_node  → LLM decides: need tool OR can answer
tool_node    → execute requested tool
observe_node → append tool result to context
end_node     → format and return final answer

Edges:
  reason → tool_node    (if tool requested)
  reason → end_node     (if final answer ready)
  tool   → observe_node
  observe → reason_node (next iteration)
```

### Hard Limits
- Max **10 iterations** per query → return partial answer with note
- Max **5 tool calls** per query → prevent infinite loops
- Total timeout: **120 seconds**
- Repeated identical tool call → detect loop, abort, notify

### Tests — `tests/test_agents.py`
- [x] Agent resolves 2-step task with tool use
- [x] Agent respects max iterations limit
- [x] Duplicate tool call detection aborts correctly

---

## Module 8 — Specialized Agents ✅
**Week 6–7 · Agent**

**File:** `core/agents/specialized.py`

### Agent 1 — Academic Agent
- Activation: `/academic <query>`
- System prompt: organize notes, create summaries, generate quizzes, connect concepts
- Tools: `search_documents`, `read_file`, `write_file`, `create_note`

### Agent 2 — Code Agent
- Activation: `/code <query>`
- System prompt: answer codebase questions, suggest refactors, generate snippets
- Tools: `search_documents`, `read_file`, `execute_python`

### Agent 3 — General Agent (default)
- Activation: any query without prefix
- Conservative filesystem actions
- Tools: all tools enabled (empty `authorized_tools` = no restriction in AgentRuntime)

### Router
Simple prefix detection: `/academic` or `/code`. LLM-based auto-detection deferred to v2.0.

### Key exports
- `ACADEMIC_AGENT_ID`, `CODE_AGENT_ID`, `GENERAL_AGENT_ID` — stable disk keys
- `make_academic_profile()`, `make_code_profile()`, `make_general_profile()` — profile factories
- `RouteResult(agent_id, query)` — router output dataclass
- `SpecializedAgentRouter.route(raw)` — returns RouteResult
- `SpecializedAgentRouter.ensure_profiles(store)` — seeds missing profiles on startup

### Tests — `tests/test_specialized.py`
- [x] `/academic` prefix routes to academic agent with stripped query
- [x] `/code` prefix routes to code agent with stripped query
- [x] Plain input routes to general agent
- [x] Academic profile has exactly the correct tool set
- [x] Code profile has exactly the correct tool set
- [x] General profile has empty tools list (means all enabled)
- [x] `ensure_profiles` seeds all three when store is empty
- [x] `ensure_profiles` does not overwrite existing profiles
- [x] `ensure_profiles` only seeds missing profiles (partial seed case)

---

## Module 9 — System Tray UI (Tauri) ✅
**Week 7–8 · UI**

**Stack:** Tauri 2.0 (Rust) + React 18 + TypeScript + Tailwind CSS

**Global hotkey:** `Cmd+Shift+Space` (macOS) / `Ctrl+Shift+Space` (Windows/Linux)

**Python backend:** `ui/tray/server.py` — FastAPI app injected with `AppState` (mockable for tests)

### REST API — Port 7842
| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/query` | POST | `{"question": str, "agent": str}` | `{"answer": str, "metadata": ResponseMetadataModel}` |
| `/index` | POST | `{"paths": list[str]}` | `{"status": "started", "job_id": str}` |
| `/status` | GET | — | `{"indexed_files": int, "ollama_ok": bool, "model": str, "provider": str, "active_agent": str, "ram_used_gb": float, "ram_available_gb": float, "queries_total": int, "avg_latency_ms": float, "p95_latency_ms": float, "tool_call_count": int, "memory_hits": int, "provider_fallbacks": int}` |
| `/config` | GET/PUT | settings object | updated settings object |

### AppState (injectable)
- `runtime`: AgentRuntime (None → 503 on /query)
- `vector_store`: VectorStore (None → `indexed_files=0`)
- `provider_registry`: ProviderRegistry (None → `ollama_ok=False`)
- `router`: SpecializedAgentRouter (always present)
- `metrics`: MetricsCollector — tracks latencies, tool calls, memory hits, provider fallbacks; computes p95

### Screens v1.0
- **Chat Window:** text input, conversation history with cited sources, loading indicator
- **Status Bar:** active model, indexed file count, Ollama status (green/red)
- **Settings Panel:** watched folders add/remove, model selector, tool toggles
- **Index Progress:** progress bar during initial bulk indexing

### Tests — `tests/test_api.py`
- [x] `/status` responds in < 100ms
- [x] `/query` returns valid JSON with `answer`, `metadata`
- [x] `/query` with empty question returns 422
- [x] `/query` without runtime returns 503
- [x] `/query` increments `queries_total` counter
- [x] `/index` returns `{"status": "started", "job_id": <uuid>}`
- [x] `/index` with empty paths returns 422
- [x] `/config` GET returns current settings dict
- [x] `/config` PUT updates and merges settings
- [x] `/status` reports correct fields including RAM, agent info, p95, tool/memory/fallback counts

---

## Module 10 — Proactive Scheduler ✅
**Week 9–10 · Awareness**

**File:** `scheduler/proactive.py`

**Dependency:** `apscheduler` · Runs every 5 minutes in background

### Triggers v1.0
| Trigger | Kind | System Action | Condition |
|---------|------|---------------|-----------|
| Calendar event 1h before | `calendar_reminder` | Search related docs, notify with summary | `attach_calendar_reader()` called |
| File modified 5+ times/day | `file_checkpoint` | Suggest summary or checkpoint | `record_file_modification()` hook |
| 2h inactivity during work hours | `resume_context` | Suggest resuming last work context | `record_activity()` hook |
| New document indexed | `new_document` | Notify doc is available for query | `on_document_indexed()` hook |

**Note:** All triggers are silent when `do_not_disturb = true` in settings.

### Key types
```python
class TriggerKind(str, Enum):
    CALENDAR_REMINDER = "calendar_reminder"
    FILE_CHECKPOINT   = "file_checkpoint"
    RESUME_CONTEXT    = "resume_context"
    NEW_DOCUMENT      = "new_document"

@dataclass
class TriggerEvent:
    kind: TriggerKind
    message: str
    payload: dict

class NotificationSink(Protocol):
    def notify(self, event: TriggerEvent) -> None: ...
```

### Tests — `tests/test_scheduler.py`
- [x] Scheduler starts and stops cleanly
- [x] `file_checkpoint` fires at threshold (≥ 5 modifications)
- [x] `file_checkpoint` does not fire below threshold
- [x] `resume_context` fires after 2h inactivity during work hours (9–18)
- [x] `resume_context` silent outside work hours
- [x] `new_document` notifies sink and returns event
- [x] `calendar_reminder` fires within 1h window when reader attached
- [x] `calendar_reminder` silent without reader
- [x] Calendar reader exception handled gracefully
- [x] `do_not_disturb=True` silences all sink emissions
- [x] Pure trigger logic (`check_file_activity`) unaffected by DND
- [x] `record_activity()` resets inactivity clock

---

## Module 11 — Calendar Integration ✅
**Week 10 · Awareness**

**Files:** `integrations/__init__.py` · `integrations/calendar_reader.py`

### Interface
```python
class CalendarReader:
    def __init__(self, ics_path: str | None = None, use_apple_calendar: bool = False): ...
    def get_upcoming_events(self, hours_ahead: int = 24) -> list[CalendarEvent]: ...

@dataclass
class CalendarEvent:
    title: str
    start: datetime
    end: datetime
    description: str = ""
    location: str = ""
```

### Backends v1.0
- **ICalBackend:** parse a local `.ics` file with `icalendar`; path set in `settings.toml → [calendar].ics_path`
- **AppleCalendarBackend:** query Apple Calendar via `osascript -l JavaScript` JXA (macOS only); enabled by `[calendar].use_apple_calendar = true`
- Google Calendar: **deferred to v2.0** (requires OAuth)

### Key details
- All-day events (DATE type) are promoted to midnight UTC datetimes
- Facade merges backends, deduplicates by `(title, start ISO)`, sorts ascending by start
- Both backends fail silently (log warning, return `[]`) — never raise to caller

### Config (`settings.toml`)
```toml
[calendar]
ics_path = ""
use_apple_calendar = false
```

### Tests — `tests/test_calendar.py`
- [x] `test_ical_returns_event_within_window`
- [x] `test_ical_filters_event_outside_window`
- [x] `test_ical_filters_past_event`
- [x] `test_ical_multiple_events_all_returned`
- [x] `test_ical_event_fields_populated`
- [x] `test_ical_returns_empty_for_missing_file`
- [x] `test_ical_returns_empty_for_invalid_content`
- [x] `test_ical_parses_all_day_event`
- [x] `test_apple_backend_returns_events`
- [x] `test_apple_backend_skips_on_non_macos`
- [x] `test_apple_backend_returns_empty_on_osascript_error`
- [x] `test_apple_backend_handles_subprocess_exception`
- [x] `test_apple_backend_handles_empty_output`
- [x] `test_apple_backend_handles_invalid_json`
- [x] `test_reader_no_backends_returns_empty`
- [x] `test_reader_uses_ical_backend`
- [x] `test_reader_events_sorted_by_start`
- [x] `test_reader_deduplicates_same_event_across_backends`
- [x] `test_reader_backend_exception_does_not_propagate`

---

## Module 12 — Config & Security Layer ✅
**Week 11 · Security**

**Files:** `config/__init__.py` · `config/loader.py` · `config/security.py`

### Config Loader — `config/loader.py`
```python
class ConfigError(Exception): ...

def load_settings(path: str | None = None) -> dict:
    """Load settings.toml; raises ConfigError on missing file or invalid TOML."""
```
- Defaults to the bundled `config/settings.toml` when no path given
- Uses stdlib `tomllib` (Python 3.11+)

### Security — `config/security.py`
```python
def validate_path(path: str, watched_paths: list[str]) -> bool:
    """True if path resolves within any watched_paths; False if list is empty."""
```
- Resolves symlinks and `..` before comparison — traversal escapes blocked
- Empty `watched_paths` always returns `False`

### `config/settings.toml` (full schema)
```toml
[general]
app_name = "Cerebro"
language = "es"
log_level = "INFO"

[inference]
model = "phi3:mini"
embedding_model = "nomic-embed-text"
base_url = "http://localhost:11434"
timeout_seconds = 30
context_window = 4096

[ingestion]
watched_paths = []
chunk_size = 512
chunk_overlap = 64
min_chunk_size = 50
excluded_patterns = [".git", "node_modules", "__pycache__", ".venv"]

[memory]
db_path = "~/.cerebro/db"

[tools]
enable_execute_python = true
enable_write_file = true
authorized_write_paths = []

[ui]
hotkey = "cmd+shift+space"
port = 7842

[scheduler]
enabled = true
check_interval_minutes = 5
do_not_disturb = false

[calendar]
ics_path = ""
use_apple_calendar = false

[security]
max_file_size_mb = 50
sandbox_timeout_seconds = 10
sandbox_memory_mb = 64
```

### Global Security Rules
- No module may access paths outside `watched_paths` or `authorized_write_paths`
- All file-access tools must call `validate_path(path: str, watched_paths: list[str]) -> bool` before operating
- No module may open network connections to destinations other than `base_url`
- Logs must never contain document content — only metadata (filename, size, timestamp)

### Tests — `tests/test_config.py`
- [x] `test_load_settings_default_path_succeeds`
- [x] `test_load_settings_returns_all_required_sections`
- [x] `test_load_settings_values_have_correct_types`
- [x] `test_load_settings_from_explicit_path`
- [x] `test_load_settings_empty_toml_returns_empty_dict`
- [x] `test_load_settings_nested_values`
- [x] `test_load_settings_missing_file_raises_config_error`
- [x] `test_load_settings_invalid_toml_raises_config_error`
- [x] `test_config_error_is_exception_subclass`
- [x] `test_validate_path_accepts_child_of_watched`
- [x] `test_validate_path_accepts_exact_watched_dir`
- [x] `test_validate_path_accepts_deeply_nested_path`
- [x] `test_validate_path_accepts_one_of_multiple_watched`
- [x] `test_validate_path_rejects_path_outside_watched`
- [x] `test_validate_path_rejects_traversal_escape`
- [x] `test_validate_path_empty_watched_returns_false`
- [x] `test_validate_path_returns_false_when_no_watched_matches`
- [x] `test_validate_path_sibling_directory_rejected`

---

## Module 13 — Packaging & Distribution ✅
**Week 12 · Release**

### Strategy
- **Python backend:** PyInstaller bundle embedded in Tauri bundle at `src-tauri/resources/cerebro-backend`
- **Ollama:** downloaded during onboarding wizard (not bundled in installer)
- **First launch wizard:**
  1. Start Ollama
  2. Download model (`phi3:mini`)
  3. Select folders to index
- **Auto-update:** Tauri's built-in updater pointing to GitHub Releases

### Build Targets
- macOS → `.dmg`
- Windows → `.msi`

### Files
| File | Purpose |
|------|---------|
| `ui/tray/wizard.py` | `WizardSession` — sentinel-based first-launch detection, Ollama health check, `ollama pull` model download, `set_watched_paths` config write |
| `ui/tray/wizard_router.py` | FastAPI `/wizard/*` router (status, step/ollama, step/model, step/folders) |
| `build/cerebro-backend.spec` | PyInstaller spec — single-folder bundle of `main.py` + all deps |
| `build/build_macos.sh` | Full macOS pipeline: PyInstaller → Tauri resources → `cargo tauri build` → `.dmg` |
| `build/build_windows.ps1` | Full Windows pipeline: PyInstaller → Tauri resources → `cargo tauri build` → `.msi` |
| `dist/` | Output directory for PyInstaller artifacts |

### Makefile targets
- `make package-backend` — run PyInstaller only
- `make package-macos` — full macOS `.dmg` build
- `make package-windows` — full Windows `.msi` build

### Tests — `tests/test_packaging.py`
- [x] `test_is_first_launch_when_no_sentinel`
- [x] `test_is_not_first_launch_after_mark_complete`
- [x] `test_creates_sentinel_file`
- [x] `test_creates_data_dir_if_missing`
- [x] `test_idempotent_when_called_twice`
- [x] `test_returns_ollama_when_not_started`
- [x] `test_returns_done_when_complete`
- [x] `test_returns_true_when_ollama_responds_200`
- [x] `test_returns_false_when_connection_refused`
- [x] `test_returns_false_on_non_200_status`
- [x] `test_calls_correct_subprocess_command`
- [x] `test_raises_wizard_error_on_nonzero_returncode`
- [x] `test_error_message_includes_stderr`
- [x] `test_pulls_both_chat_and_embed_models`
- [x] `test_stops_on_first_failure`
- [x] `test_rejects_empty_list`
- [x] `test_rejects_nonexistent_directory`
- [x] `test_writes_paths_to_settings_toml`
- [x] `test_marks_wizard_complete_after_setting_paths`
- [x] `test_accepts_multiple_valid_paths`
- [x] `test_replaces_empty_list`
- [x] `test_replaces_nonempty_existing_list`
- [x] `test_preserves_other_toml_content`
- [x] `test_status_is_first_launch_true_when_no_sentinel`
- [x] `test_status_step_is_ollama_when_not_complete`
- [x] `test_status_step_is_done_after_complete`
- [x] `test_ollama_step_returns_ok_true_when_available`
- [x] `test_ollama_step_returns_ok_false_when_unavailable`
- [x] `test_model_step_returns_500_on_pull_failure`
- [x] `test_folders_step_returns_400_on_invalid_path`
- [x] `test_folders_step_returns_ok_on_valid_path`

---

## Tech Stack Reference

| Component | Technology | Install |
|-----------|-----------|---------|
| Inference Engine | Ollama | `ollama` |
| LLM Model | Phi-3 Mini 4K Instruct (3.8B, 4-bit) | `ollama pull phi3:mini` |
| Embedding Model | nomic-embed-text | `ollama pull nomic-embed-text` |
| Vector DB | LanceDB | `pip install lancedb` |
| PDF Parsing | PyMuPDF | `pip install pymupdf` |
| Agent Framework | LangGraph | `pip install langgraph` |
| File Watcher | Watchdog | `pip install watchdog` |
| Sandbox | RestrictedPython | `pip install RestrictedPython` |
| Desktop UI | Tauri 2.0 + React | `cargo + npm` |
| Config | TOML | `pip install tomllib` |
| Logging | Loguru | `pip install loguru` |
| Scheduler | APScheduler | `pip install apscheduler` |
| Calendar | icalendar | `pip install icalendar` |
| Testing | Pytest | `pip install pytest` |

**Minimum requirements:** Python 3.11 · Node.js 20 LTS · Rust stable · 8 GB RAM

---

## Performance Limits (8 GB RAM, 4-core CPU, no GPU)

| Metric | Target | Action if Exceeded |
|--------|--------|--------------------|
| RAM (Python + Ollama) | < 5.5 GB | Alert user, offer Qwen2-1.5B |
| RAG latency p50 | < 8s | Reduce `top_k` from 5 to 3 |
| RAG latency p95 | < 20s | Log to metrics file |
| Indexing 100-page file | < 60s | Background only, never block UI |
| LanceDB size | < 2 GB per 10k docs | Notify user, offer index cleanup |
| CPU idle | < 2% | Unload model after 10min inactivity |

---

## Architecture Decision Log

| Decision | Why |
|----------|-----|
| LangGraph over CrewAI | Explicit state graph — easier to debug; critical when each tool call is costly |
| LanceDB over ChromaDB/Qdrant | Embedded (no separate process), lowest RAM footprint |
| Tauri over Electron | ~30 MB RAM vs 200–400 MB for Electron |
| Serial LLM queue | 8 GB RAM + 4 GB model = no room for concurrent inference |
| nomic-embed-text separate from chat LLM | Trained specifically for semantic retrieval; avoids chat model bias in vector space |

---

## Testing Summary

| Module | Type | Focus |
|--------|------|-------|
| 1 | Unit + Integration | LLM responses (mocked), timeouts, embedding dimensions |
| 2 | Unit | Format parsing, chunking, empty/corrupt files |
| 3 | Integration | No-duplicate upsert, search top_k, delete cleanup |
| 4 | Integration | RAG coherence, no-context response |
| 5 | Unit | Debounce, ignore filters, queue correctness |
| 6 | Unit + Security | Sandbox escapes, timeouts, path authorization |
| 7 | Integration | Multi-step tool use, iteration limits |
| 8 | Unit | Prefix routing, profile tool sets, ensure_profiles seeding |
| 9 | E2E | API response time < 100ms, valid JSON, error codes |
| 10 | Unit | Trigger thresholds, DND silencing, inactivity clock, calendar edge cases |
| 11 | Unit | iCal parsing, Apple Calendar backend, facade dedup + sort, error handling |
| 12 | Unit | Settings loading, ConfigError, validate_path authorization and traversal blocking |

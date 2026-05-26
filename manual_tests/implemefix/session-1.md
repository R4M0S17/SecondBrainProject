# Manual frontend tests — session 1

| Field | Value |
|--------|--------|
| Model | `llama-3.2-3b-instruct-q4_k_m.gguf` |
| Scope | Chat UI, tool indicators, agent selector (General / Calendar / Code) |

This document records **what you tried**, **what was expected**, **what happened**, and **follow-up recommendations**.

---

## Summary

| Area | Verdict |
|------|--------|
| Basic chat (hello) | Works |
| Arithmetic | Model answered **incorrectly** |
| Structured / agent output | Sometimes raw **JSON** appears in the message instead of rendered text |
| PDF question without file | Reasonable refusal |
| Calendar (read + create) | Read path looked OK; **create** did not behave as expected; **Calendar** agent mode hit **HTTP 400** on llama.cpp |
| Filesystem (write) | Wrong tools / search behavior; **no successful file write** |
| Settings (Watched folders, Fleet) | Controls **not clickable** / possibly not wired |

---

## Tests — General agent

| # | Prompt | Expected | Observed | Status |
|---|--------|----------|----------|--------|
| G1 | Say hello in one sentence and nothing else. | One short greeting sentence. | `Hola!` (~18.5s) | Pass — short reply (language not specified in prompt). |
| G2 | What is 17 × 23? Show only the number. | **`391`** only. | `397` (~14.1s) | **Fail** — arithmetic error (small models often slip here). |
| G3 | Explain what a Python list comprehension is in 3 bullet points. | Three bullets, human-readable. | JSON: `{"action":"answer","answer":[...]}` in Spanish (~22.3s) | **Partial** — content is on-topic, but UI should not show raw JSON if that is not intentional. |
| G4 | Summarize the main idea of a research PDF in two sentences. I have not attached a file. | Decline or generic answer without inventing a PDF. | Spanish refusal: cannot summarize without the file (~18.0s) | Pass. |
| G5 | What meetings do I have in the next 24 hours? | Calendar tool(s) run; answer lists **real** events or states none if empty. | `No hay eventos programados en el horizonte de 24 horas.` + **1 TOOL** (~28.8s) | **Partial** — plausible if calendar is empty; confirm in Apple Calendar. Tool count suggests a tool ran. |
| G6 | Create a calendar event titled "Cerebro smoke test" tomorrow at 4pm for 30 minutes. | **`create_calendar_event`** (or similar) → **confirmation** if required → then success message; **not** a “search found nothing” reply. | JSON-style answer about **no events found** for search `"cerebro smoke test"` + **1 TOOL** (~29.9s) | **Fail** — looks like a **query/search** path instead of **create** + confirm flow. |

---

## Tests — Calendar agent

| # | Prompt | Expected | Observed | Status |
|---|--------|----------|----------|--------|
| C1 | Create a calendar event titled "Cerebro smoke test" tomorrow at 4pm for 30 minutes. | Same as G6: create flow + optional confirm. | `Error: API 500: Client error '400 Bad Request' for url 'http://127.0.0.1:8080/v1/chat/completions'` | **Fail** — backend or llama.cpp rejected the **chat/completions** request (payload/model/routing issue), not a normal assistant reply. |

---

## Tests — Code agent

| # | Prompt | Expected | Observed | Status |
|---|--------|----------|----------|--------|
| D1 | Write a file called test-cerebro.txt with the word hello inside my allowed folder. | **`write_file`** (or equivalent) under authorized paths, with confirmation if policy requires it; content should be the text `hello`, not a Python script unless asked. | `{"action":"tool","tool":"create_python_file","args":{"filename":"test-cerebro.txt","code":"print("hello")"}}` (~15.7s) | **Fail** — wrong tool (`.txt` is not a Python file tool); `code` is invalid Python (`print("hello")` broken by quotes). |

---

## Tests — General agent (filesystem)

| # | Prompt | Expected | Observed | Status |
|---|--------|----------|----------|--------|
| G7 | Write a file called test-cerebro.txt with the word hello inside my allowed folder. | Same as D1. | Message about **no search results** for `"hello"` + **1 TOOL** (~22.3s) | **Fail** — **`search_files`** (or similar) misfire instead of write. |

---

## Frontend / settings — gaps you reported

| Item | Location | Symptom | Recommendation |
|------|-----------|---------|----------------|
| Watched folders | Settings → **Watched folders** → **Add Folder** | Button does not respond; may not call backend. | Treat as **P0 UI bug**: verify `FolderManager` / wizard folder step handlers and disabled-state logic; confirm `PATCH /api/config` with `watched_folders` after pick. |
| Fleet Orchestrator | Settings → **Fleet Orchestrator** (**Auto** / **Pinned**) | Toggles not clickable; unclear backend wiring. | Confirm props and whether `app_state.fleet_orchestrator` is non-null; wire or hide until implemented. |

---

## Broader notes (Mac access, tools)

- **Calendar read** (G5) may be working if the calendar is empty; validate against real events.
- **Calendar create** (G6, C1) failed for different reasons (wrong tool path vs HTTP 400) — treat separately.
- **“No Mac access”** is only partially true: a tool **did** run in several cases (`1 TOOL`), but **policy**, **permissions** (Calendar, Reminders, Full Disk Access), and **watched/authorized paths** decide what succeeds.
- Until **watched folders** work in Settings, **read_file** / **write_file** tests are harder to trust because the backend may not know your allowed paths.

---

## Suggested next retest (after fixes)

1. **G2** again after any calculator tool or stronger model — expect **`391`**.
2. **G6** — expect a **create** tool path (not a search-only reply); verify in Apple Calendar. **Note:** the runtime only pauses for a fixed subset of tools (`write_file`, `execute_python`, `delete_file`, `run_script`); `create_calendar_event` may run **without** ConfirmModal unless that is unified with `ToolDefinition.requires_confirmation`.
3. **C1** — expect **no 400** from `http://127.0.0.1:8080/v1/chat/completions`; if 400 persists, capture request body from logs.
4. **D1 / G7** — see [Agent modes vs tools](#agent-modes-general-thesis-code-calendar--auto): **General** and **Code** profiles do **not** include `write_file`; for a plain `.txt` write, test with **Thesis** (`academic-v1`) or extend tool lists. Expect either **`write_file`** (Thesis) or an intentional alternative (e.g. `create_python_file` only for `.py`).
5. **Settings** — **Add Folder** opens picker and folder appears in list after save.

---

## Raw notes archive (original wording)

<details>
<summary>Original unstructured log</summary>

- General: hello → `Hola!` · 18.5s  
- General: 17×23 → `397` · 14.1s  
- General: list comprehension → JSON `action`/`answer` · 22.3s  
- General: PDF without file → refusal in Spanish · 18.0s  
- General: meetings 24h → no events · 28.8s · 1 TOOL  
- General: create event → search/no events JSON · 29.9s · 1 TOOL  
- Calendar agent: create event → API 500 / llama 400  
- Code agent: write txt → `create_python_file` tool JSON  
- General: write txt → search for "hello" / no results · 22.3s · 1 TOOL  
- Settings: Add Folder+ not working; Fleet Auto/Pinned not clickable  
- User impression: calendar create / documents / Mac tools not working  

</details>

---

## Agent modes: General, Thesis, Code, Calendar (+ Auto)

The dropdown in the UI (`ui/tray/src/api/types.ts`, `AgentSelectorDropdown.tsx`) sends an **`agent`** string on each query. The frontend maps labels to stable backend IDs (`ui/tray/src/api/client.ts` → `AGENT_ID_MAP`):

| UI label | `agent` sent to API | Backend profile ID | Role in one sentence |
|----------|---------------------|--------------------|------------------------|
| **Auto (router)** | `"auto"` | Resolved per request | `SpecializedAgentRouter.route_with_llm()` classifies the question (prefix fast path, else LLM against `CEREBRO_LLAMACPP_URL`) into `general-v1`, `academic-v1`, `code-v1`, or `calendar-v1`. |
| **General** | `general-v1` | `general-v1` | Default assistant: **read-oriented** tools (calendar read, search docs/notes/Spotlight, list/search files). **No** `write_file`, **no** script execution in the authorized tool list. |
| **Thesis** | `academic-v1` | `academic-v1` | “Academic” profile in code (`core/agents/specialized.py`): notes, RAG-style **`search_documents`**, **`read_file`**, **`write_file`**, **`create_note`**, filesystem discovery. This is the mode closest to “research + documents + writing”. |
| **Code** | `code-v1` | `code-v1` | Dev-focused: **`read_file`**, **`search_files`**, **`create_python_file`**, **`run_script`**, **`execute_python`**, **`delete_file`**, etc. There is **no** `write_file` in `CODE_TOOLS` — asking for a random `.txt` here pushes the model toward **`create_python_file`** or other mismatched tools. |
| **Calendar** | `calendar-v1` | `calendar-v1` | Calendar + Reminders shaped prompts; tool list includes **`get_upcoming_events`**, **`query_events`**, **`search_upcoming`**, **`create_calendar_event`**, **`add_reminder`**, etc. |

**Transport difference (important for testers):** `InputArea.tsx` uses **`POST /api/query`** (non-streaming) when **Calendar** is selected, because the tool loop must finish and can return **`metadata.pending_tool`**. All other modes use **`POST /api/query/stream`**, which (in `server.py`) still runs the **same** `runtime.run()` tool graph and **simulates** streaming by chunking the final answer into SSE tokens.

---

## How tools are wired (architecture overview)

This is the mental model another engineer should load when reading the repo.

### 1. Registration: name → Python callable

At startup, `ToolRegistry` is populated with **`ToolDefinition`** rows: `name`, `description`, `handler`, `requires_confirmation` (for governance metadata), scopes, etc. (`core/tools/registry.py`). Handlers are normal async or sync functions (e.g. Apple Calendar bridges, filesystem helpers).

### 2. Authorization: which tools exist in the prompt

Each **`AgentProfile`** carries **`authorized_tools`**: a whitelist of tool **names** (`core/agents/specialized.py`). When the LangGraph runtime builds the system prompt (`core/agents/runtime.py` → `_context_assembly_node`), it **filters** the global registry to **only** definitions whose `name` is in that list. The LLM never sees tools its persona is not allowed to call (at listing time).

### 3. Execution loop: reason → tool → observe

`AgentRuntime.run()` runs a small **LangGraph**: **context** (memory + history + tool list text) → **reason** (one `chat.complete()` returning JSON-shaped `action` / `tool` / `answer`) → **tool** (dispatch) → **observe** (inject tool result as a fake user message) → reason again, until an answer or limits (`MAX_ITERATIONS`, `MAX_TOOL_CALLS`). Tool handlers are invoked by name from a **`dict[str, Callable]`** built from the registry; unknown kwargs are dropped based on `inspect.signature` so brittle small models do not crash the process.

### 4. Hard pause vs “registry confirmation”

`_tool_node` only sets **`needs_confirmation`** (which becomes **`pending_tool`** in the API) for a **fixed** set: `write_file`, `execute_python`, `delete_file`, `run_script` (`CONFIRMATION_REQUIRED_TOOLS` in `runtime.py`). **`ToolDefinition.requires_confirmation`** is honored in **`PolicyEngine`** (`core/tools/policy.py`) for validation/audit paths, but the **graph runtime** does not currently unify every `requires_confirmation=True` registry tool with that pause — so some calendar writes may **execute immediately** without the same modal path unless extended.

### 5. Path policy (when enforced)

`PolicyEngine` validates paths (e.g. `read_file` under **watched** folders, writes under **authorized write** paths). Tests in `tests/test_tool_governance.py` cover this. The runtime’s `_tool_node` still uses a simpler **“is this tool name in `authorized_tools`?”** check; full policy integration in the graph is described in code comments as a future tightening step.

### 6. Frontend confirmation

If the final `AgentState` carries **`pending_tool_*`**, FastAPI stores it in **`app_state._pending_tools[conversation_id]`** and returns **`metadata.pending_tool`**. The React client shows **ConfirmModal** and resumes via **`POST /api/tool-confirm`**.

### 7. Config injection

Authorized read/write roots come from persisted **config** (watched folders, Cerebro write sandbox). If the UI never saves folders, handlers see **empty** or default path sets — reads/writes fail or no-op in ways that look like “no Mac access”.

---

## Architectural and product risks (honest list)

| Risk | Why it hurts |
|------|----------------|
| **Whitelists differ by agent** | Users blame “the model” when the real issue is **General** / **Code** not having `write_file`. UX should clarify or route writes to **Thesis**. |
| **JSON vs plain text** | Non-streaming path uses a system template that **requires JSON** from the model; streaming UX still shows the **final string** from `run()`, which can be raw JSON if the model did not unwrap into natural language. Small models often emit invalid or partial JSON. |
| **Router vs pinned agent** | **Auto** can misclassify; a pinned agent can be the wrong specialist for the task. |
| **Calendar-only uses `/query`** | Same graph, different transport; if only Calendar hits a failing code path (payload size, timeouts), bugs look agent-specific. |
| **Simulated streaming** | `/query/stream` waits for the **full** `run()` then chunks the answer — high latency before first token; users may think the app hung. |
| **LLM router traffic** | `LLMRouter` posts to **`/v1/chat/completions`** with `"model": "router"` — servers that do not accept that model name return **400** (matches your Calendar-agent failure if routing/model config disagrees). |
| **Dual confirmation models** | Registry `requires_confirmation` vs runtime `CONFIRMATION_REQUIRED_TOOLS` can **diverge** — product security reviews should treat that as tech debt. |
| **No `PolicyEngine` in `_tool_node`** | Path escapes rely on handlers + whitelist; defense-in-depth is incomplete until policy is always enforced at dispatch. |
| **Small local models** | Tool choice, JSON validity, and math are fragile; “smoke tests” need expectations calibrated to model size. |

---

## Appendix: source pointers

| Concern | Primary files |
|---------|----------------|
| UI agent list + labels | `ui/tray/src/api/types.ts` (`AGENTS`), `ui/tray/src/components/shared/AgentSelectorDropdown.tsx` |
| ID map to backend | `ui/tray/src/api/client.ts` (`AGENT_ID_MAP`) |
| Calendar vs stream | `ui/tray/src/components/chat/InputArea.tsx` |
| Profile tool whitelists | `core/agents/specialized.py` (`GENERAL_TOOLS`, `ACADEMIC_TOOLS`, `CODE_TOOLS`, `CALENDAR_TOOLS`) |
| Router categories | `core/agents/llm_router.py`, `SpecializedAgentRouter` in `specialized.py` |
| Tool loop + confirmation set | `core/agents/runtime.py` |
| HTTP entry + `auto` resolution | `ui/tray/server.py` (`/api/query`, `/api/query/stream`) |
| Tool definitions | `core/tools/registry.py` |
| Path / confirmation policy (tests) | `core/tools/policy.py`, `tests/test_tool_governance.py` |

---

## How to give access and authorization (macOS + Cerebro)

Two layers must both succeed: **macOS / Apple** (can this process control Calendar, files, etc.?) and **Cerebro** (which tools and paths are allowed for each agent).

### Filesystem tools (`read_file`, `list_directory`, `search_files`, `write_file`, …)

**Where allowed paths are set:** at backend startup in `main.py` (env + fixed list). They are **not** rebuilt from Settings “Watched folders” when you `PATCH /api/config` alone.

Default shape (simplified):

- **`CEREBRO_FILES_PATH`** — defaults to `~/Desktop/CerebroFiles`; expanded at startup.
- **`AUTHORIZED_READ_PATHS`** — includes `~/Desktop/Javier/SecondBrain` and `CEREBRO_FILES_PATH` in the repo’s `main.py`.
- **`AUTHORIZED_WRITE_PATHS`** — `[CEREBRO_FILES_PATH]` only.

| Goal | Action |
|------|--------|
| Allow **writes** | Put targets under **`CEREBRO_FILES_PATH`** (default `~/Desktop/CerebroFiles`). Create the folder if missing. Override with env `CEREBRO_FILES_PATH=/path/to/dir` and **restart** the backend. |
| Allow **reads** elsewhere | Add the directory to **`AUTHORIZED_READ_PATHS`** in `main.py` (or future wiring from config), then **restart**. |
| **Settings → Watched folders** | Saved under `~/.cerebro/state/config.json` as `watched_folders` (wizard / `PATCH /api/config`). Today this mainly tracks onboarding / UI; **tool handlers still use the paths bound at `main.py` startup** until the app reloads the registry from config. |

### Calendar / Reminders tools

Calendar handlers use **AppleScript / JXA** (`osascript`). macOS must grant **Automation** so the **process that runs Python** (Terminal, iTerm, Cursor’s embedded terminal, or the Tauri host, depending on how you launch `make run`) may control **Calendar** and **Reminders**.

1. Start the backend the same way you always do.
2. **System Settings → Privacy & Security → Automation** (and related prompts).
3. Enable control for **Calendar** / **Reminders** for that parent app.
4. Re-run the calendar permission probe from the wizard / `POST /api/wizard/reprobe-calendar-permission` so status updates (`core/observability/macos_perms.py`).

Denied Automation often surfaces as “not allowed to send Apple events” or error **`-1743`** in logs or handler messages (see `core/tools/handlers/calendar.py`).

### Settings “Tool permissions” toggles

**Execute Python / Write File / Read File / Search Web** persist as **`tool_permissions`** in config via the UI. The **core agent runtime does not currently read `tool_permissions`** (no references under `core/`), so those switches are **stored preferences only** until the backend enforces them before tool dispatch. **Effective gates today:** per-agent `authorized_tools` in `core/agents/specialized.py`, path lists in `main.py`, and the runtime confirmation set for a few destructive tools.

### Agent selection vs tools

Even with correct OS permissions and disk paths, only agents whose **`authorized_tools`** include a tool name can use it (e.g. **Thesis** / `academic-v1` has `write_file`; **General** does not). Pick the agent that matches the capability you are testing.

### Dangerous tools and ConfirmModal

`AgentRuntime` may set **`metadata.pending_tool`** for **`write_file`**, **`execute_python`**, **`delete_file`**, **`run_script`** so the UI calls **`POST /api/tool-confirm`**. Other tools may run without that pause unless the product unifies registry `requires_confirmation` with the runtime.

### Quick checklist

1. Backend + inference (e.g. llama.cpp) running as you normally test.
2. **Writes** only under **`CEREBRO_FILES_PATH`** unless you extend **`AUTHORIZED_WRITE_PATHS`** and restart.
3. **Reads** under current **`AUTHORIZED_READ_PATHS`**, or extend `main.py` and restart.
4. **Calendar / Reminders** — Automation for the app that owns the Python process; reprobe calendar after granting.
5. **Correct agent** (e.g. Thesis for `write_file`, Calendar for schedule flows).
6. Do not assume **Watched folders** alone changes `read_file` allowed paths until startup wiring merges config into the tool registry.


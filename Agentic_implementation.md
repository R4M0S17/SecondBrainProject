# Cerebro — Agentic Implementation Plan

Full roadmap for making Cerebro a genuine agentic OS controller. Each phase is
self-contained and ordered so Claude Code can implement them sequentially without
breaking existing functionality. Run `make test` after each phase to verify no
regressions.

---

## Architecture snapshot (what exists today)

| Layer | Status |
|---|---|
| LangGraph ReAct kernel (`core/agents/kernel.py`) | ✅ complete |
| AgentRuntime with persistent state (`core/agents/runtime.py`) | ✅ complete |
| Calendar read + write + reminders (`integrations/calendar_reader.py`, `handlers/calendar.py`) | ✅ complete |
| Birthday backend via Calendar app (`integrations/calendar_reader.py`) | ✅ fixed (Phase 0-A) |
| Local timezone in all prompts and tool output (`runtime.py`, `handlers/calendar.py`) | ✅ fixed (Phase 0-B) |
| Sandboxed Python execution (`handlers/execution.py`) | ✅ complete |
| File read/write/list primitives (`handlers/filesystem.py`) | ✅ registered (Phase 1) |
| ToolRegistry with calendar + filesystem tools (`main.py`) | ✅ calendar + filesystem registered |
| `create_python_file`, `run_script`, `delete_file` (`handlers/filesystem.py`, `handlers/execution.py`) | ✅ complete (Phase 2) |
| macOS apps: Spotlight, Notes, notifications (`integrations/macos_apps.py`, `handlers/macos.py`) | ✅ complete (Phase 3) |
| Modules A7, A8 | ❌ not implemented |

**Critical gap**: `main.py` only calls `register_calendar_tools()`. Every other handler
(`filesystem`, `execution`, search) is written but invisible to the agent.

---

## Phase 0 — Bug Fixes ✅ COMPLETE (2026-05-11)

### Bug 0-A: Birthdays not found in Calendar

**Root cause**: `BirthdayBackend` (`integrations/calendar_reader.py:367`) queries
`Application("Contacts")` for birthdates. The user stores birthdays directly as events
in Apple Calendar's "Birthdays" calendar — not in Contacts. The Contacts app returns
nothing.

`AppleCalendarBackend` Phase 2 also fails because the Birthdays calendar stores events
differently: the `recurrence` JXA property is either unavailable or empty for that
calendar type, so the `FREQ=YEARLY` filter (`_contains: "FREQ=YEARLY"`) never matches.

**Fix — change `_JXA_BIRTHDAYS_TEMPLATE` and `BirthdayBackend`**:

- Target the Calendar **app** directly (not Contacts).
- Find the calendar named `"Birthdays"` (or locale variant) instead of iterating all
  calendars.
- Iterate **all events** in that calendar (no recurrence filter needed — every event
  is already a yearly birthday entry).
- Apply the `nextAnnual()` date projection to find the upcoming occurrence.
- If no calendar named `"Birthdays"` is found, fall back to scanning all calendars for
  events whose title contains "Birthday" / "Cumpleaños".

New JXA template structure:
```
var app = Application("Calendar");
var now = new Date();
var cutoff = new Date(now.getTime() + {hours_ahead} * 3600000);
var results = [];

function nextAnnual(d) {
    var next = new Date(now.getFullYear(), d.getMonth(), d.getDate());
    if (next < now) next.setFullYear(next.getFullYear() + 1);
    return next;
}

// Find Birthdays calendar by name (try both English and Spanish)
var bdayCal = null;
app.calendars().forEach(function(cal) {
    var name = cal.name();
    if (name === "Birthdays" || name === "Cumpleaños") bdayCal = cal;
});

// If found, iterate all events and project to next annual occurrence
if (bdayCal) {
    bdayCal.events().forEach(function(ev) {
        try {
            var orig = ev.startDate();
            var next = nextAnnual(orig);
            if (next >= now && next <= cutoff) {
                results.push({ title: ev.summary() || "", start: next.toISOString() });
            }
        } catch(e) {}
    });
}
// Fallback: scan all calendars for events with "birthday"/"cumpleaños" in title
if (results.length === 0) {
    app.calendars().forEach(function(cal) {
        try {
            cal.events().forEach(function(ev) {
                try {
                    var t = (ev.summary() || "").toLowerCase();
                    if (t.indexOf("birthday") >= 0 || t.indexOf("cumpleaños") >= 0) {
                        var orig = ev.startDate();
                        var next = nextAnnual(orig);
                        if (next >= now && next <= cutoff) {
                            results.push({ title: ev.summary(), start: next.toISOString() });
                        }
                    }
                } catch(e) {}
            });
        } catch(e) {}
    });
}
JSON.stringify(results);
```

**Files edited**:
- `integrations/calendar_reader.py`: replaced `_JXA_BIRTHDAYS_TEMPLATE` (targets Calendar
  app, no `FREQ=YEARLY` filter, includes English/Spanish fallback scan); updated
  `BirthdayBackend` docstring. Also fixed `ICalBackend` "now" comparison to use local TZ.

**Tests added** (`tests/test_calendar.py`):
- `test_birthday_template_targets_calendar_not_contacts`
- `test_birthday_template_has_no_freq_yearly_filter`
- `test_birthday_template_includes_fallback_title_scan`

---

### Bug 0-B: Wrong time displayed (UTC instead of local timezone)

**Root cause**: Every call to `datetime.now()` in the codebase uses
`datetime.now(timezone.utc)`. The agent reports times like "14:30 UTC" even when the
user is in e.g. America/Mexico_City (UTC-6).

**Fix — use system local timezone**:

Python 3.11+ ships `zoneinfo` in stdlib. Use `datetime.now().astimezone()` which
automatically applies the system's configured timezone (reads from macOS
`/etc/localtime`). No hardcoded timezone string needed.

Replace every occurrence of:
```python
datetime.now(timezone.utc)
```
with:
```python
datetime.now().astimezone()
```

And update the format string in `now_str` to include `%Z` (shows local TZ abbreviation
like "CST", "PDT") instead of hardcoding "UTC".

**Files edited**:
- `core/agents/runtime.py`: `datetime.now(timezone.utc)` → `datetime.now().astimezone()`,
  format `%H:%M UTC` → `%H:%M %Z` in both prompt builders; removed unused `timezone` import.
- `core/tools/handlers/calendar.py`: same fix in `get_upcoming_events`, `query_events`,
  `search_upcoming` (kept `timezone.utc` for external timestamp normalization).
- `integrations/calendar_reader.py`: fixed `ICalBackend`'s "now" comparison.
- `tests/test_tools.py`: updated 3 stale English-string assertions to match Spanish output.

**Tests added**:
- `tests/test_calendar.py`: `test_get_upcoming_events_uses_local_timezone_format`
- `tests/test_agent_runtime.py`: `test_build_system_prompt_uses_local_timezone`

**Result**: 408 passing (was 404 before Phase 0; 4 pre-existing failures all unrelated).

---

## Phase 1 — File System Agent Tools ✅ COMPLETE (2026-05-11)

**Goal**: register filesystem capabilities into the ToolRegistry so the agent can search,
read, create, and list files within an authorized output folder.

### 1-A: Create the Cerebro output folder

The authorized write path for all agent-created content is:
```
~/Desktop/CerebroFiles/
```

This folder is created automatically on first use by `write_file` (it already calls
`mkdir -p`). Add `CEREBRO_FILES_PATH` env var (default: `~/Desktop/CerebroFiles`) to
`config/loader.py` and expose it in `AppState`.

### 1-B: Add `search_files` to `handlers/filesystem.py`

New function:
```python
def search_files(
    pattern: str,
    authorized_paths: list[str],
    base_path: str | None = None,
    extension: str | None = None,
    max_results: int = 20,
) -> str
```

- Uses `pathlib.Path.rglob(pattern)` starting from `base_path` (defaults to first
  authorized path).
- Optionally filters by `extension` (e.g. `".py"`, `".md"`).
- Returns a formatted list of matching paths with sizes and modification dates.
- Respects `validate_path` — only returns files inside authorized paths.

### 1-C: Register all filesystem tools

Add `register_filesystem_tools(registry: ToolRegistry)` to `core/tools/registry.py`:

| Tool name | Handler | Confirmation | Permission |
|---|---|---|---|
| `read_file` | `filesystem.read_file` | No | `tools.fs.read` |
| `write_file` | `filesystem.write_file` | **Yes** | `tools.fs.write` |
| `create_directory` | `filesystem.create_directory` | No | `tools.fs.write` |
| `list_directory` | `filesystem.list_directory` | No | `tools.fs.read` |
| `search_files` | `filesystem.search_files` | No | `tools.fs.read` |

Note: `delete_file` is intentionally **excluded** from Phase 1 (add in Phase 2 with
extra safeguards).

### 1-D: Wire into `main.py`

```python
from core.tools.registry import ToolRegistry, register_calendar_tools, register_filesystem_tools

cal_registry = ToolRegistry()
register_calendar_tools(cal_registry)
register_filesystem_tools(cal_registry)   # add this line
```

Pass `authorized_paths` and `cerebro_files_path` from `AppState` via a partial/lambda
wrapper so handlers receive the path list without storing global state.

### 1-E: Update `CONFIRMATION_REQUIRED_TOOLS` in `runtime.py`

Add `"write_file"` (already there) — confirm it is present and `"delete_file"` will be
added in Phase 2.

**Tests**: add `tests/test_filesystem_tools.py` covering:
- `search_files` with pattern match and extension filter
- `validate_path` rejection for paths outside authorized dirs
- `write_file` creates file at correct location

---

## Phase 2 — Python Script Creation & Real Execution ✅ COMPLETE (2026-05-11)

**Goal**: agent can generate and save `.py` files to `CerebroFiles/`, and optionally
run them with user confirmation.

### 2-A: `create_python_file` tool

New handler in `handlers/filesystem.py`:
```python
def create_python_file(filename: str, code: str, authorized_paths: list[str]) -> str
```

- Validates filename is a `.py` extension and contains no path separators.
- Saves to `~/Desktop/CerebroFiles/<filename>`.
- Returns success message with full path.
- No sandboxing — the file is created but NOT executed automatically.

### 2-B: `run_script` tool (confirmation required)

New handler in `handlers/execution.py`:
```python
def run_script(filepath: str, authorized_paths: list[str], timeout_seconds: int = 30) -> str
```

- Validates path is within authorized paths.
- Runs the script via `subprocess.run(["python3", filepath], ...)`.
- Captures stdout/stderr, truncates to 4000 chars.
- **Requires confirmation** — add to `CONFIRMATION_REQUIRED_TOOLS`.

### 2-C: `delete_file` tool (confirmation required)

New handler in `handlers/filesystem.py`:
```python
def delete_file(path: str, authorized_paths: list[str]) -> str
```

- Validates path is within authorized paths.
- Moves to trash via `subprocess.run(["osascript", ...])` instead of hard delete (safer).
- **Requires confirmation** — add to `CONFIRMATION_REQUIRED_TOOLS`.

### 2-D: Register new tools

Add to `register_filesystem_tools`:

| Tool name | Confirmation |
|---|---|
| `create_python_file` | No (write-only, no execution) |
| `run_script` | **Yes** |
| `delete_file` | **Yes** |

**Tests**: `tests/test_execution_tools.py`:
- `create_python_file` saves file to correct path
- `run_script` captures output, respects timeout, rejects unauthorized paths
- `delete_file` rejected for paths outside authorized dirs

**Files edited**:
- `core/tools/handlers/filesystem.py`: added `create_python_file` (validates `.py` extension and no path separators, writes to first authorized path) and `delete_file` (moves to macOS Trash via osascript instead of hard delete).
- `core/tools/handlers/execution.py`: added `run_script` (subprocess `python3`, captures stdout+stderr truncated to 4000 chars, respects timeout, validates path via `validate_path`).
- `core/tools/registry.py`: registered `create_python_file` (no confirmation), `run_script` (confirmation required), `delete_file` (confirmation required) in `register_filesystem_tools`.
- `core/agents/runtime.py`: added `"run_script"` to `CONFIRMATION_REQUIRED_TOOLS` (`"delete_file"` was already present).

**Result**: 428 passing (was 416 after Phase 1; 12 new tests added).

---

## Phase 3 — macOS App Integration ✅ COMPLETE (2026-05-11)

**Goal**: agent can search Spotlight, create/search Notes, and send desktop notifications.

### 3-A: New file `integrations/macos_apps.py`

#### Spotlight search (`spotlight_search`)

Uses macOS `mdfind` CLI — no AppleScript needed, no permissions required:
```python
def spotlight_search(query: str, max_results: int = 10, kind: str | None = None) -> str
```
- Runs `mdfind -limit {max_results} "{query}"` (or with `-onlyin ~/Documents` if needed).
- `kind` filter (optional): maps human strings to `kMDItemKind` (`"pdf"`, `"image"`,
  `"text"`, `"folder"`) via a lookup dict.
- Returns formatted list of matching file paths + types.

#### Apple Notes create (`create_note`)

JXA template:
```javascript
var app = Application("Notes");
var folder = app.folders.byName("{folder_name}");
folder.notes.push(app.Note({ name: {title}, body: {body} }));
"ok";
```
- `folder_name` defaults to `"Notes"` (root folder).
- Sanitize `title` and `body` with `json.dumps` to prevent JS injection.

```python
def create_note(title: str, body: str, folder: str = "Notes") -> str
```

#### Apple Notes search (`search_notes`)

JXA template:
```javascript
var app = Application("Notes");
var results = [];
app.notes().forEach(function(n) {
    var t = n.name() || "";
    var b = n.body() || "";
    if (t.toLowerCase().indexOf("{kw}") >= 0 || b.toLowerCase().indexOf("{kw}") >= 0) {
        results.push({ title: t, snippet: b.substring(0, 200) });
    }
});
JSON.stringify(results);
```
```python
def search_notes(query: str, max_results: int = 10) -> str
```

#### System notification (`send_notification`)

Uses `osascript`:
```applescript
display notification "{message}" with title "{title}" sound name "default"
```
```python
def send_notification(title: str, message: str) -> str
```

### 3-B: New file `core/tools/handlers/macos.py`

Thin wrappers that call `integrations/macos_apps.py` — same pattern as `handlers/calendar.py`.

### 3-C: `register_macos_tools(registry: ToolRegistry)`

Add to `core/tools/registry.py`:

| Tool name | Confirmation | Permission | Scope |
|---|---|---|---|
| `spotlight_search` | No | `tools.macos.search` | LOCAL |
| `create_note` | No | `tools.macos.notes.write` | LOCAL |
| `search_notes` | No | `tools.macos.notes.read` | LOCAL |
| `send_notification` | No | `tools.macos.notify` | LOCAL |

### 3-D: Wire into `main.py`

```python
from core.tools.registry import ..., register_macos_tools
register_macos_tools(cal_registry)
```

**Tests**: `tests/test_macos_tools.py` — mock `subprocess.run` / osascript calls,
assert formatted output strings.

**Files created/edited**:
- `integrations/macos_apps.py`: new file with `spotlight_search` (mdfind), `create_note` (JXA), `search_notes` (JXA, uses `plaintext()` property), `send_notification` (AppleScript). Input sanitization via `json.dumps` for JXA; AppleScript uses manual quote escaping. All functions return human-readable strings; non-Darwin platforms get informative no-op messages.
- `core/tools/handlers/macos.py`: new thin wrapper re-exporting all four functions.
- `core/tools/registry.py`: added `register_macos_tools()` registering all four tools with correct permissions (`tools.macos.search`, `tools.macos.notes.write`, `tools.macos.notes.read`, `tools.macos.notify`), all `requires_confirmation=False`.
- `main.py`: added `register_macos_tools(cal_registry)` call after filesystem tools.

**Result**: 15 new tests added (all passing); 326 passing in collectable suite (pre-existing collection errors in 6 ui-dependent test files unchanged).

---

## Phase 4 — Agent Profile & Tool Authorization Update ✅ COMPLETE (2026-05-11)

**Goal**: ensure the default agent profile authorizes all new tools so the kernel
actually calls them.

### 4-A: Updated specialized tool lists in `core/agents/specialized.py`

The implementation uses `GENERAL_TOOLS = []` (empty = all tools) for the general agent
and explicit lists for specialized profiles. Extended each list with Phase 1–3 tools:

```python
ACADEMIC_TOOLS = [
    "search_documents", "read_file", "write_file", "create_note",
    "list_directory", "search_files", "search_notes", "spotlight_search",
]
CALENDAR_TOOLS = [
    "search_documents", "get_upcoming_events", "query_events", "search_upcoming",
    "create_calendar_event", "add_reminder", "send_notification",
]
CODE_TOOLS = [
    "search_documents", "read_file", "execute_python",
    "create_python_file", "run_script", "delete_file",
    "list_directory", "search_files", "create_directory",
]
GENERAL_TOOLS = []  # unchanged — empty = all tools via AgentRuntime contract
```

`ensure_profiles()` automatically syncs existing on-disk profiles to the new lists
on next startup (stale detection compares `authorized_tools` lists).

### 4-B: Extended `PolicyEngine` (`core/tools/policy.py`)

Added path/content validation for all new Phase 1–3 tools:
- `run_script`: `filepath` must be within `authorized_write_paths`
- `delete_file`: `path` must be within `authorized_write_paths`
- `create_directory`: `path` must be within `authorized_write_paths`
- `list_directory`: `path` must be within `watched_paths` (read paths)
- `search_files`: `base_path` (if provided) must be within `watched_paths`
- `create_python_file`: `code` field sanitized to `<N chars>` in audit log

### 4-C: System prompt tool-listing in `runtime.py`

No code change needed — `_build_system_prompt` already iterates `tool_defs` dynamically.
All new tools appear in the prompt automatically.

### 4-D: `ToolPermissions` frontend component

Deferred — cosmetic UI change, no functional impact.

**Files edited**:
- `core/agents/specialized.py`: extended `ACADEMIC_TOOLS`, `CALENDAR_TOOLS`, `CODE_TOOLS`
  with tools from Phases 1–3. `GENERAL_TOOLS = []` unchanged.
- `core/tools/policy.py`: added path-boundary checks for `run_script`, `delete_file`,
  `create_directory`, `list_directory`, `search_files`; added code sanitization for
  `create_python_file`.

**Tests added**:
- `tests/test_specialized.py`: `test_code_profile_includes_phase2_tools`,
  `test_academic_profile_includes_phase3_tools`, `test_calendar_profile_includes_notification_tool`
- `tests/test_tool_governance.py`: `test_policy_rejects_run_script_outside_authorized_paths`,
  `test_policy_rejects_delete_file_outside_authorized_paths`,
  `test_policy_sanitizes_create_python_file_code`
- `tests/test_agent_runtime.py`: `test_search_files_tool_reached_when_authorized`

**Result**: 450 passing (was 428 after Phase 2+3; 7 new tests added; 1 pre-existing failure in test_phase7_advanced.py unrelated).

---

## Phase 5 — Modules A7 & A8: Advanced Agent Capabilities

### Module A7: Multi-step Task Decomposition

**Goal**: for complex requests ("plan my week", "organize all my Python files into folders
by topic"), the agent decomposes the task into ordered sub-steps and executes them
sequentially, showing progress to the user.

**Implementation**:

New file `core/agents/planner.py`:

```python
class TaskPlanner:
    """Wraps AgentRuntime to handle multi-step tasks."""
    async def decompose(self, query: str, context: AssembledContext) -> list[str]
    async def execute_plan(self, steps: list[str], ...) -> AsyncIterator[str]
```

- `decompose()` calls the LLM with a planning prompt: "List the numbered steps needed
  to complete this task. Return JSON array of step strings."
- `execute_plan()` runs each step through `AgentRuntime.run()` sequentially, yielding
  progress updates between steps.
- Add a `is_complex_task()` heuristic to `core/agents/llm_router.py` that triggers the
  planner (e.g. queries with "organize", "plan", "create and then", "for each").

New endpoint `POST /api/query/plan` in `ui/tray/server.py`:
- Returns SSE stream with `{step, total, result}` events so the frontend can show a
  step-by-step progress view.

Frontend: add `PlanExecutionView` component in `ui/tray/src/components/chat/` that
shows an expandable step list with status indicators (pending / running / done).

### Module A8: Proactive Context Injection

**Goal**: the agent proactively includes relevant context (upcoming events, recent files,
pending reminders) in responses without the user having to ask.

**Implementation**:

New file `core/agents/context_enricher.py`:

```python
class ContextEnricher:
    """Adds ambient context to every query before it reaches the LLM."""
    async def enrich(self, query: str, agent_state: AgentState) -> str
```

- On every query, runs lightweight checks in parallel:
  1. `get_upcoming_events(hours_ahead=12)` — if events in next 12h, prepend summary
  2. `search_files(pattern="*", base_path=cerebro_files_path)` — list of recently
     modified files (last 24h)
  3. Checks `scheduler/proactive.py` for any pending triggers
- Injects results as a `CONTEXT_INJECTION` section appended to the system prompt.
- Controlled by a `proactive_context: bool` flag in `settings.toml` (default: `true`).

Wire into `AgentRuntime._build_system_prompt()` — call `ContextEnricher.enrich()` and
append the result after `MEMORIA RECUPERADA`.

---

## Implementation order for Claude Code

```
Phase 0-A  → Fix birthday backend (integrations/calendar_reader.py)          ✅ DONE
Phase 0-B  → Fix timezone bug (runtime.py + handlers/calendar.py)            ✅ DONE
Phase 1    → Filesystem tools (handlers/filesystem.py + registry.py + main.py)    ✅ DONE
Phase 2    → Script creation & real execution (handlers/filesystem.py + handlers/execution.py)    ✅ DONE
Phase 3    → macOS app integration (integrations/macos_apps.py + handlers/macos.py + registry.py)    ✅ DONE
Phase 4    → Profile + policy update (specialized.py + policy.py)             ✅ DONE
Phase 5-A7 → Task planner (agents/planner.py + server.py + frontend)
Phase 5-A8 → Context enricher (agents/context_enricher.py + runtime.py)
```

Run `make test` after each phase. No phase requires changes to the LangGraph kernel or
inference layer.

---

## Test coverage targets (new tests per phase)

| Phase | Test file | Min new tests | Actual |
|---|---|---|---|
| 0-A | `tests/test_calendar.py` (update) | 3 | ✅ 3 added |
| 0-B | `tests/test_calendar.py` + `tests/test_agent_runtime.py` | 2 | ✅ 2 added |
| 1 | `tests/test_filesystem_tools.py` (new) | 8 | ✅ 8 added |
| 2 | `tests/test_execution_tools.py` (new) | 5 | ✅ 12 added |
| 3 | `tests/test_macos_tools.py` (new) | 6 | ✅ 15 added |
| 4 | `tests/test_specialized.py` + `test_tool_governance.py` + `test_agent_runtime.py` | 3 | ✅ 7 added |
| 5-A7 | `tests/test_planner.py` (new) | 5 | |
| 5-A8 | `tests/test_context_enricher.py` (new) | 4 | |

Target after all phases: **430+ passing tests** (450 after Phase 4; 428 after Phase 2+3; 416 after Phase 1; was 408 after Phase 0).

---

## Environment additions (`config/loader.py`)

```toml
[files]
cerebro_files_path = "~/Desktop/CerebroFiles"
authorized_read_paths = ["~/Desktop/Javier/SecondBrain", "~/Desktop/CerebroFiles"]
authorized_write_paths = ["~/Desktop/CerebroFiles"]

[agent]
proactive_context = true
```

New env vars:
- `CEREBRO_FILES_PATH` — override output folder (default: `~/Desktop/CerebroFiles`)
- `CEREBRO_PROACTIVE_CONTEXT` — `true`/`false`

# Architectural Cleanup — June 2026

## Critical Bug Fix

### `main.py:273` — Use-before-definition of `llm_engine`
**Problem**: `ContextBuilder(inference_engine=llm_engine)` was called 7 lines before `llm_engine = InferenceEngine(...)` was defined. Crashes at runtime if `_build_app_state()` is called.

**Fix**: Moved `InferenceEngine` instantiation to line 256 (before `ContextBuilder`). The `InferenceEngine` now references the correct `LLAMACPP_URL` for the SemanticCompressor health check and RAGQueryEngine, while `ContextBuilder` receives the valid engine reference.

---

## Dead Code Removal (~1,500 lines deleted)

### `core/pipeline/` — Removed (8 stages, ~616 lines production + 470 stage code)
- Pipeline was completely bypassed by query endpoints (`/api/query`, `/api/query/stream` call `runtime.run()` directly).
- `core/pipeline/stages/` — all 8 stage files deleted
- `core/pipeline/pipeline.py` — Pipeline runner deleted
- `tests/test_pipeline.py` — corresponding test deleted (222 lines)
- No production code outside the pipeline referenced it.

### `core/agents/kernel.py` — Removed (246 lines)
- Standalone ReAct LangGraph kernel that was imported by nothing in production.
- Duplicated `MAX_ITERATIONS`, `MAX_TOOL_CALLS`, `TIMEOUT_SECONDS` from `runtime.py`.
- `tests/test_agents.py` (the only consumer) deleted along with it.

### `core/tools/audit.py` — Removed (40 lines)
- `AuditLogger` class never instantiated in any production path.
- Only referenced by `core/pipeline/stages/audit.py` (deleted) and tests.
- Tests from `tests/test_tool_governance.py` removed (3 tests).

### `core/tools/handlers/search.py` — Removed (9 lines)
- `search_documents()` wrapped `RAGQueryEngine.query()` but was never registered as a tool.
- Exported in `__init__.py` but unused.

### `core/agents/profiles/` — Removed (empty directory)
- `__init__.py` was empty (0 bytes).
- Agent profiles are hardcoded in `specialized.py`.

---

## Code Consolidation

### `main.py` — Refactored llama.cpp dual-path into factory
**Before**: ~80 lines of near-identical if/else blocks for "simple" vs "model-swap" modes, each with its own embedding + chat provider setup.

**After**: Extracted `_setup_llamacpp(embed_url, llm_url)` factory function (17 lines). The llamacpp branch now:
1. Resolves URLs for the selected mode (simple vs model-swap)
2. Calls factory once
3. Registers providers once
4. MLX secondary is registered once via `if use_mlx:` block

This eliminates 40+ duplicated lines and makes the two modes impossible to drift.

### `core/tools/registry.py` — Registered `execute_python` as a real tool
**Problem**: `execute_python` was in `CONFIRMATION_REQUIRED_TOOLS`, handled by `PolicyEngine`, authorized for code-v1 agent, and fully tested — but never registered as a `ToolDefinition` in any `register_*_tools()` function. The handler existed in `execution.py` but was an orphan.

**Fix**: Registered `execute_python` in `register_filesystem_tools()` with `requires_confirmation=True`, scope `SANDBOXED`, audit `FULL`. Parameters: `code` (str) and `timeout_seconds` (int, default 10). The handler is bound via `partial` (no path auth needed since it's sandboxed).

### `core/tools/__init__.py` — Cleaned up orphaned exports
Removed from `__all__`:
- `AuditLogger` (module deleted, tests import directly from `core.tools.audit`)
- `create_note` (from `utils.py` — conflicts with registered `create_note` from `macos.py`)
- `search_documents` (handler deleted)

### `tests/conftest.py` — Added shared fixtures
New file with three fixtures used across multiple test files:
- `mock_provider` — AsyncMock-based ChatProvider
- `mock_registry` — Mock ProviderRegistry with `get_chat`/`select_for_task`
- `tmp_app_state` — Minimal MagicMock-based AppState with tmp_path-backed paths

Previously each test file duplicated this setup.

---

## Configuration

### `.gitignore` — Added `cerebro/` duplicate
The `cerebro/` directory is a ~9.8 GB synced copy of the project. Added to `.gitignore` so `git status`, grep, and file searches don't scan it. Recommended action: delete with `rm -rf cerebro/` if not needed.

---

## Documentation

### `CLAUDE.md` — Updated to match reality
- runtime.py: 1331 → **1418** lines
- Fast path router order: 5 stages → **9 stages** (Time/Date, Config Read, URL Open, Math, File write, Reminder, Calendar read, Calendar write, File search)
- Tools: 20 → **21** (added `execute_python`)
- Tools requiring confirmation: added `execute_python`
- Pipeline section: removed (deleted)
- Profiles section: profiles in `specialized.py` (not in empty dir)
- Test files: 7 → **8** calendar test files, removed `test_pipeline.py`, added `conftest.py`
- Added shared conftest fixture note

---

## Optimizations & Fixes — June 13-14, 2026

### Lite profile interactive prompt
- **`main.py`** — New `_prompt_lite_profile()`: detects ≤10GB RAM on TTY, asks user Y/n. Skips if `CEREBRO_SKIP_LITE_PROMPT` is set or any `CEREBRO_*` env vars are present.
- **`AGENTS.md`** — Added `CEREBRO_SKIP_LITE_PROMPT` to env vars table.

### EngineSuspender (SIGSTOP/SIGCONT)
- **New file:** `core/inference/engine_suspender.py` — `EngineSuspender` class.
- **`main.py`** — PID binding via `lsof -ti :8080`, background loop every 15s.
- **`core/agents/runtime.py`** — `resume()` calls at start of `stream()`, `run()`, `run_streaming()`.
- **`ui/tray/server.py`** — New `GET /api/engine/activity` endpoint.
- **`ui/tray/src/api/client.ts`** — New `getEngineActivity()` client function.
- **`ui/tray/src/components/status/EngineIndicator.tsx`** — "suspended" state with blue dim dot.
- **`ui/tray/src/components/status/StatusBar.tsx`** — Polls `/api/engine/activity` every 10s.
- **Behavior:** 180s idle → `SIGSTOP` (pages reclaimable by kernel). Next query → `SIGCONT` (<2ms resume vs 8s reload).

### Bounded prompt cache
- **`core/inference/prompt_cache.py`** — New `enforce_cache_size()`: deletes cache if > 256 MB AND RAM < 2 GB. Configurable via `CEREBRO_MAX_CACHE_MB`.
- **`core/inference/ram_preflight.py`** — Calls `enforce_cache_size()` on every preflight.

### Adaptive context length
- **New file:** `core/inference/adaptive_context.py` — `AdaptiveContext` class.
- **`main.py`** — Instantiated in `app_state.adaptive_ctx`.
- **Behavior:** RAM < 1GB → 2048 ctx; 1-2GB → 3072; > 2GB → 4096.
- **Note:** Currently only rewrites `config/chat.args` (requires engine restart). Per-request `n_ctx` pending.

### File search P0 fix + edge case hardening
- **`core/agents/file_search_fast_path.py`:**
  - `_LOCATION_RE` — Added English prepositions `on`, `in`, `inside`.
  - `_NAMED_RE` — Made named-file indicator mandatory (prevents false match on "que").
  - `_META_QUESTION_RE` — New: rejects "explícame", "qué es", "what is", "how to".
  - `is_file_search_query` — Supports bare globs (`*.py`), content queries without verb ("archivos que contengan X"), extension hints with file noun ("archivos de tipo py").
  - `max_results` regex — Added Spanish "un" ("solo un archivo").
  - `_try_file_search_fast_path` — Now passes `authorized_paths` from `authorized_read_paths_getter` (watched_folders merge).
  - Empty tools list = no restriction (backward-compatible).
- **`core/agents/runtime.py`** — Added `authorized_read_paths_getter` parameter.
- **`core/agents/fast_path_router.py`** — Added `authorized_read_paths_getter` parameter.
- **`main.py`** — Passes `authorized_read_paths_getter=lambda: app_state.authorized_read_paths`.
- **Tests:** 56 new edge case tests in `tests/test_file_search_edge_cases.py`.

### Smoke tests converted to pytest
- **New file:** `tests/test_smoke_live.py` — 13 tests (health, status, RAM, config, latency, math, calendar, file search, file write, auth denial, agent routing).
- **Markers:** `live` and `slow` registered in `pyproject.toml`.
- **`Makefile`:** `make smoke` now runs `pytest tests/test_smoke_live.py -v`.

### Test suite totals
- Stable suite: **154 passed**, 0 failed, 5 warnings (32.31s)
- File search edge cases: **69 tests** passed
- Smoke tests: **13 tests** collected (require live backend)

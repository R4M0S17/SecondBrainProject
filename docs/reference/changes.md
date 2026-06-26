# Architectural Cleanup — June 2026

## Engine / backend split — Fases 4–5 (2026-06-25)

Full write-up: [`docs/implementation/engine-backend-split-phase4-5.md`](../implementation/engine-backend-split-phase4-5.md).

| Area | Change |
|------|--------|
| Tauri | Auto-start backend on app open; `start_cerebro_backend` / `start_cerebro_engine` commands |
| `services.ts` | `backendReady` + `engineDesired`; Turn On/Off → `/api/engine/start\|stop` |
| UI | EngineIndicator (offline vs engine off); InputArea allows fast paths without engine |
| i18n | Start/Stop engine labels; backend offline placeholder |
| Docs | DESKTOP_ONE_CLICK_LAUNCH, README, CURRENT_FOCUS updated |

**Plan complete:** [`docs/plans/engine-backend-split.md`](../plans/engine-backend-split.md) Fases 0–5 ✅

---

## Engine / backend split — Fases 2–3 (2026-06-25)

Full write-up: [`docs/implementation/engine-backend-split-phase2-3.md`](../implementation/engine-backend-split-phase2-3.md).

| Area | Change |
|------|--------|
| `CEREBRO_AUTO_START_ENGINE` | Default `false`; `make run` = backend only |
| `make dev-full` | Legacy one-shot: `CEREBRO_AUTO_START_ENGINE=true` |
| `engine_manager.py` | spawn/stop/wait for `:8080`/`:8082` |
| API | `GET/POST /api/engine/status|start|stop` |
| Tests | `tests/test_engine_api.py` |

---

## Engine / backend split — Fases 0–1 (2026-06-25)

Full write-up: [`docs/implementation/engine-backend-split-phase0-1.md`](../implementation/engine-backend-split-phase0-1.md).

| Area | Change |
|------|--------|
| `CEREBRO_AUTO_START_ENGINE` | New flag (default `true`); gates `_ensure_engine_running()` in `main.py` |
| `engine_desired` | `core/inference/engine_desired.py` + health monitor skips auto-restart when `off` |
| Desktop scripts | Split into `backend.sh`, `engine.sh`, `stop_*.sh`; shared `cerebro_desktop_common.sh` |
| Makefile | `desktop-backend`, `desktop-engine`, `desktop-launch-full`, `desktop-stop-engine/backend` |
| Tauri bundle | `build.rs` syncs all desktop scripts into app resources |

**Gate:** `make test` + `make test-stable` green; behavior unchanged with default env.

---

## Phase 0 — Test stabilization (2026-06-22)

Full write-up: [`docs/implementation/phase-0-stabilization.md`](../implementation/phase-0-stabilization.md).

| Area | Change |
|------|--------|
| Config API | `ConfigUpdateRequest` with `extra="allow"` for PATCH persistence |
| Web tools | Module-level `DDGS` import; removed invalid `trafilatura` kwarg |
| Fast paths | Order: file_write before calendar; unit_conversion last; Spanish calendar write |
| Runtime | `_is_small_model()` fixed — `Qwen3.5-2B` no longer triggers lite mode |
| Planner | Default `max_steps` restored to 20 |
| Feature flags | Added missing `is_sandbox()` |
| Tests | Global `app_state` teardown; fix_cerebro mocks; new `test_small_model_detection.py` |
| Makefile | `make test` uses `-m "not live"`, `--cov-fail-under=72` |

**Gate:** `make test-stable` 154 passed · `make test` 1138 passed · coverage 72.28%

---

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

---

---

## Low Power mode disabled — June 18, 2026

Low Power (Qwen2.5-0.5B) marked **in development**; normal mode (Qwen3.5-2B) is the default.

- `core/feature_flags.py` — `CEREBRO_LOW_POWER_ENABLED` gate (off by default)
- Backend migrates persisted `profile=low-power` → `normal` + main model on startup
- `PATCH /api/config` rejects `profile: low-power` when disabled
- Frontend toggle disabled with “In development” badge
- `config/chat.args` restored to Qwen3.5-2B
- Plan: `docs/plans/maybe-later/LOW_POWER_V2_NANO_MODE.md`

---

## Low-Power Mode Fix — June 18, 2026

### Bug: `--mmproj` concatenated with previous flag (`main.py:268`)
**Problem**: `new_content += "--mmproj bin/models/mmproj-F16.gguf\n"` lacked `\n` before `--mmproj`, producing `--log-disable--mmproj` (single token). `llama-server $(cat chat.args)` received `--log-disable--mmproj` as an invalid argument and failed to start.

**Fix**: Added `\n` prefix → `new_content += "\n--mmproj bin/models/mmproj-F16.gguf\n"`.

**Files**: `main.py:268`, `config/chat.args`

---

### Bug: chat.args corruption (`config/chat.args:6`)
**Problem**: The file had `--log-disable--mmproj bin/models/mmproj-F16.gguf` on one line instead of two separate lines.

**Fix**: Split into `--log-disable` and `--mmproj bin/models/mmproj-F16.gguf` on separate lines.

**Files**: `config/chat.args`

---

### Bug: Low-power model filename mismatch (`config/chat-lowpower.args:1`)
**Problem**: The file referenced `Qwen2.5-0.5B-Instruct-Q5_K_M.gguf` (PascalCase) but the actual file on disk is `qwen2.5-0.5b-instruct-q5_k_m.gguf` (lowercase). `llama-server` silently exited because the GGUF file didn't exist.

**Fix**: Changed `--model` path to match actual filename.

**Files**: `config/chat-lowpower.args`

---

### Bug: Low-power model overridden by profile env (`main.py:131-134`)
**Problem**: `lite-8gb.env` sets `CEREBRO_LLAMACPP_MODEL=Qwen3.5-2B-UD-Q4_K_XL.gguf`. The launcher sourced this file before starting the backend, so the low-power model set from `config.json` was immediately overwritten by the env var. The old code only set the env var if it wasn't already set (`and "CEREBRO_LLAMACPP_MODEL" not in os.environ`), but the profile env had already set it.

**Fix**: Changed condition to always override the env var when profile is low-power (removed `and "CEREBRO_LLAMACPP_MODEL" not in os.environ`). Now `config.json` persists the truth regardless of profile env files.

**Files**: `main.py:131-134`

---

### Bug: `_ensure_chat_args` always used `chat.args` and `chat` profile (`main.py:243-322`)
**Problem**: `_ensure_chat_args()` hardcoded `LLAMACPP_ARGS_FILE = "config/chat.args"` and always passed `"chat"` to `start_engine.sh`. When profile was low-power, it still rewrote `chat.args` (instead of `chat-lowpower.args`) and started the engine with the normal profile.

**Fix**:
1. Added `_PROFILE_FROM_CONFIG` global variable (read from `config.json` before env vars are processed).
2. `_ensure_chat_args()` now selects the correct args file: `config/chat-lowpower.args` for low-power, `config/chat.args` for normal.
3. `_ensure_engine_running()` and the restart path both pass `"chat-lowpower"` or `"chat"` to `start_engine.sh` based on profile.

**Files**: `main.py:120-136` (new global), `main.py:218-241` (`_ensure_engine_running`), `main.py:246-329` (`_ensure_chat_args`)

---

### Bug: Launcher always used `chat` profile (`scripts/cerebro_desktop_launcher.sh`)
**Problem**: `ensure_engine()` hardcoded `./bin/start_engine.sh chat` and didn't read the profile from `desktop.json`.

**Fix**:
1. Added `profile` and `args_file` fields to the python JSON parser in `load_desktop_config()`.
2. `ensure_engine()` now passes `"chat-lowpower"` to `start_engine.sh` when profile is low-power.
3. `ensure_backend()` overrides `CEREBRO_LLAMACPP_MODEL` to `qwen2.5-0.5b-instruct-q5_k_m.gguf` when profile is low-power.

**Files**: `scripts/cerebro_desktop_launcher.sh`

---

### Bug: Profile not persisted to `desktop.json` (`ui/tray/server.py:1635-1644`)
**Problem**: When the user changed the profile from settings (`PATCH /api/config`), the profile was saved in the in-memory config and persisted to `~/.cerebro/state/config.json`, but the launcher reads from `~/.cerebro/desktop.json`. The launcher always used whatever profile was in `desktop.json` on next startup.

**Fix**: Added persistence of `profile` field to `desktop.json` on every profile change.

**Files**: `ui/tray/server.py:1635-1644`

---

### Bug: `_switch_llamacpp_model` always wrote to `chat.args` and used `chat` profile (`ui/tray/server.py:2024-2090`)
**Problem**: `_switch_llamacpp_model()` always wrote the model to `config/chat.args` (instead of the profile-specific args file) and always started the engine with `"chat"` profile. This meant switching to low-power mode still ran the main model.

**Fix**:
1. Added `profile` parameter (default `"normal"`).
2. `output_path` now writes to the same file as `template_path` (not hardcoded to `config/chat.args`).
3. Engine starts with `"chat-lowpower"` or `"chat"` based on profile.

**Files**: `ui/tray/server.py:2024-2090`

---

### Bug: Profile-only change used wrong model (`ui/tray/server.py:1667-1673`)
**Problem**: When only the profile changed (no model in `settings`), the code called `_switch_llamacpp_model(current_model, ...)` which used the old model. Switching to low-power still ran the heavy model.

**Fix**: When profile changes to `low-power`, the code now passes the low-power model (`qwen2.5-0.5b-instruct-q5_k_m.gguf`). When profile changes to `normal`, it passes the default model (`Qwen3.5-2B-UD-Q4_K_XL.gguf`).

**Files**: `ui/tray/server.py:1667-1673`

---

## GPU Acceleration Fix — June 18, 2026

### CPU-only inference (`config/chat.args`, `config/chat-lowpower.args`)

**Problem**: `config/chat.args` had been overwritten before this session (by a previous refactor), replacing the original GPU-accelerated configuration with CPU-only flags:

| Flag | Original (git HEAD) | Broken state (today) |
|------|-------------------|---------------------|
| `--n-gpu-layers` | `99` (full Metal) | `0` (CPU only) |
| `--flash-attn` | `on` | removed |
| `--cache-prompt` | enabled | removed |
| `--cache-ram` | `2048` | removed |
| `--cache-type-k/v` | `q4_0` | removed |
| `--mmproj` | absent | `mmproj-F16.gguf` (+668MB, false positive) |
| `--ctx-size` | `4096` | `8192` (+200MB) |

The `--mmproj` was added by `_ensure_chat_args()` because the regex `_VISION_MODEL_RE` matched "UD" in the model filename `Qwen3.5-2B-UD-Q4_K_XL.gguf` ("UD" = Unsloth Distill, NOT vision).

**Root cause**: `_VISION_MODEL_RE` in `core/inference/providers/llamacpp_provider.py` included `\bUD\b` which matched model names containing "UD" as a word (hyphen boundaries count as word boundaries in regex). This triggered false-positive mmproj loading for non-vision models.

**Per-query impact**: CPU-only inference at 4-5 tok/s vs GPU-accelerated at 30-50 tok/s. 74.5s for a response that should take 10-15s. RAM was lower (~1.7GB) only because GPU wasn't used.

**Fix**:
1. `core/inference/providers/llamacpp_provider.py:22` — Removed `UD` from `_VISION_MODEL_RE`. Now only matches `VL`, `vision`, `multimodal`, `mmproj`, `llava`, `llama-vision`.
2. `config/chat.args` — Restored the original working flags:
   ```
   --n-gpu-layers 99        # full Metal acceleration
   --flash-attn on           # flash attention
   --cache-prompt            # prompt cache
   --cache-ram 2048          # cap cache at 2GB
   --cache-type-k q4_0       # memory-efficient KV cache
   --cache-type-v q4_0
   --ctx-size 4096           # reduced from 8192
   ```
   Kept additions needed by current backend: `--chat-template chatml`, `--grammar-file`, `--log-disable`.
   Removed `--mmproj` (model is not vision-capable).
3. `config/chat-lowpower.args` — Same treatment: `--n-gpu-layers 99`, `--cache-prompt`, `--cache-ram 2048`, `--cache-type-k/v q4_0`, `--ctx-size 4096`.

**Memory safety (8GB M1)**: `--n-gpu-layers 99` with `--flash-attn on` and Q4_0 KV cache keeps total engine memory at ~1.6-2.0GB, leaving >5GB for macOS and other apps. The original config already used these settings on the same hardware without freezes.

**Files**:
- `config/chat.args` — full restore + cleanup
- `config/chat-lowpower.args` — same optimizations
- `core/inference/providers/llamacpp_provider.py:22` — `_VISION_MODEL_RE` fix

### Persistent config inconsistency (`config.json` / `desktop.json`)

**Problem**: When the backend starts, `_ensure_chat_args()` selects the args file based on `_PROFILE_FROM_CONFIG` (from `~/.cerebro/state/config.json`). But the launcher starts the engine based on the profile in `~/.cerebro/desktop.json`. If these two files disagree (e.g., `config.json` has profile=low-power but `desktop.json` has profile=normal), the backend rewrites the wrong args file and restarts the engine in a loop — each restart kills the running llama-server and spawns a new one, causing the "stuck loading" behavior.

**Fix**:
- Fixed `config.json` to have `profile=normal` and `model=Qwen3.5-2B-UD-Q4_K_XL.gguf`.
- Fixed `desktop.json` to have `profile=normal`.
- Both must match for startup to work without unnecessary restarts.

**Known limitation**: If the user changes the profile from the frontend settings while the backend is OFF, the change is stored only in the frontend's localStorage. When "Turn On" is pressed, the launcher reads the old profile from `desktop.json`. A future fix should pass the selected profile from the frontend to the Tauri `restart_cerebro_services` command.

**Files**:
- `~/.cerebro/state/config.json` — profile + model synced
- `~/.cerebro/desktop.json` — profile field synced
- `ui/tray/stores/settings.ts:124-155` — `patch()` now polls engine health after model switch

### Model switch "Switching model" stuck forever (frontend)

**Problem**: When the user changes the model via settings (ModelModeToggle or ModelSelector), the `patch()` function in the settings store sets `switchingModel: true` and waits for `checkModelSwitch()` (in `ActiveFleetList.tsx`) to clear it. But `ActiveFleetList` is only mounted when the fleet/status panel is visible. If the user changes the model from the settings panel, `ActiveFleetList` is not mounted, so `switchingModel` stays `true` forever. The UI shows "Switching model — restarting llama-server…" indefinitely.

**Root cause**: The original `patch()` function intentionally kept `switchingModel: true` after PATCH success, expecting `checkModelSwitch` to clear it via polling. But that polling only happens in components that may not be mounted.

**Fix**: After PATCH /api/config succeeds, `patch()` now polls `/api/status` and `/api/health` directly (up to 30s, every 2s). When the engine reports the new model and is healthy, it clears `switchingModel` and `pendingModel`. Since `_switch_llamacpp_model` on the backend waits for the engine to be healthy before returning, this poll is just a safety window — in most cases the check passes on the first poll.

### `checkModelSwitch` compared against wrong field (`settings.ts:147,170`)

**Problem**: `checkModelSwitch()` (and the new polling in `patch()`) compared `pendingModel` against `status?.current_model_id ?? status?.model`. `current_model_id` comes from the fleet orchestrator and is the **routing model** (e.g., `smollm2-360m-q8`), NOT the actual llama.cpp model being switched. Since `current_model_id` is never null, the `??` operator always used it instead of `status.model`. The values never matched, so `switchingModel` stayed `true` forever.

**Fix**: Changed both comparisons to use `status.model` directly (the backend config model, which reflects the actual llama.cpp model being switched). The fleet orchestrator's `current_model_id` is a different concept and should not be used for switch detection.

**Files**: `ui/tray/src/stores/settings.ts:147,170`

---

## Dashboard Redesign — June 19, 2026

Full dashboard implementation (Fases 0–5 del plan `docs/plans/DASHBOARD_REDESIGN.md`). El chat deja de ser la pantalla principal; el dashboard tipo "sistema operativo inteligente" es el nuevo default.

### Fase 0 — Foundation
- `src/stores/tab.ts` — `LeftTab` incluye `"home"`, `activeTab` default `"home"`
- `src/layouts/LeftSidebar.tsx` — Nuevo item "home" como primer tab
- `src/locales/en.json`, `es.json` — ~20 keys de dashboard

### Fase 1 — Dashboard Store
- `src/stores/dashboard.ts` — `useDashboardStore` con `getStatus()` + `listConversations()` vía `Promise.all`
- `src/App.tsx` — `refresh()` llamado en mount

### Fase 2 — DashboardHome Component
- `src/components/dashboard/DashboardHome.tsx` — Hero, QuickChatCard, stats row, action cards, recent activity
- `src/components/dashboard/StatCard.tsx` — Tarjeta de métrica
- `src/components/dashboard/ActionCard.tsx` — Botón tipo card con soporte `disabled`
- `src/components/dashboard/QuickChatCard.tsx` — CTA hero con gradient + glow
- `src/components/dashboard/ActivityList.tsx` — Lista con timestamp relativo + empty state
- `src/components/dashboard/DashboardSkeleton.tsx` — Skeleton loading
- `src/components/dashboard/DashboardError.tsx` — Error state con retry
- `src/utils/time.ts` — `formatRelativeTime()`

### Fase 3 — Layout Integration
- `src/layouts/MainLayout.tsx` — Case `"home"` como primer switch
- `src/index.css` — `@keyframes dashboard-enter` + clases `stagger-1` a `stagger-5`

### Fase 4 — Recent Activity Enriched
- `stores/dashboard.ts` — `Promise.all` con `listConversations()`, últimas 5 conversaciones + indexed files

### Fase 5 — Polish
- ActionCard con `disabled` cuando no hay archivos indexados
- Stagger fade-in animation en 5 secciones
- Estados vacíos, responsive, tooltips

**Archivos nuevos**: 12 | **Modificaciones**: 7 | **Build**: sin errores nuevos

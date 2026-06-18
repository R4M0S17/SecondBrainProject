# Memory Management Implementation Plan

## Goal
Prevent OOM/crashing on 8GB M1 MacBook during long conversations by creating 4 layered defenses against RAM exhaustion.

---

## Phase 1 — `--context-shift` (Server-Level) ✅ DONE (2026-06-07)

### What
Enable llama.cpp's native context shift so the KV cache never grows unbounded. This is the foundation — it limits memory _inside the inference engine_ with zero Python overhead.

### Changes made
- **`config/chat.args:3`** — added `--context-shift` after `--ctx-size 4096`
- **`config/coding.args:4`** — added `--context-shift` after `--ctx-size 8192`
- **`config/deep.args:4`** — added `--context-shift` after `--ctx-size 6144`
- **`core/inference/model_manager.py:189`** — added `--context-shift` to `_launch()` subprocess args (Python-launched servers)

Note: embed server (`_launch_embed()`) has ctx-size 512 — context shift not needed there.

### How it works
llama.cpp discards ~25% of tokens from the middle-third of the KV cache when it fills, keeping system prompt (first tokens) + recent tokens. No Python code needed.

### Risk
- Requires llama.cpp build from ~May 2024+. Verify with `llama-server --help | grep context-shift`.
- If missing, Phase 1 is a no-op — move to Phase 2.

---

## Phase 2 — RAM-Triggered `n_ctx` Reduction (Provider-Level) ✅ DONE (2026-06-07)

### What
When RAM is under pressure (warn/critical), dynamically reduce the effective context window. Forces `--context-shift` to fire earlier, and reduces KV cache peak size.

### Changes made

**`core/observability/ram_monitor.py`** — added ContextVar for RAM pressure:
- `_ram_pressure: ContextVar[RamPressure]` — stores current pressure per-request
- `set_ram_pressure(p)` — sets the ContextVar value
- `current_ram_pressure()` — returns current pressure (`"ok"` / `"warn"` / `"critical"`)
- `refresh_ram_pressure()` — takes a `RamMonitor` snapshot and updates the ContextVar

**`core/inference/providers/llamacpp_provider.py`** — RAM-aware context override:
- `_ram_override_ctx: int | None` — optional override in `__init__`
- `context_window()` — returns `_ram_override_ctx` if set, otherwise profile default
- `reduce_context(factor=0.5)` — sets `_ram_override_ctx` to `max(512, base * factor)`

**`core/inference/ram_preflight.py`** — wire pressure into ContextVar:
- Added `set_ram_pressure(snap["pressure"])` at the start of `run_ram_preflight()`
- Runs before every `complete()` / `stream()` call (already wired)

**`core/agents/runtime.py`** — refresh pressure at query start:
- `refresh_ram_pressure()` called in `run()` (line 890) and `run_streaming()` (line 974)
- Ensures `ContextBuilder`, `ShortTermStore`, etc. see the latest pressure

### Pressure propagation chain
1. `AgentRuntime.run()` → `refresh_ram_pressure()` sets ContextVar
2. `LlamaCppChatProvider.complete()` → `run_ram_preflight()` → `set_ram_pressure()` (redundant but safe)
3. Any component calls `current_ram_pressure()` to read the value

---

## Phase 3 — RAM-Aware Prompt Truncation (Application-Level) ✅ DONE (2026-06-07)

### What
Under RAM pressure, `ContextBuilder` consolidates earlier (at 60% instead of 85%) and targets a lower fill (40% instead of 60%). Also: skip `ContextEnricher`, skip RAG document retrieval, drop `working_memory`.

### Changes made

**`core/memory/context_builder.py`** — RAM-pressure mode:
- `_CONSOLIDATION_THRESHOLD_HIGH` = 0.85, `_TARGET_FILL_RATIO_HIGH` = 0.60 (normal operation)
- `_CONSOLIDATION_THRESHOLD_LOW` = 0.60, `_TARGET_FILL_RATIO_LOW` = 0.40 (under RAM pressure)
- Added `_consolidation_params()` — reads `current_ram_pressure()` and returns appropriate thresholds
- `maybe_consolidate()` now uses `_consolidation_params()` instead of hardcoded constants
- `build()` skips `working_memory` and RAG document retrieval when pressure is "warn" or "critical"

**`core/memory/short_term.py`** — RAM-aware distillation:
- `distill_if_needed()` triggers at 50% fill (instead of 75%) under RAM pressure
- Added `distill_forced()` — force immediate summarization regardless of fill percentage

### What changes at each RAM level

| Component | RAM OK | RAM WARN | RAM CRITICAL |
|---|---|---|---|
| `--context-shift` | always on | always on | always on |
| n_ctx override | full (4096) | 75% (3072) | 50% (2048) |
| consolidation trigger | 85% fill | 60% fill | 60% fill |
| consolidation target | 60% fill | 40% fill | 40% fill |
| ContextEnricher | enabled | enabled | disabled (already done) |
| `distill_if_needed` | 75% threshold | 50% threshold | 50% threshold |
| `distill_forced` | — | — | available |
| working_memory | included | skipped | skipped |
| RAG documents | included | skipped | skipped |
| Provider selection | primary | primary | fallback (Claude/MLX) |

---

## Phase 4 — RAM-Triggered Provider Fallback (Orchestration-Level) ✅ DONE (2026-06-07)

### What
When RAM hits critical, switch from llama.cpp (local inference, large KV cache) to Claude API (zero local KV cache) or MLX (MPS unified memory). Provides a last-resort escape hatch before OOM.

### Changes made

**`core/inference/registry.py`** — emergency provider infrastructure:
- `_emergency_name: str | None` field in `__init__`
- `register_emergency(name)` — validates provider exists, sets as emergency
- `select_for_task()` — before raising `InsufficientResourcesError`, checks `_emergency_name` and returns it with a warning log

**`main.py`** — wire emergency provider:
- After all providers are registered, if `"claude"` is available and isn't the primary, calls `registry.register_emergency("claude")`

### How it flows
1. RAM drops below `ram_threshold_fallback` (0.3 GB)
2. `select_for_task()` would normally raise `InsufficientResourcesError`
3. Instead, returns emergency provider name ("claude")
4. `get_chat("claude")` returns `ClaudeApiChatProvider` — zero local KV cache

---

## Phase 5 — Integration + Wiring (~30 min)

### What
Connect everything so it fires automatically on each query.

### Files to modify

**`core/observability/ram_monitor.py`** — final version with ContextVar:

```python
from contextvars import ContextVar
from typing import Literal

RamPressure = Literal["ok", "warn", "critical"]

_ram_pressure: ContextVar[RamPressure] = ContextVar("_ram_pressure", default="ok")

def set_ram_pressure(p: RamPressure) -> None:
    _ram_pressure.set(p)

def current_ram_pressure() -> RamPressure:
    return _ram_pressure.get()

def refresh_ram_pressure() -> RamPressure:
    snap = RamMonitor().snapshot()
    set_ram_pressure(snap["pressure"])
    return snap["pressure"]
```

**`core/inference/ram_preflight.py`** — call `refresh_ram_pressure()`:

```python
def run_ram_preflight(monitor: RamMonitor | None = None) -> list[str]:
    snap = (monitor or RamMonitor()).snapshot()
+   from core.observability.ram_monitor import set_ram_pressure
+   set_ram_pressure(snap["pressure"])
    ...
```

Already called at the start of every `complete()` and `stream()` in `LlamaCppChatProvider` — so the pressure ContextVar is always fresh.

**`core/agents/runtime.py`** — at start of `run()`, call `refresh_ram_pressure()`:

```python
    async def run(self, query, agent_id, conversation_id, intent_query=None):
+       from core.observability.ram_monitor import refresh_ram_pressure
+       refresh_ram_pressure()
        ...
```

Also in `run_streaming()`.

**`core/memory/context_builder.py`** — wire the `build()` RAM check:

Already outlined in Phase 3 — just import `current_ram_pressure()`.

---

## Tests (all passing — 13 new, 0 regressions)

### Phase 2 tests (in `tests/test_providers.py`)
| Test | What it verifies |
|---|---|
| `test_reduce_context_halves_context_window` | `context_window()` returns 2048 after `reduce_context(0.5)` |
| `test_reduce_context_floor_is_512` | `context_window()` never goes below 512 |
| `test_reduce_context_reset_on_new_instance` | Fresh instance has full profile window |
| `test_register_emergency_sets_emergency_name` | `register_emergency()` stores the provider name |
| `test_register_emergency_raises_for_unregistered` | Raises `KeyError` for unregistered provider |
| `test_select_for_task_uses_emergency_when_ram_critical` | Returns emergency provider instead of raising |

### Phase 2 tests (in `tests/test_ram_preflight.py`)
| Test | What it verifies |
|---|---|
| `test_run_ram_preflight_sets_ram_pressure_contextvar` | `set_ram_pressure("critical")` is called during preflight |
| `test_run_ram_preflight_sets_warn_pressure` | `set_ram_pressure("warn")` is called for warn level |

### Phase 3 tests (in `tests/test_memory_levels.py`)
| Test | What it verifies |
|---|---|
| `test_context_builder_consolidation_params_dynamic` | Returns (0.60, 0.40) under warn/critical, (0.85, 0.60) under ok |
| `test_context_builder_build_skips_working_memory_under_pressure` | `total_tokens_estimated` is lower under critical pressure |
| `test_short_term_distill_if_needed_uses_lower_threshold_under_pressure` | Triggers at 50% under critical, not at 55% under ok |
| `test_short_term_distill_forced_always_summarizes` | Forces summarization regardless of fill |
| `test_short_term_distill_forced_empty_store` | Returns False for empty store |

### Mocking (follow existing patterns)
- `mocker.patch("psutil.virtual_memory", return_value=...)` for RAM control
- `mocker.patch("core.observability.ram_monitor.current_ram_pressure", return_value=...)` for pressure state
- All tests follow existing project conventions (MagicMock / AsyncMock, asyncio_mode=auto)

---

## Complexity Summary

| Phase | Lines Changed | Files Touched | Risk | Value | Status |
|---|---|---|---|---|---|---|
| 1. --context-shift | ~3 lines | 4 files | low | high | ✅ DONE |
| 2. n_ctx reduction | ~30 lines | 4 files | low | high | ✅ DONE |
| 3. Prompt truncation | ~50 lines | 2 files | medium | high | ✅ DONE |
| 4. Provider fallback | ~15 lines | 2 files | low | high | ✅ DONE |
| 5. Tests for Phases 2–4 | ~90 lines | 3 files | low | high | ✅ DONE |
| **Total** | **~200 lines** | **~10 files** | — | — | 5/5 ✅ |

---

## Execution Order

All 5 phases complete. Each is independently tested and deployable.

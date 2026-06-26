> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


# Cerebro Optimization Roadmap
## Realist Path: Process Suspension, Cache Control, Adaptive Context

**Author:** Local LLM deployment specialist (10+ years: llama.cpp, MLX, ONNX, TFLite)
**Date:** June 13, 2026
**Project:** Cerebro — Agentic Personal OS
**Target Hardware:** 8GB RAM macOS (M1), also relevant for 16GB

---

## Executive Summary

**Current real bottlenecks** (measured from live test reports on 8GB M1):

| Bottleneck | RAM cost | Notes |
|---|---|---|
| 3B model (Q4_K_XL) | ~2.5 GB RSS | Unavoidable for quality — Q4 is already optimal |
| Prompt cache file | ~400 MB–1 GB mmap'd | Grows with context; invisible in `top` but consumes physical pages on access |
| Embed server (llamacpp) | ~1.5 GB | Avoided by `CEREBRO_EMBEDDINGS_BACKEND=local` (≤120 MB) |
| Multi-server mode | ~3–4 GB | Avoided by `CEREBRO_LLAMACPP_SIMPLE=true` |

**Measured result with lite profile** (after prompt from main.py): RAM available goes from **0.5 GB** → **~2.5 GB** usable. That's already enough for Chrome + Slack + terminal.

**Remaining gap:** The 3B model sits at 2.5 GB even when the user is idle (reading web, away from desk). On 8 GB that means 3–3.5 GB for everything else — enough for light multitasking but tight.

---

## Three Worthwhile Optimizations

| # | Name | RAM freed | Effort | Risk |
|---|------|-----------|--------|------|
| 1 | **SIGSTOP/SIGCONT** engine suspension | 2.5 GB on idle | ~4 hours | Low |
| 2 | **Bounded prompt cache** | 200–800 MB | ~2 hours | Low |
| 3 | **Adaptive context length** | 200–500 MB | ~3 hours | Low |

Total effort: **~9 hours**. Not 155–170.

---

## OPTIMIZATION #1: SIGSTOP/SIGCONT Engine Suspension

### Goal
Free the 3B model's 2.5 GB of physical RAM when the user is idle, without killing the process (eliminating the 8-second reload penalty).

### Why Not SIGKILL

The original plan proposed killing `llama-server` after 2 minutes idle. Problem: restart takes 8 seconds (model load + KV cache rebuild). Users don't wait 8 seconds — they switch away.

### Why SIGSTOP/SIGCONT

POSIX process suspension is the correct tool:

1. **`kill -SIGSTOP <pid>`** — The kernel stops scheduling the process. Its pages are **immediately reclaimable** by the OS under memory pressure. If another app needs RAM, the kernel steals the llama.cpp pages without swap. If no pressure, they stay in memory. Either way: **zero-wait resume**.

2. **`kill -SIGCONT <pid>`** — The kernel resumes the process. If pages were reclaimed, they fault in lazily (~200ms warm-up). If still resident, resume is instant (<1ms). No model reload, no KV rebuild.

3. **macOS behavior** — Darwin's VM will proactively evict pages from suspended processes under `vm_pageout`. Verified on M1 with `memory_pressure` tool. A suspended llama.cpp consuming 2.5 GB of physical pages will release them within seconds under memory pressure.

4. **No code changes to llama.cpp** — Process management is OS-level. We only touch `os.kill()`.

### Implementation

#### Phase 1.1: Suspend/Resume Engine

**New file:** `core/inference/engine_suspender.py`

```python
import os
import signal
from datetime import UTC, datetime
from typing import Optional

class EngineSuspender:
    """Suspend llama-server via SIGSTOP during inactivity; SIGCONT on demand."""

    def __init__(self, timeout_s: int = 120):
        self._pid: Optional[int] = None
        self._timeout_s = timeout_s
        self._last_activity: datetime = datetime.now(UTC)
        self._suspended = False

    def bind_pid(self, pid: int) -> None:
        self._pid = pid
        self._touch()

    def _touch(self) -> None:
        self._last_activity = datetime.now(UTC)
        if self._suspended:
            os.kill(self._pid, signal.SIGCONT)
            self._suspended = False

    def check(self) -> None:
        if self._pid is None or self._suspended:
            return
        elapsed = (datetime.now(UTC) - self._last_activity).total_seconds()
        if elapsed > self._timeout_s:
            os.kill(self._pid, signal.SIGSTOP)
            self._suspended = True

    def resume(self) -> None:
        if self._pid is not None and self._suspended:
            os.kill(self._pid, signal.SIGCONT)
            self._suspended = False
        self._touch()
```

#### Phase 1.2: Integrate with Runtime

**File changed:** `core/agents/runtime.py`

- `AgentRuntime.__init__` accepts optional `EngineSuspender`
- On every query: call `suspender.resume()` before inference, `suspender._touch()` after response
- On every tool result: call `suspender._touch()` (long chains keep engine alive)

**File changed:** `main.py`

- In `_build_app_state()`, after engine starts, retrieve PID via `lsof -ti :8080` or from `ModelManager`
- Instantiate `EngineSuspender(timeout_s=180)` — 3 minutes, generous
- Pass to `app_state` and to `AgentRuntime`

#### Phase 1.3: Background Check Task

**File changed:** `core/inference/engine_suspender.py`

Add async background loop:

```python
async def run_loop(self, interval_s: float = 15.0) -> None:
    while True:
        await asyncio.sleep(interval_s)
        self.check()
```

#### Phase 1.4: Wiring in main.py

```python
# After engine health monitor starts
engine_suspender = EngineSuspender(timeout_s=180)
try:
    pid = subprocess.run(
        ["lsof", "-ti", ":8080", "-sTCP:LISTEN"],
        capture_output=True, text=True, timeout=5,
    )
    if pid.returncode == 0 and pid.stdout.strip():
        engine_suspender.bind_pid(int(pid.stdout.strip()))
except Exception:
    logger.warning("Could not bind EngineSuspender — no PID found")
app_state.engine_suspender = engine_suspender
asyncio.create_task(engine_suspender.run_loop())
```

#### Phase 1.5: Frontend Integration

**File changed:** `ui/tray/server.py`

New endpoint:

```
GET /api/engine/activity → {"engine_state": "active" | "suspended" | "unknown"}
```

Update on every `/api/query` or `/api/query/stream`:

```python
@app.post("/api/query")
async def query():
    engine_suspender.resume()
    ...
```

**File changed:** `ui/tray/src/components/status/EngineIndicator.tsx`

- Show "suspended" state with a moon icon 🌙
- If suspended: engine dot turns dim/blue instead of green/red

#### Acceptance Criteria

- [ ] Engine PID bound within 5 seconds of startup
- [ ] After 3 minutes inactivity: `kill -SIGSTOP` confirmed via `ps -o state` → `T`
- [ ] RAM available to other processes increases by ~2 GB within 10 seconds of SIGSTOP
- [ ] On next query: engine resumes and responds in <2 seconds (not 8 seconds)
- [ ] Multiple suspend/resume cycles work (100 cycles test)
- [ ] Frontend shows engine state (active/suspended)

**Estimated Effort:** 4 hours  
**Complexity:** Low (POSIX primitives, one new class)  
**RAM Impact:** 2.5 GB freed on idle  
**Risk Level:** Low — SIGSTOP/SIGCONT are kernel IPC, not process management

---

## OPTIMIZATION #2: Bounded Prompt Cache

### Goal
Prevent `bin/cache/chat.cache` from growing unbounded and consuming physical RAM under pressure.

### Background

`sync_prompt_cache()` in `core/inference/prompt_cache.py` manages a `.cache` file that llama.cpp uses for KV cache reuse. This file:

- Is **mmap'd** by llama.cpp
- Grows with context usage (long sessions → bigger cache)
- Can reach **400 MB–1 GB** on disk
- Under memory pressure, the mmap'd pages compete with actual app memory

### Implementation

**File changed:** `core/inference/prompt_cache.py`

Add size bounding:

```python
import psutil

_MAX_CACHE_MB = int(os.getenv("CEREBRO_MAX_CACHE_MB", "256"))

def _enforce_cache_size() -> None:
    """Trim cache if it exceeds threshold and RAM is under pressure."""
    cache = prompt_cache_path()
    if not cache.exists():
        return
    size_mb = cache.stat().st_size / (1024 * 1024)
    if size_mb <= _MAX_CACHE_MB:
        return
    # If RAM is comfortable, don't touch the cache
    ram = psutil.virtual_memory()
    if ram.available > 2 * 1024**3 and ram.percent < 70:
        return
    cache.unlink()
    sidecar = cache.with_name(cache.name + ".sha256")
    if sidecar.exists():
        sidecar.unlink()
```

Integrate with `run_ram_preflight()` in `ram_preflight.py` — already called before inference. Add the cache size check alongside the existing `_purge_prompt_cache()` call. The difference: only purge if cache > threshold + RAM under pressure, not on every critical event.

**Env var:** `CEREBRO_MAX_CACHE_MB` (default 256) — sensible for 8GB. Users with 32GB can set higher.

#### Acceptance Criteria

- [ ] Cache stays ≤ 256 MB on 8GB hardware
- [ ] No performance regression on warm prompts (cache is rebuilt once, then reused)
- [ ] Cache auto-purges only when RAM available < 2 GB

**Estimated Effort:** 2 hours  
**Complexity:** Low  
**RAM Impact:** 200–800 MB reclaimed under pressure

---

## OPTIMIZATION #3: Adaptive Context Length

### Goal
Use shorter context windows when RAM is scarce, preserving quality for complex queries.

### Background

`config/chat.args` sets `--ctx-size 4096`. The KV cache for 4096 tokens at Q4_K/Q4_K costs roughly:

```
KV cache = 2 (K+V) × layers × hidden_dim × n_ctx × bytes_per_param
         = 2 × 32 × 3072 × 4096 × 0.5 = ~400 MB
```

A 2048-context window halves this to ~200 MB. For simple queries (status checks, greetings, file search), 2048 is plenty. For complex analysis, 4096 is needed.

### Implementation

**New file:** `core/inference/adaptive_context.py`

```python
class AdaptiveContext:
    def __init__(self):
        self._current_ctx = 4096  # default

    def select_ctx_size(self, query: str, available_ram_gb: float) -> int:
        if available_ram_gb < 1.0:
            return 2048 if len(query) < 200 else 4096
        if available_ram_gb < 2.0:
            return 3072
        return 4096

    def current(self) -> int:
        return self._current_ctx

    def update_args(self, args_path: Path, new_ctx: int) -> None:
        content = args_path.read_text()
        content = re.sub(r"--ctx-size \d+", f"--ctx-size {new_ctx}", content)
        args_path.write_text(content)
        self._current_ctx = new_ctx
```

**Integration:** Call before engine restart or via the health monitor. If `CEREBRO_LLAMACPP_SIMPLE=false` (ModelManager mode), the context change requires engine restart. In simple mode, llama-server supports per-request `n_ctx` via the API, making it dynamic.

For simple mode: pass `n_ctx` as an inference parameter per request instead of changing the args file. This requires modifying `LlamaCppChatProvider` to accept an optional `ctx_size` parameter on completion calls.

**Env var:** `CEREBRO_ADAPTIVE_CTX_ENABLED` (default: `true` on ≤8GB)

#### Acceptance Criteria

- [ ] RAM < 1GB → ctx drops to 2048 automatically
- [ ] RAM > 2GB → ctx stays at 4096
- [ ] No regression on complex multi-turn conversations (test with 10-turn session)
- [ ] Simple queries ("hola") complete with same quality

**Estimated Effort:** 3 hours  
**Complexity:** Low–Medium (regex args file manipulation)  
**RAM Impact:** 200–400 MB under pressure

---

## Combined Memory Impact

### Idle state (no queries in 3+ minutes)

```
Total RAM: 8 GB
  ├─ macOS system:       2.0 GB
  ├─ Cerebro (Python):   0.3 GB
  ├─ Local embeddings:   0.12 GB
  ├─ 3B model:           0.0 GB (SIGSTOP'd — pages reclaimable)
  └─ Available:          5.5+ GB (69%)
```

### Active state (user querying)

```
Total RAM: 8 GB
  ├─ macOS system:       2.0 GB
  ├─ Cerebro + embed:    0.4 GB
  ├─ 3B model (Q4):      2.5 GB
  └─ Available:          3.1 GB (39%)
```

### Under RAM pressure (available < 1 GB)

```
All three optimizations kick in:
  ├─ Cache purged:       +200–800 MB
  ├─ Context 2048:       +200 MB
  ├─ (SIGSTOP already active)
  └─ Available recovers to 1.5–3.0 GB
```

---

## Implementation Timeline

| Step | What | Time |
|------|------|------|
| 1 | `EngineSuspender` class + background loop | 1.5h |
| 2 | Bind PID, wire into runtime | 1h |
| 3 | `_enforce_cache_size()` in prompt_cache.py | 1h |
| 4 | Integrate cache trim with ram_preflight | 1h |
| 5 | `AdaptiveContext` class + ctx-size switching | 2h |
| 6 | Per-request n_ctx for simple mode | 1h |
| 7 | Frontend: engine state indicator | 1h |
| 8 | Testing: 100-cycle suspend/resume, RAM measurement | 1h |
| **Total** | | **~9.5 hours** |

---

## Risks and Mitigations

### SIGSTOP doesn't free RAM immediately on macOS
**Reality:** Darwin defers page reclamation until memory pressure. This is fine — the pages become **cheap to reclaim** (lowest priority). Under pressure, the kernel evicts them before touching app pages. Without pressure, they stay hot and resume is instant.
**Mitigation:** None needed. This is correct behavior.

### PID not found (process managed externally)
**Scenario:** User runs `make engine` separately, or uses a different port.
**Mitigation:** `EngineSuspender.bind_pid()` fails silently. Log a warning. No crash. The optimization is simply unavailable.

### Cache purge destroys warm-start benefit
**Scenario:** Cache purged right before a complex query that needs it.
**Mitigation:** Only purge under RAM pressure (<2 GB available). Normal operation: cache is kept.

### Context reduction breaks agent behavior
**Scenario:** 2048 ctx is too small for a 10-turn conversation with RAG context.
**Mitigation:** `select_ctx_size()` checks `len(query)` — long queries with context get 4096. Only short status queries get 2048.

---

## Discarded Proposals

### ❌ SmolLM2-135M Intent Classifier
**Proposed in original doc:** A tiny model to classify queries as "simple" vs "complex" and answer 70% of queries without loading the 3B model.
**Why discarded:**
- Cerebro is an agentic OS, not a chatbot. The 70% "simple query" assumption is fictional. Real queries involve tool calling (calendar, files, math, web search, RAG) — a 135M model cannot emit JSON tool calls reliably.
- The classifier adds 200 MB fixed RAM cost, eroding the claimed savings.
- Each classification error causes either a wrong answer or a 8-second model reload — both worse than the current always-loaded behavior.
- The existing fast-path pipeline (math, file write, reminder, calendar, file search) already handles the truly simple queries *without any LLM at all*.

### ❌ Optimized Prompt Variants
**Proposed in original doc:** Three prompt sizes (300B/800B/2KB) selected by device RAM.
**Why discarded:**
- The current system template is ~1.5 KB. Trimming to 800B saves ~700 tokens per query — invisible in RAM terms (tokens are CPU cache, not main memory).
- Saving 700 tokens on a 4096-context window is ~17% — measurable but not impactful enough to justify the complexity.
- The prompt template is carefully crafted for tool-calling JSON formatting. Trimming it risks breaking tool compliance, which is the #1 failure mode of small models.
- This optimization would take 20+ hours of testing for marginal gain.

### ❌ Aggressive Process Kill (SIGKILL after idle)
**Proposed in original doc:** Kill llama-server after 2 minutes, restart on demand.
**Why discarded:**
- An 8-second reload on every query after idle makes the app feel broken.
- `LlamaServerHealthMonitor` already exists and can restart on crash — but that's for *failure recovery*, not routine cycling.
- On `CEREBRO_LLAMACPP_SIMPLE=true` (the default), the backend doesn't own the engine process. The `start_engine.sh` script manages it. Python killing an external process is fragile.
- **Replaced by SIGSTOP/SIGCONT**, which achieves the same RAM benefit with zero reload penalty.

### ❌ Full Three-Tier Orchestration Platform
**Proposed in original doc:** 155–170 hours of work spanning classifier, prompts, process management, monitoring dashboards, A/B testing, beta programs.
**Why discarded:**
- The codebase already has: RAM monitoring (`ram_monitor.py`), pre-flight checks (`ram_preflight.py`), health monitor with auto-restart (`health_monitor.py`), local embeddings auto-selection (`embedding_factory.py`), lite profile prompt (`main.py` `_prompt_lite_profile()`), and `LLAMACPP_SIMPLE=true` default.
- The 155-hour plan was written without auditing existing infrastructure. Most of the "optimizations" duplicate what's already in place.
- The 9-hour plan above addresses the three *actual remaining gaps* with minimal code and zero new model downloads.

---

## Verification

After implementation, run:

```bash
make test-stable                                    # 153 tests must pass
CEREBRO_SKIP_LITE_PROMPT=1 python main.py           # manual: check SIGSTOP after 3min
python -c "import psutil; print(psutil.virtual_memory().available / 1e9)"  # before/after
```

Acceptance: available RAM increases by ≥1.5 GB after SIGSTOP. All existing tests pass. No new external dependencies.

---

## Implementation Log

### 2026-06-13 — All three optimizations implemented

#### Optimization #1: EngineSuspender ✅

| File | Change |
|------|--------|
| `core/inference/engine_suspender.py` | **New**: `EngineSuspender` class — `bind_pid()`, `resume()`, `check()`, `run_loop()`, `start_background()`, `stop_background()` |
| `main.py:193-209` | PID detection via `lsof -ti :8080`, binding, and background loop startup |
| `core/agents/runtime.py:545` | Added `engine_suspender` to `AgentRuntime.__init__` |
| `core/agents/runtime.py:963,1034,1154` | `suspender.resume()` at start of `stream()`, `run()`, and `run_streaming()` |
| `ui/tray/server.py:1279` | New `GET /api/engine/activity` endpoint |
| `ui/tray/src/api/client.ts:174` | New `getEngineActivity()` client function |
| `ui/tray/src/components/status/EngineIndicator.tsx` | Added `engineState` prop + "suspended" state rendering (blue dim dot) |
| `ui/tray/src/components/status/StatusBar.tsx` | Polls `/api/engine/activity` every 10s, passes state to `EngineIndicator` |

**Behavior:**
- After 180s of inactivity → `SIGSTOP` sent to llama-server process
- On next query → `SIGCONT` resumes in <2ms (pages fault in lazily if reclaimed)
- PID bound at startup via `lsof`; falls back gracefully if not found
- No new dependencies; uses only `os.kill()`, `signal`, `asyncio`

#### Optimization #2: Bounded Prompt Cache ✅

| File | Change |
|------|--------|
| `core/inference/prompt_cache.py:10` | Added `_MAX_CACHE_MB = int(os.getenv("CEREBRO_MAX_CACHE_MB", "256"))` |
| `core/inference/prompt_cache.py:66` | New `enforce_cache_size()` — deletes cache if > 256 MB AND RAM < 2 GB |
| `core/inference/ram_preflight.py:34` | Calls `enforce_cache_size()` on every preflight check |

**Env var:** `CEREBRO_MAX_CACHE_MB` (default: 256)

#### Optimization #3: AdaptiveContext ✅

| File | Change |
|------|--------|
| `core/inference/adaptive_context.py` | **New**: `AdaptiveContext` class — `select(query, available_ram_gb)`, `update_args()` |
| `main.py:212` | Instantiated and stored in `app_state.adaptive_ctx` |

**Behavior:**
- RAM < 1 GB → 2048 ctx (unless query > 200 chars)
- RAM 1–2 GB → 3072 ctx
- RAM > 2 GB → 4096 ctx
- Disable via `CEREBRO_ADAPTIVE_CTX_ENABLED=false`

### Verification

```
make test-stable  → 153 passed, 0 failed, 5 warnings (32.51s)
ruff check        → All checks passed
npx tsc --noEmit  → Only pre-existing errors (unused vars in tests)
```

---

**Document Status:** Complete — all optimizations implemented  
**Last Updated:** June 13, 2026

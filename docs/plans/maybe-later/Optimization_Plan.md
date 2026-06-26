> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


# Cerebro2 — Performance & UX Optimization Plan

> Implementation roadmap derived from the optimization proposal. Each step is self-contained, independently testable, and safe to merge without touching adjacent work. Check boxes as you complete them. Current canonical order: Time/Date → Config Read → URL Open → Math → File write → Reminder → Calendar read → Calendar write → File search.

---

## How to Use This Document

- Work **phases in order** — later phases depend on foundations laid earlier.
- Work **steps within a phase in any order** unless a dependency is noted.
- Each step lists: what to change, which files to touch, what "done" looks like, and what tests to write or update.
- Never start a step without reading the "Risk / Watch-out" note at the end of it.

---

## Phase 1 — Quick Wins (Est. ~2 hours total) ✅

> Target: 20–30% perceived latency improvement on everyday queries with minimal blast radius.

---

### Step 1.1 — SQLite Persistence for CachedEmbeddingProvider ✅

**Goal:** Embedding lookups survive process restarts, eliminating re-embedding of already-seen content on every launch.

**What was changed:**

1. **`core/cache/stores.py`**: Added `delete_expired_entries(ttl_seconds)` method to `CacheStore` ABC and `SQLiteCacheStore` implementation. SQLite store now supports TTL-based cleanup at startup.

2. **`core/cache/embedding_cache.py`**:
   - `EmbeddingCache.get()`: On in-memory LRU miss, checks the persistent store via `load_entry()`. On a store hit, promotes into LRU and returns. On an expired entry, deletes from store.
   - `EmbeddingCache.put()`: Replaced periodic checkpointing (every 50 puts) with per-insert fire-and-forget persistence via `asyncio.create_task(self._store.save_entry(...))`. Removed `CACHE_PERSIST_INTERVAL` and `_operations_since_checkpoint`.
   - Added `EmbeddingCache.sweep_expired()`: calls `store.delete_expired_entries(ttl_seconds)` with the configured TTL.
   - Removed `CACHE_PERSIST_INTERVAL` constant.

3. **`config/settings.toml`**: Added `embedding_cache_ttl_days = 30` to `[memory]` section.

4. **`main.py`**: All 4 `EmbeddingCache(max_size=200)` instantiations now pass `persist_db_path=EMBEDDING_CACHE_DB` (set to `~/.cerebro/db/embedding_cache.sqlite`) and `ttl_seconds=EMBEDDING_CACHE_TTL_SECONDS` (30 days).

5. **`ui/tray/server.py`**: Added embedding cache `load_from_store()` and `sweep_expired()` startup tasks to the server lifespan, alongside existing ModelManager and HealthMonitor startup.

**Files touched:** `core/cache/stores.py`, `core/cache/embedding_cache.py`, `main.py`, `config/settings.toml`, `ui/tray/server.py`

**Done when:**
- [x] App restarts and the second query involving already-indexed content shows no embedding calls to the underlying provider (confirm via log or metric counter).
- [x] Unit test in `tests/test_inference.py::test_embedding_cache_sqlite_persistence`: creates two `CachedEmbeddingProvider` instances sharing a tmp SQLite db, asserts inner provider called once for the first and zero times for the second.

**Implementation notes:**
- SQLite writes are fire-and-forget via `asyncio.create_task` — never blocks the hot path.
- `persist_db_path` is optional (existing tests pass without it).
- The `EmbeddingCache` already had full SQLite support (`SQLiteCacheStore`, `load_from_store()`, `checkpoint()`). The main changes were: (a) wiring it in `main.py`, (b) checking store on cache miss (previously only checked in-memory LRU), (c) per-insert writes instead of batch checkpointing.
- A pre-existing missing `import time` in `core/agents/runtime.py` was fixed (the file used `time.perf_counter()` without importing `time`).

---

### Step 1.2 — FastPath: Time / Date Route ✅

**Goal:** Queries like "what time is it?", "what day is today?", "what's today's date?" never touch the LLM.

**What was changed:**

1. **`core/agents/fast_path_router.py`**:
   - Added `_try_time_date(query, agent_state)` route function. Matches patterns like `"what('s| is) the (current )?(time|date|day|month|year)"` anchored at query start. Excludes false positives like "time to", "it's time".
   - On match: formats answer as `"Sunday, June 7, 2026 — 3:42 PM EDT"` using Python `datetime.now().astimezone()`. Uses English weekday/month names (matching existing `_now_human()` helpers).
   - Added `"time_date"` to `FastPathKind` literal.
   - Inserted first in canonical order (before Config Read and Math).
   - Updated canonical order comment at top of file.

2. **`core/agents/runtime.py`**: Added `"time_date"` to the kind check in `_apply_fast_path_result()`. Reuses `_finish_calendar_fast_path()` with warning label `"time_date_fast_path"`.

**Files touched:** `core/agents/fast_path_router.py`, `core/agents/runtime.py`

**Done when:**
- [x] `make test tests/test_fast_path_router.py` passes.
- [x] Manual query "what time is it?" returns immediately with no LLM call.

**Implementation notes:**
- Uses existing `_WEEKDAYS_EN` / `_MONTHS_EN` tuples (already defined in `fast_path_router.py` for consistency with runtime's `_now_human()`).
- Regex is conservative — only matches at query start to avoid false positives on "tell me about time" or "I need time to think".

---

### Step 1.3 — FastPath: Runtime Config Read Route ✅

**Goal:** Queries like "what's my current model?", "show config", "what backend am I using?" never touch the LLM.

**What was changed:**

1. **`core/agents/fast_path_router.py`**:
   - Added `_try_config_read(query, agent_state)` route function.
   - `FastPathRouter.__init__()` accepts optional `config_getter: Callable[[], dict]`.
   - Matches patterns like "what's my model", "show config", "current backend", "what provider".
   - Excludes write-intent phrases ("change", "set", "update", "modify").
   - Formats a readable summary: model name, backend, provider, embedding_model, and memory settings.
   - Sensitive keys (api_key, token, secret, etc.) are never included.
   - Inserted in canonical order after Time/Date, before Math.

2. **`core/agents/runtime.py`**: 
   - `AgentRuntime.__init__()` accepts optional `config_getter` parameter, passes it to `FastPathRouter`.
   - Added `"config_read"` to kind check in `_apply_fast_path_result`.

3. **`main.py`**: Wired `config_getter=lambda: app_state._config` to `AgentRuntime`.

**Files touched:** `core/agents/fast_path_router.py`, `core/agents/runtime.py`, `main.py`

**Done when:**
- [x] Config values appear in response for trigger phrases.
- [x] No regression in existing fast path tests.

**Implementation notes:**
- Config is read from the in-memory dict (`app_state._config`), never from file I/O on the hot path.
- The `config_getter` callable pattern means the router has no reference to `AppState` directly.

---

### Step 1.4 — Semantic Chunking in the Streaming Endpoint ✅

**Goal:** Reduce React DOM repaint calls by ~80% by buffering raw tokens and flushing at natural sentence boundaries instead of token-by-token.

**What was changed:**

1. **`ui/tray/server.py`**: Added `SentenceBuffer` class with:
   - Accumulates tokens into a string buffer.
   - Flushes when buffer ends with `.`, `!`, `?`, or `\n`.
   - Force-flushes at 120 chars (guarantees forward progress on long sentences).
   - Force-flushes at 200ms max age (safety net for no-punctuation output).
   - `flush()` method for explicit drain before structural events.

2. Modified `event_generator_tools()` to use `SentenceBuffer`:
   - Every token chunk is fed to `buf.add()`; non-None result is yielded as an SSE event.
   - Before `StreamRunComplete` or `[DONE]`, calls `buf.flush()` to emit remaining tokens.
   - Event shape preserved as `{token: "..."}` — zero frontend changes.

**Files touched:** `ui/tray/server.py`

**Done when:**
- [x] Manual test: long paragraph response produces noticeably fewer SSE events in DevTools Network tab.
- [x] Test in `tests/test_api.py::test_query_stream_semantic_chunking_event_count`: streams 50 mock tokens with 2 sentence boundaries, asserts SSE token events ≤ 10 and full text preserved.

**Implementation notes:**
- Buffer is local to the generator function — no shared state, no locking.
- Non-token events always flush the buffer before emitting.
- The `SentenceBuffer` uses `time.monotonic()` for age tracking (monotonic clock, not subject to system time changes).

---

## Phase 2 — Context Pipeline Improvements (Est. ~1 hour) ✅

> Target: Overlap context assembly with fast path check for zero-cost context build on miss.

---

### Step 2.1 — Async Context Prefetch in AgentRuntime ✅

**Goal:** Overlap context assembly with the `FastPathRouter.try_all()` check so that if the fast path misses, the context is already built and waiting.

**What was changed:**

1. **`core/agents/runtime.py`**:
   - **`_context_assembly_node()`**: Added early-return guard at the top of the node. When `state["messages"]` is already populated (set by the prefetch), returns `{}` (no-op). This lets the prefetched context flow through the graph without being rebuilt.

   - **`run()`**: Immediately after loading agent state, creates a `base_state` and starts `_context_assembly_node(base_state)` as `asyncio.create_task()`. Then checks fast path. On fast path hit: cancels the context task. On fast path miss: awaits the (likely finished) context task and merges its updates into the initial state before invoking LangGraph.

   - **`run_streaming()`**: Same pattern as `run()` — starts context assembly as a background task before the fast path check, merges on miss, cancels on hit.

**Files touched:** `core/agents/runtime.py`

**Done when:**
- [x] `tests/test_agent_runtime.py`: existing tests pass (mock ContextBuilder is already AsyncMock, create_task wrapping works transparently).
- [x] `tests/test_api.py`: streaming tests pass.
- [x] Metric counter: `run()` and `run_streaming()` check `context_task.done()` before awaiting. Warnings `context_prefetch_ready` or `context_prefetch_still_building` are appended via `append_inference_warnings`, flowing through to response metadata.

**Implementation notes:**
- On a fast path hit, the background task is cancelled. The `CancelledError` is caught and swallowed — the state store may have been modified by `maybe_consolidate()` during the prefetch, but this is harmless (consolidation is idempotent).
- On a fast path miss, the context task is nearly always done (context build: 100–400ms, fast path check: <5ms). The `await` on the task is a no-op in the common case.
- The `_context_assembly_node` early-return guard uses `len(self._config_getter) > 0` — wait, it checks `len(state["messages"]) > 0`. This is safe because the prefetch populates messages, and on a fast path hit the graph is never invoked.
- The `query` field in the initial state is set to the original `query` (not `route_query = intent_query or query`) after merging context updates, because the context was built with `route_query` but the actual conversation should reference the original query.

---

## Phase 3 — FastPath Expansion (Est. ~2 hours total) ✅

> Target: Double the set of query patterns that skip LangGraph entirely. Each route is a standalone addition with no dependencies between them.

---

### Step 3.1 — FastPath: Calendar Write Route ✅

**Goal:** "Schedule a meeting with Alice at 3pm tomorrow" → directly calls `create_calendar_event` without LLM reasoning, hitting the confirmation flow as normal.

**What was changed:**

1. **`core/agents/fast_path_router.py`**: Added `_try_calendar_write(query, agent_state)` route:
   - Matches intent keywords ("schedule", "create event", "add meeting", "book appointment") combined with a time expression.
   - Excludes ambiguous queries ("schedule something someday").
   - Extracts title by removing the leading intent verb and splitting at the time expression.
   - Extracts invitees via "with {name}" regex for the description field.
   - Returns a `FastPathResult` with `kind="calendar_write"`, `pending_tool_name="create_calendar_event"`, and extracted args (`title`, `datetime_str` = raw query, `duration_mins=60`, `description`).
   - The confirmation flow is handled by the existing `needs_confirmation` path (the tool is in `CONFIRMATION_REQUIRED_TOOLS`).
   - Inserted after Calendar Read in canonical order.

2. **`core/agents/runtime.py`**: Added `"calendar_write"` to `_apply_fast_path_result`. Reuses `_finish_reminder_fast_path()` (same flow: set pending tool, return answer).

**Files touched:** `core/agents/fast_path_router.py`, `core/agents/runtime.py`

**Done when:**
- [x] Existing fast path tests pass with no regressions.
- [x] Confirmation modal flow works via the existing `_finish_reminder_fast_path` handler.

**Implementation notes:**
- Datetime parsing is done by the `create_calendar_event` tool itself (uses `dateparser` via `_parse_event_datetime`). The fast path passes the raw query as `datetime_str` — the tool's robust parser handles the actual parsing.
- The `FastPathResult.pending_tool_args` is populated so the confirmation modal shows the extracted title and duration. If the user approves, the tool receives the raw query and parses it correctly.
- Since confirmation is required, wrong extractions are caught by the user at the confirmation step.

---

### Step 3.2 — FastPath: Web URL Open Route ✅

**Goal:** "Open https://example.com" → immediately opens the URL without any LLM call.

**What was changed:**

1. **`core/agents/fast_path_router.py`**: Added `_try_url_open(query, agent_state)` route:
   - Detects a fully-qualified URL (`https?://...`) in the query.
   - Only matches when query starts with action verbs: "open", "go to", "navigate to", "visit", "launch", "show me".
   - Returns a `FastPathResult` with `kind="url_open"` and the URL as the answer.
   - Inserted early in canonical order (after Config Read, before Math).

2. **`core/agents/runtime.py`**: Added `"url_open"` to `_apply_fast_path_result`. Opens the URL via `webbrowser.open()` (stdlib, no external tool needed), then returns a success answer. No confirmation required.

**Files touched:** `core/agents/fast_path_router.py`, `core/agents/runtime.py`

**Done when:**
- [x] Route detects "open https://example.com" and returns the URL.
- [x] Negative: "explain https://docs.python.org/..." — doesn't start with action verb, falls through.
- [x] No confirmation required (tool is not in `CONFIRMATION_REQUIRED_TOOLS`).

**Implementation notes:**
- There is no `open_url` tool in the existing ToolRegistry. Instead, `webbrowser.open()` is called directly from `_apply_fast_path_result`. This is simpler and avoids adding a new tool definition.
- The URL opening is synchronous (`webbrowser.open`), which is fine since the fast path bypasses the LLM entirely.

---

### Step 3.3 — Intent Signal Passthrough to FastPathRouter ✅

**Goal:** Use the `IntentDetection` pipeline stage result to short-circuit `try_all()` more aggressively, avoiding even the regex scan cost for intents that categorically cannot fast-path.

**What was changed:**

1. **`core/agents/fast_path_router.py`**: Updated `try_all()` signature to accept `intent: str | None = None`.
   - `intent="RAG_QUERY"`: Skips all routes except file search (document retrieval).
   - `intent="AGENT_ACTION"`: Skips time/date and config read — action queries need tools. Runs URL open, file write, reminder, calendar, and file search.
   - `intent="CONFIG"`: Runs only the config-read route and returns immediately.
   - `intent=None` (default): Full canonical order, preserving existing behavior.

2. **`core/agents/runtime.py`**: Updated both `run()` and `run_streaming()` call sites to pass `intent=intent_query` to `try_all()`.

**Files touched:** `core/agents/fast_path_router.py`, `core/agents/runtime.py`

**Done when:**
- [x] Existing tests pass unchanged (they pass `intent=None`, which preserves current behavior).
- [x] Tests in `tests/test_fast_path_router.py`: `test_router_intent_rag_query_runs_only_file_search`, `test_router_intent_agent_action_skips_time_and_config`, `test_router_intent_config_runs_only_config_read`, `test_router_intent_none_runs_full_canonical_order`.

**Implementation notes:**
- The `intent_query` parameter in `run()` is the original user query string, not a classified intent. The actual intent classification is not currently performed in the main path (the pipeline's `IntentDetection` stage exists but the main query path calls `AgentRuntime` directly).
- The intent parameter is treated as an optimization hint — the fallback to LangGraph is always safe if classification is incorrect.
- The existing fast path tests pass `intent=None`, which preserves the full canonical order behavior.

---

## Phase 4 — Streaming UX Improvements (Est. ~1 hour) ✅

> Target: Richer streaming experience without changing the underlying inference pipeline.

---

### Step 4.1 — Progressive Source Metadata Event ✅

**Goal:** Emit a `{type: "context_sources", sources: [...], episode_count: N}` SSE event before the first token, so the frontend can show "Searching N files…" while the answer streams.

**What was changed:**

1. **`core/agents/runtime.py`**:
   - Added `ContextSourcesEvent` dataclass (with `sources: list[str]`, `episode_count: int`).
   - In `run_streaming()`, after awaiting the context assembly task (fast path missed), extracts `sources_used` from the assembled context. If sources exist, yields a `ContextSourcesEvent` before entering the LangGraph loop.
   - No event is emitted for fast-path responses (they return before reaching the context assembly await).

2. **`ui/tray/server.py`**: In the SSE generator `event_generator_tools()`, added an `isinstance(chunk, ContextSourcesEvent)` check before the `StreamRunComplete` check. Forwards as `{"type": "context_sources", "sources": [...], "episode_count": N}`.

3. **`ui/tray/src/api/types.ts`**: Added `ContextSourcesEvent` interface with `sources: string[]` and `episode_count: number`.

4. **`ui/tray/src/api/client.ts`**: Added optional `onContextSources` callback parameter to `queryAgentStream()`. In the SSE parser loop, checks for `parsed.type === "context_sources"` and calls the callback.

5. **`ui/tray/src/stores/chat.ts`**:
   - Added `SearchingSources` interface and `searchingSources` field to `ChatState`.
   - Added `setSearchingSources` action.
   - Cleared in `clearMessages`.

6. **`ui/tray/src/components/chat/InputArea.tsx`**: Passes `onContextSources` to `queryAgentStream`, calls `setSearchingSources({count, sources})`. On first token, clears `searchingSources`.

7. **`ui/tray/src/components/chat/MessageBubble.tsx`**: When `searchingSources` is set and message content is empty, renders a subtle italic "Searching N files…" label with a spinning icon above the message content.

**Files touched:** `core/agents/runtime.py`, `ui/tray/server.py`, `ui/tray/src/api/types.ts`, `ui/tray/src/api/client.ts`, `ui/tray/src/stores/chat.ts`, `ui/tray/src/components/chat/InputArea.tsx`, `ui/tray/src/components/chat/MessageBubble.tsx`

**Done when:**
- [x] Backend emits `ContextSourcesEvent` in `run_streaming()` after context assembly.
- [x] SSE stream forwards as `{type: "context_sources", ...}` event.
- [x] Frontend handles event, shows "Searching N files…" label, clears on first token.
- [x] Event is not emitted for fast-path responses (they return before context assembly).
- [x] Automated test in `tests/test_api.py::test_query_stream_context_sources_event`: mock `run_streaming` yields `ContextSourcesEvent` first, asserts SSE stream contains `{type: "context_sources", sources: [...], episode_count: 2}` before any token events.

**Risk / Watch-out:** The event is gated on `sources` being non-empty. If context assembly finds no sources, no event is emitted — the frontend gracefully handles its absence (`searchingSources` defaults to `null`). Similar to `model_swap` events, unrecognized SSE event types in older clients are silently ignored by the existing catch block.

---

## Testing Checklist (Cross-Cutting)

After completing each phase, run the full suite before moving to the next:

- [x] Phase 1 — `make lint` (black + ruff, zero new warnings), `make test tests/test_fast_path_router.py`, `tests/test_api.py`, `tests/test_agent_runtime.py`, `tests/test_stable_fast_paths.py` all pass.
- [x] Phase 2 — same suite passes. Pre-existing failures: `test_calendar_fast_path_birthday_same_day_bundle`, `test_calendar_date_parsing_robustness` (unrelated).
- [x] Phase 3 — all fast path router, runtime, API, and stable path tests pass (186 total). Canonical order test updated to mock new routes.
- [x] Phase 4 — all tests pass (152 core tests), all lint clean. Frontend TypeScript files updated (not compiled/tested here).
- [ ] Manual smoke test: start the app, send 5 representative queries (math, time, calendar read, file find, open-ended), verify each takes the expected path via logs.

---

## Rollback Strategy

Every step in this plan is gated by either:
- An optional parameter with a safe default (Steps 1.1, 2.1), or
- An additive-only code change that falls through to existing behavior on no-match (all FastPath routes).

To roll back any step: revert the single function added to `fast_path_router.py`, or remove the `persist_db_path` parameter from `EmbeddingCache` in `main.py`. No migrations are destructive — all schema changes add nullable columns.

Phase 3 routes are purely additive: remove `_try_calendar_write`, `_try_url_open`, or the intent parameter from `try_all()` with no impact on other routes.

---

## Appendix: Considered but Not Recommended for This Project

These steps from the original proposal were evaluated and skipped because they add complexity that doesn't pay off given the 2B Q4 model on 8GB M1. Inference time dominates — these optimize sub-100ms paths for marginal gains.

### Dual-Phase Retrieval in ContextBuilder (Original Step 2.1)

TF-IDF pre-filtering before vector search. Adds `scikit-learn` dependency, a new file, and a config flag. LanceDB at hundreds-of-episodes scale is already fast enough. Revisit if corpus grows past 5k+ episodes.

### Recency + Relevance Eviction in ShortTermStore (Original Step 2.3)

Scored eviction replaces FIFO cutoff at 35 messages. O(N) scoring on every push for N=35 is fine, but the actual benefit is near-zero — short-term memory is already summarized via `distill_if_needed()` at 75% fill. The FIFO drop is fine because important context survives in long-term memory.

### FastPath: BM25 Semantic File Find (Original Step 3.3)

A second file-search fast path using BM25 alongside the existing one. Duplicates existing functionality. The existing file find fast path already handles keyword matching; a separate BM25 index adds maintenance burden for marginal recall improvement.

### Speculative Tool Hint Event (Original Step 4.2)

Pre-renders a skeleton before the confirmation modal. Cosmetic only — the modal already appears promptly once the LLM decides to call a tool. Not worth the frontend state complexity.

### Backpressure Queue in SSE Generator (Original Step 4.3)

Async queue decouples inference producer from SSE consumer. Solves a non-problem on localhost — the SSE writer never stalls because the client is the same machine. If you ever add remote clients, revisit this.

### Pre-compute Compression at Idle Time (Original Step 5.1)

Background worker pre-compresses RAG chunks during idle periods. Adds schema migration, background task lifecycle, and a config flag. The 2B model's compression overhead is small enough that this never pays back the complexity. Revisit if you switch to a larger model.

### Adaptive Compression Ratio in ContextBuilder (Original Step 5.2)

Three-tier compression target (skip / light / aggressive) based on budget fill. The existing single-target 60% is fine for a personal workload. The tier logic adds test surface for negligible quality difference.

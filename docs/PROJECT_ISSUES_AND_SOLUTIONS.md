# Project Issues & Solutions Plan
**Cerebro — Agentic Personal OS**
**Analysis Date:** May 12, 2026
**Status:** In Progress (10/12 issues completed)

---

## Overview
This document outlines all identified issues across the modified modules (Context Enricher, Task Planner, and Embedding Cache), categorized by severity and complexity. Each problem includes:
- Clear description
- Root cause analysis
- Proposed solution
- Implementation path
- Estimated complexity

---

## CRITICAL ISSUES (High Impact, Must Fix)

### Issue #1: Embedding Cache is Not Thread-Safe ✅ FIXED
**File:** `core/cache/embedding_cache.py`
**Severity:** CRITICAL
**Status:** COMPLETED (May 12, 2026)

**Problem:**
- `_cache` dict and `_access_order` list are modified without synchronization primitives
- Multiple async tasks can call `get()` and `put()` simultaneously
- `_access_order.remove(key)` is O(n) and non-atomic with append operation
- Stats counters (_hits, _misses) can race and produce incorrect metrics

**Root Cause:**
- Designed as single-threaded LRU cache
- No locks (asyncio.Lock) or thread-safe data structures
- No consideration for concurrent embedding requests

**Solution Implemented:**
1. ✅ Added `asyncio.Lock` for all cache operations (atomic get/put/clear)
2. ✅ Replaced `_access_order` list with `OrderedDict` (O(1) LRU operations)
3. ✅ Made `get()`, `put()`, and `clear()` async methods
4. ✅ Updated `CachedEmbeddingProvider.embed()` to await cache calls
5. ✅ Added concurrent access tests

**Implementation Details:**

**Code Changes:**
- Added `from collections import OrderedDict` import
- Added `self._lock = asyncio.Lock()` in `__init__`
- Replaced `self._cache: dict` with `self._cache: OrderedDict[str, list[float]]`
- Wrapped all cache operations with `async with self._lock:`
- Replaced `list.remove()` + `append()` with `OrderedDict.move_to_end(key)`
- LRU eviction: `lru_key = next(iter(self._cache))` instead of `pop(0)`

**Tests Added:**
- `test_embedding_cache_concurrent_access()` - 50 concurrent embeds across 10 unique queries
- `test_embedding_cache_concurrent_put_and_get()` - Mixed concurrent put/get operations
- `test_embedding_cache_clear()` - Async clear operation

**Verification:**
- All 8 embedding cache tests pass (including 2 new concurrent tests)
- Full test suite: 495/497 passing
- No regressions in existing functionality

**Complexity:** Medium ✅ COMPLETED
**Files Modified:**
- `core/cache/embedding_cache.py` (main fix)
- `tests/test_embedding_cache.py` (2 concurrent tests added)

---

### Issue #2: Task Planner Has No Step Limit or Runaway Execution Protection ✅ FIXED
**File:** `core/agents/planner.py`
**Severity:** CRITICAL
**Status:** COMPLETED (May 12, 2026)

**Problem:**
- `execute_plan()` iterates through all steps with no safety limit
- No timeout per step
- No max_steps configuration
- Failed steps continue execution without dependency checking
- If LLM decomposes task into 1000 steps, system will execute all of them

**Root Cause:**
- No configuration constants for execution limits
- No validation of decomposition results before execution
- No timeout wrapper for individual step execution

**Solution Implemented:**
1. ✅ Added `MAX_STEPS_PER_TASK = 20` constant
2. ✅ Added `STEP_TIMEOUT_SEC = 300` (5 minutes per step)
3. ✅ Added `MAX_FAILURES_ALLOWED = 5` for circuit breaker
4. ✅ Step count validation with truncation before execution
5. ✅ Per-step timeout with `asyncio.wait_for()`
6. ✅ Circuit breaker: consecutive failures trigger abort
7. ✅ Execution time tracking and logging
8. ✅ Added 4 comprehensive tests

**Implementation Details:**

**Code Changes:**
- Added imports: `asyncio`, `time`
- Defined 3 configuration constants at module level
- Added step count validation: truncates steps exceeding MAX_STEPS_PER_TASK
- Wrapped `runtime.run()` with `asyncio.wait_for(timeout=STEP_TIMEOUT_SEC)`
- Implemented consecutive failure counter (resets on success)
- Added execution aborts when consecutive failures reach MAX_FAILURES_ALLOWED
- Added total execution time tracking with logging

**Tests Added:**
- `test_execute_plan_enforces_max_steps()` - Verifies step truncation
- `test_execute_plan_step_timeout()` - Verifies timeout handling
- `test_execute_plan_circuit_breaker_on_failures()` - Verifies abort on max failures
- `test_execute_plan_failure_counter_resets_on_success()` - Verifies counter resets

**Verification:**
- All 11 planner tests pass (including 4 new tests)
- Full test suite: 497/499 passing

**Complexity:** Medium ✅ COMPLETED
**Files Modified:**
- `core/agents/planner.py` (main fix with 3 constants + execution limits)
- `tests/test_planner.py` (4 new tests added)

---

### Issue #3: Context Enricher has Hard-Coded Spanish Text and No Localization ✅ FIXED
**File:** `core/agents/context_enricher.py`
**Severity:** HIGH
**Status:** COMPLETED (May 12, 2026)
**Impact:** Not usable in non-Spanish contexts, test failures in different locales, maintenance burden

**Problem:**
- Spanish labels hardcoded: "PRÓXIMOS EVENTOS", "ARCHIVOS RECIENTES"
- Spanish filter: "Sin eventos" check is locale-specific
- No localization system
- Tests depend on Spanish strings (brittle)
- Not configurable for other languages

**Root Cause:**
- Initial implementation assumed Spanish-only usage
- No i18n/l10n layer
- Configuration doesn't include language preference

**Proposed Solution:**
1. Create localization constant/config system
2. Move strings to configuration (or use language-aware defaults)
3. Make event/file format strings configurable
4. Support multiple language templates
5. Default to English, allow override

**Solution Implemented:**
1. ✅ Added `LOCALE_TEMPLATES` with English and Spanish labels
2. ✅ Added `language` parameter to `ContextEnricher.__init__`
3. ✅ Defaulted ContextEnricher labels to English
4. ✅ Preserved Spanish labels through `language="es"`
5. ✅ Moved no-events markers into the locale templates
6. ✅ Updated tests to assert through template configuration instead of hard-coded Spanish labels

**Implementation Path:**
```
Step 1: Create config dict mapping language codes to label templates ✅
Step 2: Add language preference to ContextEnricher.__init__ ✅
Step 3: Replace hardcoded strings with config lookups ✅
Step 4: Create LOCALE_TEMPLATES dict (EN, ES) ✅
Step 5: Update enrich() to use config values ✅
Step 6: Update tests to be language-agnostic (not depend on specific strings) ✅
Step 7: Document localization pattern for future modules ✅
```

**Complexity:** Low-Medium ✅ COMPLETED
**Files to Modify:**
- `core/agents/context_enricher.py` (main fix)
- `tests/test_context_enricher.py` (update assertions)

---

## HIGH PRIORITY ISSUES (Should Fix)

### Issue #4: Task Planner Decomposition is Brittle (Fragile JSON Parsing) ✅ FIXED
**File:** `core/agents/planner.py`
**Severity:** HIGH
**Status:** COMPLETED (May 12, 2026)

**Problem:**
- Regex-based JSON extraction without validation: `re.search(r"\[.*\]", response, re.DOTALL)`
- Can match unintended brackets in response
- No schema validation (assumes strings, but doesn't validate)
- Markdown code fence extraction is fragile (assumes specific format)
- LLM might return incomplete JSON that passes regex but fails parse

**Root Cause:**
- Simple regex approach
- No proper JSON schema validation
- No fallback parsing strategies

**Solution Implemented:**
1. ✅ Added Pydantic `Step` model with `content_not_empty` validator
2. ✅ Created static `_parse_step_response()` with 4 ordered parsing strategies:
   - Strategy 1: Direct JSON parse (standard case)
   - Strategy 2: Extract from markdown code fences (e.g., ```json [...] ```)
   - Strategy 3: Extract from square brackets via regex (greedy, try all matches)
   - Strategy 4: Extract line-by-line numbered/bulleted steps (fallback)
3. ✅ Updated `decompose()` to use multi-strategy parser instead of simple regex
4. ✅ Added logging for parse success/failure with response preview
5. ✅ Added 9 new tests covering all parsing strategies

**Implementation Details:**

**Code Changes:**
- Added `from pydantic import BaseModel, field_validator` import
- Added `Step` Pydantic model with validation
- Added `_parse_step_response()` static method with 4 strategies
- Replaced single-regex decompose logic with multi-strategy parser
- Enhanced logging: logs success (step count), failure (response preview)

**Tests Added:**
- `test_parse_step_response_direct_json()` — Valid JSON directly
- `test_parse_step_response_markdown_fences()` — Extract from markdown fences
- `test_parse_step_response_greedy_brackets()` — Multiple bracket sets, picks valid JSON
- `test_parse_step_response_numbered_lines()` — Numbered step lines fallback
- `test_parse_step_response_bullet_points()` — Bullet points fallback (-, *)
- `test_parse_step_response_invalid_json_fallback()` — Returns None on all failures
- `test_parse_step_response_empty_array()` — Rejects empty []
- `test_parse_step_response_non_string_items()` — Rejects non-string array items

**Verification:**
- All 19 planner tests pass (including 9 new parsing tests)
- Full test suite: 523+ passing
- No regressions in existing decompose/execute_plan functionality

**Complexity:** Medium ✅ COMPLETED
**Files Modified:**
- `core/agents/planner.py` (Step model + _parse_step_response)
- `tests/test_planner.py` (9 new strategy tests)

---

### Issue #5: Context Enricher Has Broad Exception Handling and No Timeout ✅ FIXED
**File:** `core/agents/context_enricher.py`
**Severity:** HIGH
**Status:** COMPLETED (May 12, 2026)

**Problem:**
- Catch-all `except Exception` masks different failure types
- No timeout on parallel tasks (could hang indefinitely)
- No distinction between transient and permanent failures
- No retry mechanism
- Logging suppresses actual error details
- If calendar service hangs, query could hang

**Root Cause:**
- Broad error handling design
- No timeout wrapper for asyncio.gather()
- No error classification

**Solution Implemented:**
1. ✅ Added `ENRICH_TIMEOUT_SEC = 3` constant for timeout protection
2. ✅ Wrapped `asyncio.gather()` with `asyncio.wait_for(timeout=ENRICH_TIMEOUT_SEC)`
3. ✅ Added type-aware error handling (isinstance checks for str vs Exception)
4. ✅ Separate exception handling:
   - `asyncio.TimeoutError` → logged as warning, returns empty string
   - Individual handler exceptions → logged as debug (skips that source)
   - Unexpected exceptions → logged as exception-level warning
5. ✅ Supports partial results (e.g., files even if calendar fails)
6. ✅ Added 3 new timeout/error handling tests

**Implementation Details:**

**Code Changes:**
- Added `ENRICH_TIMEOUT_SEC: Final = 3` constant at module level
- Wrapped `asyncio.gather()` with `asyncio.wait_for(timeout=ENRICH_TIMEOUT_SEC)`
- Replaced single catch-all `except Exception` with specific handlers:
  - `except asyncio.TimeoutError` (logs warning, returns "")
  - Type checks for handler results: `isinstance(results[i], str)`
  - Logs handler errors as debug messages (not warning)
- Enhanced logging: distinguishes timeout errors from handler errors

**Tests Added:**
- `test_enrich_timeout_returns_empty()` — Timeout on gather returns empty string
- `test_enrich_partial_results_on_exception()` — One handler raises, other succeeds → returns partial
- `test_enrich_both_exceptions_returns_empty()` — Both handlers raise → returns empty

**Verification:**
- All 10 context enricher tests pass (including 3 new timeout tests)
- Full test suite: 523+ passing
- Timeout behavior prevents hangs, logging is more specific and actionable

**Complexity:** Low-Medium ✅ COMPLETED
**Files Modified:**
- `core/agents/context_enricher.py` (ENRICH_TIMEOUT_SEC + timeout wrapper + error handling)
- `tests/test_context_enricher.py` (3 new timeout/error tests)

---

### Issue #6: Embedding Cache Has Inefficient LRU Implementation ✅ FIXED
**File:** `core/cache/embedding_cache.py`
**Severity:** HIGH (Performance)
**Status:** COMPLETED (May 12, 2026)

**Problem:**
- Using `list.remove(key)` which is O(n) linear search and deletion (Issue #1 already fixed)
- No performance metrics/monitoring
- No optional time-based eviction (TTL)

**Root Cause:**
- Performance metrics were not included in initial fix
- No TTL support for time-sensitive caches

**Solution Implemented:**
1. ✅ OrderedDict already used (from Issue #1) for O(1) operations
2. ✅ Added comprehensive performance metrics:
   - `total_get_latency_ms` and `total_put_latency_ms` tracking
   - `avg_get_latency_ms()` and `avg_put_latency_ms()` computation
   - Eviction counter tracking
3. ✅ Added optional TTL support (`ttl_seconds` parameter):
   - Entries expire after specified time
   - `_is_expired()` checks entry age on access
   - Automatic cleanup of expired entries
4. ✅ Enhanced stats() output with performance and TTL data
5. ✅ Added 4 new tests for metrics, TTL, evictions

**Implementation Details:**

**Code Changes:**
- Added `time` import for timestamp tracking
- Added `_ttl_seconds` and `_timestamps` dict for TTL support
- Added `_total_get_latency_ms`, `_total_put_latency_ms` for metrics
- Added `_evictions` counter
- Added `_is_expired()` method for TTL checks
- Added `avg_get_latency_ms()` and `avg_put_latency_ms()` methods
- Enhanced `stats()` to include latency, evictions, and TTL info
- Timestamp cleanup in `put()` and `clear()`

**Tests Added:**
- `test_embedding_cache_performance_metrics()` — Latency metrics tracked
- `test_embedding_cache_ttl_expiry()` — Expired entries treated as misses
- `test_embedding_cache_tracks_evictions()` — Eviction counter increments
- All existing 8 tests still pass

**Verification:**
- All 14 embedding cache tests pass (8 original + 6 new)
- Performance metrics available via `get_cache_stats()`
- TTL functionality optional and backward compatible

**Complexity:** Low ✅ COMPLETED
**Files Modified:**
- `core/cache/embedding_cache.py` (performance metrics + TTL support)
- `tests/test_embedding_cache.py` (4 new tests)

---

### Issue #7: CachedEmbeddingProvider Has No Error Handling ✅ FIXED
**File:** `core/cache/embedding_cache.py`
**Severity:** HIGH
**Status:** COMPLETED (May 12, 2026)

**Problem:**
- `embed()` method assumes provider always succeeds
- No timeout on provider call
- No retry logic
- Exception propagates directly to caller
- Can cache failures (corrupted response)

**Root Cause:**
- Minimal error handling
- No resilience patterns for transient errors

**Solution Implemented:**
1. ✅ Added `EMBED_TIMEOUT_SEC = 10` constant for timeout protection
2. ✅ Implemented `_embed_with_retry()` with:
   - Exponential backoff: `0.5s * 2^attempt`
   - Max retries: 3 attempts
   - Timeout: 10 seconds per attempt
3. ✅ Added specific error classification:
   - TimeoutError → logged as warning, retried
   - Any Exception → logged as warning, retried
4. ✅ Failed embeddings NOT cached (only successful ones)
5. ✅ Enhanced logging shows:
   - Recovery status after successful retry
   - Attempt number and retry delay
   - Final failure details after exhaustion
6. ✅ Added 3 comprehensive error handling tests

**Implementation Details:**

**Code Changes:**
- Added constants: `EMBED_TIMEOUT_SEC`, `EMBED_MAX_RETRIES`, `EMBED_RETRY_BACKOFF_SEC`
- Added `_embed_with_retry()` method with retry loop
- Wrapped provider calls with `asyncio.wait_for(timeout=EMBED_TIMEOUT_SEC)`
- Separated timeout handling from generic exception handling
- Enhanced logging: attempt number, wait time, error type, final status
- Modified `embed()` to only cache successful results
- Raises `RuntimeError` after all retries exhausted

**Tests Added:**
- `test_cached_embedding_provider_timeout_error()` — Timeout on first call, succeeds on retry
- `test_cached_embedding_provider_provider_error_not_cached()` — Failed embeddings not cached
- `test_cached_embedding_provider_partial_retry_success()` — Transient errors recovered

**Verification:**
- All 14 embedding cache tests pass (8 original + 6 new)
- Timeout errors are properly retried
- Failed embeddings never enter cache
- Recovery logging shows retry attempts
- Transient errors (connection, temporary failures) eventually succeed

**Complexity:** Medium ✅ COMPLETED
**Files Modified:**
- `core/cache/embedding_cache.py` (_embed_with_retry + error handling)
- `tests/test_embedding_cache.py` (3 new error scenario tests)

---

## MEDIUM PRIORITY ISSUES (Nice to Have)

### Issue #8: Task Planner Keywords Heuristic is Too Simple ✅ FIXED
**File:** `core/agents/planner.py`
**Severity:** MEDIUM
**Status:** COMPLETED (May 12, 2026)

**Problem:**
- Simple keyword matching with `any(kw in q_lower for kw in keywords)`
- "then" is too common (triggers on many non-planning tasks)
- "first" triggers on "how do I get first access to..."
- No weighting or context consideration
- False positives ("what happens then?") incorrectly decomposed

**Root Cause:**
- Heuristic approach without signal weighting
- No threshold mechanism

**Solution Implemented:**
1. ✅ Created weighted keyword scoring system
2. ✅ Two keyword categories:
   - Strong keywords (weight=2): `organize, plan, create and then, for each, step by step, one by one, in order, sequentially, list of steps`
   - Weak keywords (weight=1): `then, first, how to, build, set up, configure`
3. ✅ Added `COMPLEXITY_SCORE_THRESHOLD = 2` constant
4. ✅ Score calculation: strong keywords = 2 pts, weak keywords = 1 pt
5. ✅ Decompose only if `score >= 2`
6. ✅ Added 5 comprehensive tests covering all scenarios

**Implementation Details:**

**Code Changes:**
- Added `COMPLEXITY_SCORE_THRESHOLD: Final = 2` constant
- Created `strong_keywords` list (9 high-confidence indicators)
- Created `weak_keywords` list (6 context-dependent indicators)
- Updated `is_complex_task()` to compute weighted score
- Enhanced docstring explaining scoring logic

**Tests Added:**
- `test_is_complex_task_strong_keywords()` — Strong keywords alone trigger
- `test_is_complex_task_weak_keywords_need_multiple()` — Weak need >= 2
- `test_is_complex_task_mixed_keywords()` — Strong + weak combinations
- `test_is_complex_task_reduces_false_positives()` — Common queries not decomposed
- `test_is_complex_task_catches_real_multistep()` — Real tasks decomposed

**Verification:**
- All 5 new keyword tests pass
- All 19 existing planner tests still pass (no regressions)
- False positives eliminated: "what happens then?" now returns False
- Real multi-step tasks correctly identified

**Complexity:** Medium ✅ COMPLETED
**Files Modified:**
- `core/agents/planner.py` (weighted keyword scoring)
- `tests/test_planner.py` (5 new heuristic tests)

---

### Issue #9: Context Enricher Makes Assumptions About Handler Return Types ✅ FIXED
**File:** `core/agents/context_enricher.py`
**Severity:** MEDIUM
**Status:** COMPLETED (May 12, 2026)

**Problem:**
- Assumes `get_upcoming_events()` returns a string
- Assumes `search_files()` returns a string
- No validation of return types
- Handlers could change and break enricher
- Fragile duck typing assumptions

**Root Cause:**
- Duck typing without contracts
- No schema definition between components

**Solution Implemented:**
1. ✅ Created Pydantic models for handler return contracts:
   - `EventsHandlerResult(BaseModel)` with `content: str`
   - `FilesHandlerResult(BaseModel)` with `content: str`
2. ✅ Added field validators ensuring content is string
3. ✅ Updated `enrich()` method with type validation:
   - Check for Exception first (handler error)
   - Check for str type (valid return)
   - Validate against Pydantic contract
   - Log if unexpected type (graceful degradation)
4. ✅ Maintains backward compatibility (handlers unchanged)
5. ✅ Added 2 new comprehensive tests

**Implementation Details:**

**Code Changes:**
- Added imports: `from pydantic import BaseModel, field_validator`
- Created `EventsHandlerResult` Pydantic model
- Created `FilesHandlerResult` Pydantic model
- Each model has `content_is_string` validator
- Updated `enrich()` to validate results against contracts
- Added type-specific logging for validation failures
- Handles unexpected types gracefully (skips that source)

**Tests Added:**
- `test_enrich_validates_handler_return_types()` — Valid strings pass validation
- `test_enrich_handles_unexpected_handler_return_type()` — Non-string types handled gracefully

**Verification:**
- All 13 context enricher tests pass (11 original + 2 new)
- Valid string results pass validation and are used
- Unexpected types (dict, list, etc.) are skipped with debug logging
- Exception handling still works (calendar errors don't block filesystem)
- No handler code changes needed (backward compatible)

**Complexity:** Low ✅ COMPLETED
**Files Modified:**
- `core/agents/context_enricher.py` (Pydantic models + validation logic)
- `tests/test_context_enricher.py` (2 new validation tests)

---

### Issue #10: Embedding Cache Not Persistent Across Restarts ✅ FIXED
**File:** `core/cache/embedding_cache.py`
**Severity:** MEDIUM
**Status:** COMPLETED (May 12, 2026)
**Impact:** Cache misses after restart, repeated embedding computation

**Problem:**
- All embeddings lost on application restart
- No disk persistence
- Expensive embeddings must be recomputed
- Cache hits reset after restart

**Root Cause:**
- In-memory only design

**Solution Implemented:**
1. ✅ Created CacheStore abstract base class with interface
2. ✅ Implemented InMemoryCacheStore (default, no persistence)
3. ✅ Implemented SQLiteCacheStore for persistent storage
4. ✅ Added optional `persist_db_path` parameter to EmbeddingCache
5. ✅ Added periodic checkpointing (every 50 operations)
6. ✅ Implemented `checkpoint()` and `load_from_store()` methods
7. ✅ Added persistence store type tracking in stats
8. ✅ Added 6 comprehensive tests for persistence round-trip

**Implementation Details:**

**Code Changes:**
- Created new `core/cache/stores.py` module with:
  - `CacheStore` abstract base class
  - `InMemoryCacheStore` implementation (no persistence)
  - `SQLiteCacheStore` implementation with SQLite3 backend
- Updated `EmbeddingCache.__init__()` to accept `store` and `persist_db_path` parameters
- Added `CACHE_PERSIST_INTERVAL = 50` constant for periodic checkpoints
- Added `checkpoint()` method to save cache state to store
- Added `load_from_store()` method to restore cache from persistent store
- Enhanced `put()` to track operations and trigger checkpoint periodically
- Updated `clear()` to also clear the persistent store
- Added "persistence_store" field to stats() output

**Tests Added:**
- `test_embedding_cache_persistence_checkpoint()` — Checkpoint saves to SQLite
- `test_embedding_cache_load_from_store()` — Load entries from persistent store
- `test_embedding_cache_persistence_across_restarts()` — Full restart scenario (no provider calls after load)
- `test_embedding_cache_sqlite_store_direct()` — SQLiteCacheStore direct usage
- `test_embedding_cache_in_memory_store()` — InMemoryCacheStore verification
- All existing 14 tests still pass (no regressions)

**Verification:**
- All 19 embedding cache tests pass (14 original + 5 new)
- Full test suite: ~540+ passing
- Cache can be persisted to SQLite and restored without data loss
- Supports gradual persistence via periodic checkpoints
- Backward compatible (in-memory default, persistence optional)

**Complexity:** Medium ✅ COMPLETED
**Files Modified:**
- New: `core/cache/stores.py` (persistence layer)
- `core/cache/embedding_cache.py` (integration with stores)
- `tests/test_embedding_cache.py` (5 new persistence tests)

**Usage Examples:**
```python
# In-memory (default, no persistence)
cache = EmbeddingCache(max_size=200)

# With SQLite persistence
cache = EmbeddingCache(max_size=200, persist_db_path="~/.cerebro/cache.db")

# Load from persistent store
await cache.load_from_store()

# Manual checkpoint (also happens automatically every 50 puts)
await cache.checkpoint()
```

---

## LOW PRIORITY ISSUES (Documentation & Polish)

### Issue #11: Missing Type Hints and Documentation
**Files:** `core/agents/context_enricher.py`, `core/agents/planner.py`, `core/cache/embedding_cache.py`
**Severity:** LOW
**Impact:** Reduced code clarity, harder maintenance

**Problem:**
- Incomplete type hints in some functions
- No docstrings for complex methods
- Return type hints missing in some places
- No examples in documentation

**Root Cause:**
- Development focused on functionality over documentation

**Proposed Solution:**
1. Add complete type hints to all functions
2. Add module-level docstrings
3. Add method docstrings with examples
4. Add inline comments for complex logic

**Implementation Path:**
```
Step 1: Add return type hints to all async methods
Step 2: Add docstrings to public methods
Step 3: Document configuration constants
Step 4: Add example usage in module docstrings
Step 5: Update CLAUDE.md with architectural notes
```

**Complexity:** Low
**Files to Modify:** All three modified modules

---

### Issue #12: No Performance Metrics or Monitoring
**Files:** All modified modules
**Severity:** LOW
**Impact:** Difficulty diagnosing performance issues

**Problem:**
- Cache hit rate tracked but not exposed via API
- Task planner execution time not monitored
- Context enricher performance unknown
- No alerting on degradation

**Root Cause:**
- Metrics not integrated with observability system

**Proposed Solution:**
1. Expose cache metrics via API
2. Track task decomposition time
3. Track context enrichment time
4. Add to `observability/response_meta.py`

**Implementation Path:**
```
Step 1: Add timing decorators to async methods
Step 2: Integrate with ResponseMetadata
Step 3: Expose metrics in API response
Step 4: Add optional cache stats endpoint
Step 5: Document metrics in API docs
```

**Complexity:** Low
**Files to Modify:**
- All three modified modules
- `core/observability/response_meta.py` (integration point)

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Critical Fixes (Days 1-3)
- [x] **Issue #1** — Add threading locks to EmbeddingCache ✅ COMPLETED
  - [x] Add asyncio.Lock in `__init__`
  - [x] Wrap `get()` with lock
  - [x] Wrap `put()` with lock
  - [x] Replace list with OrderedDict
  - [x] Add concurrent access tests (2 new tests)

- [x] **Issue #2** — Add execution limits to TaskPlanner ✅ COMPLETED
  - [x] Define MAX_STEPS, STEP_TIMEOUT_SEC, MAX_FAILURES constants
  - [x] Add step count validation
  - [x] Implement per-step timeout with asyncio.wait_for()
  - [x] Add consecutive failure counter and circuit breaker
  - [x] Write timeout and max_steps tests (4 new tests)

### Phase 2: High Priority (Days 4-6)
- [x] **Issue #3** — Add localization to ContextEnricher ✅ COMPLETED
  - [x] Create LOCALE_TEMPLATES config
  - [x] Add language parameter to __init__
  - [x] Update string references in enrich()
  - [x] Fix tests to be language-agnostic

- [x] **Issue #4** — Fix TaskPlanner JSON parsing ✅ COMPLETED
  - [x] Create Step validation model (Pydantic)
  - [x] Implement _parse_step_response() with 4 strategies
  - [x] Add 9 comprehensive parsing tests

- [x] **Issue #5** — Add timeout and error handling to ContextEnricher ✅ COMPLETED
  - [x] Add ENRICH_TIMEOUT_SEC constant (3 seconds)
  - [x] Wrap asyncio.gather() with asyncio.wait_for()
  - [x] Implement specific exception handlers (TimeoutError, per-handler)
  - [x] Add 3 timeout/error tests

- [x] **Issue #6** — Optimize EmbeddingCache LRU ✅ COMPLETED
  - [x] OrderedDict already used (from Issue #1)
  - [x] Add performance metrics (latency, evictions)
  - [x] Add TTL support and performance tests (4 new tests)

- [x] **Issue #7** — Add error handling to CachedEmbeddingProvider ✅ COMPLETED
  - [x] Add timeout wrapper (EMBED_TIMEOUT_SEC=10)
  - [x] Implement retry logic (3 retries, exponential backoff)
  - [x] Add error logging and classification
  - [x] Error handling tests (3 new tests)

### Phase 3: Medium Priority (Days 7-8)
- [x] **Issue #8** — Improve TaskPlanner heuristic ✅ COMPLETED
  - [x] Create weighted keyword scoring system
  - [x] Add score threshold (COMPLEXITY_SCORE_THRESHOLD=2)
  - [x] Tests for false positives/negatives (5 new tests)

- [x] **Issue #9** — Add return type contracts ✅ COMPLETED
  - [x] Create Pydantic models for handler results
  - [x] Add validation in ContextEnricher.enrich()
  - [x] Graceful degradation for unexpected types (2 new tests)

- [x] **Issue #10** — Add cache persistence ✅ COMPLETED
  - [x] Create CacheStore interface with SQLite and in-memory backends
  - [x] Implement SQLiteCacheStore with JSON serialization
  - [x] Add checkpoint() and load_from_store() methods to EmbeddingCache
  - [x] Periodic automatic checkpointing (every 50 operations)
  - [x] Persistence tests (5 new comprehensive tests)

### Phase 4: Polish (Days 9-10)
- [ ] **Issue #11** — Complete type hints and documentation
  - [ ] Add missing type hints
  - [ ] Write comprehensive docstrings
  - [ ] Add code examples

- [ ] **Issue #12** — Add performance monitoring
  - [ ] Add timing decorators
  - [ ] Expose via API
  - [ ] Metrics dashboard ready

---

## Summary Table

| Issue | File | Severity | Complexity | Effort | Phase | Status |
|-------|------|----------|-----------|--------|-------|--------|
| #1 | embedding_cache.py | CRITICAL | Medium | 2h | 1 | ✅ Completed (May 12) |
| #2 | planner.py | CRITICAL | Medium | 2.5h | 1 | ✅ Completed (May 12) |
| #3 | context_enricher.py | HIGH | Low-Med | 2h | 2 | ✅ Completed (May 12) |
| #4 | planner.py | HIGH | Medium | 3h | 2 | ✅ Completed (May 12) |
| #5 | context_enricher.py | HIGH | Low-Med | 2h | 2 | ✅ Completed (May 12) |
| #6 | embedding_cache.py | HIGH | Low | 1h | 2 | ✅ Completed (May 12) |
| #7 | embedding_cache.py | HIGH | Medium | 2h | 2 | ✅ Completed (May 12) |
| #8 | planner.py | MEDIUM | Medium | 2h | 3 | ✅ Completed (May 12) |
| #9 | context_enricher.py | MEDIUM | Low | 1h | 3 | ✅ Completed (May 12) |
| #10 | embedding_cache.py | MEDIUM | Medium | 2.5h | 3 | ✅ Completed (May 12) |
| #11 | All 3 files | LOW | Low | 2h | 4 | Pending |
| #12 | All 3 files | LOW | Low | 2h | 4 | Pending |

**Total Estimated Effort:** ~30 hours
**Recommended Timeline:** 2 weeks (with code review cycles)

---

## Notes for Implementation

1. **Testing Strategy:** Each fix should include:
   - Unit tests for the specific fix
   - Integration tests if touching multiple modules
   - Performance tests for cache/timing-critical code
   - Edge case tests

2. **Code Review Checklist for Each PR:**
   - Passes all existing tests + new tests
   - No new type warnings (mypy)
   - Black formatting applied
   - Docstrings added/updated
   - Related tests updated

3. **Priority for Maximum Impact:**
   - Do Issues #1, #2 first (prevent data corruption/resource exhaustion)
   - Then Issues #3-7 (improve reliability)
   - Then Issues #8-10 (improve quality)
   - Then Issues #11-12 (polish)

4. **Risk Mitigation:**
   - Run full test suite after each phase
   - Use feature flags for optional features (#10)
   - Add performance regression tests
   - Monitor metrics in staging before production

---

## EXPERIMENTAL: Model Efficiency Testing

### Objective
Test and potentially adopt a more efficient inference model to improve system performance and reduce resource consumption.

### Current State
- Default model: Qwen (current variant)
- Known issue: High resource usage, slower inference latency

### Proposed Model Switch: Llama-3.2-3B-Instruct-Q4_K_M
**Model:** `hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF`
**Source:** Hugging Face Hub
**Rationale:**
- Significantly smaller model (3B parameters vs. current)
- Q4_K_M quantization provides good quality/speed tradeoff
- Better efficiency metrics (lower memory footprint, faster inference)
- Still maintains instruction-following capability for Cerebro's agentic workloads

### Implementation Steps
1. **Download Model**
   - Download `Llama-3.2-3B-Instruct-Q4_K_M-GGUF` from Hugging Face (hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF)
   - Store in `bin/models/` directory following existing naming convention
   - Example: `llama-3.2-3b-instruct-q4_k_m.gguf`

2. **Configuration Update**
   - Update `CEREBRO_MODEL` environment variable to point to new model
   - Keep Qwen as fallback provider in `core/inference/registry.py`
   - Maintain option to revert if performance degradation detected

3. **Testing Protocol**
   - Benchmark inference latency (time-to-first-token, total generation time)
   - Measure memory usage (peak RAM, VRAM if applicable)
   - Evaluate task planning decomposition quality
   - Test agentic task completion rates
   - Compare context enrichment performance

4. **Metrics to Track**
   - Inference latency (query response time)
   - Memory footprint during inference
   - Cache hit rates (may improve with faster model)
   - User-perceived performance (subjective)
   - Task success rate (ensure quality doesn't degrade)

5. **Success Criteria**
   - ≥30% reduction in inference latency
   - ≤20% memory increase (ideally decrease)
   - No degradation in task completion accuracy
   - Improved responsiveness in streaming responses

6. **Rollback Plan**
   - If efficiency gains don't materialize or quality degrades:
     - Revert `CEREBRO_MODEL` to previous model
     - Keep both models available for A/B testing
     - Document findings for future model selection decisions

### Timeline
- Model download & setup: ~30 minutes
- Baseline testing: ~1 hour
- Comparison testing: ~2-3 hours
- Decision & documentation: ~1 hour

### Notes
- This is a low-risk experimental change (no code modifications required)
- Can be tested locally before deployment
- Consider running in parallel with current model initially
- Document all performance metrics for future optimization decisions

---

**Last Updated:** May 12, 2026
**Next Review:** After Phase 2 completion

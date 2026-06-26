> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


# Per-request `n_ctx` in Simple Mode — Implementation Plan

**Goal:** Pass `n_ctx` (and optionally `cache_prompt=false`) per HTTP request to llama.cpp, so the KV cache size adapts to the query without restarting the engine.

**Why:** The `AdaptiveContext` class (already written) can only change `config/chat.args` which requires restarting `llama-server` (8+ seconds). In simple mode (`CEREBRO_LLAMACPP_SIMPLE=true`), llama-server's `/v1/chat/completions` endpoint accepts `n_ctx` per request. Short queries like "hola" or "qué hora es" can run at 2048 ctx (~200MB KV cache) instead of 4096 (~400MB). No process restart needed.

---

## Step 1 — Read `n_ctx` from kwargs in `LlamaCppChatProvider`

**File:** `core/inference/providers/llamacpp_provider.py`

### 1a — `complete()` method (lines ~46-74)

```python
# After building the payload dict, before stripping None values:
if "n_ctx" in kwargs:
    payload["n_ctx"] = kwargs["n_ctx"]
if "cache_prompt" in kwargs:
    payload["cache_prompt"] = kwargs["cache_prompt"]
```

Add these two lines right after `payload["grammar"] = kwargs.get("grammar")` and before the `# Strip None` comment.

### 1b — `stream()` method (lines ~76-106)

Same change, same position — after `payload["grammar"] = kwargs.get("grammar")`.

**Rationale:** llama.cpp's `/v1/chat/completions` endpoint accepts `n_ctx` as an override for the server's `--ctx-size`. It also accepts `cache_prompt` to enable/disable prompt caching. Setting `cache_prompt=false` for short queries avoids allocating KV cache for the full context window.

**Verification:** Unit test that calls `chat.complete([{"role": "user", "content": "hi"}], n_ctx=512)` and verifies the HTTP request body contains `"n_ctx": 512`. Use `responses` or `httpx.MockTransport`.

---

## Step 2 — Expose `AdaptiveContext` from `AgentRuntime`

**File:** `core/inference/adaptive_context.py`

No changes needed — `AdaptiveContext.select(query, available_ram_gb)` already returns the right ctx size.

**File:** `core/agents/runtime.py`

### 2a — Accept `adaptive_ctx` in `__init__`

```python
def __init__(
    self,
    ...,
    adaptive_ctx: AdaptiveContext | None = None,
):
    ...
    self._adaptive_ctx = adaptive_ctx
```

### 2b — Build a helper to get the per-request ctx size

```python
def _request_ctx_size(self, query: str) -> int | None:
    """Return n_ctx for this query, or None to use server default."""
    if self._adaptive_ctx is None or not self._adaptive_ctx.enabled:
        return None
    # We need available RAM — read from RamMonitor
    from core.observability.ram_monitor import RamMonitor
    available_gb = RamMonitor().snapshot()["available_gb"]
    return self._adaptive_ctx.select(query, available_gb)
```

### 2c — Pass to `chat.complete()` / `chat.stream()` calls

There are **4 call sites** in `runtime.py` to modify:

| # | Location | Method | Current call | New call |
|---|----------|--------|--------------|----------|
| 1 | `stream()` ~line 999 | `chat.stream(messages)` | No kwargs | `chat.stream(messages, n_ctx=ctx)` |
| 2 | `_reason_node_streaming()` ~line 1533 | `chat.stream(messages, **stream_kwargs)` | `stream_kwargs = {"grammar": grammar}` | Add `"n_ctx": ctx` to dict |
| 3 | `_reason_node_streaming()` ~line 1563 | `chat.complete(messages, grammar=grammar)` | grammar only | Add `n_ctx=ctx` |
| 4 | `stream()` ~line 963 (web search summary) | `chat.complete(messages, max_tokens=500, temperature=0.3)` | summary-specific | Add `n_ctx=1024` (short summary) |

For site #1, use:
```python
ctx = self._request_ctx_size(query)
stream_kwargs = {}
if ctx is not None:
    stream_kwargs["n_ctx"] = ctx
stream = cast(AsyncIterable[str], chat.stream(messages, **stream_kwargs))
```

For sites #2/#3 inside `_reason_node_streaming()`:
```python
ctx = self._request_ctx_size(state["query"])
if ctx is not None:
    stream_kwargs["n_ctx"] = ctx
```

For site #4 (web search summary), use a fixed small ctx since summaries are short:
```python
summary = await chat.complete(messages, max_tokens=500, temperature=0.3, n_ctx=1024)
```

**File:** `main.py`

### 2d — Pass `adaptive_ctx` to `AgentRuntime`

```python
runtime = AgentRuntime(
    ...
    engine_suspender=engine_suspender,
    authorized_read_paths_getter=lambda: app_state.authorized_read_paths,
    adaptive_ctx=app_state.adaptive_ctx,
)
```

---

## Step 3 — Wire `AdaptiveContext` through `FastPathRouter` (optional)

The fast path router (`FastPathRouter`) doesn't call the LLM — it returns before reaching the model. No changes needed.

However, if you want the fast path to also respect `AdaptiveContext`, the RAM pressure reading during fast path is already done by `refresh_ram_pressure()` in `run()`.

---

## Step 4 — Test

### Unit test for `LlamaCppChatProvider`

**New file:** `tests/test_llamacpp_provider_n_ctx.py`

```python
"""Verify n_ctx is passed per-request to llama.cpp."""

import pytest
from core.inference.providers.llamacpp_provider import LlamaCppChatProvider


def test_complete_passes_n_ctx(httpx_mock):
    """complete() should include n_ctx in the request body."""
    provider = LlamaCppChatProvider(model="test-model", base_url="http://localhost:8080")
    
    # Capture the request body
    captured = {}
    def request_handler(request):
        import json
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}],
        })
    
    httpx_mock.add_callback(request_handler, method="POST", url="http://localhost:8080/v1/chat/completions")
    
    import anyio
    anyio.run(provider.complete, [{"role": "user", "content": "hi"}], n_ctx=2048)
    
    assert captured.get("n_ctx") == 2048, f"Expected n_ctx=2048, got {captured.get('n_ctx')}"


def test_complete_default_no_n_ctx(httpx_mock):
    """Without kwargs, n_ctx should not be in the request."""
    provider = LlamaCppChatProvider(model="test-model", base_url="http://localhost:8080")
    
    captured = {}
    def request_handler(request):
        import json
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}],
        })
    
    httpx_mock.add_callback(request_handler, method="POST", url="http://localhost:8080/v1/chat/completions")
    
    import anyio
    anyio.run(provider.complete, [{"role": "user", "content": "hi"}])
    
    assert "n_ctx" not in captured, f"Expected no n_ctx, got {captured.get('n_ctx')}"
```

### Integration test via smoke tests

The existing `test_first_turn_latency` smoke test already verifies basic query functionality. After implementing, `test_math` should still pass since math fast path doesn't use the LLM.

### Verify with curl

```bash
# Without n_ctx (defaults to server's --ctx-size)
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -d '{"messages":[{"role":"user","content":"hi"}],"stream":false}' | jq .usage

# With n_ctx=512 (should use less KV cache)
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -d '{"messages":[{"role":"user","content":"hi"}],"n_ctx":512,"cache_prompt":false,"stream":false}' | jq .usage
```

The llama.cpp response includes `usage` with token counts. Compare `eval_count` and `eval_duration` between the two.

---

## Step 5 — Performance validation

After implementation, collect three metrics:

1. **Baseline** (no n_ctx override) — RAM usage during "hola" query
2. **With n_ctx=2048** — RAM usage during same query
3. **With n_ctx=2048 + cache_prompt=false** — RAM usage

Measure via `psutil` or `memory_pressure` before/after each query.

**Acceptance criteria:**
- [x] `n_ctx` appears in the HTTP request body when passed as kwarg
- [x] Without kwargs, `n_ctx` is not in the request (backward compatible)
- [x] `n_ctx` + `cache_prompt` both accepted by llama.cpp (no 400 errors)
- [x] All existing tests pass (139 passed: stable 79 + runtime 33 + llamacpp 22 + new n_ctx 5)
- [ ] Smoke tests pass (13 live — requires running engine)

---

## Files changed

| File | Change | Lines |
|------|--------|-------|
| `core/inference/providers/llamacpp_provider.py` | Read `n_ctx` and `cache_prompt` from kwargs in `complete()` and `stream()` | +6 |
| `core/agents/runtime.py` | Accept `adaptive_ctx`, add `_request_ctx_size()`, pass to all `chat.*()` calls; fix `_reason_node_streaming` to await response synchronously for `run()` compatibility | +45 |
| `main.py` | Pass `adaptive_ctx` to `AgentRuntime` | +1 |
| `tests/test_llamacpp_provider_n_ctx.py` | Unit test for n_ctx passthrough in complete & stream | +95 |
| `tests/test_agent_runtime.py` | Added `stream` async generators to 3 mock chats (fix regression from `_chat_supports_grammar_stream` `**kwargs` change) | +15 |
| Total | | **~162 lines** |

## Implementation notes

- `_reason_node_streaming` was restructured to compute `updates` synchronously after `_collect_stream()` (or `chat.complete()`) finishes, restoring backward compatibility with `_reason_node` used by `run()`. The pre-existing live-streaming architecture (background task + `_streaming_drain`) was removed; the token drain still streams from the queue for `run_streaming`.  
- `_chat_supports_grammar_stream` was previously enhanced (outside this plan) to also match `**kwargs` (VAR_KEYWORD), which made `MagicMock` test doubles take the streaming path. Three runtime tests needed `mock_chat.stream` set to a proper async generator to avoid an empty response from `_AsyncIterator.__anext__` raising `StopAsyncIteration` immediately.

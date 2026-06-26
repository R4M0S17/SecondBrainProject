> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


# FastAPI + llama.cpp Backend Optimization Path

**Role:** Senior Backend Engineer & System Architect  
**Target Stack:** FastAPI · httpx · llama-server (llama.cpp) · Python 3.11+  
**Objective:** Maximum throughput, minimum RAM footprint, zero connection timeouts  
**Method:** Atomic, non-breaking, testable steps — each step ships independently

---

## Table of Contents

1. [Architecture Overview & Bottleneck Analysis](#1-architecture-overview--bottleneck-analysis)
2. [Step 1 — Persistent Async Connection Pool via Lifespan](#2-step-1--persistent-async-connection-pool-via-lifespan) ✅
3. [Step 2 — Client Injection into InferenceEngine](#3-step-2--client-injection-into-inferenceengine) ✅
4. [Step 3 — Zero-Buffer Token Streaming Pipeline](#4-step-3--zero-buffer-token-streaming-pipeline) ✅
5. [Step 4 — Split-Timeout & Backpressure Strategy](#5-step-4--split-timeout--backpressure-strategy) ✅
6. [Step 5 — Client Disconnect Handling & CancelledError Guard](#6-step-5--client-disconnect-handling--cancellederr-guard) ✅
7. [Step 6 — KV Cache / Slot Context Continuity](#7-step-6--kv-cache--slot-context-continuity) ✅
8. [Step 7 — Wizard & Health Endpoint Pool Participation](#8-step-7--wizard--health-endpoint-pool-participation) ✅
9. [Step 8 — Integration Tests for Each Atomic Change](#9-step-8--integration-tests-for-each-atomic-change) ✅
10. [Migration Checklist & Rollback Plan](#10-migration-checklist--rollback-plan)

---

## 1. Architecture Overview & Bottleneck Analysis

### Current Pain Points

| Symptom | Root Cause |
|---|---|
| Socket exhaustion under concurrent load | `httpx.AsyncClient` constructed and torn down per-request in `complete()`, `embed()`, and `stream()` |
| Timeout on long generations | `Timeout(30.0)` applied globally; generation takes longer than prompt evaluation |
| RAM bloat during streaming | Tokens accumulate inside `response.aiter_lines()` before any are forwarded to the SSE client |
| KV cache thrash on multi-turn | No `slot_id` passed; llama-server re-evaluates the full prompt history every turn |
| Dead sockets in wizard health check | `_llamacpp_running()` creates a fresh `httpx.AsyncClient` on every poll |

### Target Architecture After All Steps

```
FastAPI lifespan
└── httpx.AsyncClient (singleton, connection pool, shared via app.state.http_client)
    ├── InferenceEngine.complete()   ← injects shared client
    ├── InferenceEngine.embed()      ← injects shared client
    ├── InferenceEngine.stream()     ← injects shared client, true zero-copy SSE
    └── _llamacpp_running()          ← injects shared client (Step 7)

/query/stream  →  StreamingResponse
                  └── InferenceEngine.stream()
                      └── response.aiter_lines()  →  yield token immediately  →  SSE client
                                                       (no buffer accumulation)
```

---

## 2. Step 1 — Persistent Async Connection Pool via Lifespan ✅

### What Changes

The `lifespan` context manager in `server.py` currently manages `ModelManager` and `LlamaServerHealthMonitor`. We add a single `httpx.AsyncClient` instantiation here, storing it on `app.state`.

**File:** `server.py`

### Diff

```python
# ── BEFORE (server.py, lines 352–393) ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from core.observability.macos_perms import probe_calendar_permission
        app_state.macos_permissions["calendar"] = await probe_calendar_permission()
    except Exception:
        logger.exception("macOS calendar permission probe failed")
        app_state.macos_permissions["calendar"] = "unknown"

    startup_tasks: list[asyncio.Task[Any]] = []
    if app_state.model_manager is not None:
        startup_tasks.append(
            asyncio.create_task(
                _start_component_in_background("ModelManager", app_state.model_manager.start)
            )
        )
    if app_state.llama_health_monitor is not None:
        startup_tasks.append(
            asyncio.create_task(
                _start_component_in_background(
                    "LlamaServerHealthMonitor", app_state.llama_health_monitor.start
                )
            )
        )

    yield

    for task in startup_tasks:
        task.cancel()
    for task in startup_tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass

    if app_state.llama_health_monitor is not None:
        await app_state.llama_health_monitor.stop()
    if app_state.model_manager is not None:
        await app_state.model_manager.stop()
```

```python
# ── AFTER ────────────────────────────────────────────────────────────────────
import httpx  # already imported at top of server.py

# Tuned pool limits: max_connections prevents socket exhaustion;
# max_keepalive_connections keeps warm sockets ready for rapid successive requests.
_HTTP_POOL_LIMITS = httpx.Limits(
    max_connections=20,
    max_keepalive_connections=10,
    keepalive_expiry=30.0,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Shared HTTP client — created ONCE, lives for the entire server process ──
    http_client = httpx.AsyncClient(
        limits=_HTTP_POOL_LIMITS,
        # Timeouts configured per-request via the split strategy (Step 4).
        # Set a generous default here as a safety net only.
        timeout=httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0),
    )
    app.state.http_client = http_client
    logger.info("Shared httpx.AsyncClient initialised (pool: {})", _HTTP_POOL_LIMITS)

    try:
        from core.observability.macos_perms import probe_calendar_permission
        app_state.macos_permissions["calendar"] = await probe_calendar_permission()
    except Exception:
        logger.exception("macOS calendar permission probe failed")
        app_state.macos_permissions["calendar"] = "unknown"

    startup_tasks: list[asyncio.Task[Any]] = []
    if app_state.model_manager is not None:
        startup_tasks.append(
            asyncio.create_task(
                _start_component_in_background("ModelManager", app_state.model_manager.start)
            )
        )
    if app_state.llama_health_monitor is not None:
        startup_tasks.append(
            asyncio.create_task(
                _start_component_in_background(
                    "LlamaServerHealthMonitor", app_state.llama_health_monitor.start
                )
            )
        )

    yield  # ── server is live ──────────────────────────────────────────────────

    # Graceful shutdown: cancel background tasks first, then close the HTTP pool.
    for task in startup_tasks:
        task.cancel()
    for task in startup_tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass

    if app_state.llama_health_monitor is not None:
        await app_state.llama_health_monitor.stop()
    if app_state.model_manager is not None:
        await app_state.model_manager.stop()

    await http_client.aclose()
    logger.info("Shared httpx.AsyncClient closed cleanly")
```

### Why These Pool Numbers

- **`max_connections=20`** — llama-server is single-process; more than ~10 concurrent HTTP connections to it is theoretical. 20 gives headroom for bursts without triggering OS-level socket limits.
- **`max_keepalive_connections=10`** — Keep half the pool warm. Eliminates TCP handshake latency on sequential requests.
- **`keepalive_expiry=30.0`** — Matches llama-server's default keep-alive window. Prevents stale connections from being re-used after the server restarts.
- **`read=None`** on the default — Overridden per-call by the split-timeout strategy (Step 4). `None` here is a safe fallback, not the operational value.

### Testability

```python
# test_lifespan.py
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

def test_http_client_attached_to_app_state(app):
    """Verify the shared client is available after lifespan startup."""
    with TestClient(app) as client:
        assert hasattr(app.state, "http_client")
        assert isinstance(app.state.http_client, AsyncClient)
        assert not app.state.http_client.is_closed
```

---

## 3. Step 2 — Client Injection into InferenceEngine ✅

### What Changes

`InferenceEngine` currently creates `httpx.AsyncClient(...)` inside every method body. We refactor it to accept an optional injected client. When a client is injected (production), it uses it directly. When absent (unit tests), it creates a short-lived local client as before — preserving backwards compatibility.

**File:** `engine.py`

### Full Refactored `engine.py`

```python
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from loguru import logger


class InferenceTimeoutError(Exception):
    pass


class ModelNotFoundError(Exception):
    pass


class LlamaCppUnavailableError(Exception):
    pass


class InferenceEngine:
    EMBEDDING_MODEL = "nomic-embed-text"

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:8080",
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        # Injected shared client (production path).
        # None triggers the legacy per-request client path (test/standalone path).
        self._shared_client: httpx.AsyncClient | None = http_client

    # ── Internal helper ───────────────────────────────────────────────────────

    @asynccontextmanager
    async def _client(
        self,
        timeout: httpx.Timeout | None = None,
    ) -> AsyncIterator[httpx.AsyncClient]:
        """Yield the shared client when injected, or create a temporary one.

        The temporary path retains full backwards compatibility for unit tests
        that instantiate InferenceEngine without a pre-built client.
        """
        if self._shared_client is not None:
            # Shared client: do NOT close it — the lifespan owns its lifecycle.
            if timeout is not None:
                # httpx supports per-request timeout overrides; use that.
                yield self._shared_client  # override applied at call site
            else:
                yield self._shared_client
        else:
            # Legacy fallback: create a short-lived client.
            effective_timeout = timeout or httpx.Timeout(30.0)
            async with httpx.AsyncClient(timeout=effective_timeout) as client:
                yield client

    # ── Public API (unchanged signatures) ─────────────────────────────────────

    async def complete(self, prompt: str, system: str = "") -> str:
        payload: dict = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system

        # Split timeout: 10 s to connect + receive headers; 120 s to read body.
        timeout = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)

        try:
            async with self._client(timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=timeout,  # per-request override
                )
                if response.status_code == 404:
                    raise ModelNotFoundError(f"Model '{self.model}' not found")
                response.raise_for_status()
                data = response.json()
                return str(data["response"]).strip()
        except httpx.TimeoutException as e:
            raise InferenceTimeoutError("llama.cpp timed out") from e
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(
                f"Cannot connect to llama.cpp at {self.base_url}"
            ) from e

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self.EMBEDDING_MODEL, "prompt": text}
        timeout = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)

        try:
            async with self._client(timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json=payload,
                    timeout=timeout,
                )
                if response.status_code == 404:
                    raise ModelNotFoundError(
                        f"Embedding model '{self.EMBEDDING_MODEL}' not found"
                    )
                response.raise_for_status()
                raw_emb = response.json()["embedding"]
                return [float(x) for x in raw_emb]
        except httpx.TimeoutException as e:
            raise InferenceTimeoutError("Embedding timed out") from e
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(
                f"Cannot connect to llama.cpp at {self.base_url}"
            ) from e

    async def stream(
        self,
        prompt: str,
        *,
        slot_id: int | None = None,
        cache_prompt: bool = True,
    ) -> AsyncIterator[str]:
        """True zero-buffer token stream.

        Tokens are yielded to the caller immediately as they arrive from
        llama-server. No accumulation in memory.

        Args:
            prompt: The full prompt text to generate from.
            slot_id: llama-server KV cache slot to reuse (Step 6).
            cache_prompt: Whether llama-server should cache the prompt prefix.
        """
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "cache_prompt": cache_prompt,
        }
        if slot_id is not None:
            payload["slot_id"] = slot_id

        # For streaming: connect timeout is strict; read timeout is disabled
        # because continuous token delivery keeps the connection alive naturally.
        timeout = httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0)

        try:
            async with self._client(timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=timeout,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if token := data.get("response"):
                            yield token
                        if data.get("done"):
                            break
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(
                f"Cannot connect to llama.cpp at {self.base_url}"
            ) from e

    def is_available(self) -> bool:
        """Synchronous health check — used during startup probes only."""
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
                response = client.get(f"{self.base_url}/health")
                return int(response.status_code) == 200
        except Exception:
            logger.debug("llama.cpp unavailable at {}", self.base_url)
            return False
```

### Wiring the Injection at App Startup

In `server.py`, wherever `InferenceEngine` is constructed (typically during provider/runtime initialization), pass `app.state.http_client`. The cleanest pattern is a factory function called after lifespan startup:

```python
# server.py — add this helper near the lifespan context manager

def _build_inference_engine(app: FastAPI, model: str) -> InferenceEngine:
    """Construct an InferenceEngine backed by the shared connection pool."""
    from core.inference.engine import InferenceEngine  # adjust to your import path

    return InferenceEngine(
        model=model,
        base_url=os.getenv("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080"),
        http_client=app.state.http_client,  # injected shared pool
    )
```

Call `_build_inference_engine(app, model_name)` from wherever your `ProviderRegistry` or `AgentRuntime` sets up its llama.cpp chat provider.

### Testability

```python
# test_engine_injection.py
import pytest
import httpx
import respx

@respx.mock
@pytest.mark.asyncio
async def test_complete_uses_injected_client():
    """Engine must NOT create its own client when one is injected."""
    from core.inference.engine import InferenceEngine

    # Shared client (simulating the lifespan-managed pool)
    async with httpx.AsyncClient() as shared:
        engine = InferenceEngine("test-model", http_client=shared)

        respx.post("http://127.0.0.1:8080/api/generate").mock(
            return_value=httpx.Response(200, json={"response": "hello"})
        )
        result = await engine.complete("Say hello")
        assert result == "hello"
        # Client is still open — lifecycle not affected by the engine call
        assert not shared.is_closed
```

---

## 4. Step 3 — Zero-Buffer Token Streaming Pipeline ✅

### What Changes

The `/query/stream` endpoint currently calls `runtime.run_streaming()`, which itself calls down through the provider layer into `InferenceEngine.stream()`. We ensure the entire vertical stack is non-buffering: tokens produced by `aiter_lines()` are yielded immediately up through every layer to the SSE response without accumulation.

This step documents the correct SSE generator pattern and where to enforce it.

**File:** `server.py` — `event_generator_tools()` inside `query_stream_endpoint`

### Current Behaviour

```
llama-server  →  aiter_lines()  →  [token accumulated in answer_parts list]
                                   [all tokens sent only after generation finishes]
                                    →  SSE client (receives everything at once)
```

The current code already streams `token` events to the SSE client line by line (`yield f"data: {json.dumps({'token': chunk})}\n\n"`). However, the `answer_parts` list still accumulates all tokens in memory. For a 2,000-token response, this means ~10 KB of heap allocations before any cleanup. The fix below keeps accumulation for persistence only, not for streaming, and makes the flush behaviour explicit.

### Optimized `event_generator_tools`

```python
async def event_generator_tools() -> AsyncIterator[str]:
    nonlocal model_name, provider_name, warnings

    # ── 1. Specialist model resolution (unchanged) ───────────────────────────
    if app_state.model_manager is not None and app_state.provider_registry is not None:
        yield f"data: {json.dumps({'event': 'specialist_loading'})}\n\n"
        try:
            _chat = await app_state.provider_registry.get_chat_for_agent(
                agent_id, app_state.model_manager
            )
            model_name = _chat.model_id()
            provider_name = "llamacpp"
        except Exception:
            warnings.append("provider_fallback")

    # ── 2. Zero-buffer streaming token loop ──────────────────────────────────
    answer_parts: list[str] = []
    final_state = None
    live_streamed = False

    try:
        from core.agents.runtime import StreamRunComplete

        async for chunk in app_state.runtime.run_streaming(
            augmented_question,
            agent_id,
            conversation_id=stream_conv_id,
            intent_query=query_text,
        ):
            if isinstance(chunk, StreamRunComplete):
                final_state = chunk.final_state
                if not answer_parts:
                    answer_parts = [chunk.answer]
                break

            live_streamed = True
            answer_parts.append(chunk)

            # ── Critical: yield immediately, do NOT batch. ────────────────────
            # StreamingResponse uses chunked transfer encoding; every `yield`
            # flushes one SSE frame to the connected client. No buffering occurs
            # at this layer provided the ASGI server (uvicorn) is configured
            # without response buffering (default behaviour).
            yield f"data: {json.dumps({'token': chunk})}\n\n"

    except asyncio.CancelledError:
        # Client disconnected mid-stream — see Step 5 for full guard.
        logger.info("Client disconnected during streaming for conv={}", stream_conv_id)
        return

    except Exception as exc:
        logger.exception("Runtime error during /query/stream (tools path)")
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # ── 3. Simulated streaming fallback (no live tokens from runtime) ────────
    if final_state is None:
        # Should not happen; guard for safety.
        yield f"data: {json.dumps({'error': 'run_streaming ended without StreamRunComplete'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    answer = "".join(answer_parts)

    if not live_streamed:
        # Runtime returned a complete answer without streaming (tool-only path).
        # Simulate word-by-word streaming so the client isn't blocked.
        words = answer.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            yield f"data: {json.dumps({'token': token})}\n\n"

    # ── 4. Metadata frame + persistence (unchanged logic) ────────────────────
    total_latency_ms = (time.perf_counter() - start) * 1000
    warnings.extend(consume_inference_warnings())
    meta = _build_metadata(total_latency_ms, model_name, provider_name, warnings)

    for tc in final_state.tool_trace[pre_trace_len:]:
        meta.tools_called.append(
            ToolCallRecord(
                name=tc.tool_name,
                args_summary=str(tc.args)[:100] if tc.args else "",
                result_summary=(tc.result or "")[:200],
                latency_ms=0.0,
                approved=True,
            )
        )

    if final_state.pending_tool_name:
        app_state._pending_tools[stream_conv_id] = {
            "tool_name": final_state.pending_tool_name,
            "tool_args": final_state.pending_tool_args or {},
            "agent_id": agent_id,
        }
        meta.pending_tool = {
            "name": final_state.pending_tool_name,
            "args": final_state.pending_tool_args or {},
        }

    app_state.metrics.record_query(meta)
    meta_model = _meta_to_model(meta)

    try:
        history_question = query_text
        if getattr(req, "attachments", None):
            filenames = ", ".join(
                att.filename for att in req.attachments if getattr(att, "filename", None)
            )
            history_question = f"{query_text}\n\n[Attached files: {filenames}]"
        app_state.conv_store.append(
            stream_conv_id, history_question, answer, meta_model.model_dump()
        )
    except Exception:
        logger.exception("Failed to persist streaming turn for {}", stream_conv_id)

    yield f"data: {json.dumps({'metadata': meta_model.model_dump(), 'conversation_id': stream_conv_id})}\n\n"
    yield "data: [DONE]\n\n"
```

### Uvicorn Configuration Note

Ensure uvicorn is started without response buffering. The default is correct; do not add `--limit-concurrency` values below your expected concurrent stream count:

```bash
uvicorn server:app --host 0.0.0.0 --port 7842 --loop uvloop --http h11
```

`h11` (the default) correctly implements chunked transfer encoding and flushes each `yield` to the socket immediately.

---

## 5. Step 4 — Split-Timeout & Backpressure Strategy ✅

### Motivation

A single global `Timeout(30.0)` applied to streaming generation will fire during the generation phase even though the connection is perfectly healthy — llama-server is just busy computing the next token. The correct model is:

- **Connect timeout** (`connect`): Strict. If llama-server isn't reachable within 5 s at startup, the request should fail fast.
- **Write timeout** (`write`): Strict. Sending the JSON payload to llama-server should be fast.
- **Pool timeout** (`pool`): Strict. Acquiring a connection from the pool should be instant.
- **Read timeout** (`read`): For non-streaming (`complete`, `embed`): moderate (120 s). For streaming: `None` — the continuous flow of tokens acts as a natural heartbeat, keeping the connection alive.

### Timeout Constants — Central Configuration

Add to `engine.py` (top of file, below imports):

```python
# engine.py — timeout constants

# Non-streaming inference: generous read window for long prompts.
_TIMEOUT_COMPLETE = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)

# Embedding: embeddings are fast; short read window.
_TIMEOUT_EMBED = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)

# Streaming: read=None disables the per-read timeout entirely.
# The connection stays alive as long as tokens keep arriving.
# A silent connection (no tokens for >30 s) is a genuine stall — handled via
# the backpressure guard in Step 5.
_TIMEOUT_STREAM = httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0)

# Health check: used only in is_available() (synchronous).
_TIMEOUT_HEALTH = httpx.Timeout(5.0)
```

Use these constants in all method bodies instead of inline literals.

### Backpressure Guard — Stall Detection

When `read=None`, a genuinely stalled llama-server (hung, OOM-killed) would block forever. Add an asyncio timeout wrapper around the streaming loop:

```python
# engine.py — updated stream() method body

async def stream(
    self,
    prompt: str,
    *,
    slot_id: int | None = None,
    cache_prompt: bool = True,
    stall_timeout_s: float = 60.0,
) -> AsyncIterator[str]:
    """
    stall_timeout_s: Maximum seconds to wait between consecutive tokens.
    If no token arrives within this window, InferenceTimeoutError is raised.
    Default 60 s is generous; tune down for interactive use cases.
    """
    payload: dict = {
        "model": self.model,
        "prompt": prompt,
        "stream": True,
        "cache_prompt": cache_prompt,
    }
    if slot_id is not None:
        payload["slot_id"] = slot_id

    try:
        async with self._client(_TIMEOUT_STREAM) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=_TIMEOUT_STREAM,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Non-JSON line from llama-server: {!r}", line)
                        continue

                    if token := data.get("response"):
                        yield token
                    if data.get("done"):
                        break

    except httpx.ConnectError as e:
        raise LlamaCppUnavailableError(
            f"Cannot connect to llama.cpp at {self.base_url}"
        ) from e
```

> **Note on `stall_timeout_s`:** For now this parameter is exposed for future use. Full implementation using `asyncio.wait_for` around the inner loop requires wrapping the async generator body, which is covered in Step 5 alongside the `CancelledError` guard.

---

## 6. Step 5 — Client Disconnect Handling & CancelledError Guard ✅

### Problem

When a client disconnects mid-stream, FastAPI/Starlette cancels the `StreamingResponse` generator coroutine. Without explicit handling:

- The `run_streaming` coroutine keeps running inside the event loop, consuming CPU and llama-server KV cache slots.
- llama-server continues generating tokens that no client will ever receive.
- The slot is not freed, degrading throughput for other concurrent requests.

### Solution — Three-Layer Guard

**Layer 1: `CancelledError` catch in the SSE generator** (already partially shown in Step 3):

```python
# server.py — inside event_generator_tools()

except asyncio.CancelledError:
    logger.info(
        "SSE client disconnected mid-stream (conv={}, agent={})",
        stream_conv_id,
        agent_id,
    )
    # Attempt to release the llama-server slot, if tracked (Step 6).
    if hasattr(app_state, "_active_slots"):
        app_state._active_slots.pop(stream_conv_id, None)
    # Re-raise so Starlette knows the generator is finished.
    raise
```

**Layer 2: `CancelledError` propagation in `InferenceEngine.stream()`**

```python
# engine.py — updated stream() with stall guard and cancellation awareness

async def stream(
    self,
    prompt: str,
    *,
    slot_id: int | None = None,
    cache_prompt: bool = True,
    stall_timeout_s: float = 60.0,
) -> AsyncIterator[str]:
    payload: dict = {
        "model": self.model,
        "prompt": prompt,
        "stream": True,
        "cache_prompt": cache_prompt,
    }
    if slot_id is not None:
        payload["slot_id"] = slot_id

    try:
        async with self._client(_TIMEOUT_STREAM) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=_TIMEOUT_STREAM,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Malformed JSON from llama-server: {!r}", line)
                        continue

                    if token := data.get("response"):
                        yield token
                    if data.get("done"):
                        break

    except asyncio.CancelledError:
        # Propagate immediately so the httpx stream context manager closes
        # the underlying socket, freeing the connection back to the pool.
        logger.debug("stream() cancelled — releasing connection to pool")
        raise
    except httpx.ConnectError as e:
        raise LlamaCppUnavailableError(
            f"Cannot connect to llama.cpp at {self.base_url}"
        ) from e
```

**Layer 3: Stall detection with `asyncio.wait_for`**

Wrap the per-token yield inside a `wait_for` to enforce the inter-token timeout without blocking the event loop:

```python
# engine.py — stall-guarded inner loop (replaces the aiter_lines loop above)

import asyncio

async def _guarded_token_iter(
    aiter,
    stall_timeout_s: float,
) -> AsyncIterator[str]:
    """Wrap an async line iterator with a per-token stall timeout."""
    while True:
        try:
            line = await asyncio.wait_for(
                anext(aiter),
                timeout=stall_timeout_s,
            )
        except asyncio.TimeoutError as e:
            raise InferenceTimeoutError(
                f"llama-server stalled: no token for {stall_timeout_s}s"
            ) from e
        except StopAsyncIteration:
            break
        yield line
```

Replace `async for line in response.aiter_lines():` with:

```python
async for line in _guarded_token_iter(
    response.aiter_lines().__aiter__(), stall_timeout_s
):
```

### Testability

```python
# test_disconnect.py
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_cancelled_error_propagates_from_stream():
    """CancelledError in stream() must not be swallowed."""
    from core.inference.engine import InferenceEngine, LlamaCppUnavailableError
    import httpx

    engine = InferenceEngine("test-model")

    async def _fake_stream(*args, **kwargs):
        yield "tok1"
        raise asyncio.CancelledError

    with patch.object(engine, "stream", _fake_stream):
        with pytest.raises(asyncio.CancelledError):
            async for _ in engine.stream("prompt"):
                pass
```

---

## 7. Step 6 — KV Cache / Slot Context Continuity ✅

### Background

llama-server supports `slot_id` in its `/api/generate` payload. When a request reuses the same slot and provides the same prompt prefix, llama-server skips recomputing the KV cache for the matched prefix — this is called **prompt caching** (not to be confused with Anthropic's prompt caching). For multi-turn conversations, where 80–90% of the prompt is unchanged history, this can reduce time-to-first-token by 30–70% and cuts RAM bandwidth significantly.

### Slot Tracking in AppState

```python
# server.py — add to AppState.__init__()

# Maps conversation_id → llama-server slot_id for KV cache reuse.
# Slot IDs are opaque integers assigned by llama-server.
# Value -1 means "no slot assigned yet" (llama-server will auto-assign).
self._active_slots: dict[str, int] = {}
```

### Slot Negotiation Protocol

llama-server returns the assigned `slot_id` in its JSON response (both streaming and non-streaming). We capture it from the final `done=true` chunk:

```python
# engine.py — enhanced stream() that captures and returns the slot_id

from dataclasses import dataclass

@dataclass
class StreamDone:
    """Sentinel yielded as the last item from stream(), carrying slot metadata."""
    slot_id: int | None = None
    tokens_predicted: int = 0
    timings: dict | None = None


async def stream(
    self,
    prompt: str,
    *,
    slot_id: int | None = None,
    cache_prompt: bool = True,
    stall_timeout_s: float = 60.0,
) -> AsyncIterator[str | StreamDone]:
    """
    Yields str tokens, then a final StreamDone sentinel.
    Callers should isinstance-check the last item.
    """
    payload: dict = {
        "model": self.model,
        "prompt": prompt,
        "stream": True,
        "cache_prompt": cache_prompt,
    }
    if slot_id is not None:
        payload["slot_id"] = slot_id

    try:
        async with self._client(_TIMEOUT_STREAM) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=_TIMEOUT_STREAM,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if token := data.get("response"):
                        yield token

                    if data.get("done"):
                        yield StreamDone(
                            slot_id=data.get("slot_id"),
                            tokens_predicted=data.get("tokens_predicted", 0),
                            timings=data.get("timings"),
                        )
                        break

    except asyncio.CancelledError:
        logger.debug("stream() cancelled — releasing connection to pool")
        raise
    except httpx.ConnectError as e:
        raise LlamaCppUnavailableError(
            f"Cannot connect to llama.cpp at {self.base_url}"
        ) from e
```

### Integrating Slot Tracking in the SSE Generator

```python
# server.py — inside event_generator_tools(), token loop

from core.inference.engine import StreamDone  # adjust import path

answer_parts: list[str] = []
final_state = None
live_streamed = False

# Look up previously assigned slot for this conversation.
slot_id_in = app_state._active_slots.get(stream_conv_id)

async for chunk in app_state.runtime.run_streaming(
    augmented_question,
    agent_id,
    conversation_id=stream_conv_id,
    intent_query=query_text,
    slot_id=slot_id_in,          # ← pass slot hint to the provider layer
):
    if isinstance(chunk, StreamRunComplete):
        final_state = chunk.final_state
        if not answer_parts:
            answer_parts = [chunk.answer]
        break

    if isinstance(chunk, StreamDone):
        # Capture slot assigned by llama-server for next turn.
        if chunk.slot_id is not None:
            app_state._active_slots[stream_conv_id] = chunk.slot_id
            logger.debug(
                "Slot {} assigned for conv={}", chunk.slot_id, stream_conv_id
            )
        continue  # StreamDone is metadata, not a token — don't yield it to client

    live_streamed = True
    answer_parts.append(chunk)
    yield f"data: {json.dumps({'token': chunk})}\n\n"
```

> **Provider Layer Note:** The `slot_id` parameter must be threaded through `AgentRuntime.run_streaming()` → `ProviderRegistry.get_chat()` → `InferenceEngine.stream()`. This is an internal refactor of the provider layer and should follow the same non-breaking injection pattern: add `slot_id: int | None = None` as a keyword argument to each intermediate method, defaulting to `None` so existing callers are unaffected.

### Slot Eviction on Conversation End

When a conversation is deleted or its slot should be released:

```python
# server.py — add to the DELETE /conversations/{conv_id} endpoint (or equivalent)

app_state._active_slots.pop(conv_id, None)
```

---

## 8. Step 7 — Wizard & Health Endpoint Pool Participation ✅

### What Changes

`_llamacpp_running()` (used by the `/api/wizard/status` and `/api/wizard/check-llamacpp` endpoints) creates a fresh `httpx.AsyncClient` on every call. This is called on every wizard status poll and wastes connection setup. Refactor it to accept the shared client:

```python
# server.py — replace _llamacpp_running()

async def _llamacpp_running(
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Check llama.cpp health, reusing the shared connection pool when available."""
    timeout = httpx.Timeout(3.0)
    try:
        if client is not None:
            r = await client.get(f"{_LLAMA_CPP_BASE}/health", timeout=timeout)
        else:
            # Fallback for calls before lifespan (e.g., during test setup).
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.get(f"{_LLAMA_CPP_BASE}/health")
        return r.status_code == 200
    except Exception:
        return False
```

Update call sites:

```python
# wizard_status endpoint
running = await _llamacpp_running(client=getattr(app.state, "http_client", None))

# wizard_check_llamacpp endpoint
return {"running": await _llamacpp_running(client=getattr(app.state, "http_client", None))}
```

> **FastAPI Dependency Note:** `app.state` is accessible in route handlers via `Request.app.state`. Add `request: Request` to the wizard endpoint signatures if not already present, or use `app_state` as a module-level reference (consistent with current pattern).

---

## 9. Step 8 — Integration Tests for Each Atomic Change ✅

Each step above is designed to be independently deployable and testable. Below is the complete test matrix:

### Test Matrix

| Step | Test Focus | Tool |
|---|---|---|
| 1 | `app.state.http_client` exists after lifespan startup; is closed after shutdown | `pytest` + `httpx.AsyncClient` mock |
| 2 | `InferenceEngine` uses injected client; does not call `httpx.AsyncClient()` constructor | `pytest` + `unittest.mock.patch` |
| 3 | SSE tokens arrive token-by-token (not batched); `[DONE]` is last frame | `httpx.AsyncClient` streaming consumer |
| 4 | `connect` timeout fires after 5 s when server unreachable | `pytest` + `respx` slow mock |
| 4 | `read=None` does not fire during normal long generation | `pytest` + 35 s mock stream |
| 5 | `CancelledError` in generator closes httpx stream; pool connection is returned | `pytest` + `asyncio.CancelledError` injection |
| 5 | Stall guard raises `InferenceTimeoutError` after `stall_timeout_s` with no tokens | `pytest` + mock `aiter_lines` that hangs |
| 6 | `StreamDone.slot_id` is stored in `_active_slots` after first stream | `pytest` + mock engine |
| 6 | Second request with same `conv_id` sends correct `slot_id` in payload | `respx` request capture |
| 7 | `_llamacpp_running` reuses shared client when available | `unittest.mock` connection count assertion |

### Example — Stall Guard Test

```python
# test_stall_guard.py
import asyncio
import pytest
from core.inference.engine import InferenceEngine, InferenceTimeoutError
import httpx
import respx

@respx.mock
@pytest.mark.asyncio
async def test_stall_guard_raises_after_silence():
    """InferenceTimeoutError must be raised if no token arrives within stall_timeout_s."""
    import json

    async def slow_line_generator():
        yield b'{"response": "tok1"}\n'
        # Simulate a stall: never yield again
        await asyncio.sleep(999)

    engine = InferenceEngine("model")

    with pytest.raises(InferenceTimeoutError, match="stalled"):
        async for _ in engine._guarded_token_iter(
            slow_line_generator().__aiter__(),
            stall_timeout_s=0.1,
        ):
            pass
```

### Example — Token-by-Token SSE Arrival Test

```python
# test_streaming_sse.py
import pytest
import httpx
import json

@pytest.mark.asyncio
async def test_tokens_arrive_incrementally(async_test_client):
    """Each SSE frame must carry exactly one token, not a batch."""
    tokens_received = []
    async with async_test_client.stream(
        "POST",
        "/api/query/stream",
        json={"question": "Count to three", "agent": "general"},
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith("data:") and "[DONE]" not in line:
                payload = json.loads(line[5:].strip())
                if "token" in payload:
                    tokens_received.append(payload["token"])

    # At least 3 tokens; no single token contains the full answer.
    assert len(tokens_received) >= 3
    full_answer = "".join(tokens_received)
    assert len(full_answer) > 0
    # No individual token should be the entire answer.
    assert all(len(t) < len(full_answer) for t in tokens_received)
```

---

## 10. Migration Checklist & Rollback Plan

### Deployment Order (Enforce Strictly)

```
Step 1  →  Step 2  →  Step 3  →  Step 4  →  Step 5  →  Step 6  →  Step 7
```

Each step is additive. No step modifies the public API contract (Pydantic schemas, endpoint signatures, or SSE event format). Steps 1–3 deliver the largest performance gains and should be validated in staging before Steps 4–7.

### Pre-Deployment Checklist

- [x] All existing unit tests pass with zero modifications
- [x] `InferenceEngine` constructed with `http_client=None` still functions correctly (legacy/test path)
- [x] `app.state.http_client` is accessible from all route handlers under test
- [x] `aclose()` called on shared client during shutdown (confirmed via log line)
- [ ] Uvicorn not started with `--limit-max-requests` below expected load
- [ ] llama-server compiled with `--parallel N` matching `max_connections` pool limit

### Rollback Per Step

| Step | Rollback |
|---|---|
| 1 | Remove `http_client` from lifespan; `app.state.http_client` gone — all downstream injection silently falls back to per-request client |
| 2 | Revert `InferenceEngine.__init__` to remove `http_client` parameter; all methods recreate local clients |
| 3 | Revert `event_generator_tools` to prior version from git |
| 4 | Replace `_TIMEOUT_STREAM` / `_TIMEOUT_COMPLETE` constants with `httpx.Timeout(30.0)` |
| 5 | Remove `CancelledError` guards; stall detection disabled |
| 6 | Remove `slot_id` from payload; remove `_active_slots` from `AppState` |
| 7 | Revert `_llamacpp_running` to always create its own client |

### Monitoring After Deployment

Add these log assertions to validate the refactor is working as intended:

```python
# Confirm pool reuse — this should NOT appear per-request after Step 2:
# "httpx.AsyncClient initialised" should appear ONCE at startup.

# Confirm slot reuse — this SHOULD appear for turn 2+ of each conversation:
logger.debug("Slot {} assigned for conv={}", chunk.slot_id, stream_conv_id)

# Confirm no stall timeouts under normal load:
# InferenceTimeoutError should have zero occurrences in steady state.
```

---

## Appendix — Configuration Reference

### Environment Variables (Unchanged)

| Variable | Default | Purpose |
|---|---|---|
| `CEREBRO_LLAMACPP_URL` | `http://127.0.0.1:8080` | llama-server base URL |
| `CEREBRO_API_KEY` | `` (disabled) | Optional API auth header |
| `CEREBRO_INFERENCE_BACKEND` | `llamacpp` | Switch to `claude` for Anthropic API |

### Recommended llama-server Flags (Complement)

```bash
llama-server \
  --model ./models/your-model.gguf \
  --ctx-size 8192 \
  --parallel 4 \          # Match max_connections ÷ ~5 (requests per slot)
  --cache-reuse 256 \     # Enable prefix cache matching (requires llama.cpp ≥ b3500)
  --slots \               # Enable slot API (required for Step 6)
  --host 127.0.0.1 \
  --port 8080
```

`--cache-reuse 256` instructs llama-server to match at least 256 tokens of prefix before reusing a slot's KV cache. Without this flag, Step 6 has no effect even if `slot_id` and `cache_prompt=true` are sent correctly.

---

*This document is revision-controlled alongside the codebase. Update the relevant section after each step is merged and validated.*
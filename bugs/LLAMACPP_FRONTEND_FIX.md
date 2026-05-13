# Fix: llama.cpp → Frontend Connection

## Progress Checklist

### Phase 1 — Wire llama.cpp to the backend & fix status bar
- [x] **1a** `pyproject.toml` — add `python-dotenv>=1.0` dependency
- [x] **1b** `main.py` — call `load_dotenv()` before `os.getenv` reads
- [x] **1c** `make install` — reinstall after dep change
- [x] **2a** `main.py` — read `CEREBRO_LLAMACPP_SIMPLE` env var
- [x] **2b** `main.py` — add simple llamacpp path (skip ModelManager)
- [x] **3**  `.env` — set `CEREBRO_LLAMACPP_SIMPLE=true` + URL + model + profile
- [x] **4a** `ui/tray/server.py` — fix status endpoint: derive real provider name & availability
- [x] **4b** `ui/tray/server.py` — fix status endpoint return: replace hardcoded `provider="ollama"`
- [x] **4c** `core/inference/registry.py` — expose `primary_name` property
- [x] **5a** `ui/tray/src/components/status/OllamaIndicator.tsx` — rewrite as provider-aware `EngineIndicator`
- [x] **5b** `ui/tray/src/components/status/StatusBar.tsx` — pass `provider` prop to indicator

### Phase 2 — Fix "Error: Load failed" on message send
- [x] **7a** `ui/tray/server.py` — always send `[DONE]` after error in `event_generator_tools`
- [x] **7b** `ui/tray/server.py` — always send `[DONE]` after error in `event_generator`
- [x] **8**  `ui/tray/src/api/client.ts` — handle `{error}` SSE events in `queryAgentStream`
- [x] **9**  `ui/tray/src/components/chat/InputArea.tsx` — replace "Load failed" with actionable message

---

## Root Cause Summary

| # | Symptom | Cause |
|---|---------|-------|
| 1 | "OLLAMA DOWN", model shows `phi3:mini` | `main.py` ignores `.env` → defaults to Ollama; Ollama not running |
| 2 | Even with env vars set, still broken | `INFERENCE_BACKEND=llamacpp` activates `ModelManager` which spawns its own llama-server on 8080/8081/8082, conflicting with `make engine` |
| 3 | Status bar always shows "Ollama" | `server.py:704` hardcodes `provider="ollama"` |
| 4 | Indicator always says "Ollama OK/down" | `OllamaIndicator.tsx` ignores the `provider` field |
| 5 | "Error: Load failed" on send | Backend port 7842 not reachable (backend not started with `make run`) |
| 6 | Silent empty response on send | Stream error SSE `{"error":"..."}` is ignored by client; `[DONE]` never sent |

**Correct workflow**: `make engine` → single llama-server on port 8080. `make run` → Python API on 7842. They talk directly. No `ModelManager` needed.

---

## Phase 1 — Wire llama.cpp to the Backend & Fix Status Bar

---

### Step 1a — Add `python-dotenv` dependency

**File**: `cerebro/pyproject.toml`

In the `[project]` `dependencies` list, add:
```toml
"python-dotenv>=1.0",
```

---

### Step 1b — Load `.env` at startup

**File**: `cerebro/main.py`

Add two lines at the very top, immediately after `from __future__ import annotations` and before `import os`:

```python
from dotenv import load_dotenv
load_dotenv()  # no-op if .env is absent
```

---

### Step 1c — Reinstall dependencies

Run from `cerebro/`:
```bash
make install
```

---

### Step 2a — Read the new env var

**File**: `cerebro/main.py`

Add after the existing env-var block (around line 37, after `LLAMACPP_PROFILE`):

```python
LLAMACPP_SIMPLE = os.getenv("CEREBRO_LLAMACPP_SIMPLE", "false").lower() == "true"
```

---

### Step 2b — Add simple llamacpp path in `_build_app_state`

**File**: `cerebro/main.py`

Replace the entire `if INFERENCE_BACKEND == "llamacpp":` block (lines 54–74) with:

```python
if INFERENCE_BACKEND == "llamacpp":
    from core.inference.providers.llamacpp_embedding_provider import LlamaCppEmbeddingProvider

    if LLAMACPP_SIMPLE:
        # Direct connection to the llama-server started by `make engine` on port 8080.
        # No ModelManager, no port conflicts.
        llamacpp_chat = LlamaCppChatProvider(
            model=LLAMACPP_MODEL,
            base_url=LLAMACPP_URL,
            profile=LLAMACPP_PROFILE,
        )
        registry.register("llamacpp", llamacpp_chat, embed)
        registry.set_primary("llamacpp")
        logger.info(
            "Inference: llama.cpp simple mode → {} (no model swapping)", LLAMACPP_URL
        )
    else:
        # Full model-swapping mode: ModelManager spawns router + specialist + embed servers.
        model_manager = ModelManager()
        llm_router = LLMRouter()
        app_state.model_manager = model_manager

        embed = LlamaCppEmbeddingProvider(base_url=model_manager.embed_url)
        llamacpp_chat = LlamaCppChatProvider(
            model=LLAMACPP_MODEL,
            base_url=model_manager.specialist_url,
            profile=LLAMACPP_PROFILE,
        )
        registry.register("llamacpp", llamacpp_chat, embed)
        registry.register(
            "ollama",
            ollama_chat,
            OllamaEmbeddingProvider(model=EMBED_MODEL, base_url=OLLAMA_URL),
        )
        logger.info(
            "Inference: llama.cpp model swapping (specialist {}, embeddings {}), Ollama fallback",
            model_manager.specialist_url,
            model_manager.embed_url,
        )
```

---

### Step 3 — Update `.env`

**File**: `cerebro/.env`

Add or update these lines (leave all `CEREBRO_ROUTER_*` / `CEREBRO_SPECIALIST_*` vars in place — they're only read when `CEREBRO_LLAMACPP_SIMPLE=false`):

```dotenv
CEREBRO_INFERENCE_BACKEND=llamacpp
CEREBRO_LLAMACPP_SIMPLE=true
CEREBRO_LLAMACPP_URL=http://127.0.0.1:8080
CEREBRO_LLAMACPP_MODEL=Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf
CEREBRO_LLAMACPP_PROFILE=chat
```

---

### Step 4a — Fix status endpoint: derive real provider

**File**: `ui/tray/server.py` — `status_endpoint()` function (~line 674)

Replace:
```python
    ollama_ok = False
    model_name = "phi3:mini"
    if app_state.provider_registry is not None:
        try:
            chat = app_state.provider_registry.get_chat()
            ollama_ok = chat.is_available()
            model_name = chat.model_id()
        except Exception:
            pass
```

With:
```python
    engine_ok = False
    model_name = "—"
    active_provider = "unknown"
    if app_state.provider_registry is not None:
        try:
            chat = app_state.provider_registry.get_chat()
            engine_ok = chat.is_available()
            model_name = chat.model_id()
            active_provider = app_state.provider_registry.primary_name
        except Exception:
            pass
```

---

### Step 4b — Fix status endpoint: return real provider name

**File**: `ui/tray/server.py` — `StatusResponse(...)` return (~line 700)

Replace:
```python
    return StatusResponse(
        indexed_files=indexed_files,
        ollama_ok=ollama_ok,
        model=model_name,
        provider="ollama",
```

With:
```python
    return StatusResponse(
        indexed_files=indexed_files,
        ollama_ok=engine_ok,
        model=model_name,
        provider=active_provider,
```

---

### Step 4c — Expose `primary_name` on `ProviderRegistry`

**File**: `core/inference/registry.py`

The internal attribute is `self._primary_name` (line 68). Add this property anywhere inside `ProviderRegistry`, after `set_primary`:

```python
@property
def primary_name(self) -> str:
    return self._primary_name or "unknown"
```

---

### Step 5a — Rewrite `OllamaIndicator` as provider-aware `EngineIndicator`

**File**: `ui/tray/src/components/status/OllamaIndicator.tsx`

Replace the entire file content with:

```tsx
interface EngineIndicatorProps {
  ok: boolean;
  provider?: string;
}

export default function EngineIndicator({ ok, provider }: EngineIndicatorProps) {
  const label =
    provider === "llamacpp" ? "llama.cpp" :
    provider === "mlx"      ? "MLX"       : "Ollama";
  return (
    <div className="flex items-center gap-1">
      <div
        className={`w-[6px] h-[6px] rounded-full ${
          ok ? "bg-[#4ade80]" : "bg-[#ffb4ab]"
        }`}
      />
      <span className={ok ? "text-[#4ade80]" : "text-[#ffb4ab]"}>
        {ok ? `${label} OK` : `${label} down`}
      </span>
    </div>
  );
}
```

---

### Step 5b — Update `StatusBar.tsx` to use `EngineIndicator`

**File**: `ui/tray/src/components/status/StatusBar.tsx`

Change the import from:
```tsx
import OllamaIndicator from "./OllamaIndicator";
```
To:
```tsx
import EngineIndicator from "./OllamaIndicator";
```

Change the render call from:
```tsx
<OllamaIndicator ok={ollamaOk} />
```
To:
```tsx
<EngineIndicator ok={ollamaOk} provider={status?.provider} />
```

---

## Phase 2 — Fix "Error: Load failed" on Message Send

**Two distinct failure modes:**

- **Failure A** — Backend port 7842 not listening → `fetch()` in WebKit throws `TypeError: Load failed` → `InputArea.tsx` shows raw `"Error: Load failed"` with no context.
- **Failure B** — Backend running but LLM unreachable → streaming endpoint yields `{"error":"..."}` SSE event then returns **without `[DONE]`** → client silently drops the event, assistant message stays empty.

---

### Step 7a — Always send `[DONE]` after error in `event_generator_tools`

**File**: `ui/tray/server.py` — inside `event_generator_tools()` (~line 472)

Replace:
```python
            except Exception as exc:
                logger.exception("Runtime error during /query/stream (tools path)")
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                return
```

With:
```python
            except Exception as exc:
                logger.exception("Runtime error during /query/stream (tools path)")
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
                yield "data: [DONE]\n\n"
                return
```

---

### Step 7b — Always send `[DONE]` after error in `event_generator`

**File**: `ui/tray/server.py` — inside `event_generator()` (~line 537)

Replace:
```python
        except Exception as exc:
            logger.exception("Streaming error during /query/stream")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            return
```

With:
```python
        except Exception as exc:
            logger.exception("Streaming error during /query/stream")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"
            return
```

---

### Step 8 — Handle `{error}` SSE events in `queryAgentStream`

**File**: `ui/tray/src/api/client.ts` — inside the SSE `for` loop (~line 89)

Replace:
```typescript
        try {
          const parsed = JSON.parse(payload) as Record<string, unknown>;
          if (typeof parsed.token === "string") {
            onToken(parsed.token);
          } else if (parsed.metadata) {
            metadata = parsed.metadata as ResponseMetadata;
            if (typeof parsed.conversation_id === "string") {
              onConversationId?.(parsed.conversation_id);
            }
          }
        } catch {
          // ignore malformed SSE lines
        }
```

With:
```typescript
        let streamError: string | null = null;
        try {
          const parsed = JSON.parse(payload) as Record<string, unknown>;
          if (typeof parsed.token === "string") {
            onToken(parsed.token);
          } else if (parsed.metadata) {
            metadata = parsed.metadata as ResponseMetadata;
            if (typeof parsed.conversation_id === "string") {
              onConversationId?.(parsed.conversation_id);
            }
          } else if (typeof parsed.error === "string") {
            streamError = parsed.error;
          }
        } catch {
          // ignore malformed SSE lines
        }
        if (streamError) throw new Error(streamError);
```

The `throw` is outside the `try/catch` so the error propagates to `InputArea.tsx`.

---

### Step 9 — Replace "Load failed" with actionable message

**File**: `ui/tray/src/components/chat/InputArea.tsx` — catch block (~line 108)

Replace:
```tsx
    } catch (e: unknown) {
      if ((e as Error).name !== "AbortError") {
        updateMessage(assistantId, {
          content: `Error: ${(e as Error).message ?? "Request failed"}`,
        });
      }
    }
```

With:
```tsx
    } catch (e: unknown) {
      if ((e as Error).name !== "AbortError") {
        const msg = (e as Error).message ?? "Request failed";
        const isNetworkDown =
          msg === "Load failed" ||
          msg === "Failed to fetch" ||
          msg === "Network request failed";
        updateMessage(assistantId, {
          content: isNetworkDown
            ? "Cannot reach the backend. Make sure `make run` is running on port 7842."
            : `Error: ${msg}`,
        });
      }
    }
```

---

## Verification

Start everything in order:

```bash
# Terminal 1 — LLM engine
cd cerebro && make engine       # llama-server on port 8080

# Terminal 2 — Python API
cd cerebro && make run          # FastAPI on port 7842 (now loads .env)

# Terminal 3 — Frontend
cd cerebro/ui/tray && npm run dev
```

Expected results:
- Status bar shows **`llama.cpp OK`** (green dot)
- Model name shows `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf`
- RAM gauge reads real system memory
- Sending a message returns a response (no "Load failed")
- If llama-server is down, shows `"llama.cpp down"` (red dot) and a clear error on send

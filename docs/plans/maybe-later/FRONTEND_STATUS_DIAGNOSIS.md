> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


# Frontend Status Diagnosis

## Symptoms

| What you see | What it should say |
|---|---|
| "OLLAMA DOWN" in status bar | "llama.cpp OK" |
| `—` for model, RAM 0 / 0, 0 files | Real values |
| "Cannot reach the backend…" on send | LLM response |
| `phi3:mini · ollama` badge at top | `Qwen_Qwen3-4B… · llamacpp` |

---

## Root Cause 1 — Backend is not running (primary)

**Port 7842 has nothing listening.**

`make run` was never started, so every request from the frontend fails:

- `/api/status` → network error → status store keeps `null` → status bar shows all
  zeros and defaults (`model = "—"`, `ollama_ok = false`)
- `/api/query/stream` → WebKit throws `"Load failed"` → InputArea shows the
  actionable error we wired in Phase 2

**Fix**: open a terminal in `cerebro/` and run:

```bash
make engine   # terminal 1 — llama-server on :8080
make run      # terminal 2 — FastAPI on :7842
```

---

## Root Cause 2 — Model badge hardcodes `· ollama`

**File**: `ui/tray/src/components/shared/AgentSelectorDropdown.tsx` line 110

```tsx
{model} · ollama   // ← "ollama" is a string literal, never changes
```

`model` comes from `status?.model ?? "phi3:mini"`, so:

- Backend down → `status` is `null` → shows `phi3:mini · ollama`
- Backend up (llamacpp) → shows correct model name but still `· ollama`

**Fix**: read `status?.provider` and map it exactly like `EngineIndicator` does.
This is already fixed in this branch — see below.

---

## Root Cause 3 — Status bar default model is `"phi3:mini"`

**File**: `ui/tray/src/components/shared/AgentSelectorDropdown.tsx` line 66

```tsx
const model = status?.model ?? "phi3:mini";
```

When the backend is down and `status` is `null`, the fallback is `"phi3:mini"` — the
old Ollama model — instead of something neutral like `"—"`.

**Fix**: change the fallback to `"—"` (also fixed below).

---

## Fix Applied — `AgentSelectorDropdown.tsx`

```tsx
// Before
const model = status?.model ?? "phi3:mini";
// …
{model} · ollama

// After
const model = status?.model ?? "—";
const providerLabel =
  status?.provider === "llamacpp" ? "llama.cpp" :
  status?.provider === "mlx"      ? "MLX"       :
  status?.provider === "ollama"   ? "Ollama"    : "—";
// …
{model} · {providerLabel}
```

---

## Full Startup Order

```bash
# Terminal 1
cd cerebro && make engine      # llama-server on :8080

# Terminal 2
cd cerebro && make run         # FastAPI on :7842  (reads .env → llamacpp simple mode)

# Terminal 3
cd cerebro/ui/tray && npx tauri dev
```

Expected state once all three are running:

| Element | Expected |
|---|---|
| Badge (top) | `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · llama.cpp` |
| Status bar engine indicator | `llama.cpp OK` (green) |
| Status bar model | `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| RAM gauge | real system memory |
| Chat send | LLM response, no error |

# Claude API — Frontend Integration
## Modular implementation path for Claude Code

This file drives the frontend work to let users switch between **Local** (llama.cpp / MLX) and **Claude API** modes without touching the terminal. Each module is self-contained and can be implemented in order.

**What changes:** status bar, engine badge, model selector, settings backend toggle, and wizard flow.  
**What does NOT change:** chat logic, streaming, tool confirmation, conversation history — those already work with either backend because the API contract (`/api/query/stream`) is identical.

---

## Current state (read before starting)

| File | Relevant current behaviour |
|---|---|
| `api/types.ts:88` | `StatusResponse.provider: string` — already returned by backend |
| `api/types.ts:128` | `LocalModel.provider: "llamacpp" \| "mlx"` — no `"claude"` |
| `api/types.ts:111` | `AppConfig` — no `inference_backend` field |
| `components/status/EngineIndicator.tsx:8` | Only handles `"mlx"` and falls back to `"llama.cpp"` |
| `components/status/StatusBar.tsx:20` | Always renders `RamGauge` — irrelevant in cloud mode |
| `components/settings/ModelSelector.tsx:56` | Always shows local GGUF / MLX pickers |
| `components/settings/SettingsPanel.tsx:62` | No backend toggle section |
| `stores/wizard.ts` | 3 fixed steps; no backend-choice step |
| `components/wizard/WizardShell.tsx:71` | Always shows `StepLlamaCpp` then `StepModel` |

---

## Module F1 — Types: add Claude to the type system

**File:** `cerebro/ui/tray/src/api/types.ts`

### 1a. Add `"claude"` to `LocalModel.provider`

```ts
// line 128 — current:
export interface LocalModel {
  name: string;
  size_gb: number;
  provider: "llamacpp" | "mlx";
}

// replace with:
export interface LocalModel {
  name: string;
  size_gb: number;
  provider: "llamacpp" | "mlx" | "claude";
}
```

### 1b. Add `inference_backend` to `AppConfig`

```ts
// line 111 — after `embedding_model: string;` add:
  inference_backend: "llamacpp" | "claude";
```

### 1c. Add `CLAUDE_MODELS` constant (static list, no backend needed)

Append to the bottom of `types.ts`:

```ts
export interface ClaudeModel {
  id: string;
  label: string;
  context_k: number;
  note: string;
}

export const CLAUDE_MODELS: ClaudeModel[] = [
  { id: "claude-opus-4-7",            label: "Claude Opus 4.7",   context_k: 200, note: "Most capable" },
  { id: "claude-sonnet-4-6",          label: "Claude Sonnet 4.6", context_k: 200, note: "Best balance (default)" },
  { id: "claude-haiku-4-5-20251001",  label: "Claude Haiku 4.5",  context_k: 200, note: "Fastest · lowest cost" },
];
```

### 1d. Update `DEFAULT_CONFIG` in `stores/settings.ts`

```ts
// stores/settings.ts line 32 — add the new field to DEFAULT_CONFIG:
const DEFAULT_CONFIG: AppConfig = {
  model: "phi3:mini",
  watched_folders: [],
  tool_permissions: { ... },   // unchanged
  dnd_enabled: false,
  embedding_model: "nomic-embed-text",
  inference_backend: "llamacpp",   // ← add this
};
```

---

## Module F2 — API client: backend switch call

**File:** `cerebro/ui/tray/src/api/client.ts`

No new endpoint needed — `updateConfig` already sends a PATCH. Add a typed helper so callers don't pass raw strings:

```ts
// add after updateConfig():
export async function switchInferenceBackend(
  backend: "llamacpp" | "claude"
): Promise<AppConfig> {
  return updateConfig({ inference_backend: backend });
}
```

---

## Module F3 — System store: `isClaudeMode` selector

**File:** `cerebro/ui/tray/src/stores/system.ts`

Add a selector at the bottom of the file (outside the store, no store change needed):

```ts
// add at the bottom of system.ts:
export function selectIsClaudeMode(status: StatusResponse | null): boolean {
  return status?.provider === "claude";
}
```

Components import this and call `selectIsClaudeMode(useSystemStore(s => s.status))`.

---

## Module F4 — EngineIndicator: Claude badge

**File:** `cerebro/ui/tray/src/components/status/EngineIndicator.tsx`

Full replacement (component is small):

```tsx
interface EngineIndicatorProps {
  ok: boolean;
  provider?: string;
}

export default function EngineIndicator({ ok, provider }: EngineIndicatorProps) {
  if (provider === "claude") {
    return (
      <div className="flex items-center gap-1">
        <div className="w-[6px] h-[6px] rounded-full bg-[#a78bfa]" />
        <span className="text-[#a78bfa]">Claude API</span>
      </div>
    );
  }

  const label = provider === "mlx" ? "MLX" : "llama.cpp";
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

**Visual result:** purple dot + "Claude API" text in Claude mode; existing green/red for local modes.

---

## Module F5 — StatusBar: hide RAM gauge in Claude mode

**File:** `cerebro/ui/tray/src/components/status/StatusBar.tsx`

Import `selectIsClaudeMode` and conditionally render the right group:

```tsx
import { selectIsClaudeMode } from "../../stores/system";

// inside StatusBar(), after existing const declarations:
const isCloud = selectIsClaudeMode(status);

// Replace the Right group JSX:
{/* Right group */}
<div className="flex items-center gap-3">
  {isCloud ? (
    <span className="opacity-60">cloud inference</span>
  ) : (
    <>
      <RamGauge used={ramUsed} total={ramTotal} />
      <span className="opacity-20">•</span>
    </>
  )}
  <LatencyBadge p95={p95} />
  <span className="opacity-20">•</span>
  <span>{queries} queries</span>
</div>
```

In Claude mode: RAM gauge is hidden (irrelevant — inference runs remotely), replaced by the static label `"cloud inference"`. Latency and query count still show because they come from the backend metrics.

---

## Module F6 — ModelSelector: Claude mode panel

**File:** `cerebro/ui/tray/src/components/settings/ModelSelector.tsx`

### 6a. Import what's needed at the top

```ts
import { useSystemStore, selectIsClaudeMode } from "../../stores/system";
import { CLAUDE_MODELS } from "../../api/types";
```

### 6b. Read current mode inside the component

```ts
export default function ModelSelector() {
  const { models, activeModel, llamaCppModels, llamaCppLoading, patch } = useSettingsStore();
  const status = useSystemStore((s) => s.status);
  const isCloud = selectIsClaudeMode(status);

  // ... rest unchanged until return
```

### 6c. Conditional render — add before the existing `return`

```tsx
  if (isCloud) {
    return (
      <section className="space-y-4">
        <p className="text-[10px] font-mono uppercase tracking-widest text-[#928ea0] mb-1 px-1">
          Cloud · Claude API
        </p>
        <div className="space-y-1">
          {CLAUDE_MODELS.map((m) => (
            <div
              key={m.id}
              className={`flex items-center justify-between p-2 rounded-[6px] ${
                status?.model === m.id ? "bg-[#242736] border-l-2 border-[#a78bfa]" : "opacity-50"
              }`}
            >
              <div className="flex flex-col">
                <span className="text-[13px] font-semibold text-[#e5e0ed]">{m.label}</span>
                <span className="text-[10px] font-mono text-[#c9c4d7]">{m.note}</span>
              </div>
              <span className="bg-[#1a1d27] px-1.5 py-0.5 rounded text-[10px] font-mono text-[#a78bfa]">
                {m.context_k}K ctx
              </span>
            </div>
          ))}
        </div>
        <p className="text-[10px] font-mono text-[#474554] px-2">
          Active model set via{" "}
          <span className="text-[#94a3b8]">CEREBRO_CLAUDE_MODEL</span> env var
        </p>

        {/* Embedding notice — always shown */}
        <div className="flex items-center gap-2 px-2 py-1 bg-[#0e0d15] border border-[#242736] rounded">
          <span className="text-[11px] text-[#8b8fa8] font-mono">
            Embedding: nomic-embed-text (local, always)
          </span>
        </div>
      </section>
    );
  }

  // existing local-mode return below — unchanged
  return ( ... );
```

---

## Module F7 — SettingsPanel: backend toggle section

**File:** `cerebro/ui/tray/src/components/settings/SettingsPanel.tsx`

### 7a. Imports

```ts
import { useSystemStore, selectIsClaudeMode } from "../../stores/system";
import { switchInferenceBackend } from "../../api/client";
import { useState } from "react";
```

### 7b. Add inside `SettingsPanel()` component body

```ts
const status = useSystemStore((s) => s.status);
const isCloud = selectIsClaudeMode(status);
const [switching, setSwitching] = useState(false);

const handleBackendSwitch = async (backend: "llamacpp" | "claude") => {
  setSwitching(true);
  try {
    await switchInferenceBackend(backend);
  } finally {
    setSwitching(false);
  }
};
```

### 7c. Add a "Backend" section to the scrollable content — insert BEFORE the existing "Model" section

```tsx
{/* Backend */}
<section>
  <label className="block text-[11px] font-bold tracking-[0.05em] text-[#8b8fa8] uppercase mb-2">
    Inference Backend
  </label>
  <div className="flex gap-2">
    <button
      onClick={() => void handleBackendSwitch("llamacpp")}
      disabled={switching || !isCloud}
      className={`flex-1 py-2 rounded-[6px] text-[12px] font-semibold transition-colors ${
        !isCloud
          ? "bg-[#242736] border border-[#94a3b8] text-[#e5e0ed]"
          : "bg-[#1a1d27] border border-[#242736] text-[#474554] hover:border-[#474554]"
      }`}
    >
      Local
    </button>
    <button
      onClick={() => void handleBackendSwitch("claude")}
      disabled={switching || isCloud}
      className={`flex-1 py-2 rounded-[6px] text-[12px] font-semibold transition-colors ${
        isCloud
          ? "bg-[#2d1f4a] border border-[#a78bfa] text-[#a78bfa]"
          : "bg-[#1a1d27] border border-[#242736] text-[#474554] hover:border-[#474554]"
      }`}
    >
      Claude API
    </button>
  </div>
  <p className="text-[10px] font-mono text-[#474554] mt-1 px-1">
    {isCloud
      ? "Restart backend to apply · set ANTHROPIC_API_KEY"
      : "Restart backend to apply · set CEREBRO_INFERENCE_BACKEND=claude"}
  </p>
</section>
```

**Visual result:** two toggle buttons, active one is highlighted (green border = local, purple border = Claude API). Switching saves to config; the hint reminds the user a backend restart is needed.

---

## Module F8 — SettingsPanel footer: engine status

**File:** `cerebro/ui/tray/src/components/settings/SettingsPanel.tsx`

The `<footer>` inside `SettingsPanel` currently hard-codes a green "Engine OK" dot. Update it to reflect the active provider:

```tsx
{/* bottom of SettingsPanel aside, replace existing footer: */}
<footer className="h-[28px] bg-[#1a1d27] border-t border-[#242736] flex items-center justify-between px-3 shrink-0">
  <div className="flex items-center gap-1">
    <div
      className={`w-1.5 h-1.5 rounded-full ${
        isCloud ? "bg-[#a78bfa]" : status?.engine_ok ? "bg-[#4ade80]" : "bg-[#ffb4ab]"
      }`}
    />
    <span
      className={`text-[10px] font-bold tracking-[0.05em] uppercase ${
        isCloud ? "text-[#a78bfa]" : status?.engine_ok ? "text-[#4ade80]" : "text-[#ffb4ab]"
      }`}
    >
      {isCloud ? "Claude API" : status?.engine_ok ? "Engine OK" : "Engine down"}
    </span>
  </div>
</footer>
```

---

## Module F9 — Wizard: backend selection step

The wizard currently assumes llama.cpp. In Claude API mode, steps 0 (llama.cpp check) and 1 (model check) are irrelevant. The fix is: add a step 0 where the user picks **Local** or **Claude API**, then either show the existing steps or jump straight to folders.

### 9a. `stores/wizard.ts` — expand step count and add mode state

Full replacement:

```ts
import { create } from "zustand";

type WizardMode = "local" | "claude";

interface WizardState {
  currentStep: 0 | 1 | 2 | 3;
  mode: WizardMode | null;
  isComplete: boolean;
  setMode: (m: WizardMode) => void;
  advance: () => void;
  complete: () => void;
  reset: () => void;
}

export const useWizardStore = create<WizardState>((set, get) => ({
  currentStep: 0,
  mode: null,
  isComplete: false,

  setMode: (m) => set({ mode: m }),

  advance: () => {
    const { currentStep, mode } = get();
    if (currentStep === 0) {
      // After mode pick: local goes to step 1 (llama.cpp check), claude jumps to step 3 (folders)
      set({ currentStep: mode === "claude" ? 3 : 1 });
      return;
    }
    const next = currentStep + 1;
    if (next > 3) {
      set({ isComplete: true });
    } else {
      set({ currentStep: next as 1 | 2 | 3 });
    }
  },

  complete: () => set({ isComplete: true }),
  reset: () => set({ currentStep: 0, mode: null, isComplete: false }),
}));
```

### 9b. New file: `components/wizard/StepBackend.tsx`

```tsx
import { useWizardStore } from "../../stores/wizard";

interface StepBackendProps {
  onReady: (ready: boolean) => void;
}

export default function StepBackend({ onReady }: StepBackendProps) {
  const { mode, setMode } = useWizardStore();

  const pick = (m: "local" | "claude") => {
    setMode(m);
    onReady(true);
  };

  return (
    <div className="w-full space-y-3 mb-6">
      <p className="text-[14px] leading-[20px] text-[#e8eaf0] text-center">
        Choose how Cerebro runs inference.
      </p>

      {/* Local option */}
      <button
        onClick={() => pick("local")}
        className={`w-full p-4 rounded-lg border text-left transition-colors ${
          mode === "local"
            ? "border-[#94a3b8] bg-[#1a2030]"
            : "border-[#242736] bg-[#0f1117] hover:border-[#474554]"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`w-2 h-2 rounded-full ${mode === "local" ? "bg-[#4ade80]" : "bg-[#474554]"}`} />
          <span className="text-[14px] font-semibold text-[#e5e0ed]">Local · llama.cpp</span>
        </div>
        <p className="text-[12px] text-[#8b8fa8] pl-4">
          Runs entirely on-device. Private. Requires 4–8 GB RAM.
        </p>
      </button>

      {/* Claude API option */}
      <button
        onClick={() => pick("claude")}
        className={`w-full p-4 rounded-lg border text-left transition-colors ${
          mode === "claude"
            ? "border-[#a78bfa] bg-[#1a1030]"
            : "border-[#242736] bg-[#0f1117] hover:border-[#474554]"
        }`}
      >
        <div className="flex items-center gap-2 mb-1">
          <div className={`w-2 h-2 rounded-full ${mode === "claude" ? "bg-[#a78bfa]" : "bg-[#474554]"}`} />
          <span className="text-[14px] font-semibold text-[#e5e0ed]">Cloud · Claude API</span>
        </div>
        <p className="text-[12px] text-[#8b8fa8] pl-4">
          Anthropic's frontier models. 200K context. Requires{" "}
          <code className="text-[#a78bfa] bg-[#1a1030] px-1 rounded">ANTHROPIC_API_KEY</code>.
        </p>
      </button>
    </div>
  );
}
```

### 9c. `components/wizard/WizardShell.tsx` — wire the new step

```tsx
import StepBackend from "./StepBackend";
// keep existing StepLlamaCpp, StepModel, StepFolders imports

// Inside WizardShell():
const { currentStep, mode } = useWizardStore();

// Step content block — replace the three conditionals:
{currentStep === 0 && <StepBackend onReady={setStepReady} />}
{currentStep === 1 && mode === "local" && <StepLlamaCpp onReady={setStepReady} />}
{currentStep === 2 && mode === "local" && <StepModel onReady={setStepReady} />}
{currentStep === 3 && <StepFolders onReady={handleFolderReady} />}
```

Update `WizardDots` call to use a max of 4 dots in local mode and 2 in Claude mode:

```tsx
<WizardDots currentStep={currentStep} total={mode === "claude" ? 2 : 4} />
```

Update `WizardDots.tsx` to accept a `total` prop if it currently hard-codes 3 dots.

### 9d. `components/wizard/WizardDots.tsx` — accept `total` prop

Check current implementation and update the dots render to use `total` instead of the hard-coded value (likely `Array.from({length: 3})`).

---

## Module F10 — Header: provider badge (optional, low priority)

**File:** `cerebro/ui/tray/src/layouts/Header.tsx`

A small visual touch — show a purple "API" badge next to the logo in Claude mode:

```tsx
import { useSystemStore, selectIsClaudeMode } from "../stores/system";

// inside Header():
const isCloud = selectIsClaudeMode(useSystemStore((s) => s.status));

// After the logo img:
{isCloud && (
  <span className="text-[9px] font-bold tracking-widest uppercase px-1.5 py-0.5 rounded bg-[#2d1f4a] text-[#a78bfa] font-mono">
    API
  </span>
)}
```

---

## Implementation order

Run these in sequence. Each module compiles independently.

```
F1  ✅ types.ts + DEFAULT_CONFIG          (foundation — do first)
F2  ✅ api/client.ts                      (1 helper function)
F3  ✅ stores/system.ts                   (1 selector)
F4  ✅ EngineIndicator.tsx                (self-contained, tiny)
F5  ✅ StatusBar.tsx                      (reads F3 selector)
F6  ✅ ModelSelector.tsx                  (reads F3 selector)
F7  ✅ SettingsPanel.tsx backend toggle   (reads F3, calls F2)
F8  ✅ SettingsPanel.tsx footer           (same file, finish it)
F9  ✅ wizard store + StepBackend +       (can be done last)
      WizardShell wiring + WizardDots
F10 ✅ Header badge                       (optional cosmetic)
```

---

## Files changed / created

| File | Action |
|---|---|
| `src/api/types.ts` | Edit — add `"claude"` to provider union, `inference_backend` to `AppConfig`, `CLAUDE_MODELS` constant |
| `src/api/client.ts` | Edit — add `switchInferenceBackend()` |
| `src/stores/system.ts` | Edit — add `selectIsClaudeMode` selector |
| `src/stores/settings.ts` | Edit — add `inference_backend` to `DEFAULT_CONFIG` |
| `src/stores/wizard.ts` | Edit — add `mode` state + new 4-step logic |
| `src/components/status/EngineIndicator.tsx` | Edit — Claude API branch |
| `src/components/status/StatusBar.tsx` | Edit — hide RAM gauge in cloud mode |
| `src/components/settings/ModelSelector.tsx` | Edit — Claude mode panel |
| `src/components/settings/SettingsPanel.tsx` | Edit — backend toggle + footer |
| `src/components/wizard/StepBackend.tsx` | **Create** — new backend-picker step |
| `src/components/wizard/WizardShell.tsx` | Edit — wire `StepBackend`, update step routing |
| `src/components/wizard/WizardDots.tsx` | Edit — accept `total` prop |
| `src/layouts/Header.tsx` | Edit — API badge (optional) |

---

## Backend config endpoint (required for F7 toggle)

For the settings toggle (F7) to persist, the backend's `/api/config` PATCH endpoint must accept and save `inference_backend`. This is a 2-line backend change in `ui/tray/server.py` — add `inference_backend: Optional[str]` to the `ConfigPatch` Pydantic model and write it to `settings.toml`. The frontend already sends it via `updateConfig()`.

The actual backend switch still requires a process restart — this is expected and communicated to the user via the hint text in F7.

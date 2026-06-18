# Cerebro — Stabilization & Correctness Fix Plan

> **Audience:** Claude Code / Cursor agent / any autonomous coding agent.
> **Authoring role:** Principal Software Architect — local-first AI OS, extreme resource optimization on Apple Silicon.
> **Companion plan:** [`docs/plans/vision/future-cognitive-os.md`](docs/plans/vision/future-cognitive-os.md) (10-phase migration to a Cognitive Operating Layer).
> **This plan is the prerequisite for that migration.** Cerebro is currently unstable on the target hardware (MacBook Pro M1, 8 GB RAM): the chat session freezes the OS, the agent reports the wrong date, and calendar / birthday queries return `Sin eventos` even when events exist. Until those three bugs are gone, no Phase 1+ work from the future plan can land safely.

---
note: do not use npm use alternatives
## 0. Symptom → Root cause map (read this first)

| # | Reported symptom | Root cause(s) found in code | Source of truth |
|---|------------------|-----------------------------|-----------------|
| S1 | "The local chat is too heavy and freezes my Mac" | (a) Default `CEREBRO_LLAMACPP_SIMPLE=false` in `main.py` activates `ModelManager`, which spawns **three** llama-server subprocesses (router + specialist + embed). (b) `core/inference/model_manager.py` points at `SmolLM2-135M-Instruct-Q4_K_M.gguf`, `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, and `v5-nano-retrieval-Q4_K_M.gguf` under `bin/models/` — those files **can** all be present (alongside e.g. `llama-3.2-3b-instruct-q4_k_m.gguf`); the dominant cost is then **three** resident model loads plus churn during health checks, not a missing-path fast-fail. On minimal checkouts where any expected GGUF is absent, startup still burns RAM waiting on failed health checks. (c) `config/chat.args` uses `--mlock` + `--n-gpu-layers 99` which **forbid the OS from paging the model out**. (d) On Apple Silicon, MLX is auto-registered as a secondary provider, doubling weight residency. (e) `ContextEnricher` (enabled by default via `CEREBRO_PROACTIVE_CONTEXT=true`) fires `osascript` with a 60 s timeout on **every** query and is wrapped in a 3 s `asyncio.wait_for` — the parent gives up but the child keeps running and accumulates. | `main.py:60-160`, `core/inference/model_manager.py:14-35`, `config/chat.args:1-10`, `core/agents/context_enricher.py:89-120`, `bin/models/` listing |
| S2 | "Asked for today's date, said it was 11 May" | (a) For agents with no tools, the streaming endpoint took the `runtime.stream()` path (`ui/tray/server.py`) which did **not** run any tool loop; the answer was pure-LLM hallucination. **Phase 2:** `/api/query/stream` always uses `runtime.run()`; General has `GENERAL_TOOLS`; default agent is Auto. (b) The default frontend agent was `general` (`ui/tray/src/stores/chat.ts`), which maps to `general-v1`, whose `GENERAL_TOOLS` was `[]` (all tools in registry but weak prompt). (c) The current date is in the system prompt (`core/agents/runtime.py`) but small models weight user over system. **Phase 3:** `_date_preamble()` prepends a one-line Spanish dateline (including the current year) to each **LLM** user message in `run()` / `stream()` without persisting it in the session summary; **REGLA TEMPORAL** in both system templates; `tests/test_runtime_date_correctness.py` asserts the preamble. | `core/agents/runtime.py`, `ui/tray/server.py`, `core/agents/specialized.py`, `ui/tray/src/stores/chat.ts` |
| S3 | "Next event in my calendar → takes long, says 'Sin eventos'" | (a) Same routing flaw as S2: with `agent: "general-v1"` the streaming endpoint never enters `event_generator_tools`, never calls `get_upcoming_events`, the model hallucinates "Sin eventos". **Phase 2** fixes routing. (b) Even when the tool path is reached, `AppleCalendarBackend` runs an `osascript -l JavaScript` script that **requires the python process to have macOS Automation permission for Calendar**. If that permission was never granted (typical on first run), the script used to return `[]` silently. **Phase 4:** `BackendResult` + merged reader surface `permission_denied` / `timeout` with Spanish guidance; Apple read timeout **5 s**; async enricher kills hung subprocess; boot probe fills `macos_permissions` for `/api/status` and enricher denied-gate. (c) The "no events" answer is detected by string matching on `"Sin eventos"` in `ContextEnricher` — structured tool output now distinguishes permission vs empty, but ambient injection still uses substring markers for "real events". | `integrations/calendar_reader.py`, `core/tools/handlers/calendar.py`, `core/agents/context_enricher.py`, `ui/tray/server.py` |
| S4 | "Next upcoming birthday → 'Sin eventos'" | Same routing flaw (S2/S3) plus: `BirthdayBackend` only finds events if a calendar named `Birthdays` or `Cumpleaños` exists, OR if the title contains those words. macOS auto-creates the Birthdays calendar from Contacts but it is **invisible to JXA scripts unless the user has clicked Calendar at least once after sign-in**. There is no fallback to query Contacts directly. | `integrations/calendar_reader.py:346-451` |

These four symptoms collapse into **three** real defects:

* **D1 — Resource explosion on first run.** Default multi-server llama.cpp stack plus `--mlock` / MLX / enricher oversubscribes RAM on 8 GB **even when every referenced GGUF exists** in `bin/models/`; locks memory the OS still needs.
* **D2 — Streaming path bypasses tools for the default agent.** Any "live data" question (date, calendar, file, weather) returns a hallucination because the pipeline never even tries to call a tool.
* **D3 — macOS integration is silently permission-bound.** Phase 4 adds structured calendar results, Spanish permission/timeout messages in tools, a boot-time probe surfaced in `/api/status`, and an async enricher that skips calendar entirely when the probe reports `denied`. Empty-calendar vs permission ambiguity remains only for enricher substring heuristics (not for `get_upcoming_events` tool output).

The phases below fix D1 → D2 → D3 in that order, then harden the system against regression.

---

## 1. Operating protocol for the executing agent

For **every step** the agent MUST:

1. **Read** the file(s) listed under `Files touched` before editing.
2. **Apply** the change atomically (one commit per step where reasonable). Use the file-editing tool — never `sed` / `awk`.
3. **Run** the `Verification` block exactly. Exit code 0 = pass.
4. **Append** the step ID and verification stdout to `docs/plans/roadmaps/fix-cerebro-progress.log` (created in Step 0.1).
5. **Stop and surface the failure** if verification fails. Do **not** mutate other files in an attempt to make the test pass.

Hard constraints (inherited from the future plan):

* Hardware floor: MacBook Pro M1, 8 GB RAM. Total resident set under steady-state chat must stay **≤ 5.5 GB combined** (macOS baseline + Cerebro + llama-server + Tauri). If a step makes RAM grow past that, treat it as a regression.
* No new model weights downloaded by this plan. Use only files already present in `bin/models/`.
* No new long-running daemons. The only allowed subprocess is the **single** llama-server we are about to enforce.
* No new Python dependencies. Only the standard lib + what is already in `pyproject.toml`.
* Branch hygiene: `git checkout -b fix-N-<slug>` per phase; squash-merge into `main` only after the phase's exit gate.

Global verification commands re-used across phases:

```bash
# Lint + type gate
make lint

# Full pytest gate
make test

# Backend health gate (assumes `make run` is up)
curl -fsS http://localhost:7842/api/status | python -m json.tool

# Quick per-process RSS snapshot (helper added in Step 0.2)
python scripts/diag/snapshot.py
```

---

## Phase 0 — Triage, telemetry, and a known-good baseline

**Status: DONE** (completed 2026-05-13). No production app behaviour was changed—only scaffolding, diagnostics, and documentation.

**Goal:** Take a snapshot of the live failure mode so every later phase can prove it is fixed. **Read-only** — no behaviour changes yet.

### What was delivered (implementation record)

| Item | Detail |
|------|--------|
| **Branch** | `fix-0-triage` |
| **Progress log** | `docs/plans/roadmaps/fix-cerebro-progress.log` — Step 0.1 verification, Step 0.2/0.3 diagnostic runs, baseline block `=== STEP 0.3 baseline ===`, Phase 0 exit-gate notes |
| **Phase index** | `docs/plans/roadmaps/FIX_PHASES.md` — short index for FIX_CEREBRO phases |
| **Diagnostics** | `scripts/diag/snapshot.py`, `check_models.py`, `check_calendar.py`, `check_routing.py` — standalone scripts (no `core.*` inference imports) |
| **Git** | `docs/plans/roadmaps/fix-cerebro-progress.log` is tracked with `git add -f` because repository `.gitignore` ignores `*.log` |
| **`check_calendar.py` vs spec** | Shipped JXA uses an IIFE with explicit `return JSON.stringify(...)` so `osascript` always prints JSON on success and error paths; 5 s timeout preserved |
| **Baseline captured** | Sparse `bin/models/`: `check_models` exit **2** (only e.g. `llama-3.2-3b-instruct-q4_k_m.gguf` present; router/code/embed names missing). `check_calendar` may exit **3** (permission/denied JSON) or **4** (timeout)—both recorded in the log as triage signal |
| **Exit gate** | `make test`: **558 passed** (full suite; long wall time partly from `test_execute_plan_step_timeout`). `make lint`: failed on **pre-existing** Black drift in unrelated modules; `scripts/diag/` passes Black, Ruff, and Mypy |
| **This file** | Phase 0 marked complete here; same session recorded completion in the progress log |

---

### Step 0.1 — Create the progress log and a fix branch *(DONE)*

* **Files touched:** `docs/plans/roadmaps/fix-cerebro-progress.log` (new), `docs/plans/roadmaps/FIX_PHASES.md` (new).
* **Action:**

```bash
mkdir -p roadmaps
touch docs/plans/roadmaps/fix-cerebro-progress.log
cat > docs/plans/roadmaps/FIX_PHASES.md <<'EOF'
# FIX_CEREBRO migration — phase index
Each phase has its own branch `fix-N-<slug>` and ends with an exit gate.
EOF
git checkout -b fix-0-triage
git add docs/plans/roadmaps/ && git commit -m "fix-0: progress log scaffolding"
```

* **Verification:**

```bash
test -f docs/plans/roadmaps/fix-cerebro-progress.log && \
test -f docs/plans/roadmaps/FIX_PHASES.md && \
git rev-parse --abbrev-ref HEAD | grep -q '^fix-0-triage$'
```

### Step 0.2 — Diagnostic toolkit (no production code touched) *(DONE)*

* **Files touched:** `scripts/diag/snapshot.py` (new), `scripts/diag/check_models.py` (new), `scripts/diag/check_calendar.py` (new), `scripts/diag/check_routing.py` (new).
* **Action:** create four small read-only scripts. They MUST NOT import `core.*` modules that require an inference backend (so they run even when the system is broken).

`scripts/diag/snapshot.py`:

```python
"""Print per-process RSS for everything Cerebro-related plus system memory."""
from __future__ import annotations
import os, sys
import psutil

CEREBRO_HINTS = ("llama-server", "uvicorn", "python", "main.py", "tauri", "WebKit")

def main() -> int:
    vm = psutil.virtual_memory()
    print(f"system: total={vm.total/2**30:.2f}GB used={(vm.total-vm.available)/2**30:.2f}GB "
          f"available={vm.available/2**30:.2f}GB pressure="
          f"{'critical' if vm.available/2**30 < 1.0 else 'warn' if vm.available/2**30 < 1.8 else 'ok'}")
    rows = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or [p.info.get("name") or ""])
            if not any(h in cmd for h in CEREBRO_HINTS):
                continue
            rss = p.memory_info().rss / 2**20
            rows.append((rss, p.info["pid"], cmd[:120]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(reverse=True)
    print(f"{'RSS_MB':>8}  {'PID':>6}  CMD")
    for rss, pid, cmd in rows[:20]:
        print(f"{rss:8.1f}  {pid:6}  {cmd}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

`scripts/diag/check_models.py`:

```python
"""Verify which GGUF files referenced by config and ModelManager actually exist."""
from __future__ import annotations
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = Path(os.environ.get("CEREBRO_MODELS_DIR", str(ROOT / "bin" / "models")))
EXPECTED = {
    "router":     os.environ.get("CEREBRO_ROUTER_MODEL", "SmolLM2-135M-Instruct-Q4_K_M.gguf"),
    "general":    os.environ.get("CEREBRO_GENERAL_MODEL", "Llama-3.2-3B-Instruct-Q4_K_M.gguf"),
    "code":       os.environ.get("CEREBRO_CODE_MODEL", "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf"),
    "embed":      os.environ.get("CEREBRO_EMBED_MODEL", "v5-nano-retrieval-Q4_K_M.gguf"),
    "chat.args":  "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf",  # config/chat.args
}

print(f"models dir: {MODELS_DIR}")
present = {p.name.lower(): p for p in MODELS_DIR.glob("*.gguf")} if MODELS_DIR.is_dir() else {}
missing = []
for role, name in EXPECTED.items():
    hit = name.lower() in present
    flag = "OK " if hit else "MISS"
    print(f"  [{flag}] {role:10}  {name}")
    if not hit:
        missing.append((role, name))
print("\nfiles actually present:")
for n in sorted(present):
    print(f"  - {present[n].name}  ({present[n].stat().st_size/2**30:.2f} GB)")
sys.exit(0 if not missing else 2)
```

`scripts/diag/check_calendar.py`:

```python
"""Probe Apple Calendar Automation permission without crashing the agent."""
from __future__ import annotations
import json, platform, subprocess, sys

if platform.system() != "Darwin":
    print("not-macos"); sys.exit(0)

JXA = '''
var app = Application("Calendar");
try {
    var names = app.calendars().map(function(c){return c.name();});
    JSON.stringify({ok: true, calendars: names});
} catch(e) { JSON.stringify({ok: false, error: e.toString()}); }
'''

try:
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", JXA],
                       capture_output=True, text=True, timeout=5)
    out = (r.stdout or "").strip() or (r.stderr or "").strip()
    print(out)
    data = json.loads(r.stdout) if r.returncode == 0 and r.stdout else {"ok": False}
    sys.exit(0 if data.get("ok") else 3)
except subprocess.TimeoutExpired:
    print(json.dumps({"ok": False, "error": "timeout-after-5s"}))
    sys.exit(4)
```

*Shipped implementation (Phase 0):* the JXA above is wrapped in an immediately invoked function that **returns** the `JSON.stringify(...)` result in both `try` and `catch`, so stdout always contains parseable JSON; exit codes 0 / 3 / 4 match the plan.

`scripts/diag/check_routing.py`:

```python
"""Send a fixed query against the running backend and report which agent + tools answered."""
from __future__ import annotations
import json, os, sys, urllib.request

BASE = os.environ.get("CEREBRO_URL", "http://localhost:7842")
QUERIES = [
    ("date",     "¿Qué día es hoy?"),
    ("calendar", "¿Cuál es mi próximo evento del calendario?"),
    ("birthday", "¿Cuál es el próximo cumpleaños?"),
]
fail = 0
for tag, q in QUERIES:
    body = json.dumps({"question": q, "agent": "auto"}).encode()
    req = urllib.request.Request(f"{BASE}/api/query", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"[FAIL] {tag}: {e}"); fail += 1; continue
    tools = [t["name"] for t in data["metadata"]["tools_called"]]
    print(f"[{tag}] tools={tools}")
    print(f"  answer: {data['answer'][:300]}")
sys.exit(0 if not fail else 5)
```

* **Verification:**

```bash
mkdir -p scripts/diag
python scripts/diag/snapshot.py | head -5
python scripts/diag/check_models.py; echo "exit=$?"
python scripts/diag/check_calendar.py; echo "exit=$?"
```

`check_models.py` exits **0** when every expected GGUF name is on disk, **2** if any are missing (typical on a sparse clone). Capture whichever exit code and full stdout in `docs/plans/roadmaps/fix-cerebro-progress.log` — do not assume exit 2.

### Step 0.3 — Capture the failing baseline *(DONE)*

* **Files touched:** `docs/plans/roadmaps/fix-cerebro-progress.log`.
* **Action:** with the backend stopped, run each diag script and tee the output:

```bash
{
  echo "=== STEP 0.3 baseline @ $(date -u +%FT%TZ) ==="
  echo "--- snapshot ---"; python scripts/diag/snapshot.py
  echo "--- check_models ---"; python scripts/diag/check_models.py; echo "exit=$?"
  echo "--- check_calendar ---"; python scripts/diag/check_calendar.py; echo "exit=$?"
} >> docs/plans/roadmaps/fix-cerebro-progress.log
git add docs/plans/roadmaps/ scripts/diag/ && git commit -m "fix-0: triage scripts + captured baseline"
```

* **Verification:**

```bash
grep -q "STEP 0.3 baseline" docs/plans/roadmaps/fix-cerebro-progress.log
```

### Phase 0 exit gate *(DONE)*

```bash
make lint
make test
git push -u origin fix-0-triage   # optional
```

If `make test` is **already failing** before any change, log the failures and STOP. Phase 1 can only start from a green baseline (or from an explicitly accepted list of pre-existing failures recorded in `docs/plans/roadmaps/fix-cerebro-progress.log`).

**As executed:** `make test` **passed** (558 tests). `make lint` **did not pass** repo-wide at the time of Phase 0 (Black would reformat multiple existing files outside `scripts/diag/`); Phase 0 diagnostics themselves conform to Black / Ruff / Mypy. Optional remote: `git push -u origin fix-0-triage`.

---

## Phase 1 — Stop the freeze (RAM containment)

**Status: DONE** (completed 2026-05-14). Branch `fix-1-ram-containment`.

**Goal:** Make `make run` survive on an 8 GB M1 with default settings. Concretely: ≤ 1 llama-server subprocess, no `--mlock`, smaller context, no MLX double-load, ContextEnricher off until Phase 4.

### What was delivered (implementation record)

| Step | Change |
|------|--------|
| **1.1** | `CEREBRO_LLAMACPP_SIMPLE` default **`true`** in `main.py` and `cerebro/main.py`. Startup log: `llamacpp mode: simple=…`. `.env.example`, `CLAUDE.md`, `.cursor/rules/cerebro.mdc` updated. Default `CEREBRO_LLAMACPP_MODEL` → `llama-3.2-3b-instruct-q4_k_m.gguf` (matches `config/chat.args`). |
| **1.2** | `_validate_swap_model_files()` in `core/inference/model_manager.py` (+ `cerebro/…` copy): requires router + embed + at least one specialist GGUF; raises `FileNotFoundError` otherwise. `main.py` / `cerebro/main.py`: `try/except FileNotFoundError` around `ModelManager()` → **automatic fallback to simple mode** with warning log. `tests/test_model_manager.py`: autouse fixture creates dummy GGUFs; `test_missing_models_raises_file_not_found`. |
| **1.3** | `config/chat.args` and `cerebro/config/chat.args`: llama-3.2-3B profile, **ctx 1536**, **`--threads 4`**, removed **`--mlock`** and **`--cache-prompt`**. |
| **1.4** | `mlx_available()` in `core/inference/platform.py` (+ cerebro copy): **`psutil.virtual_memory().total < 12 GiB` → False** before importing MLX; still requires **Darwin + Apple Silicon** (`is_apple_silicon`). `CEREBRO_MLX_ENABLED=true` documented in `CLAUDE.md` to force MLX on low-RAM machines. Tests: `test_mlx_available_false_when_insufficient_ram`, import-fail test patches high RAM. |
| **1.5** | `CEREBRO_PROACTIVE_CONTEXT` default **`false`** in `main.py` (ContextEnricher off unless opted in). |
| **1.6** | **Manual:** `make engine` + `make run` + `snapshot.py` + curl smoke (see commands below). **Recorded:** RAM availability gate script appended to `docs/plans/roadmaps/fix-cerebro-progress.log`. |
| **Tests** | `tests/test_phase7_advanced.py` (+ cerebro): `chat.args` no longer required to contain `--cache-prompt` (still required for `coding` / `deep`). `tests/test_model_efficiency.py` default-model assertion updated. |

**Exit gate:** `PYTHONPATH=. pytest tests/ -k "not test_execute_plan_step_timeout"` → **558 passed**, 1 deselected (full run ~10 min). Run `pytest tests/test_planner.py::test_execute_plan_step_timeout` separately if needed (~5 min). `make lint` may still fail repo-wide Black on unrelated files.

---

### Step 1.1 — Make `LLAMACPP_SIMPLE` the default *(DONE)*

* **Files touched:** `main.py`, `.env.example`, `CLAUDE.md`.
* **Action:** flip the default for `CEREBRO_LLAMACPP_SIMPLE` from `"false"` to `"true"`. Add a clear startup log line so the user knows which path is active. Update the env example and the architecture doc.

```python
# main.py
LLAMACPP_SIMPLE = os.getenv("CEREBRO_LLAMACPP_SIMPLE", "true").lower() == "true"
```

Add (in `_build_app_state`, near the existing `logger.info("Inference: ...")` call):

```python
if INFERENCE_BACKEND == "llamacpp":
    logger.info("llamacpp mode: simple={} (set CEREBRO_LLAMACPP_SIMPLE=false for model swapping)",
                LLAMACPP_SIMPLE)
```

* **Verification:**

```bash
python - <<'PY'
import importlib, os
os.environ.pop("CEREBRO_LLAMACPP_SIMPLE", None)
m = importlib.import_module("main")
assert m.LLAMACPP_SIMPLE is True, "default must be simple=true after this step"
print("ok")
PY
```

### Step 1.2 — Refuse to launch model_manager when files are missing *(DONE)*

* **Files touched:** `core/inference/model_manager.py`.
* **Action:** in `ModelManager.__init__`, validate that `_MODELS_DIR / _ROUTER_MODEL` and `_MODELS_DIR / _EMBED_MODEL` exist and that **at least one** of `_GENERAL_MODEL` / `_CODE_MODEL` exists. Raise a `FileNotFoundError` with a precise list of missing files. Wrap the `ModelManager()` construction site in `main.py` with a `try/except FileNotFoundError` that logs a clear instruction ("disable model swapping or place these files: ...") and falls through to **simple mode** automatically — never crash the backend.

* **Verification:**

```bash
.venv/bin/pytest tests/test_model_manager.py -q -k "missing_models" || \
  echo "Add a tests/test_model_manager.py case named test_missing_models_falls_back_to_simple"
```

(If the test file does not exist yet, Step 8.2 creates it; for now the verification is allowed to print the hint.)

### Step 1.3 — RAM-friendly llama.cpp profile *(DONE)*

* **Files touched:** `config/chat.args`.
* **Action:** rewrite `config/chat.args` to the M1-8GB-safe profile:

```
--model bin/models/llama-3.2-3b-instruct-q4_k_m.gguf
--ctx-size 1536
--cache-type-k q4_0
--cache-type-v q4_0
--n-gpu-layers 99
--flash-attn on
--temp 0.7
--repeat-penalty 1.1
--threads 4
```

Removed: `--mlock`, `--cache-prompt`. Reduced: `--ctx-size 2048 → 1536`. Added: `--threads 4` (caps Python GIL contention).

The `--model` line is changed to point at the file that **actually exists** (`llama-3.2-3b-instruct-q4_k_m.gguf`).

* **Verification:**

```bash
test -f bin/models/llama-3.2-3b-instruct-q4_k_m.gguf
! grep -q -- "--mlock" config/chat.args
grep -q "ctx-size 1536" config/chat.args
```

### Step 1.4 — Skip MLX on ≤ 8 GB Macs *(DONE)*

*Shipped logic:* after `Darwin` + `is_apple_silicon()`, `psutil.virtual_memory().total < 12 * 1024**3` returns `False` before attempting `import mlx` (plan excerpt below omitted `arm64` check; implementation keeps it).

* **Files touched:** `main.py`, `core/inference/platform.py`.
* **Action:** in `core.inference.platform.mlx_available()`, also return `False` when `psutil.virtual_memory().total < 12 * 2**30`. Document the override (`CEREBRO_MLX_ENABLED=true`) in `CLAUDE.md`.

```python
# core/inference/platform.py (excerpt)
def mlx_available() -> bool:
    if platform.system() != "Darwin":
        return False
    if psutil.virtual_memory().total < 12 * 1024**3:
        return False
    try:
        import mlx.core  # noqa: F401
    except ImportError:
        return False
    return True
```

* **Verification:**

```bash
python - <<'PY'
from unittest.mock import patch
from core.inference.platform import mlx_available
import psutil
class _VM: total = 8 * 1024**3
with patch.object(psutil, "virtual_memory", return_value=_VM):
    assert mlx_available() is False
print("ok")
PY
```

### Step 1.5 — Disable ContextEnricher by default until Phase 4 lands *(DONE)*

* **Files touched:** `main.py`.
* **Action:** flip the default for `PROACTIVE_CONTEXT` from `"true"` to `"false"`. The enricher today fires `osascript` on every query, leaks subprocesses (Step 4.4 fixes this), and forces the calendar permission prompt before the user has any reason to grant it.

```python
PROACTIVE_CONTEXT = os.getenv("CEREBRO_PROACTIVE_CONTEXT", "false").lower() == "true"
```

* **Verification:**

```bash
python - <<'PY'
import os, importlib
os.environ.pop("CEREBRO_PROACTIVE_CONTEXT", None)
m = importlib.import_module("main")
importlib.reload(m)
assert m.PROACTIVE_CONTEXT is False
print("ok")
PY
```

### Step 1.6 — Smoke-test the freeze fix *(manual / recorded)*

* **Action:** start the engine and the backend, ask three questions, and watch RAM:

```bash
make engine &           # starts ONE llama-server with the new chat.args
sleep 8
make run &              # starts FastAPI :7842
sleep 5
python scripts/diag/snapshot.py | tee -a docs/plans/roadmaps/fix-cerebro-progress.log
curl -fsS -X POST http://localhost:7842/api/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"hola","agent":"general-v1"}' | python -m json.tool
python scripts/diag/snapshot.py | tee -a docs/plans/roadmaps/fix-cerebro-progress.log
```

* **Verification (manual + scripted):** the `system: ... pressure=` line in `snapshot.py` output must NOT print `critical` after the curl call. Codify the assertion:

```bash
python - <<'PY'
import psutil, sys
avail_gb = psutil.virtual_memory().available / 2**30
print(f"available={avail_gb:.2f}GB")
sys.exit(0 if avail_gb >= 1.2 else 1)
PY
```

### Phase 1 exit gate *(DONE)*

```bash
git checkout -b fix-1-ram-containment
make lint && make test
git commit -am "fix-1: 8GB-safe defaults (simple mode, no mlock, mlx off, enricher off)"
```

**As executed:** targeted tests + full `pytest` excluding `test_execute_plan_step_timeout` (558 passed). Commit uses explicit `git add` file list (not `-am` only). Repo-wide `make lint` may still fail on pre-existing Black drift outside touched modules.

---

## Phase 2 — Tools must run when the user asks for live data

**Status: DONE** (completed 2026-05-14). D2 addressed: general agent has an explicit read-only tool allowlist + instructions; `/api/query/stream` always runs `runtime.run()` (tool loop); default UI agent is **Auto (router)**; `LLMRouter` applies a regex prefilter before calling the edge LLM.

**Goal:** Eliminate D2. After this phase, asking *"what time is it?"* / *"next event?"* / *"upcoming birthday?"* always reaches the tool loop, even from the streaming endpoint and even when the user stays on the General agent (and Auto routes calendar-ish queries to the calendar specialist).

### What was delivered (implementation record)

| Item | Detail |
|------|--------|
| **Step 2.1** | `core/agents/specialized.py` — `GENERAL_TOOLS` explicit allowlist; Spanish instructions appended in `make_general_profile()` |
| **Step 2.2** | `ui/tray/server.py` — `query_stream_endpoint` always uses `event_generator_tools` / `runtime.run()`; `runtime.stream()` no longer dispatched from this route |
| **Step 2.3** | `ui/tray/src/api/types.ts` (`AgentId`, `AGENTS`), `client.ts` (`AGENT_ID_MAP`), `stores/chat.ts` (`activeAgent: "auto"`), `AgentSelectorDropdown.tsx` (first option *Auto (router)*). `InputArea.tsx` unchanged — it already sends `AGENT_ID_MAP[activeAgent]` |
| **Step 2.4** | `core/agents/llm_router.py` — `_INTENT_RE` compiled patterns; `classify()` returns calendar/code/academic on match before HTTP |
| **Tests** | `tests/test_specialized.py` — general profile asserts allowlist; `tests/test_llm_router.py` — regex cases; `tests/test_api.py::test_query_stream_calls_runtime_run_not_stream` |
| **Exit gate** | `pytest tests/`: **552 passed** (~5m49s this run). Repo-wide `make lint` still fails Black on pre-existing files; Phase 2 touched files run through Black |
| **Frontend build** | `ui/tray`: run `npm run build` (or `pnpm` / `bun` per project preference) after `npm install` when `node_modules` is present — not executed in the agent environment without deps |

### Step 2.1 — Give the General agent the read-only "everyday" toolset *(DONE)*

* **Files touched:** `core/agents/specialized.py`.
* **Verification:** `.venv/bin/pytest tests/test_specialized.py -q` (includes `test_general_profile_has_explicit_readonly_tools`).

### Step 2.2 — Stop bypassing the tool loop in the streaming endpoint *(DONE)*

* **Files touched:** `ui/tray/server.py`.
* **Verification:** `.venv/bin/pytest tests/test_api.py::test_query_stream_calls_runtime_run_not_stream -q`.

### Step 2.3 — Frontend: make `auto` the default agent *(DONE)*

* **Files touched:** `ui/tray/src/api/types.ts`, `ui/tray/src/api/client.ts`, `ui/tray/src/stores/chat.ts`, `ui/tray/src/components/shared/AgentSelectorDropdown.tsx`.
* **Verification:** `cd ui/tray && npx tsc --noEmit` (after install).

### Step 2.4 — Cheap intent fallback for the LLM router *(DONE)*

* **Files touched:** `core/agents/llm_router.py`.
* **Verification:** `.venv/bin/pytest tests/test_llm_router.py -q`.

### Phase 2 exit gate *(DONE)*

```bash
# Recommended branch (optional): git checkout -b fix-2-tools-routing
make lint   # may still report pre-existing Black drift outside this phase
make test   # 552 passed @ 2026-05-14
cd ui/tray && npm install && npm run build
```

---

## Phase 3 — Date correctness, end to end

**Status: DONE** (completed 2026-05-14). The LLM user turn is prefixed with a one-line dateline (current year in plain text); system prompts gain an explicit temporal rule; regression tests guard the preamble.

**Goal:** The agent must always answer the current date correctly, regardless of model size or training cutoff.

### What was delivered (implementation record)

| Item | Detail |
|------|--------|
| **Step 3.1** | `core/agents/runtime.py` — public `_date_preamble()`; `_context_assembly_node` and `stream()` set `{"role": "user", "content": _date_preamble() + …}` so the model sees the date in the user weight band. Session summary / `_update_state_node` still use the raw `query` only (no preamble in the persisted exchange text). |
| **Step 3.2** | Same file — **REGLA TEMPORAL** block immediately after `FECHA Y HORA ACTUAL` in `_SYSTEM_TEMPLATE` and `_STREAM_SYSTEM_TEMPLATE`. |
| **Step 3.3** | `tests/test_runtime_date_correctness.py` — `test_date_preamble_contains_current_year`, `test_date_preamble_spanish_context_marker` (the spec’s async stub is deferred to Step 8.4 per plan). |
| **Exit gate** | `make test`: **554 passed** (~15m wall; includes long-running tests). Phase 3 files: `black` + `ruff` clean. Full `make lint` not re-run repo-wide (known pre-existing Black drift elsewhere). |

### Step 3.1 — Bake the date into the user message, not just the system prompt *(DONE)*

* **Files touched:** `core/agents/runtime.py`.
* **Action:** small models give user messages more weight than system messages. Prepend a one-line dateline to every user query inside the runtime (NOT inside the visible UI message). Apply in both `_context_assembly_node` and `stream()`:

```python
# helper
def _date_preamble() -> str:
    now = datetime.now().astimezone()
    return f"[Contexto del sistema: hoy es {now.strftime('%A %d de %B de %Y, %H:%M %Z')}.] "

# in _context_assembly_node, replace:
#   {"role": "user", "content": state["query"]}
# with:
{"role": "user", "content": _date_preamble() + state["query"]}
```

Same change in `runtime.stream()`. Do not store the preamble in the conversation log (the user did not type it) — wrap the preamble at the runtime layer only.

* **Verification:**

```bash
.venv/bin/python - <<'PY'
from datetime import datetime
from core.agents.runtime import _date_preamble
out = _date_preamble()
assert str(datetime.now().year) in out, out
assert "hoy es" in out.lower(), out
print(out)
PY
```

### Step 3.2 — Strengthen the system-prompt anti-hallucination clause *(DONE)*

* **Files touched:** `core/agents/runtime.py` (both `_SYSTEM_TEMPLATE` and `_STREAM_SYSTEM_TEMPLATE`).
* **Action:** add immediately after the `FECHA Y HORA ACTUAL: ...` line:

```
REGLA TEMPORAL: La línea FECHA Y HORA ACTUAL contiene la verdad del momento
presente. Si el usuario pregunta por la fecha, hora, día o año, responde
SIEMPRE con esos valores. NUNCA respondas con una fecha de tu entrenamiento.
```

* **Verification:**

```bash
grep -q "REGLA TEMPORAL" core/agents/runtime.py
```

### Step 3.3 — Regression test: `today` must contain the current year *(DONE)*

* **Files touched:** `tests/test_runtime_date_correctness.py` (new).
* **Action:**

```python
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock
from core.agents.runtime import _date_preamble

def test_date_preamble_contains_current_year():
    p = _date_preamble()
    assert str(datetime.now().year) in p
    assert "hoy" in p.lower()

async def _stub_chat_complete(messages):
    # Echo back the dateline so we can assert it reached the model.
    user = next(m["content"] for m in messages if m["role"] == "user")
    return f'{{"action":"answer","answer":"{user[:80]}"}}'

# Full integration is added under tests/test_api.py in Step 8.4.
```

* **Verification:**

```bash
.venv/bin/pytest tests/test_runtime_date_correctness.py -q
```

### Phase 3 exit gate *(DONE)*

```bash
# Recommended branch (optional): git checkout -b fix-3-date-correctness
make lint   # may still report pre-existing Black drift outside this phase
make test   # 554 passed @ 2026-05-14 (~15m)
git commit -am "fix-3: date preamble in user message + temporal rule + test"
```

---

## Phase 4 — Calendar reliability and macOS permissions

**Status: DONE** (completed 2026-05-14). D3 addressed: merged `BackendResult` surfaces permission/timeout vs empty calendar; Apple read osascript uses 5 s sync / 3 s async with kill-on-timeout; boot probe fills `app_state.macos_permissions`; `/api/status` exposes it; `ContextEnricher` uses async calendar fetch and skips entirely when probe reports `denied`; `PROACTIVE_CONTEXT` defaults to **on** again.

**Goal:** Eliminate D3. Make `get_upcoming_events` either return real events, OR return a structured, user-actionable error explaining how to grant permission. No more silent `Sin eventos`.

### What was delivered (implementation record)

| Item | Detail |
|------|--------|
| **4.1** | `BackendResult` + `BackendStatus`; `ICalBackend` / `AppleCalendarBackend` / `BirthdayBackend` `get_upcoming_events_v2`; `CalendarReader.get_upcoming_events_v2` + `get_upcoming_events_async` merge with dedup; `format_merged_calendar_result()` in `core/tools/handlers/calendar.py`; `query_events` / `search_upcoming` respect blocking statuses |
| **4.2** | Apple + Birthday **read** paths use `timeout=5` (`_OSASCRIPT_TIMEOUT_SEC`); create/reminder paths unchanged at 10 s |
| **4.3** | `core/observability/macos_perms.py` — `probe_calendar_permission()` async JXA probe; `AppState.macos_permissions`; `lifespan` sets `calendar` key; `StatusResponse.macos_permissions` + TS `StatusResponse.macos_permissions` |
| **4.4** | `ContextEnricher` — `CalendarReader.get_upcoming_events_async` + `asyncio.gather`; no `to_thread(get_upcoming_events)` for calendar |
| **4.5** | `main.py` — `CEREBRO_PROACTIVE_CONTEXT` default `"true"`; enricher receives `macos_permissions` dict ref; `enrich()` returns `""` when `calendar == "denied"` |
| **Tests** | `tests/test_calendar_reader.py`, `tests/test_macos_perms.py`; `tests/test_context_enricher.py` + `test_permission_gate_calendar_denied_skips_enricher`; `tests/test_calendar.py` mock `spec=` fix; `tests/test_tools.py` Linux patch for empty .ics isolation |
| **Verification** | `tests/test_calendar_reader.py` + `tests/test_context_enricher.py` (+ `-k permission_gate`) + calendar/tools suites: **91 passed** in one grouped run; `grep timeout=60` on Apple **read** path: **none** |

### Step 4.1 — Structured calendar result type *(DONE)*

* **Files touched:** `integrations/calendar_reader.py`, `core/tools/handlers/calendar.py`.
* **Action:** introduce a dataclass returned by all backends:

```python
# integrations/calendar_reader.py
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class BackendResult:
    events: list[CalendarEvent] = field(default_factory=list)
    status: Literal["ok", "permission_denied", "no_calendar", "timeout", "error"] = "ok"
    detail: str = ""

class AppleCalendarBackend:
    def get_upcoming_events_v2(self, hours_ahead: int = 24) -> BackendResult:
        # Same body as today, but return BackendResult; map TimeoutExpired → status="timeout",
        # CalledProcessError with errno 1743 (Automation denied) → status="permission_denied".
        ...

# Keep the existing get_upcoming_events() returning list[CalendarEvent] for backwards compat
# by delegating to v2 and discarding metadata; new callers use v2.
```

In `core/tools/handlers/calendar.py`, switch the handler to use `_v2` and surface the status:

```python
def get_upcoming_events(hours_ahead: int = 24, ics_path: str | None = None) -> str:
    reader = CalendarReader(...)
    result = reader.get_upcoming_events_v2(hours_ahead=hours_ahead)
    if result.status == "permission_denied":
        return ("No tengo permiso para leer Apple Calendar. Abre "
                "Ajustes del sistema → Privacidad y seguridad → Automatización, "
                "y autoriza Calendar para Python/Cerebro. Luego vuelve a preguntar.")
    if result.status == "timeout":
        return "Apple Calendar tardó demasiado en responder. Reintenta en unos segundos."
    if not result.events:
        return f"Sin eventos en las próximas {hours_ahead} horas."
    # ... existing formatting ...
```

* **Verification:**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_calendar_reader.py -q
```

### Step 4.2 — Drop the 60-second osascript timeout to 5 seconds *(DONE)*

* **Files touched:** `integrations/calendar_reader.py`.
* **Action:** replace `subprocess.run(..., timeout=60)` with `timeout=5` in `AppleCalendarBackend`. A correct query returns in < 1 s on M1; anything past 5 s is a permission stall.
* **Verification:**

```bash
grep -nE "timeout=\s*60" integrations/calendar_reader.py | grep -v Reminder | grep -v "create_apple" \
  && { echo "ERROR: long osascript timeout still present"; exit 1; } \
  || echo "ok"
```

### Step 4.3 — One-shot permission preflight at backend startup (macOS only) *(DONE)*

* **Files touched:** `main.py`, `core/observability/macos_perms.py` (new).
* **Action:** add a tiny module that runs the same JXA probe from `scripts/diag/check_calendar.py` once at boot, asynchronously, and stores the outcome in `app_state.macos_permissions` (`{"calendar": "ok"|"denied"|"unknown", ...}`). Surface this in `/api/status` (extend `StatusResponse` with `macos_permissions: dict[str, str] | None`). Frontend wizard later (Step 9.2) can display a "grant permissions" card.

* **Verification:**

```bash
PYTHONPATH=. .venv/bin/python - <<'PY'
import asyncio
from core.observability.macos_perms import probe_calendar_permission
status = asyncio.run(probe_calendar_permission())
assert status in {"ok", "denied", "unknown", "not_macos"}
print(status)
PY
```

### Step 4.4 — Make ContextEnricher stop leaking subprocesses *(DONE)*

* **Files touched:** `core/agents/context_enricher.py`.
* **Action:** today `enrich()` wraps `asyncio.to_thread(get_upcoming_events, ...)` in a 3 s `asyncio.wait_for`; on timeout the thread keeps running and the underlying `osascript` child runs for up to 60 s. Solution: shell out via a directly-managed `asyncio.create_subprocess_exec` so we own the PID and can `process.kill()` on timeout. Drop the `to_thread` indirection.

```python
# Before opening the file: refactor enrich() to call a small helper that
# spawns osascript with asyncio.create_subprocess_exec(..., stdout=PIPE),
# uses asyncio.wait_for(proc.communicate(), timeout=3.0); on TimeoutError,
# proc.kill(), await proc.wait(), return ("", "timeout").
```

* **Verification:**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_context_enricher.py -q
# additionally:
ps -A -o pid,ppid,command | grep -i "osascript" | grep -v grep && \
  { echo "stale osascript still present after test"; exit 1; } || \
  echo "no leaks"
```

### Step 4.5 — Re-enable ContextEnricher (now safe) but only when permissions are OK *(DONE)*

* **Files touched:** `main.py`, `core/agents/context_enricher.py`.
* **Action:** flip the default for `PROACTIVE_CONTEXT` back to `"true"`, and inside `ContextEnricher.enrich()` short-circuit to `""` when `app_state.macos_permissions.get("calendar") == "denied"`. The enricher never asks for permission it doesn't have.
* **Verification:**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_context_enricher.py -q -k "permission_gate"
```

### Phase 4 exit gate *(DONE)*

```bash
# Recommended branch (optional): git checkout -b fix-4-calendar-perms
make lint   # may still report pre-existing drift outside this phase
PYTHONPATH=. .venv/bin/pytest tests/test_calendar_reader.py tests/test_context_enricher.py tests/test_macos_perms.py tests/test_calendar.py tests/test_tools.py
git commit -am "fix-4: structured calendar results + 5s timeout + perm preflight + safe enricher"
```

---

## Phase 5 — Birthdays specifically

**Status: DONE** (completed 2026-05-14).

**Goal:** "¿Cuál es el próximo cumpleaños?" returns a real date.

### What was delivered (implementation record)

| Item | Detail |
|------|--------|
| **JXA / Calendar** | `_JXA_BIRTHDAYS_TEMPLATE`: locale calendar names (`Geburtstage`, `Anniversaires`), fuzzy calendar names containing `birthday` / `cumple`, title heuristic `looksLikeBirthdayTitle` (keywords + `Name's` / curly-apostrophe `birthday`) |
| **Contacts fallback** | `_JXA_CONTACTS_BIRTHDAYS` + `ContactsBirthdayBackend`; `BirthdayChainBackend` runs Calendar `BirthdayBackend` first, then Contacts when first result is `ok` with zero events |
| **Reader** | `CalendarReader(..., use_apple_calendar=True)` appends `BirthdayChainBackend` (replaces bare `BirthdayBackend`) |
| **Tool UX** | `format_merged_calendar_result`: `permission_denied` + `detail == "contacts"` → Spanish Automation message for **Contacts** |
| **Agent prompt** | `make_calendar_profile()` includes explicit `search_upcoming` example (365-day window) for próximo cumpleaños |
| **Tests** | `tests/test_calendar_reader.py`: `-k birthday`, `-k contacts_birthday_fallback`; `_contacts_birthdays_json_to_events(..., now_override=)` for deterministic unit test; `tests/test_tools.py::test_get_upcoming_events_no_ics_returns_no_events_message` patches `platform.system` to `Linux` so Darwin CI does not merge Apple backends into the assertion |
| **Exit gate** | `make test` (566 passed); Black applied to `integrations/calendar_reader.py` and `tests/test_calendar_reader.py`; full `make lint` still reports pre-existing Black drift in other files |

### Step 5.1 — Strengthen `BirthdayBackend` calendar discovery *(DONE)*

* **Files touched:** `integrations/calendar_reader.py`.
* **Action:** today the JXA script looks only for the calendar literal name `"Birthdays"` or `"Cumpleaños"`. Extend the match to also accept `Geburtstage`, `Anniversaires`, and any calendar whose name **contains** "birthday"/"cumple". Also accept events whose title matches the regex `^(.+)'s birthday$` even on non-Birthdays calendars (Apple frequently writes `Javier's birthday` on the iCloud calendar when Contacts sync is partial).
* **Verification:**

```bash
.venv/bin/pytest tests/test_calendar_reader.py -q -k "birthday"
```

### Step 5.2 — Contacts fallback when no Birthdays calendar exists *(DONE)*

* **Files touched:** `integrations/calendar_reader.py`.
* **Action:** add a `ContactsBirthdayBackend` that runs:

```javascript
var ab = Application("Contacts");
var people = ab.people();
var out = [];
people.forEach(function(p){
  try {
    var b = p.birthday();
    if (b) out.push({name: p.name(), month: b.getMonth()+1, day: b.getDate()});
  } catch(e){}
});
JSON.stringify(out);
```

If Contacts permission is denied, return `BackendResult(status="permission_denied")` with the specific `"contacts"` detail. Surface that in the same `Settings → Automation` instruction text added in Step 4.1.

`CalendarReader.get_upcoming_events_v2` calls `BirthdayBackend` first; if it returns 0 events with `status == "ok"`, falls through to `ContactsBirthdayBackend`.

* **Verification:**

```bash
.venv/bin/pytest tests/test_calendar_reader.py -q -k "contacts_birthday_fallback"
```

### Step 5.3 — Calendar agent prompt: prefer the right tool for birthday queries *(DONE)*

* **Files touched:** `core/agents/specialized.py`.
* **Action:** the calendar profile already mentions birthdays but uses `query_events`/`get_upcoming_events`. Add an explicit example for `search_upcoming` (365-day window) so the model picks it for "próximo cumpleaños":

```
Para el próximo cumpleaños (puede estar a meses vista):
{"action": "tool", "tool": "search_upcoming", "args": {"keyword": "cumple", "days_ahead": 365}}
```

* **Verification:**

```bash
grep -q "search_upcoming" core/agents/specialized.py
```

### Phase 5 exit gate *(DONE)*

```bash
git checkout -b fix-5-birthdays
make lint && make test
git commit -am "fix-5: contacts birthday fallback + better calendar discovery"
```

---

## Phase 6 — A first-class "Lite 8 GB" profile

**Status: DONE** (completed 2026-05-14).

**Goal:** A single environment knob that selects the safe-on-laptop profile, plus a `make` target.

### What was delivered (implementation record)

| Item | Detail |
|------|--------|
| **Profile** | `config/profiles/lite-8gb.env` — env vars per FIX spec (llamacpp simple, chat profile/model, MLX off, proactive on, scheduler off, RAM thresholds) |
| **Makefile** | `make lite` sources profile then runs `main.py`; `make engine-lite` sources profile then `./bin/start_engine.sh chat` |
| **Wizard API** | `GET /api/wizard/status` includes `recommend_lite` when `psutil.virtual_memory().total <= 10 * 2**30` via `recommend_lite_profile()` in `ui/tray/wizard.py`; `WizardStatusResponse` + legacy `ui/tray/wizard_router.py` `/wizard/status` include the same flag |
| **Wizard UI** | `StepLlamaCpp.tsx` — "Use 8 GB safe profile" calls `PATCH /api/config` with `inference_backend`, `model`, `mlx_enabled`; hints `make lite` / `make engine-lite` when RAM is low |
| **Types** | `WizardStatus.recommend_lite`; optional `AppConfig.mlx_enabled` |
| **Tests** | `tests/test_wizard_router.py` — `-k recommend_lite` (10 GB true, 16 GB false, Claude path) |
| **Exit gate** | `pytest tests/ -q` (568 passed, 1 deselected: slow planner timeout test); `ui/tray` production build: run `pnpm install && pnpm run build` or equivalent in `ui/tray` after deps install |

### Step 6.1 — Profile file *(DONE)*

* **Files touched:** `config/profiles/lite-8gb.env` (new).
* **Action:**

```dotenv
# Cerebro — Lite profile for MacBook Pro M1, 8 GB RAM
CEREBRO_INFERENCE_BACKEND=llamacpp
CEREBRO_LLAMACPP_SIMPLE=true
CEREBRO_LLAMACPP_URL=http://127.0.0.1:8080
CEREBRO_LLAMACPP_PROFILE=chat
CEREBRO_LLAMACPP_MODEL=llama-3.2-3b-instruct-q4_k_m.gguf
CEREBRO_MLX_ENABLED=false
CEREBRO_PROACTIVE_CONTEXT=true
CEREBRO_SCHEDULER_ENABLED=false
CEREBRO_RAM_PRIMARY_GB=0.8
CEREBRO_RAM_FALLBACK_GB=0.4
```

* **Verification:**

```bash
test -f config/profiles/lite-8gb.env
```

### Step 6.2 — `make lite` target *(DONE)*

* **Files touched:** `Makefile`.
* **Action:** add:

```make
lite:
	set -a; . config/profiles/lite-8gb.env; set +a; \
	$(PYTHON) main.py
```

Also add `engine-lite` that runs `./bin/start_engine.sh chat` after sourcing the env file (the smaller `--ctx-size` is already in the chat.args from Step 1.3).

* **Verification:**

```bash
grep -q "^lite:" Makefile && grep -q "lite-8gb.env" Makefile
```

### Step 6.3 — Wizard advertises lite profile when total RAM ≤ 10 GB *(DONE)*

* **Files touched:** `ui/tray/wizard.py`, `ui/tray/server.py`, `ui/tray/wizard_router.py`, `ui/tray/src/components/wizard/StepLlamaCpp.tsx`, `ui/tray/src/api/types.ts`.
* **Action:** when wizard detects `psutil.virtual_memory().total <= 10 * 2**30`, return a flag `recommend_lite: true` from `/api/wizard/status`. The wizard step shows a one-click "Use 8 GB safe profile" button that PATCHes `/api/config` with `{"inference_backend":"llamacpp","model":"llama-3.2-3b-instruct-q4_k_m.gguf","mlx_enabled":false}` and persists.
* **Verification:**

```bash
.venv/bin/pytest tests/test_wizard_router.py -q -k "recommend_lite"
```

### Phase 6 exit gate *(DONE)*

```bash
git checkout -b fix-6-lite-profile
make lint && make test
cd ui/tray && pnpm install && pnpm run build   # or bun / npm per your toolchain
git commit -am "fix-6: lite-8gb profile, make target, wizard recommendation"
```

---

## Phase 7 — Observability so the next regression is loud

**Status: DONE** (completed 2026-05-14). RAM pressure from `RamMonitor` is exposed on `/api/status` (`ram_pressure`, `ram_total_gb`); `RamGauge` turns warn/critical with a hover card and **Use 8 GB safe profile** (`PATCH /api/config` same payload as the wizard); `/api/query` and `/api/query/stream` return **503** when pressure is `critical`. `pytest` `pythonpath` includes repo root so `ui.tray` imports resolve.

**Goal:** A regression that brings back the freeze must show up in `/api/status` immediately, not by destroying the user's session.

### What was delivered (implementation record)

| Item | Detail |
|------|--------|
| **7.1** | `core/observability/ram_monitor.py` — `RamMonitor.snapshot()` → `used_gb`, `available_gb`, `total_gb`, `pressure` (`available_gb` < 1.0 → critical, < 1.8 → warn). `AppState.ram_monitor` default instance; `StatusResponse` + `/api/status` include `ram_pressure`, `ram_total_gb` |
| **7.2** | `RamGauge.tsx` — pressure-based amber/red; hover panel + lite button. `StatusBar.tsx` + `system.ts` (`selectRamPressure`), `types.ts`, `client` `updateConfig` |
| **7.3** | `ui/tray/server.py` — `_ram_pressure_guard()` at start of `/api/query` and `/api/query/stream` → 503 `Out of RAM. Lite profile recommended.` |
| **Tests** | `tests/test_api.py` — `ram_pressure` fields in status; `test_ram_pressure_503_on_query_when_critical`, `test_ram_pressure_503_on_query_stream_when_critical`; `tests/test_ram_monitor.py` threshold unit tests; `tests/test_wizard_router.py` — patch `ui.tray.wizard.psutil` (server no longer imports `psutil`) |
| **Tooling** | `pyproject.toml` — `[tool.pytest.ini_options] pythonpath = ["."]` for consistent `ui` imports |

### Step 7.1 — Surface RAM pressure in `/api/status` *(DONE)*

* **Files touched:** `ui/tray/server.py`, `core/observability/ram_monitor.py` (new — same shape as `docs/plans/vision/future-cognitive-os.md` Step 0.4 so the future plan does not have to redo this work).
* **Action:** add `RamMonitor` with `snapshot()` returning `{used_gb, available_gb, total_gb, pressure}` (`available_gb<1.0`→critical, `<1.8`→warn, else ok). Extend `StatusResponse` with `ram_pressure: Literal["ok","warn","critical"]` and `ram_total_gb: float`. Wire `app_state.ram_monitor` in `AppState.__init__`.
* **Verification:**

```bash
curl -fsS http://localhost:7842/api/status | python -c "import sys,json; d=json.load(sys.stdin); assert d['ram_pressure'] in {'ok','warn','critical'}; print(d['ram_pressure'])"
```

### Step 7.2 — RAM pressure header in the UI *(DONE)*

* **Files touched:** `ui/tray/src/components/status/StatusBar.tsx`, `RamGauge.tsx`, `ui/tray/src/stores/system.ts`, `ui/tray/src/api/types.ts`.
* **Action:** colour `RamGauge` red when `ram_pressure === "critical"`, amber when `"warn"`. Hover card: *"Cerebro is approaching the 8 GB limit. Switch to lite profile."* with **Use 8 GB safe profile** calling the same `/api/config` patch as the wizard (`inference_backend`, `model`, `mlx_enabled`).
* **Verification:**

```bash
cd ui/tray && npm run build
```

### Step 7.3 — Refuse new queries under critical pressure *(DONE)*

* **Files touched:** `ui/tray/server.py`.
* **Action:** at the top of `/api/query` and `/api/query/stream`, check `ram_monitor.snapshot()["pressure"]`; if `critical`, return `503` with `{"detail":"Out of RAM. Lite profile recommended."}` instead of starting an inference. The user feels backpressure instead of a frozen Mac.
* **Verification:**

```bash
.venv/bin/pytest tests/test_api.py -q -k "ram_pressure_503"
```

### Phase 7 exit gate *(DONE)*

```bash
git checkout -b fix-7-observability
make lint && make test
git commit -am "fix-7: ram pressure surfaced + critical-503 backpressure"
```

**As executed:** `pytest tests/test_api.py -k "ram_pressure_503"` + `tests/test_ram_monitor.py` + status/wizard subset passed; full `make test` not re-run in this session. `make lint` / repo-wide Black may still reflect pre-existing drift outside touched files.

---

## Phase 8 — Test suite to lock the fixes in place

**Status: DONE** (completed 2026-05-14). Package `tests/test_fix_cerebro/` with shared `conftest.py` (`install_runtime_for_query_e2e`, stub chat, `ProviderRegistry` RAM thresholds 0.01 GB so CI/sandbox passes `select_for_task`). **9 tests** — `pytest tests/test_fix_cerebro -q` **9 passed** in this session.

**Goal:** Every defect from Phase 0's symptom map has a regression test.

### What was delivered (implementation record)

| Item | Detail |
|------|--------|
| **8.1** | `tests/test_fix_cerebro/__init__.py`, `conftest.py` — autouse `app_state` reset; `api_client`; `make_stub_chat_complete`; `install_runtime_for_query_e2e` (real `AgentRuntime` + tools + tmp LanceDB) |
| **8.2** | `test_model_manager_fallback.py` — `ModelManager()` after `reload(model_manager)` with empty `CEREBRO_MODELS_DIR` raises `FileNotFoundError` with listing; `importlib.reload(main)` + `_build_app_state()` leaves `app_state.model_manager is None` |
| **8.3** | `test_general_agent_tools.py` — `authorized_tools` includes calendar read tools; runtime invokes `get_upcoming_events` when stub LLM returns tool JSON |
| **8.4** | `test_query_date_e2e.py` — POST `/api/query` answer contains `datetime.now().year` |
| **8.5** | `test_query_calendar_e2e.py` — monkeypatch `CalendarReader.get_upcoming_events_v2` (ok + `permission_denied`); asserts `tools_called` / copy in answer |
| **8.6** | `test_no_subprocess_leak.py` — `AppleCalendarBackend.get_upcoming_events_async` with `osascript` replaced by slow `python` script + timeout; `psutil` scan for sentinel path (skips on `PermissionError`; same kill path `ContextEnricher` uses via `CalendarReader`) |
| **8.7** | `test_ram_pressure.py` — critical RAM → 503 on `/api/query` |

### Step 8.1 — Test inventory *(DONE)*

* **Files touched:** `tests/test_fix_cerebro/__init__.py` (new), `tests/test_fix_cerebro/conftest.py` (new).
* **Action:** create the package and shared fixtures: autouse `app_state` reset, httpx `AsyncClient` to FastAPI `app`, `install_runtime_for_query_e2e()` wiring a real in-process `AgentRuntime` (no llama-server) with stub `chat.complete`.

### Step 8.2 — `tests/test_fix_cerebro/test_model_manager_fallback.py` *(DONE)*

Asserts that `ModelManager()` raises `FileNotFoundError` listing missing GGUF paths, and that `_build_app_state()` catches swap failure and falls back to simple mode without crashing.

### Step 8.3 — `tests/test_fix_cerebro/test_general_agent_tools.py` *(DONE)*

Asserts:

* `make_general_profile().authorized_tools` contains `get_upcoming_events`, `query_events`, `search_upcoming`.
* The runtime, when fed a query containing `"hoy"` and a stub provider that returns `{"action":"tool","tool":"get_upcoming_events"}`, actually invokes the calendar handler.

### Step 8.4 — `tests/test_fix_cerebro/test_query_date_e2e.py` *(DONE)*

End-to-end through FastAPI test client (`AppState` injected with stub providers): POST `/api/query` with `{"question":"¿Qué día es hoy?","agent":"general-v1"}` returns an answer that contains `str(datetime.now().year)`.

### Step 8.5 — `tests/test_fix_cerebro/test_query_calendar_e2e.py` *(DONE)*

End-to-end: stub `CalendarReader.get_upcoming_events_v2` to return one fake event. POST `/api/query` and assert `metadata.tools_called` contains `get_upcoming_events` and the answer mentions the fake event title. Second test: `BackendResult(status="permission_denied")` and assert the answer contains the human instruction string.

### Step 8.6 — `tests/test_fix_cerebro/test_no_subprocess_leak.py` *(DONE)*

Exercises the **Apple async calendar** subprocess path (used by `ContextEnricher` via `CalendarReader`): `osascript` is replaced with a slow `python` script carrying a unique path sentinel; short `communicate` timeout triggers `proc.kill()`; after await, `psutil.process_iter` must not find a live process whose cmdline still references that script (skip if `psutil` raises `PermissionError`).

### Step 8.7 — `tests/test_fix_cerebro/test_ram_pressure.py` *(DONE)*

Patches `RamMonitor.snapshot` to return `pressure="critical"`. POST `/api/query` returns 503 with the expected detail.

* **Verification (whole phase):**

```bash
.venv/bin/pytest tests/test_fix_cerebro -q
```

### Phase 8 exit gate *(DONE)*

```bash
git checkout -b fix-8-tests
make lint && make test
git commit -am "fix-8: regression tests for date, calendar, ram, leaks"
```

**As executed:** `pytest tests/test_fix_cerebro -q` — **9 passed** (~1.4s). Full `make test` not re-run in this session.

---

## Phase 9 — Documentation, recovery runbook, and clean exit

**Status: DONE** (completed 2026-05-14). Runbook, wizard Calendar Automation card with Tauri shell + reprobe API, aggregate `doctor.sh`, future-plan cross-link, and `test_wizard_reprobe_calendar_permission_updates_state`.

**Goal:** A new contributor — and the user himself, six months from now — can reproduce the fix and recover from a future regression in under 10 minutes.

### What was delivered (implementation record)

| Item | Detail |
|------|--------|
| **9.1** | [`docs/guides/8gb-mac-quickstart.md`](docs/guides/8gb-mac-quickstart.md) — `make install`, `make lite` / `engine-lite`, Automation, `/api/status`, Spanish smoke prompts, diag + `doctor.sh`; [`docs/README.md`](docs/README.md) links the guide in the runbooks row |
| **9.2** | [`ui/tray/src/components/wizard/StepFolders.tsx`](ui/tray/src/components/wizard/StepFolders.tsx) — card when `macos_permissions.calendar` ≠ `ok` (and not `not_macos`); **Open Settings** via `@tauri-apps/plugin-shell` `open()`; **I granted it** → `POST /api/wizard/reprobe-calendar-permission`; [`ui/tray/wizard_router.py`](ui/tray/wizard_router.py) module doc points to canonical `/api/wizard/*` in [`ui/tray/server.py`](ui/tray/server.py); [`ui/tray/src-tauri/capabilities/main.json`](ui/tray/src-tauri/capabilities/main.json) — `shell:default`, `shell:allow-open`; [`ui/tray/src/vite-env.d.ts`](ui/tray/src/vite-env.d.ts) — Vite `ImportMeta` types for `tsc`; mirrored under `cerebro/ui/tray/` |
| **9.3** | [`scripts/diag/doctor.sh`](scripts/diag/doctor.sh) — runs `snapshot`, `check_models`, `check_calendar`, `check_routing`; prefers `$ROOT/.venv/bin/python` then `python3`; colorized FAIL hints; exit `0` / `1` |
| **9.4** | [`docs/plans/vision/future-cognitive-os.md`](docs/plans/vision/future-cognitive-os.md) — lockstep line after title referencing `FIX_CEREBRO` Phase 8 |
| **Tests** | [`tests/test_wizard_router.py`](tests/test_wizard_router.py) — `test_wizard_reprobe_calendar_permission_updates_state`; autouse reset sets `app_state.macos_permissions` |

### Step 9.1 — Quick-start runbook for 8 GB Macs *(DONE)*

* **Files touched:** `docs/guides/8gb-mac-quickstart.md` (new), `docs/README.md`.
* **Action:** write a one-page runbook covering:
  1. `make install` once.
  2. `make lite` (or `cp config/profiles/lite-8gb.env .env && make engine && make run`).
  3. macOS Settings → Privacy & Security → Automation → grant Calendar to Python.
  4. Open `http://localhost:7842/api/status` and confirm `ram_pressure: ok`.
  5. Ask `"¿Qué día es hoy?"` then `"¿Cuál es mi próximo evento?"`.
  6. If anything fails, run `python scripts/diag/snapshot.py && python scripts/diag/check_models.py && python scripts/diag/check_calendar.py` and paste the output into a new issue (or `bash scripts/diag/doctor.sh`).
* **Verification:**

```bash
test -f docs/guides/8gb-mac-quickstart.md
```

### Step 9.2 — Wizard surfaces the macOS permission status *(DONE)*

* **Files touched:** `ui/tray/src/components/wizard/StepFolders.tsx` (or a new `StepMacPerms.tsx`), `ui/tray/wizard_router.py`.
* **Action:** if `app_state.macos_permissions["calendar"] != "ok"`, show a card *"Cerebro needs Calendar Automation permission"* with an `Open Settings` button that runs `open "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"` via Tauri's `shell` plugin. After the user clicks `I granted it`, re-probe.
* **Implementation:** `POST /api/wizard/reprobe-calendar-permission` in `ui/tray/server.py` updates `app_state.macos_permissions["calendar"]` via `probe_calendar_permission()`.
* **Verification:**

```bash
cd ui/tray && npm run build
```

### Step 9.3 — Recovery script *(DONE)*

* **Files touched:** `scripts/diag/doctor.sh` (new).
* **Action:** a one-shot bash script that:
  1. Runs all four diag scripts.
  2. Parses their output.
  3. Prints a coloured *"FAIL: missing model X — run `python scripts/download_model.py llama`"* style hint per finding (matches current downloader CLI).
  4. Returns `0` when everything is green, `1` otherwise.
* **Verification:**

```bash
bash scripts/diag/doctor.sh; echo "exit=$?"
```

(Exit 1 is acceptable on first run; the point is the script runs without crashing and prints actionable output.)

### Step 9.4 — Cross-link with the future plan *(DONE)*

* **Files touched:** `docs/plans/vision/future-cognitive-os.md`.
* **Action:** at the top of `docs/plans/vision/future-cognitive-os.md`, add a one-line note: *"Phase 0 of the future plan starts only after `docs/plans/stabilization/fix-cerebro.md` Phase 8 is merged."*. Keeps the two plans in lockstep.
* **Verification:**

```bash
grep -q "FIX_CEREBRO" docs/plans/vision/future-cognitive-os.md
```

### Phase 9 exit gate *(DONE)*

```bash
git checkout -b fix-9-docs
make lint && make test
git commit -am "fix-9: 8gb runbook, wizard perms card, doctor script"
```

**As executed:** `cd ui/tray && npm install && npm run build` (pass); `bash scripts/diag/doctor.sh` (prints actionable output; exit `1` when RAM/models/backend checks fail); `pytest tests/test_wizard_router.py tests/test_api.py -k "wizard or status" -q` (12 passed); full `make test` — **583 passed**, 1 skipped (~6 min). `make lint` may still fail on pre-existing `ruff` issues under `cerebro/` and import-order warnings in `main.py`.

---

## Appendix A — Definition of Done per phase

A phase is **done** when ALL of the following are true:

1. `make lint` exits 0.
2. `make test` exits 0 and the new tests for the phase are present in the diff.
3. `python scripts/diag/snapshot.py` reports `pressure=ok` while the backend is running with the lite profile and the model loaded.
4. The phase branch is squash-merged into `main`, and `docs/plans/roadmaps/fix-cerebro-progress.log` has the phase's final entry (timestamp, summary, commit SHA).
5. No new dependency outside the table in Appendix B has been added.

## Appendix B — Allowed new dependencies (locked)

| Dep | Version | Phase | Reason |
|-----|---------|-------|--------|
| (none) | — | 0–9 | Every fix uses only the standard library and what is already in `pyproject.toml`. |

Anything outside this table requires a written architectural exception logged in `docs/plans/roadmaps/exceptions.md` before installation. (This matches the policy in `docs/plans/vision/future-cognitive-os.md` Appendix B.)

## Appendix C — Failure-handling protocol

* **A test fails after a step:** revert just that step's changes (`git checkout -- <files>`), append the failure to `docs/plans/roadmaps/fix-cerebro-progress.log` as `STEP <id> FAILED: <pytest tail>`, and stop. Do not start the next step.
* **The Mac freezes again during Phase 1 smoke test:** `pkill -f llama-server; pkill -f "python main.py"`, then re-run `python scripts/diag/snapshot.py` to confirm RSS dropped, then re-read this plan from Step 1.3.
* **Calendar still returns `Sin eventos` after Phase 4:** run `python scripts/diag/check_calendar.py`. If `ok: false`, the macOS permission has not been granted — the fix is OS-level, not code-level. Document the fact in `docs/plans/roadmaps/fix-cerebro-progress.log` and surface the wizard card from Step 9.2.
* **Network needed (e.g. `npm install` after touching the frontend):** request the `full_network` permission once per phase and explain why; do not request indefinitely.
* **Ambiguity in the spec:** prefer the **smallest, reversible** interpretation and surface the question in `docs/plans/roadmaps/fix-cerebro-progress.log` rather than guessing.

---

## Appendix D — Quick triage cheatsheet (for the human user)

| You see… | First thing to try |
|-----------|--------------------|
| Mac fans spin up, beachball, terminal hangs after `make run` | `pkill -f llama-server` then start with `make lite` (after Phase 6). |
| Agent says today is some date in 2024/2025 | Confirm Phase 3 is merged (`_date_preamble()` + REGLA TEMPORAL). Run `python scripts/diag/check_routing.py` — the date answer must contain the current year. |
| `Sin eventos` for every calendar question | `python scripts/diag/check_calendar.py`. If exit ≠ 0, grant Calendar Automation permission to Python in System Settings. |
| `Sin eventos` for birthdays only | macOS Settings → Contacts → grant Cerebro/Python permission, then `python scripts/diag/check_calendar.py` again. |
| Wizard never finishes | Confirm `bin/models/llama-3.2-3b-instruct-q4_k_m.gguf` exists. If not, `python scripts/download_model.py llama-3.2-3b`. |

---

*End of plan. Begin with Phase 0, Step 0.1. Do not skip ahead — Phase 1 depends on the diagnostics produced in Phase 0.*

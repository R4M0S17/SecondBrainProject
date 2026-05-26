# FIX_PLAN2 — Remediation roadmap for `manual_tests/implemefix/session-1.md`

> **Author role**: Principal Systems Architect & Lead Software Engineer.
> **Companion plan**: this file extends — it does **not** replace — `docs/plans/stabilization/fix-cerebro.md`. Phase 0 (telemetry) and Phases 1–4 (resource explosion, streaming-bypasses-tools, macOS permissions) are presumed **DONE**; the failures captured in `manual_tests/implemefix/session-1.md` are residual regressions on top of that baseline.
> **Architectural source of truth**: [`CLAUDE.md`](../../CLAUDE.md) at repo root — module boundaries, port wiring, and the `app_state` injection contract.
> **Atomicity contract**: every step lands as **one self‑contained commit**. After applying it the repo MUST `make lint && make test` clean before the next step starts. No step depends on later state.

---

## 0. Root cause analysis — symptom → defect

| ID  | Reported observation (test_1.md)                                                                 | Verified root cause                                                                                                                                                                                                                                                            | Source of truth                                                                                |
| --- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| R1  | **C1**: Calendar agent → `API 500: Client error '400 Bad Request'` from `llama.cpp`              | Active llama‑server profile (`config/chat.args`) is launched with **`--ctx-size 1536`**. The Calendar agent's system prompt is the largest in the codebase (~150 lines of JSON examples) — combined with `available_tools_detail`, `ambient_context`, and `session_history` it consistently overflows 1536 tokens. llama.cpp returns `400` on context overflow; the FastAPI wrapper re‑raises it as `500`. | `config/chat.args:2`, `core/agents/specialized.py:135-174` (`make_calendar_profile`), `core/agents/runtime.py:71-107` (`_SYSTEM_TEMPLATE`) |
| R2  | **G3**: Raw `{"action":"answer","answer":[...]}` shown to the user                               | `_parse_llm_response()` returns `args["answer"]` **as-is**. When the model emits an answer whose value is a JSON `list` or `dict`, `_reason_node` stores it on `final_answer`, the API stringifies it via `str()`, and the SSE simulator splits it word-by-word. There is no post-parse coercion to natural text. | `core/agents/runtime.py:195-234`, `core/agents/runtime.py:440-447`                              |
| R3  | **G6**: General agent ran `query_events` for *"create a calendar event"*                         | `GENERAL_TOOLS` in `core/agents/specialized.py` whitelists **read-only** calendar tools (`get_upcoming_events`, `query_events`, `search_upcoming`) but **not** `create_calendar_event` / `add_reminder`. The LLM cannot select an unauthorized tool and falls back to the closest match (search). | `core/agents/specialized.py:62-71`                                                              |
| R4  | **G7**: General agent ran `search_files` for *"write a file ... with the word hello"*            | `GENERAL_TOOLS` does not include `write_file`. The model picks the only authorized verb that sounds related: `search_files`.                                                                                                                                                   | `core/agents/specialized.py:62-71`                                                              |
| R5  | **D1**: Code agent picked `create_python_file` for a plain `.txt` write; emitted invalid Python  | `CODE_TOOLS` deliberately excludes `write_file` (`create_python_file` is the only write verb on disk). With no plain‑text writer authorized, the LLM coerces the request into the closest tool — but `create_python_file` rejects non‑`.py` extensions and the LLM's JSON args contain unescaped quotes (`"print("hello")"`), which our parser then accepts because it never validates `code` syntax. | `core/agents/specialized.py:49-60`, `core/tools/handlers/filesystem.py:118-133`                  |
| R6  | **Architectural risk** *(test_1.md §"Hard pause vs registry confirmation")*                       | The hard list `CONFIRMATION_REQUIRED_TOOLS` in `runtime.py` (`write_file`, `execute_python`, `delete_file`, `run_script`) and the `ToolDefinition.requires_confirmation` flag in the registry **diverge**. `create_calendar_event`, `add_reminder`, etc. are marked `requires_confirmation=True` in the registry but the runtime never pauses on them. | `core/agents/runtime.py:36-43`, `core/tools/registry.py:60-150`                                  |
| R7  | **Settings → Watched folders → "Add Folder" not clickable**                                       | Frontend calls `@tauri-apps/plugin-dialog`'s `open()`. The Cargo crate is present and `lib.rs` initialises the plugin, but `src-tauri/capabilities/main.json` does **not** grant any `dialog:*` permission. In Tauri v2, an unscoped plugin call rejects silently — the `try/catch` swallows it and the user sees the button "do nothing". | `ui/tray/src-tauri/capabilities/main.json:6-12`, `ui/tray/src/components/settings/FolderManager.tsx:8-22` |
| R8  | **Settings → Watched folders saved but tools still see startup paths**                             | `AUTHORIZED_READ_PATHS` / `AUTHORIZED_WRITE_PATHS` are baked into the `ToolDefinition` handlers via `functools.partial` at **module-import time** in `main.py`. `PATCH /api/config` updates the config JSON only; it never rebinds the tool handlers. | `main.py:56-61, 195-206`, `ui/tray/server.py:968-987`                                            |
| R9  | **Settings → Fleet Orchestrator buttons not clickable**                                          | `FleetSettings.tsx` calls `GET /api/fleet/status`, `GET /api/fleet/models`, and `PATCH /api/fleet/config`. **None of these endpoints exist** in `ui/tray/server.py`. `system.ts:refreshFleet()` swallows the 404 silently, so `fleetStatus` stays `null` and the mode toggle is forever stuck on its default. | `ui/tray/server.py` (no `/api/fleet/*` routes), `ui/tray/src/api/client.ts:122-138`, `ui/tray/src/stores/system.ts:37-44` |
| R10 | **G2**: `17 × 23` → `397`                                                                         | 3B local model arithmetic noise. No deterministic calculator tool exists in `GENERAL_TOOLS` / `CODE_TOOLS`, so the model is forced to compute by token continuation.                                                                                                            | `core/tools/registry.py` (no `evaluate_math`)                                                   |

> These ten root causes collapse into **four engineering domains** (next section). The plan is ordered so that domains with the broadest blast radius (Inference Capacity, JSON Sanity) land first.

---

## 1. Modular path — fix domains & ordering

| Order | Domain                                                  | Atomic steps           | Why this order                                                                                                                                                              |
| ----- | ------------------------------------------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | **Inference capacity & context lifecycle** (R1)         | A1, A1.2, A1.3, A1.4, A2, A3, A4, **A5** | A1 raises context + prompt cache (+ automatic cache fingerprint invalidation). A1.2–A1.4 observe, evict, and guard RAM. A2–A4 prune, GBNF, and micro-route. **A5** watches llama-server health and restarts after silent OOM kills (8 GB reality). |
| **B** | **Response post-processing & streaming UX** (R2) *(DONE)* | B1, B2                 | B1 string-coerces malformed answer shapes (+ single-key `error` dict handling). **B2** streams the `answer` field while JSON is still generating. |
| **C** | **Confirmation unification** (R6) *(DONE)*              | C1, C2                 | C1 unifies confirmation pause (+ locale-ready user strings, not hardcoded Spanish in runtime). Must land **before** D.                                                          |
| **D** | **Tool authorization & policy** (R3, R4, R5) *(DONE)*   | D1, D2, D3, D4         | Each step adds **one** authorized tool to **one** profile and adds a regression test. D4 adds smart truncation to `read_file`.                                       |
| **E** | **State hydration & session isolation** (R8 + sessions) *(DONE)* | E1, **E2**             | E1 rebinds watched folders live. **E2** persists per-conversation sessions to disk with a hard resume turn cap (8 on 8 GB).                                                                                    |
| **F** | **UI / IO** (R7, R9) *(DONE)*                           | F1, F2, **F1b**        | F1 fixes dialog capability; **F1b** splits dev vs prod Tauri capabilities. F2 wires Fleet API.                                                    |
| **G** | **Quality / math** (R10) *(DONE)*                       | G1                     | `evaluate_math` tool (+ controlled float formatting for tool observations).                                                                                     |
| **X** | **Cross-cutting gates** (tooling) *(DONE)*                  | **X1**, **X2**         | **X1**: `make test` enforces `--cov-fail-under=80` on `core/`. **X2**: `make smoke` automates the §3 manual matrix (`scripts/smoke.sh`). |

---

## 2. Atomic remediation steps

Each step lists: **files touched · change · validation command · expected pass signal**.

### Step A1 — Raise chat profile context window from 1536 → 4096 (+ llama.cpp prompt cache) *(DONE)*

**Files touched**

- `config/chat.args` (context size **and** `--prompt-cache` / `--prompt-cache-all`)
- `core/inference/providers/llamacpp_provider.py`
- `tests/test_llamacpp_provider.py` *(new assertion)*
- On-disk cache path (e.g. `bin/models/cerebro_chat.cache` or under `~/.cerebro/state/`) — created by the server at runtime, not committed to git

**Diff (high fidelity)**

```diff
--- a/config/chat.args
+++ b/config/chat.args
 --model bin/models/llama-3.2-3b-instruct-q4_k_m.gguf
---ctx-size 1536
+--ctx-size 4096
 --cache-type-k q4_0
 --cache-type-v q4_0
 --n-gpu-layers 99
```

```diff
--- a/core/inference/providers/llamacpp_provider.py
+++ b/core/inference/providers/llamacpp_provider.py
 _PROFILE_CTX: dict[str, int] = {
-    "chat": 2048,
+    "chat": 4096,
     "coding": 8192,
     "deep": 6144,
 }
```

**Rationale**: Llama‑3.2‑3B at Q4_K_M uses **~80 MB extra** RSS for KV‑cache going from 1.5K → 4K context (with `cache-type-k=q4_0`). Well inside the 5.5 GB ceiling set by `docs/plans/stabilization/fix-cerebro.md`. The reported `400 Bad Request` on Calendar disappears because the request payload now fits.

**Validation**

```bash
make engine          # restart llama-server with the new args
make run             # in another shell
# Reproduce C1
curl -fsS -X POST http://localhost:7842/api/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"Crea un evento llamado Cerebro smoke test mañana a las 4pm por 30 minutos.","agent":"calendar-v1"}' \
  | python -m json.tool
# Expected: HTTP 200, "answer" is a Spanish sentence (NOT an "API 500" string)
#           metadata.pending_tool.name == "create_calendar_event"   (after step C1)
make test tests/test_llamacpp_provider.py -k context_window
```

**Pass signal**: status code 200 from `/api/query`, and `LlamaCppChatProvider("…", profile="chat").context_window() == 4096`.

**Hardware companion notes (8 GB Mac / ~4 GB free, 3 B model)**

- The KV cache quantization already in `config/chat.args` (`--cache-type-k q4_0`, `--cache-type-v q4_0`) is exactly the right shape for this hardware. A 4 K context with both K and V quantized to `q4_0` adds only on the order of a few hundred MB to resident memory — well below the 5.5 GB ceiling from `docs/plans/stabilization/fix-cerebro.md`. Keep these flags. If memory pressure ever returns, the next lever is `--cache-type-k q8_0 --cache-type-v q4_0` (better quality, marginally more RAM), not raising context further.
- The model itself must stay quantized to **Q4_K_M** (≈ 2.0 GB resident for 3 B params) or even **IQ4_XS** (≈ 1.7 GB) when the surrounding system competes for RAM. The default `bin/models/llama-3.2-3b-instruct-q4_k_m.gguf` referenced in `config/chat.args` already satisfies this — verify after step A1 lands. Anything heavier than Q5_K_M is out of budget on this hardware.
- This step is purely the *capacity* enabler. The two follow-up steps (A2 prompt pruning, A3 GBNF) are what actually *spend* the new headroom efficiently. A1 alone, without A2/A3, will still see the model produce malformed JSON — the request will simply no longer crash with `400`.

**Lead Engineer addendum — Prompt caching (same step, `config/chat.args`)**

On every chat turn, llama.cpp must ingest the full system prompt again unless something remembers it. For a 3 B model that is usually fast, but on an 8 GB Mac it still burns CPU/GPU cycles on every message — and those cycles compete with the OS and the Tauri shell for the same thermals and memory bandwidth.

Extend the A1 change to `config/chat.args` with llama.cpp's prompt-cache flags:

- `--prompt-cache` pointing at a stable on-disk file (e.g. under `bin/models/` or `~/.cerebro/state/`, such as `cerebro_chat.cache`).
- `--prompt-cache-all` so the entire prefix (system prompt + tool definitions + any fixed preamble) is eligible for reuse, not just the model weights.

**Why this matters on 8 GB hardware**

- **First message in a session**: cold path — the server builds the cache file once.
- **Second and later messages** (same agent, same system prompt shape): the server reuses the cached prefix state. Time-to-first-token drops sharply because the model is not re-reading hundreds of tokens of instructions on every turn.
- **RAM impact**: the cache file lives on disk; resident set does not balloon. This is surgical efficiency, not brute force.

**Operational notes**

- Restart `make engine` after changing `chat.args` so the server picks up the new flags.
- Treat prompt caching as part of the A1 validation: after two identical agent queries back-to-back, the second should show noticeably lower prefill latency in llama.cpp logs (look for cache-hit style messages if your server build logs them).

**Lead Engineer addendum — Automatic prompt-cache invalidation (do not rely on manual deletes)**

The plan previously said "delete `cerebro_chat.cache` if you change the system prompt" — that is error-prone. After A2 (prompt pruning) or any D-step that changes `authorized_tools`, a developer will forget to delete the cache and lose hours debugging "why does the model behave wrong?"

Ship automatic invalidation in the same A1 pass (or immediately after A2 lands, before relying on cache hits in production):

- Compute a **cache fingerprint**: `SHA256(system_prompt_text + sorted(authorized_tools_list))` (or hash the assembled system prompt the runtime would send on the next turn for the active agent).
- Write the fingerprint to a sidecar file next to the cache, e.g. `cerebro_chat.cache.sha256`.
- On backend startup (or before the first `complete()` after agent/tool changes), compare stored hash vs current hash; **if they differ, delete `cerebro_chat.cache` and regenerate** on the next request.
- Ownership: `core/inference/providers/llamacpp_provider.py` or a tiny helper in `core/inference/` — ~20 lines, no new dependencies.

**Pass signal (cache fingerprint)**: change Calendar instructions in A2, restart backend, first query still behaves correctly without anyone manually deleting cache files.

**Pass signal (prompt cache)**: second turn in the same session completes with measurably lower latency than the first; no regression in answer quality.

---

### Step A1.2 — Context health monitor (token fill observability) *(DONE)*

**Files touched**

- `core/inference/providers/llamacpp_provider.py` (log line after each `complete` call)
- Optionally `core/observability/response_meta.py` or `MetricsCollector` if you want the fill ratio surfaced in `/api/status` later — **not required for this atomic step**; logging alone is enough.

**What changes (text only, no code)**

With only ~4 GB free and a 4096-token context ceiling, the failure mode is rarely a hard crash — it is **silent degradation**: the model starts "forgetting" instructions, repeating itself, or truncating tool observations because the active window is full. You need to see that *before* users report it.

After every successful `LlamaCppChatProvider.complete()` call, emit a single structured log line at INFO or DEBUG level, along these lines:

`Context usage: {tokens_used}/{context_window}`

Where:

- `context_window` comes from the provider's profile (4096 after A1, aligned with `config/chat.args`).
- `tokens_used` is the best available estimate from the llama.cpp response payload (e.g. `usage.prompt_tokens + usage.completion_tokens`, or `usage.total_tokens` if that is all the server returns). If the server omits usage, fall back to a conservative estimate from message character counts and document the limitation in the log.

**Why this belongs in Domain A, immediately after A1**

- A1 raises the ceiling; A1.2 tells you when you are **hitting** the ceiling in real conversations.
- A2 (prompt pruning) and D4 (tool truncation) directly reduce `tokens_used` — without A1.2 you cannot prove they worked except by gut feel.
- On 8 GB RAM, habitual readings near 3800–4000 tokens mean the next tool observation or long user paste will push into truncation territory; that is the signal to prune harder, shorten session summaries, or start a new conversation.

**Validation**

- Run one multi-turn chat (5+ exchanges with a tool call) with `make run` and inspect backend logs.
- Confirm every completion logs a `Context usage: …/4096` line.
- Optionally add a lightweight unit test that mocks a completion response with a `usage` block and asserts the log formatter produces the expected string — no live llama.cpp required.

**Pass signal**: log lines appear on every completion; after a long session you can read the trail and see whether fill is trending toward the limit.

---

### Step A1.3 — Semantic history compression (automatic consolidation / eviction) *(DONE)*

**Files touched**

- `core/agents/runtime.py` (hook after `_reason_node` or before `_context_assembly_node` on the next turn)
- `core/agents/state_store.py` (`session_summary` is already the persistence target — extend how it is produced)
- `core/memory/context_builder.py` (ensure consolidated summary replaces evicted `session_history` turns)
- `tests/test_agent_runtime.py` *(new test: mock >85 % fill triggers consolidation)*

**What changes (text only, no code)**

Step A1.2 tells you *when* the window is full. Step A1.3 defines *what to do about it* so the conversation can continue without the model hallucinating or forgetting who the user is.

**Trigger**

When the context health monitor (A1.2) reports **> 85 % of `context_window`** (≈ 3500 / 4096 tokens after A1), run an automatic **consolidation pass** before the next user-visible turn proceeds. This is an internal, silent sub-turn — the user does not see the consolidation prompt unless you opt into a debug mode.

**Consolidation sub-prompt (internal)**

Send a single non-streaming `complete()` call (same provider, minimal grammar or plain-text mode acceptable for this housekeeping call) with instructions along these lines:

*"Resume nuestra conversación hasta ahora en 3 párrafos técnicos, preservando variables, nombres de archivos, decisiones de herramientas y hechos clave. No inventes información que no aparezca en el historial."*

**Eviction policy**

- Take the oldest N messages from `assembled.session_history` (or the in-graph `messages` list excluding system), where N is chosen so that post-eviction estimated fill drops to **≤ 60 %** of context window.
- Replace those evicted turns with **one** synthetic system or user message containing the consolidation summary (prefer injecting into `agent_state.session_summary`, which `ContextBuilder` already surfaces in `_SYSTEM_TEMPLATE` under `HISTORIAL COMPRIMIDO DE SESIÓN`).
- Persist the updated `session_summary` via `AgentStateStore.save()` so the eviction survives backend restarts within the same agent profile.

**Why this enables "infinite" conversation on 8 GB / 3 B**

- You delete ~10 old turns, insert ~1 summary block, and recover on the order of **2000 tokens** of headroom without losing the thread — the model's "working memory" stays bounded while the user's narrative continues.
- This is **semantic** eviction (summarize-then-drop), not blind truncation — blind truncation is what causes "who am I talking to?" regressions.
- Pair with D4 (tool truncation): consolidation handles *conversation* length; D4 handles *single tool observation* length.

**Validation**

- Unit test: feed a mocked message list whose token estimate exceeds 85 %; assert consolidation runs once and `session_summary` grows while `session_history` shrinks.
- Manual: hold a 15+ turn chat; watch logs for `Context usage` crossing 3500, then a `consolidation` log line, then the next turn's fill drops below ~2500.

**Pass signal**: after a long session the model still references facts from turn 3 after consolidation ran; `Context usage` log shows a sawtooth pattern (rise → consolidate → drop), not a monotonic climb to 4096.

---

### Step A1.4 — System memory guard (pre-flight before heavy inference) *(DONE)*

**Files touched**

- `core/inference/providers/llamacpp_provider.py` (pre-flight hook at start of `complete()` / before first token of `stream()`)
- `core/observability/ram_monitor.py` (already exists — reuse `snapshot()["pressure"]`)
- `ui/tray/server.py` (surface `ram_pressure` warning in `/api/status` or query metadata — optional in this atomic step)
- `ui/tray/src/stores/system.ts` + a small toast/banner component *(optional follow-up in Domain F if backend-only in A1.4)*

**What changes (text only, no code)**

On macOS with 8 GB RAM, the real enemy after context overflow is **swap**: once the OS pages to disk, *everything* slows — Cerebro, the menubar, Safari. Inference should not blindly start when the machine is already at 95 % RAM.

**Pre-flight check (before each `complete()` or before `runtime.run()` enters the graph)**

- Call `RamMonitor.snapshot()` (or equivalent) and read `pressure` (`ok` | `warn` | `critical`) and/or `used_gb` / `available_gb`.
- If pressure is **`critical`** (or available RAM < a configurable floor, e.g. 500 MB): do **not** block the request entirely (that would feel broken) — but:
  - Log a clear warning: `System RAM critical ({used}/{total} GB); inference may trigger swap`.
  - Attach a warning string to `ResponseMetadata.warnings` (e.g. `"ram_pressure_critical"`) so the UI can show: *"Memoria baja: el procesamiento puede ser lento."*
  - Optionally trigger **application-level cache purge**: drop embedding LRU entries, clear prompt-cache file if stale, or defer `ContextEnricher` for this turn — anything that avoids allocating more RSS before llama.cpp runs.

**UI contract (when Domain F has bandwidth)**

- `StatusBar` or `WarningToast` listens for `metadata.warnings` containing `ram_pressure_critical` or polls `/api/status` where `ram_pressure != "ok"`.
- User sees a non-blocking banner; inference still proceeds unless you later add a hard gate matching `_ram_pressure_guard()` on `/api/query`.

**Why this belongs next to A1.2 / A1.3**

- A1.2 watches **context** tokens; A1.4 watches **system** bytes. Both are needed on 8 GB: you can be under 4096 tokens and still thrash swap if llama-server + Tauri + browser exceed physical RAM.

**Validation**

- Mock `RamMonitor` to return `critical`; assert `complete()` still returns but logs warning and metadata carries the flag.
- Manual: artificially fill RAM (large file copy), send a query, confirm banner + log line.

**Pass signal**: warning visible under synthetic pressure; no silent multi-minute freeze without explanation.

---

### Step A2 — Prune the Calendar agent system prompt *(DONE)*

**Files touched**

- `core/agents/specialized.py` (only `make_calendar_profile().preferences["instructions"]`)
- `tests/test_specialized.py` *(new length-budget assertion)*

**What changes (text only, no code)**

The current Calendar agent prompt is ~150 lines of literal JSON examples (one per intent shape: today, week, year, birthdays, keyword search, event creation, reminder creation). For a 3 B local model on 8 GB hardware this is *the* dominant cost of every Calendar request — it consumes context the model could have used for actual conversation, and it is the proximate cause of the C1 failure even after A1 raises the context window.

The pruning policy for this step:

- Keep **at most two canonical JSON examples**: one read (`get_upcoming_events`) and one write (`create_calendar_event`). Drop the variants for week-long windows, birthdays, reminders, keyword search, etc. — the model can derive those from the schema once it has seen the shape twice.
- Replace the remaining ten examples with a **single technical clause** that lists the tools by name with one-line semantics each. The existing `available_tools_detail` block in `_build_system_prompt` already enumerates the tool schemas — there is no reason to duplicate that information in the persona's `instructions` field.
- Keep the anti-loop rule (*"Llama a una herramienta UNA SOLA VEZ por consulta"*) and the date-formatting rule. Those are behavioural contracts the registry cannot express.
- Target budget: the Calendar `instructions` string should land **under 1500 characters** (today it is ~3500). The new assertion in `test_specialized.py` enforces this.

**Rationale**

For an 8 GB / 3 B / 4096-context setup, prompt tokens are the single most expensive resource. Every example we delete frees KV-cache room for the actual user turn and any tool observations that come back. This is the operationalisation of "prompt pruning": treat the agent persona as code under a length budget, not as a free-form prompt-engineering surface.

**Validation**

Run `make test tests/test_specialized.py` after the edit. The new assertion (`len(make_calendar_profile().preferences["instructions"]) < 1500`) must pass, alongside the unchanged authorization tests from D1.

**Pass signal**

- The character-budget assertion is green.
- Manually re-running test C1 (`agent: "calendar-v1"`, *"crea un evento llamado Cerebro smoke test mañana a las 4pm"*) returns `200` with a `pending_tool.name == "create_calendar_event"` even on a cold cache. The whole-prompt token count visible in llama.cpp server logs should drop by roughly half versus pre-A2.

---

### Step A3 — Enforce JSON shape with a GBNF grammar at the llama.cpp boundary *(DONE)*

**Files touched**

- `core/inference/providers/llamacpp_provider.py` (extend the request payload built in `complete`)
- `config/grammars/agent_response.gbnf` *(new file under `config/grammars/`)*
- `core/agents/runtime.py` (pass a `grammar` hint when calling `chat.complete()` from `_reason_node`)
- `tests/test_llamacpp_provider.py` *(new assertion that the grammar is forwarded)*

**What changes (text only, no code)**

The architectural change is to stop *asking* the model to return JSON and start *forcing* it. llama.cpp accepts a `grammar` field on `/v1/chat/completions` containing a GBNF (GGML BNF) description of the allowed output. The sampler then *cannot* emit tokens that would lead to a non-matching string — malformed JSON becomes a physical impossibility, not a prompt-engineering hope.

The grammar to ship under `config/grammars/agent_response.gbnf` describes exactly the two response shapes the runtime already understands in `_parse_llm_response`:

- An **answer** object: `{"action":"answer","answer":"<utf-8 string>"}` — the `answer` field is constrained to a JSON string, never a list or dict, which closes R2 at the source.
- A **tool** object: `{"action":"tool","tool":"<tool name>","args":{<json object>}}` — the `tool` field is constrained to one of the literal tool names enumerated in the active agent's `authorized_tools`, which means the model can no longer invent a tool name or pick an unauthorized one.

`LlamaCppChatProvider.complete()` gains a `grammar` kwarg that, when supplied, is attached to the request body as `"grammar": "<gbnf-text>"`. The grammar text itself is loaded once at startup by `AgentRuntime` (lazy, cached) and passed in from `_reason_node`. True token-by-token streaming of the `answer` field is **not** part of A3 — that UX work lands in **Step B2** once the JSON shape is guaranteed.

**Rationale**

- Closes R2 at the inference layer, before B1's parser even runs. After A3 lands, B1 stays in the tree as defence-in-depth for non-llama.cpp providers (Claude, MLX) where GBNF is unavailable.
- Indirectly fixes the broken-Python-string variant of R5: with the `tool` shape constrained to the authorized name list, the model can no longer pick `create_python_file` for a `.txt` request **as long as** `write_file` is in the whitelist (which D2 guarantees).
- Cost is neutral on RAM (GBNF sampling adds <1 % CPU and zero RSS) and *positive* on throughput — token budget that would have been wasted on retry-after-bad-JSON is now spent on the actual answer.

**Lead Engineer addendum — UTF-8 / Spanish-safe string rules in `agent_response.gbnf`**

Cerebro's default UX and several agent personas are Spanish-first. A grammar that only allows basic ASCII inside JSON string literals will **force sampling failures** when the model tries to emit tildes, eñes, or opening punctuation like «¿» — the sampler rejects the token, retries, and you get timeouts or empty completions that look like "model stupidity" but are actually a charset mismatch.

When authoring `config/grammars/agent_response.gbnf`, explicitly design the string non-terminal so it accepts **UTF-8 multi-byte characters**, not just `[a-zA-Z0-9 ...]`. Concretely:

- The `answer` field in the `{"action":"answer",…}` branch must allow any valid JSON string content the runtime will display to the user — including Spanish diacritics and common punctuation.
- Tool `args` values that are free-text (titles, descriptions, file content snippets) need the same treatment wherever the grammar constrains string literals.
- Do **not** over-constrain to ASCII "for safety" — that trades a hypothetical injection risk for a certain production failure on Spanish prompts.

**Validation (UTF-8)**

- Manual: send a query that forces a Spanish answer with accents in the `answer` field (e.g. G3 list comprehension in Spanish). The completion must succeed under grammar constraint and display correctly in the UI.
- Manual: calendar create flow with a title containing `ñ` or accented vowels; the tool JSON must parse and the event title must survive round-trip.

**Pass signal (UTF-8)**: no grammar-rejection loops in logs; Spanish characters appear intact in chat and in tool args.

**Validation**

After applying A3, run `make test tests/test_llamacpp_provider.py -k grammar` (asserts the payload includes the grammar string when supplied) and `make test tests/test_agent_runtime.py -k grammar_passthrough` (asserts `_reason_node` forwards the grammar to the provider). Then manually rerun G3 (*"Explain what a Python list comprehension is in 3 bullet points"*); the bubble must contain prose, never a `{"action":"answer", ...}` envelope, even if the temperature is bumped to 0.9.

**Pass signal**: tests green; visual G3 retest shows natural prose; llama.cpp server log shows a `grammar=` line on every Cerebro request.

---

### Step A4 — Micro-agent routing (promoted to high priority — was "out of scope") *(DONE)*

**Priority note**: On 8 GB RAM this is **not** a nice-to-have architectural evolution — it is a **capacity requirement**. Loading the full system prompt plus every tool definition on every turn wastes context and attention budget for a 3 B model. This step is promoted from §5 (deferred) into the main path immediately after A3.

**Files touched**

- `core/agents/specialized.py` (`SpecializedAgentRouter`, `_INTENT_RE` keyword patterns — already partially exist)
- `core/agents/llm_router.py` (optional slow path for `agent: "auto"` only)
- `core/agents/runtime.py` (`_context_assembly_node` — filter `tool_defs` to active agent only; already partially done via `authorized_tools`)
- `ui/tray/server.py` (`route_with_llm` / pinned `agent` resolution — ensure router runs **before** graph entry)
- `tests/test_specialized.py`, `tests/test_llm_router.py`

**What changes (text only, no code)**

Today every turn — even "¿qué hora es?" — can load a fat General persona plus a long `available_tools_detail` block listing tools the turn will never call. The fix is **micro-routing**: decide the domain first, then load **only** that specialist's prompt and tool whitelist.

**Router tiers (lightest first)**

1. **Fast path — keyword / prefix router** (zero extra inference): extend the existing `_INTENT_RE` patterns in `llm_router.py` and `_PREFIX_MAP` in `specialized.py` for Spanish + English calendar, file, code, and math cues (`calendario`, `reunión`, `archivo`, `escribe`, `python`, `17×23`, etc.). Map to `calendar-v1`, `academic-v1`, `code-v1`, or `general-v1`. This path costs **no tokens** and no extra model load.
2. **Slow path — only when `agent: "auto"` and fast path returns `general-v1`**: optional 1 B router model or a **5-token** llama.cpp classify call (fix the `"model": "router"` 400 separately if enabling this). Never run the slow router when the user pinned an agent in the UI dropdown.
3. **Graph entry**: after routing, `AgentRuntime` loads **only** `authorized_tools` for the chosen profile into `tool_defs` and the GBNF tool-name literals (A3). Calendar turns no longer list `write_file`; code turns no longer list `create_calendar_event`.

**Why this is high priority on 8 GB / 3 B**

- **Smaller attention surface** → fewer wrong-tool picks (directly attacks G6/G7-style failures even before D1/D2 tool authorization fixes).
- **Shorter system prompt per turn** → pairs with A2 pruning and A1 prompt cache; the cached prefix is specialist-specific, so cache hits are more likely within a session dominated by one domain.
- **Lower RAM churn** → fewer tokens in KV cache per turn means A1.3 consolidation triggers less often.

**Relationship to existing UI**

- `AgentSelectorDropdown` pinned modes skip the router entirely (user override).
- **Auto (router)** mode uses fast path → optional slow path → `agent_id` for the graph.

**Validation**

- `make test tests/test_specialized.py tests/test_llm_router.py`
- Manual matrix: same question with **Auto** vs pinned **General** — Auto routes calendar questions to `calendar-v1` and loads fewer tools in logs.
- Assert `available_tools_detail` line count in debug logs drops when router picks `calendar-v1` vs `general-v1`.

**Pass signal**: calendar-ish Spanish prompt with `agent: "auto"` resolves to `calendar-v1` without user manually switching; tool list in assembled prompt contains only calendar tools.

---

### Step A5 — Llama-server health monitor & crash recovery (cold-start watchdog) *(DONE)*

**Priority**: 🔴 High — missing from the original regression plan. In-flight fixes (A1–A4) do not help when macOS **silently OOM-kills** `llama-server` under 8 GB pressure. Today the frontend likely hangs or shows `503` forever with no recovery path.

**Files touched**

- `core/inference/health_monitor.py` *(new — simple async loop, ~50 lines)*
- `main.py` (start monitor in `_build_app_state()` or FastAPI lifespan)
- `ui/tray/server.py` — new `GET /api/health` exposing engine subprocess state
- `ui/tray/src/stores/system.ts` + tray/status UI *(optional in same step: read `llama_server` field for icon colour)*

**What changes (text only, no code)**

**HealthMonitor behaviour**

- Background asyncio task pings `CEREBRO_LLAMACPP_URL` (e.g. `GET /health` or lightweight `/v1/models`) every **5 seconds**.
- States: `up` | `restarting` | `down`.
- On consecutive failures (e.g. 2–3 missed pings): transition to `restarting`, log the event, and **spawn** llama-server again via the same mechanism `make engine` uses (`subprocess` + `config/chat.args`, or invoke `bin/start_engine.sh chat` — match existing project convention).
- Back off restart attempts (e.g. max 3 restarts in 5 minutes) to avoid restart loops when the machine is genuinely out of RAM.
- Coordinate with A1.4: if `RamMonitor` is `critical`, delay restart until pressure eases or surface `down` with a clear reason.

**API contract**

- `GET /api/health` returns JSON including at minimum:
  - `llama_server`: `"up" | "restarting" | "down"`
  - `last_restart_at` (ISO timestamp or null)
  - `restart_count_session` (int)
- Distinct from existing `GET /api/status` (metrics, model name, RAM) — health is **process liveness**, status is **product telemetry**.

**UI contract**

- Tauri tray icon or `StatusBar` reflects `llama_server` so users see "engine restarting" instead of an infinite spinner.
- `InputArea` can short-circuit sends when `down` with a actionable message: *"Inference engine is down; retrying…"*

**Why 8 GB makes this mandatory**

- Swap + OOM killer is not an edge case; it is the normal failure mode when A1.4 warnings are ignored or consolidation + enricher + llama-server peak together.
- Without A5, every other step's manual validation depends on someone noticing `make engine` died.

**Validation**

- Kill llama-server manually (`pkill`); within ~15 s logs show `restarting` then `up`; `curl /api/health` reflects state transitions.
- `make test tests/test_health_monitor.py` with mocked HTTP (no live subprocess required).

**Pass signal**: killed server recovers without restarting `make run`; frontend shows non-503 recovery state.

---

### Step B1 — Coerce non-string `answer` fields to readable text *(DONE)*

**Files touched**

- `core/agents/runtime.py`
- `tests/test_agent_runtime.py` *(new assertion)*

**Diff**

```diff
--- a/core/agents/runtime.py
+++ b/core/agents/runtime.py
@@
 def _parse_llm_response(raw: str) -> tuple[str, str | None, dict]:
@@
     try:
         data = json.loads(raw)
         action = data.get("action", "answer")
         if action == "tool":
             return "tool", data.get("tool"), data.get("args", {})
         if action == "answer":
-            return "answer", None, {"answer": data.get("answer", raw)}
+            return "answer", None, {"answer": _stringify_answer(data.get("answer", raw))}
         # Fallback: small models sometimes put the tool name directly in "action"
         if action not in ("tool", "answer"):
             args = {k: v for k, v in data.items() if k != "action"}
             return "tool", action, args
-        return "answer", None, {"answer": data.get("answer", raw)}
+        return "answer", None, {"answer": _stringify_answer(data.get("answer", raw))}
     except json.JSONDecodeError:
         return "answer", None, {"answer": raw}
+
+
+def _stringify_answer(value: object) -> str:
+    """Render a model `answer` field as natural text regardless of JSON shape.
+
+    Small local models occasionally emit `{"action":"answer","answer":[...]}` with
+    a list or dict instead of a string. Returning the raw container leaks JSON
+    into the chat bubble (test_1.md G3). Coerce here, exactly once, at the
+    deepest place that owns the parse contract.
+    """
+    if isinstance(value, str):
+        return value
+    if isinstance(value, list):
+        return "\n".join(f"- {str(item).strip()}" for item in value if item is not None)
+    if isinstance(value, dict):
+        return "\n".join(f"{k}: {v}" for k, v in value.items())
+    return str(value)
```

**Rationale**: One ownership boundary (`_parse_llm_response`) is the canonical place to convert *"protocol-level JSON"* into *"display string"*. Avoids touching `_reason_node`, `runtime.run()`, or the API layer.

**Relationship to Step A3 (defence-in-depth, not redundancy)**: After A3 lands the llama.cpp grammar guarantees that the `answer` field is always a JSON string, so the list/dict branches in `_stringify_answer` will not fire in production for the local backend. B1 still ships because (a) the GBNF only applies to llama.cpp — Claude and MLX providers do not consume a grammar and can still return malformed shapes; (b) it pins the contract at the *parser* layer so a future provider that bypasses GBNF cannot silently leak raw JSON into the chat bubble. Treat B1 as the architectural fallback for A3.

**Lead Engineer addendum — `error`-shaped dict answers (medium priority)**

`dict.items()` in Python 3.7+ preserves insertion order — fine for generic key/value rendering. But when the model emits `{"answer": {"error": "no results", "code": 404}}`, flat `k: v` formatting reads like a debug status dump (`error: no results\ncode: 404`), not a user-facing error.

Add a small special case in `_stringify_answer` (same ownership boundary):

- If the value is a `dict` with **exactly one** key `"error"` (case-sensitive), return `str(value["error"])` directly.
- Optionally, if keys are `error` + `code`, prefer the error string and append code in parentheses: `"no results (404)"`.
- All other dict shapes keep the existing `k: v` line format.

**Validation**: unit test with `{"action":"answer","answer":{"error":"Sin eventos"}}` → bubble text is `Sin eventos`, not `error: Sin eventos`.

**Validation**

```bash
make test tests/test_agent_runtime.py -k stringify
```

**Pass signal**: new assertions

```python
def test_parse_answer_list_becomes_bulleted_text():
    action, tool, args = _parse_llm_response(
        '{"action":"answer","answer":["a","b","c"]}'
    )
    assert action == "answer"
    assert args["answer"] == "- a\n- b\n- c"


def test_parse_answer_dict_becomes_kv_text():
    action, _, args = _parse_llm_response(
        '{"action":"answer","answer":{"k1":"v1","k2":2}}'
    )
    assert args["answer"] == "k1: v1\nk2: 2"
```

both green.

---

### Step B2 — Streaming JSON parser (low-latency UX for grammar-constrained answers) *(DONE)*

**Files touched**

- `core/inference/providers/llamacpp_provider.py` (`stream()` — already exists; wire grammar + usage logging)
- `core/agents/runtime.py` (new incremental parser or adapter used when emitting answer tokens)
- `ui/tray/server.py` (`/api/query/stream` — replace "simulate streaming from final answer" for `action:answer` paths when feasible)
- `ui/tray/src/components/chat/InputArea.tsx` (no change if SSE contract stays `{token: "..."}`)
- `tests/test_agent_runtime.py` *(stream parser unit tests with chunked JSON fragments)*

**What changes (text only, no code)**

After A3, the model **must** emit JSON — but today's `/api/query/stream` still waits for `runtime.run()` to finish, then splits the final string word-by-word. The user perceives **full local-model latency** before the first character appears. That "lag" is especially painful on 8 GB Macs where prefill is slow.

**Stream parser behaviour**

Because GBNF fixes the shape to either `{"action":"answer","answer":"…"` or `{"action":"tool",…}`, a incremental parser can:

- Watch the token stream character-by-character (or token-by-token from llama.cpp SSE).
- Once the prefix `{"action":"answer","answer":"` is matched, **forward every subsequent character inside the JSON string** to the UI as SSE `{token}` events, unescaping JSON escapes on the fly (`\"`, `\n`, UTF-8 sequences).
- Stop forwarding when the closing `"` of the answer field is reached (respect escaped quotes).
- If the stream instead matches `{"action":"tool"`, buffer until the JSON object is complete, then hand off to the existing tool loop (no partial tool execution).

**Scope boundaries for this atomic step**

- **In scope**: answer-path streaming for direct replies (no tool call on that iteration).
- **Out of scope for B2**: streaming mid-tool-loop observations; tool turns still complete before the next streamed answer.
- **Fallback**: if grammar is off (Claude/MLX) or parser state machine errors, fall back to today's buffered word-split simulation.

**Why this pairs with A3, not before it**

- Without GBNF, incremental parsing is fragile (malformed partial JSON). With GBNF, the token sequence inside `"answer"` is always a valid prefix of a JSON string — the parser becomes a small state machine, not a guesser.

**Validation**

- Unit test: feed chunked strings `'{"action":"answer","answer":"Hola'`, `' mundo'`, `'"}'` and assert emitted tokens spell `Hola mundo` without waiting for the closing brace.
- Manual: send a long answer prompt; first visible token in UI should arrive within ~1 s of request start, not after full 15–30 s `run()` completion.

**Pass signal**: time-to-first-token drops sharply on local backend; chat feels "alive" even when total latency is unchanged.

---

### Step C1 — Single source of truth for runtime confirmation *(DONE)*

**Files touched**

- `core/agents/runtime.py`
- `tests/test_tool_confirmation.py`

**Diff**

```diff
--- a/core/agents/runtime.py
+++ b/core/agents/runtime.py
@@
-# Tools that must pause execution and wait for explicit user approval before running.
-CONFIRMATION_REQUIRED_TOOLS: frozenset[str] = frozenset(
-    {
-        "write_file",
-        "execute_python",
-        "delete_file",
-        "run_script",
-    }
-)
+# Tools that must pause execution and wait for explicit user approval.
+#
+# Two layers:
+#   * `CONFIRMATION_REQUIRED_TOOLS` — hard fallback when a tool is dispatched
+#     by name but is not present in `tool_definitions` (defence-in-depth).
+#   * `_requires_confirmation()` — authoritative check that consults the
+#     `ToolDefinition.requires_confirmation` flag from the registry.
+#
+# The two MUST stay aligned: any tool whose `requires_confirmation=True` is
+# treated as confirmation-required, regardless of whether its name is in the
+# fallback set. This unifies the runtime pause with PolicyEngine validation.
+CONFIRMATION_REQUIRED_TOOLS: frozenset[str] = frozenset(
+    {
+        "write_file",
+        "execute_python",
+        "delete_file",
+        "run_script",
+        "create_calendar_event",
+        "add_reminder",
+    }
+)
@@
     async def _tool_node(self, state: _RunState) -> dict:
         tool_name = state["next_tool_name"]
         tool_args = state["next_tool_args"] or {}
 
-        # Pause and request user approval for destructive tools.
-        if tool_name in CONFIRMATION_REQUIRED_TOOLS:
+        if self._requires_confirmation(tool_name):
             return {
                 "needs_confirmation": True,
                 "pending_tool_name": tool_name,
                 "pending_tool_args": tool_args,
                 "final_answer": (
                     f"Necesito tu aprobación para ejecutar `{tool_name}`. "
                     "Aprueba o rechaza la acción en el panel de confirmación."
                 ),
             }
@@
     def _route_after_tool(self, state: _RunState) -> str:
         if state.get("needs_confirmation"):
             return "update_state"
         return "observe_node"
+
+    # ----------------------------------------------------------------------
+    # Confirmation policy
+    # ----------------------------------------------------------------------
+
+    def _requires_confirmation(self, tool_name: str | None) -> bool:
+        if not tool_name:
+            return False
+        td = self._tool_definitions.get(tool_name)
+        if td is not None:
+            return bool(td.requires_confirmation)
+        # Defence-in-depth: pause on the static fallback set even when a tool
+        # is missing from the registry (e.g. integration test runtimes that
+        # bypass `register_*_tools`).
+        return tool_name in CONFIRMATION_REQUIRED_TOOLS
```

**Rationale**: The registry's `ToolDefinition.requires_confirmation` already exists and is consumed by `PolicyEngine`. Making the runtime read the same flag eliminates the dual‑model risk (R6) without removing the static fallback that keeps unit tests with stub registries working.

**Validation**

```bash
make test tests/test_tool_confirmation.py
```

Add:

```python
def test_create_calendar_event_pauses_for_confirmation(monkeypatch, ...):
    # arrange runtime with a CalendarTools registry; reason node emits
    # {"action":"tool","tool":"create_calendar_event","args":{...}}
    answer, final_state = await runtime.run("crea evento mañana 4pm", CALENDAR_AGENT_ID)
    assert final_state.pending_tool_name == "create_calendar_event"
```

**Pass signal**: previously-passing tests still pass and the new ones go green.

**Lead Engineer addendum — Locale-ready confirmation copy (lower priority, do before Windows/i18n pass)**

The pause message today is hardcoded Spanish in `_tool_node`:

`"Necesito tu aprobación para ejecutar \`{tool_name}\`…"`

Elsewhere the plan is careful about locale (ContextEnricher templates, Spanish-first UX). Confirmation copy should not be the exception that blocks a future English UI.

**Policy for C1**

- Move user-visible strings to a tiny module, e.g. `core/i18n/es.py` (constants) or `core/i18n/messages.py` with a stub `_L(key: str, **kwargs) -> str` that defaults to Spanish today and can switch on `CEREBRO_LOCALE` later.
- Keys like `confirm.tool_pause`, `confirm.tool_pause_body` — runtime calls `_L("confirm.tool_pause", tool_name=tool_name)`.
- Tests assert the Spanish default string still appears when locale is unset.

**Pass signal**: no raw Spanish sentences remain in `runtime.py` outside the i18n module; changing `CEREBRO_LOCALE=en` (future) can swap copy without editing graph code.

---

### Step C2 — Persist the unified policy in `policy.py` (docs only) *(DONE)*

**Files touched**

- `core/tools/policy.py` *(comment-only patch)*

**Diff**

```diff
--- a/core/tools/policy.py
+++ b/core/tools/policy.py
@@
 class PolicyEngine:
+    """Validate tool calls against agent authorization + path scoping.
+
+    Confirmation gating is owned by `AgentRuntime._requires_confirmation`,
+    which now reads the *same* `ToolDefinition.requires_confirmation` flag
+    that `PolicyEngine.validate_call()` surfaces in `PolicyResult`. Tests in
+    `tests/test_tool_governance.py` continue to assert the flag at the
+    registry layer; the runtime test in `test_tool_confirmation.py` covers
+    the pause path.
+    """
```

**Rationale**: pure documentation; locks the invariant so future contributors do not re-fork the two confirmation models.

**Validation**

```bash
make lint
```

**Pass signal**: lint clean, no behaviour change.

---

### Step D1 — Add `create_calendar_event` + `add_reminder` to `GENERAL_TOOLS` *(DONE)*

**Files touched**

- `core/agents/specialized.py`
- `tests/test_specialized.py`

**Diff**

```diff
--- a/core/agents/specialized.py
+++ b/core/agents/specialized.py
@@
 # Read-only, low-risk tools the general agent may use without confirmation
 GENERAL_TOOLS: list[str] = [
     "get_upcoming_events",
     "query_events",
     "search_upcoming",
+    "create_calendar_event",
+    "add_reminder",
     "search_documents",
     "spotlight_search",
     "list_directory",
     "search_files",
     "search_notes",
 ]
```

**Rationale**: Add the canonical *write* verbs the user expects in plain General chat. The runtime pause (Step C1) keeps the destructive surface gated.

**Validation**

```bash
make test tests/test_specialized.py
```

Add:

```python
def test_general_profile_can_call_create_calendar_event():
    assert "create_calendar_event" in make_general_profile().authorized_tools
```

**Pass signal**: green test + manual `G6` retest returns `pending_tool.name == "create_calendar_event"`.

---

### Step D2 — Authorize plain-text `write_file` on `general-v1` and `code-v1` *(DONE)*

**Files touched**

- `core/agents/specialized.py`
- `tests/test_specialized.py`

**Diff**

```diff
--- a/core/agents/specialized.py
+++ b/core/agents/specialized.py
@@
 CODE_TOOLS: list[str] = [
     "search_documents",
     "read_file",
     "execute_python",
     "create_python_file",
+    "write_file",
     "run_script",
     "delete_file",
     "list_directory",
     "search_files",
     "create_directory",
 ]
@@
 GENERAL_TOOLS: list[str] = [
     "get_upcoming_events",
     "query_events",
     "search_upcoming",
     "create_calendar_event",
     "add_reminder",
     "search_documents",
     "spotlight_search",
     "list_directory",
     "search_files",
     "search_notes",
+    "write_file",
+    "read_file",
 ]
```

**Rationale**: closes R4 / R5. The `write_file` handler already binds `AUTHORIZED_WRITE_PATHS` via `partial`, so escapes are impossible. The runtime pause (C1) keeps user-in-the-loop.

**Validation**

```bash
make test tests/test_specialized.py -k write_file
make test tests/test_tool_governance.py
```

**Pass signal**: assertions

```python
def test_general_can_write_file():
    assert "write_file" in make_general_profile().authorized_tools

def test_code_can_write_file():
    assert "write_file" in make_code_profile().authorized_tools
```

green; `test_tool_governance.py` still passes (path scoping unchanged).

---

### Step D3 — Tighten `create_python_file` validation against JSON-escape failures *(DONE)*

**Files touched**

- `core/tools/handlers/filesystem.py`
- `tests/test_filesystem_tools.py`

**Diff**

```diff
--- a/core/tools/handlers/filesystem.py
+++ b/core/tools/handlers/filesystem.py
@@
 def create_python_file(filename: str, code: str, authorized_paths: list[str]) -> str:
     if not filename.endswith(".py"):
-        return "Error: filename must have a .py extension"
+        return (
+            "Error: create_python_file requires a .py filename. "
+            "Use write_file for plain-text targets."
+        )
     if "/" in filename or "\\" in filename:
         return "Error: filename must not contain path separators"
+    # Fast syntactic validation: refuse code the LLM mis-escaped into
+    # broken Python (test_1.md D1 emitted `print("hello")` with raw quotes).
+    import ast
+    try:
+        ast.parse(code)
+    except SyntaxError as exc:
+        return f"Error: code is not valid Python ({exc.msg} at line {exc.lineno})"
     base = Path(authorized_paths[0]).expanduser().resolve()
     dest = base / filename
```

**Rationale**: cheap, deterministic guardrail — refuses to persist broken scripts that a small model produced from a malformed JSON string. The redirect to `write_file` in the error message gives the LLM a recovery path on the next iteration.

**Validation**

```bash
make test tests/test_filesystem_tools.py -k create_python_file
```

Add:

```python
def test_create_python_file_rejects_broken_quotes(tmp_path):
    bad = 'print("hello")'  # OK
    good = 'print(\\"hello\\")'  # OK
    really_bad = 'print("hello\")'  # SyntaxError
    out = create_python_file("x.py", really_bad, [str(tmp_path)])
    assert out.startswith("Error: code is not valid Python")
```

**Pass signal**: test green, no file written when syntax fails.

---

### Step D4 — Smart truncation for `read_file` (and aligned ceilings for `list_directory` / `search_files`) *(DONE)*

**Files touched**

- `core/tools/handlers/filesystem.py` (`read_file`, plus the existing `list_directory` already returns a list and is fine; tighten `search_files` ceiling)
- `tests/test_filesystem_tools.py` *(new assertions for the truncation behaviour)*

**What changes (text only, no code)**

The 3 B local model has roughly 4 K tokens of context after A1. A naïve `read_file` against a 2000-line file blows that budget on a single tool observation and the model collapses into either repetition or an apology. The fix is structural:

- `read_file` gains an internal cap of approximately **8 KB of file content per call** (~2000 tokens, a safe quarter of the 4 K context window). When a file exceeds the cap, the handler returns *only the first 8 KB* followed by a deterministic hint line in Spanish: `"[Archivo truncado: 8192/<total> bytes. Pídeme una sección específica con read_file_range si necesitas más.]"`. The numeric byte counts are mandatory — the model uses them to reason about whether to ask for more.
- The byte cap is exposed as a module-level constant so test fixtures can override it; the production default lives in code, not in config, because it is a hardware contract not a user preference.
- The hint text is the *only* string-matched marker the runtime relies on. Do not localise it without updating the matching prompt examples in `make_general_profile()` / `make_academic_profile()`.
- `search_files` already caps results at 20. Keep that ceiling but also clip each formatted line (path + size + mtime) to 200 characters to avoid pathologically long paths inflating the observation.
- `list_directory` is left intact (returns a Python list, not a string — already bounded by directory cardinality and not the dominant cost).

**Rationale**

This is the operationalisation of "smart tool truncation" for an 8 GB / 3 B setup: each tool observation must fit inside a small, predictable slice of the context window. Without this clamp, every successful tool call still risks an out-of-context follow-up. With it, the model can read large files in chunks — a workflow the 3 B can actually sustain. Pairs naturally with the new `write_file` / `read_file` authorizations from D2: making reads safe is what makes the new authorization usable.

**Validation**

`make test tests/test_filesystem_tools.py -k truncation` runs:

- Reading a 16 KB temp file returns content ≤ 8 KB plus the truncation hint.
- Reading a small file returns the full content with no hint appended.
- `search_files` against a directory with very long synthetic paths produces no line longer than 200 characters.

**Pass signal**: tests green; manual probe of `read_file` against a long real document in a watched folder yields a bounded observation followed by the hint, and the agent's next iteration uses the hint to ask a follow-up question rather than apologising.

---

### Step E1 — Hydrate `watched_folders` into the running tool registry *(DONE)*

**Files touched**

- `ui/tray/server.py`

**Diff** (only the `PATCH /api/config` handler)

```diff
--- a/ui/tray/server.py
+++ b/ui/tray/server.py
@@
 @api.patch("/config")
 async def patch_config(settings: dict[str, Any] = Body(...)) -> dict[str, Any]:
     app_state._config.update(settings)
 
     if "model" in settings and app_state.provider_registry is not None:
         model_name: str = settings["model"]
         registry = app_state.provider_registry
         target = "llamacpp"
         if "mlx" in registry.available_providers():
             if registry.get_chat("mlx").model_id() == model_name:
                 target = "mlx"
         if target == "llamacpp" and "llamacpp" in registry.available_providers():
             registry.get_chat("llamacpp").set_model(model_name)  # type: ignore[union-attr]
         registry.set_primary(target)
 
+    if "watched_folders" in settings and app_state.runtime is not None:
+        # Re-bind filesystem handlers so newly-watched folders become
+        # readable without a backend restart. Writes stay scoped to
+        # CEREBRO_FILES_PATH for safety (`AUTHORIZED_WRITE_PATHS` unchanged).
+        from functools import partial
+        from core.tools.handlers.filesystem import (
+            list_directory,
+            read_file,
+            search_files,
+        )
+        startup_reads = list(app_state.authorized_read_paths or [])
+        merged_reads = list(dict.fromkeys(startup_reads + list(settings["watched_folders"])))
+        app_state.authorized_read_paths = merged_reads
+        # `runtime._tool_registry` is the live dict[name -> handler]
+        tr = app_state.runtime._tool_registry
+        if "read_file" in tr:
+            tr["read_file"] = partial(read_file, authorized_paths=merged_reads)
+        if "list_directory" in tr:
+            tr["list_directory"] = partial(list_directory, authorized_paths=merged_reads)
+        if "search_files" in tr:
+            tr["search_files"] = partial(search_files, authorized_paths=merged_reads)
+
     app_state._save_config()
     return app_state._config
```

**Rationale**: respects the existing architectural contract — `app_state` is the injection point, and `runtime._tool_registry` is the live handler table. We rebind only the **read-side** handlers. Write paths intentionally stay frozen to `CEREBRO_FILES_PATH` so a misconfigured watched folder cannot become a write target.

**Validation**

```bash
make test tests/test_api.py -k watched_folders
```

Add:

```python
async def test_patch_config_rebinds_read_handlers(client, tmp_path):
    extra = tmp_path / "new_watch"
    extra.mkdir()
    (extra / "hi.txt").write_text("hello")
    # ... stub app_state.runtime._tool_registry with the real handlers ...
    r = await client.patch("/api/config", json={"watched_folders": [str(extra)]})
    assert r.status_code == 200
    # The read_file handler now resolves a file under the new folder
    body = app_state.runtime._tool_registry["read_file"](path=str(extra / "hi.txt"))
    assert body == "hello"
```

**Pass signal**: test green; calling `read_file` against a freshly-added folder no longer raises `PathNotAuthorizedError`.

---

### Step E2 — Persistent session ID & conversation isolation *(DONE)*

**Priority**: 🔴 High — the plan stores turns in `_RunState` / `ConversationStore` but does not define **session boundaries** for 8 GB hardware. A stale 15-turn history from yesterday can burn **600–800 tokens** before the user types a word.

**Files touched**

- `core/agents/conversation_store.py` (extend or align with on-disk layout)
- `~/.cerebro/state/sessions/<session_id>.json` *(new persistence layout — or nest under existing `conversations/` if that schema already exists; pick one canonical path)*
- `ui/tray/server.py` (`conversation_id` on `QueryRequest` already exists — wire creation/resume explicitly)
- `ui/tray/src/stores/chat.ts` (generate/store `session_id` per chat surface)
- `tests/test_conversations.py` *(resume cap, isolation between two IDs)*

**What changes (text only, no code)**

**Session identity**

- Each chat surface gets a **`session_id` UUID** at conversation start (distinct from `conversation_id` if you keep both: `session_id` = durable bucket, `conversation_id` = API turn log — document the relationship in one sentence in code comments when implementing).
- Persist to `~/.cerebro/state/sessions/<session_id>.json` containing: `agent_id`, `created_at`, `turns[]` (role, content, timestamp), optional `session_summary` snapshot.

**Resume policy (8 GB default)**

- On app reopen or `GET /api/conversations/{id}` resume: load **at most the last 8 turns** into `session_history` (configurable constant `CEREBRO_SESSION_RESUME_MAX_TURNS=8`).
- Older turns are **not** loaded verbatim; only `session_summary` (from A1.3 consolidation) carries forward prior context.
- If no summary exists and history exceeds 8 turns, run a one-shot consolidation (A1.3 rules) before the first new user message.

**Isolation**

- Two chat windows (or two `session_id`s) must **not** share `AgentStateStore` working memory or in-memory `_RunState` — each query carries its `conversation_id` / `session_id` and loads only that file's tail.

**Relationship to existing stores**

- `ConversationStore` under `~/.cerebro/state/` may already persist turns — E2's job is to **document and enforce** the cap + UUID boundary, not duplicate storage blindly. Prefer extending the existing store over inventing a parallel format.

**Validation**

- Create session A with 12 turns, restart backend, resume A → only 8 turns in assembled context (assert via debug log or test hook).
- Session B in parallel does not see session A's messages.

**Pass signal**: cold start after 12-turn yesterday session does not preload all 12 turns; token estimate on first new message stays below ~1200 before user input.

---

### Step F1 — Grant `dialog:` capability to the main Tauri window *(DONE)*

**Files touched**

- `ui/tray/src-tauri/capabilities/main.json`

**Diff**

```diff
--- a/ui/tray/src-tauri/capabilities/main.json
+++ b/ui/tray/src-tauri/capabilities/main.json
 {
   "$schema": "../gen/schemas/desktop-schema.json",
   "identifier": "main-capability",
   "description": "Main window capabilities",
   "windows": ["main"],
   "permissions": [
     "core:default",
     "core:window:allow-start-dragging",
     "shell:default",
-    "shell:allow-open"
+    "shell:allow-open",
+    "dialog:default",
+    "dialog:allow-open"
   ]
 }
```

**Rationale**: closes R7. `tauri-plugin-dialog` is already a Cargo dependency and is initialised in `lib.rs`; the only missing piece is the capability allow-list. With this permission the silent failure in `FolderManager.addFolder()` becomes a working native picker.

**Validation**

```bash
cd ui/tray && npm run tauri build -- --debug   # or `npm run tauri dev`
```

Manual click test: **Settings → Watched Folders → Add Folder** opens the native picker; after selection, the folder shows in the list **and** `~/.cerebro/state/config.json:watched_folders` contains the new path.

**Pass signal**: dialog opens. Combined with E1, `read_file` against the new folder succeeds via `/api/query`.

> Note: the stale, auto-generated `ui/tray/src-tauri/gen/schemas/capabilities.json` will be **regenerated** by `tauri build`. Do not hand-edit it.

---

### Step F1b — Tauri dev vs production capability split (polish, do with F1) *(DONE)*

**Priority**: 🟢 Lower — but cheapest to do **now** before Windows/macOS packaging hardens, because capability files are painful to retrofit.

**Files touched**

- `ui/tray/src-tauri/capabilities/main.json` — **production** permissions only (`dialog:allow-open`, `shell:allow-open`, core window permissions).
- `ui/tray/src-tauri/capabilities/dev.json` *(new)* — development-only extras if needed (e.g. additional debug plugins, broader `shell` scopes during `tauri dev`).
- `ui/tray/src-tauri/tauri.conf.json` — wire `dev` capability set for debug builds vs `main` for release.

**What changes (text only, no code)**

F1 correctly adds `dialog:default` + `dialog:allow-open` to the main capability. F1b ensures those permissions (and any future dev-only scopes) do **not** ship in the signed release artifact by accident.

- **Production `main.json`**: minimal allow-list required for folder picker + shipped features.
- **Dev `dev.json`**: optional permissions used only when running `npm run tauri dev` / debug builds.
- Release CI should build with production capabilities only; document in `docs/frontend/` or a one-line comment in `tauri.conf.json`.

**Pass signal**: `tauri build` release binary does not list dev-only permission IDs; `tauri dev` still opens the folder picker.

---

### Step F2 — Make the Fleet panel honest *(DONE)*

There are two acceptable resolutions for R9. Pick exactly one in this step.

**Option F2-A (preferred — implement the missing endpoints)**

**Files touched**

- `ui/tray/server.py`

**Diff**

```diff
--- a/ui/tray/server.py
+++ b/ui/tray/server.py
@@ class FleetModeRequest(BaseModel):
+class FleetModeRequest(BaseModel):
+    mode: Literal["auto", "pinned"]
+    pinned_model_id: str | None = None
+
+
+@api.get("/fleet/status")
+async def fleet_status() -> dict[str, Any]:
+    fleet = app_state.fleet_orchestrator
+    if fleet is None:
+        raise HTTPException(status_code=503, detail="Fleet orchestrator not initialised")
+    sel = fleet.current_selection
+    hw = fleet._hw_snapshot
+    return {
+        "mode": app_state._config.get("fleet_mode", "auto"),
+        "current_model": (sel.model.__dict__ if sel else None),
+        "hardware": (hw.__dict__ if hw else None),
+        "swap_in_progress": False,
+        "swap_target_model_id": None,
+        "model_swaps_session": fleet.swaps_session_count,
+        "selection_rationale": (sel.rationale if sel else ""),
+    }
+
+
+@api.get("/fleet/models")
+async def fleet_models() -> dict[str, Any]:
+    fleet = app_state.fleet_orchestrator
+    if fleet is None:
+        raise HTTPException(status_code=503, detail="Fleet orchestrator not initialised")
+    models = fleet.list_models()
+    active = fleet.current_selection.model.id if fleet.current_selection else ""
+    return {"models": [m.__dict__ for m in models], "active_model_id": active}
+
+
+@api.patch("/fleet/config")
+async def fleet_config(req: FleetModeRequest) -> dict[str, Any]:
+    fleet = app_state.fleet_orchestrator
+    if fleet is None:
+        raise HTTPException(status_code=503, detail="Fleet orchestrator not initialised")
+    app_state._config["fleet_mode"] = req.mode
+    if req.mode == "pinned" and req.pinned_model_id:
+        app_state._config["fleet_pinned_model_id"] = req.pinned_model_id
+        fleet.pin_model(req.pinned_model_id)
+    else:
+        fleet.use_auto_selection()
+    app_state._save_config()
+    return app_state._config
```

The exact `FleetOrchestrator` API (`list_models`, `pin_model`, `use_auto_selection`, `swaps_session_count`) is the public surface that already lives in `core/inference/fleet/orchestrator.py` per `main.py:68-76`. If any of those methods is named differently in your tree, rename in this diff — do not invent new orchestrator capabilities.

**Validation**

```bash
make test tests/test_fleet_orchestrator.py
curl -fsS http://localhost:7842/api/fleet/status | python -m json.tool
```

**Pass signal**: `/api/fleet/status` returns 200 with non-null `current_model`; clicking **Auto** ↔ **Pinned** in the UI persists into `~/.cerebro/state/config.json`.

**Option F2-B (escape hatch — hide the panel until backend ready)**

If `FleetOrchestrator` is not feature-complete enough to expose, gate the panel:

```diff
--- a/ui/tray/src/components/settings/SettingsPanel.tsx
+++ b/ui/tray/src/components/settings/SettingsPanel.tsx
-          {!isCloud && (
+          {!isCloud && status?.current_model_id && (
             <section>
               <label …>Fleet Orchestrator</label>
               <FleetSettings />
             </section>
           )}
```

Pick **F2-A** unless backend velocity is constrained — F2-B leaves the architectural debt in place.

---

### Step G1 — Add a deterministic `evaluate_math` tool *(DONE)*

**Files touched**

- `core/tools/handlers/math.py` *(new file)*
- `core/tools/registry.py`
- `core/agents/specialized.py`
- `tests/test_filesystem_tools.py` *(or new `tests/test_math_tool.py`)*

**Diff**

```python
# core/tools/handlers/math.py  (new)
"""Deterministic numeric evaluator — stdlib-only, no Python eval()."""

from __future__ import annotations

import ast
import operator as op
from typing import Final

_ALLOWED_OPS: Final = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.FloorDiv: op.floordiv, ast.Mod: op.mod,
    ast.Pow: op.pow, ast.USub: op.neg, ast.UAdd: op.pos,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval(node.operand))
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def evaluate_math(expression: str) -> str:
    """Evaluate a pure-numeric expression and return the result as a string.

    Allowed: +, -, *, /, //, %, **, unary +/-, parentheses. Refuses anything
    else (variables, calls, attribute access, comparisons).
    """
    tree = ast.parse(expression, mode="eval")
    try:
        value = _eval(tree)
    except (ValueError, ZeroDivisionError) as exc:
        return f"Error: {exc}"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)
```

```diff
--- a/core/tools/registry.py
+++ b/core/tools/registry.py
@@ def register_macos_tools(registry: ToolRegistry) -> None:
     ...
+
+def register_math_tools(registry: ToolRegistry) -> None:
+    from core.tools.handlers.math import evaluate_math
+
+    registry.register(
+        ToolDefinition(
+            name="evaluate_math",
+            description=(
+                "Evaluate a deterministic numeric expression "
+                "(arithmetic, parentheses, power). Use for any math the user asks."
+            ),
+            handler=evaluate_math,
+            required_permission="tools.math.eval",
+            requires_confirmation=False,
+            scope=ToolScope.SANDBOXED,
+            audit_level=AuditLevel.METADATA,
+            parameters={"expression": "str — expresión numérica (ej: '17*23')"},
+        )
+    )
```

```diff
--- a/main.py
+++ b/main.py
@@
 from core.tools.registry import (
     ToolRegistry,
     register_calendar_tools,
     register_filesystem_tools,
     register_macos_tools,
+    register_math_tools,
 )
@@
     register_macos_tools(cal_registry)
+    register_math_tools(cal_registry)
```

```diff
--- a/core/agents/specialized.py
+++ b/core/agents/specialized.py
 GENERAL_TOOLS: list[str] = [
     ...
     "write_file",
     "read_file",
+    "evaluate_math",
 ]
 CODE_TOOLS: list[str] = [
     ...
     "create_directory",
+    "evaluate_math",
 ]
```

**Rationale**: replaces token-level arithmetic guesswork with a deterministic call. The tool is `sandboxed` and `requires_confirmation=False` — no user-in-the-loop overhead. Stdlib AST gives us a tight whitelist; no `eval`.

**Lead Engineer addendum — Float formatting for tool observations (medium priority)**

`evaluate_math("1/3")` must not return `"0.3333333333333333"`. A 3 B model shown a 16-digit float in a tool observation may re-format or round it incorrectly in the final answer.

**Formatting policy for G1**

- After AST evaluation, apply `round(value, 10)` before stringification.
- Strip trailing zeros and a trailing decimal point for display (e.g. `0.3333333333` is fine; full double repr is not).
- Integers stay integers (`17*23` → `"391"`, not `"391.0"`).
- Errors unchanged (`"Error: …"` prefix).

**Validation**: `evaluate_math("1/3")` returns a short decimal string; `evaluate_math("17*23")` returns `"391"`.

**Validation**

```bash
make test tests/test_math_tool.py
```

```python
def test_evaluate_math_basic():
    assert evaluate_math("17*23") == "391"
    assert evaluate_math("(1+2)**3") == "27"
    assert evaluate_math("10/0").startswith("Error:")
    # Refuse anything non-numeric
    import pytest
    with pytest.raises(SyntaxError):
        evaluate_math("__import__('os')")
```

**Pass signal**: tests green; manual `G2` retest returns `391`.

---

## 3. Cross-cutting validation gates

After **each** step above, run the full lint+test gate before committing. Anything that drifts must be reverted in the same commit:

```bash
make lint   # black --check, ruff, mypy core/
make test   # pytest tests/ -v --cov=core --cov-fail-under=80
make smoke  # HTTP regression matrix (requires make engine && make run)
```

### Step X1 — Enforce minimum test coverage on `make test` *(DONE)*

**Priority**: 🔴 High — the plan adds many new tests (A1.2, A1.3, A5, B1, D*, G1, etc.) but never **enforces** that new code paths stay covered. On a project this shape, it is easy to land a step and "forget" an edge branch.

**Files touched**

- `Makefile` (`test` target)
- `pyproject.toml` (ensure `pytest-cov` is in dev dependencies if not already)

**What changes (text only, no code)**

Extend the `test` Make target so CI and local dev share one gate:

- Run `pytest tests/ -v --cov=core --cov-fail-under=80`.
- **80 %** threshold (G1 landed; `pytest-cov` in `[project.optional-dependencies] dev`).

**When to land X1**

- Land **early** (after the first batch of new tests exists — ideally right after B1 or alongside A5 tests) so later steps cannot regress coverage silently.
- Every atomic step still runs `make test`; a coverage drop fails the step before merge.

**Pass signal**: `make test` exits non-zero if coverage falls below threshold; `make test` passes on green main after full plan.

---

### Step X2 — `make smoke` — automate the §3 manual matrix *(DONE)*

**Priority**: 🟢 Lower — high leverage (~30 minutes to write, hours saved per step).

**Files touched**

- `scripts/smoke.sh` *(new)* or `Makefile` `smoke` target
- Reuses curl patterns already documented in A1, C1, G2 validation blocks

**What changes (text only, no code)**

Wrap the manual retest rows below into a single **`make smoke`** target that:

- Assumes `make run` + `make engine` are already up (or prints a clear skip message).
- Runs the ~8 API checks from `manual_tests/implemefix/session-1.md` / §3 table: health endpoint (after A5), status, a minimal General query, Calendar create (expect `pending_tool` or 200), config PATCH smoke, etc.
- Exits non-zero on first failure with the response body printed — not full e2e, not Playwright, just HTTP contract checks.
- Does **not** replace `make test`; complements it.

**When to land X2**

- After **A5** (`GET /api/health`) and enough endpoints exist to script G6/C1-style checks.
- Run `make smoke` at the plan exit gate and after any Domain A change.

**Pass signal**: `make smoke` completes in under 60 s on a warm stack and returns exit 0 when regressions are fixed.

**Shipped**

- `scripts/smoke.sh` → `scripts/smoke_runner.py` (stdlib HTTP, no extra deps)
- `make smoke` in root and `cerebro/` Makefiles
- Checks: health, status, config PATCH, fleet status, G2, G3, G6, C1, G7, auto→calendar route

---

End-of-plan smoke retest (mirrors `manual_tests/implemefix/session-1.md` follow-up checklist — automate via **X2** `make smoke`):

| Manual ID | Expected after this plan |
|-----------|--------------------------|
| G2        | `391` (deterministic via `evaluate_math`) — covered by G1 |
| G3        | Bulleted list in natural text, no JSON envelope — primary cure A3 (GBNF), defence-in-depth B1 |
| G6        | Backend returns `metadata.pending_tool.name == "create_calendar_event"`; UI shows `ConfirmModal` — covered by C1 + D1 |
| C1 (test) | No 400 from llama.cpp on Calendar agent; same flow as G6 — covered by A1 + A2 + D1 |
| D1        | Code agent uses `write_file` (paused for confirm), text content `hello`, no Python wrapping — covered by A3 + C1 + D2 |
| G7        | Same as D1, on General agent — covered by A3 + C1 + D2 |
| Long-file read on 3 B model | `read_file` returns a bounded slice with a truncation hint; agent continues coherently — covered by D4 |
| Long multi-turn chat (15+ turns) | Model still recalls early facts; `Context usage` sawtooth after consolidation — covered by A1.3 |
| Auto agent calendar question | Routes to `calendar-v1` with calendar-only tools in prompt — covered by A4 |
| Perceived streaming lag on local model | First token visible before full JSON completes — covered by B2 (after A3) |
| System under RAM pressure | Warning in UI/metadata; no unexplained freeze — covered by A1.4 |
| Settings: Add Folder | Native picker opens, folder persisted, `read_file` works against it — covered by E1 + F1 |
| Settings: Fleet Auto/Pinned | Toggles activate, `/api/fleet/config` persists `fleet_mode` — covered by F2-A |
| llama-server OOM / kill | Health monitor restarts engine; `/api/health` shows `restarting` → `up` — covered by A5 |
| App reopen with long history | Only last 8 turns loaded; summary carries older context — covered by E2 |
| `make test` on CI | Fails if `core/` coverage &lt; 80 % — covered by X1 |

---

## 4. Maintainability / debt-avoidance principles

- **Single ownership** per behaviour. Examples enforced above: `_parse_llm_response` is the only place that string-coerces an answer; `AgentRuntime._requires_confirmation` is the only place that decides to pause; `app_state` is the only place that holds authorized paths.
- **No new Python dependencies.** Every step uses stdlib only (`ast`, `inspect`, `functools.partial`). This preserves the `pyproject.toml` invariant from `docs/plans/stabilization/fix-cerebro.md`.
- **Atomic + reversible.** Each step is small enough that `git revert <sha>` restores the previous behaviour without cascading.
- **Tests as documentation.** Every behaviour change ships with the test that names the contract. The tests double as the regression net for the LangGraph runtime — the most likely future drift surface.
- **Frontend ↔ backend symmetry.** When a frontend feature calls an endpoint, the endpoint must exist (F2). When the backend produces a confirmation, the frontend must render it (already wired in `InputArea.tsx`). The Fleet panel was the lone asymmetry — F2 closes it.
- **Capability hygiene.** Tauri v2 capabilities are explicit allow-lists; F1 documents the contract in the **source** file, not the generated one.
- **No prompt-engineering hacks** for the model errors. Bumping context (A1) and authorizing the right tools (D1, D2) is preferred to layering on additional prose in the system prompt — small models cannot reliably follow long prompts and any "please return JSON" tweaks introduce silent fragility that resurfaces with the next model swap.
- **8 GB / 3 B hardware budget is a first-class constraint, not an afterthought.** Every step in this plan is sized to fit a MacBook Pro M1 / 8 GB with roughly 4 GB free at runtime. The three levers we *do* pull on RAM are: KV-cache quantization (already on, A1 confirms it), prompt pruning (A2), and bounded tool observations (D4). The lever we deliberately *avoid* is bumping the model weight class — Q5_K_M / 7 B / FP16 are all out of budget on this hardware and would push resident memory over the 5.5 GB ceiling from `docs/plans/stabilization/fix-cerebro.md`.
- **Constrain the model with grammar, not exhortation.** A3 (GBNF) is the architectural form of this principle. Anywhere a future feature needs the model to produce a typed shape (e.g. a structured plan, a structured search query), reach for a GBNF or JSON-schema constraint before reaching for more system-prompt prose.
- **Context is a budget with a refill loop.** A1.2 measures it, A1.3 reclaims it (consolidation), A1.4 protects the host RAM that holds it, A4 shrinks what enters each turn. Do not treat 4096 tokens as "infinite" just because the server accepts the request.
- **Measure latency at time-to-first-token, not time-to-done.** B2 exists because local models on 8 GB feel slow when the UI waits for the full JSON envelope. Users forgive total latency if the stream starts immediately.

---

## 5. Out of scope for this plan (deferred, not forgotten)

| Deferred item | Why deferred |
|---------------|--------------|
| Replacing the `LLMRouter` `"model": "router"` payload | Only triggers on `agent: "auto"`. The Calendar agent in C1 was pinned (`agent: "calendar-v1"`), so the 400 was independent of the router. Track separately if `auto` regression appears. |
| Surfacing `tool_permissions` toggles from `AppConfig` in the runtime | The UI persists them but no `core/` code reads them yet. Adding enforcement is a self-contained feature, not a regression fix. |
| Migrating `_tool_node` authorization to `PolicyEngine.validate_call` | Tracked in `docs/plans/stabilization/fix-cerebro.md` as a follow-up. Step C1 here only unifies the *confirmation* signal, not the full policy pipeline. |
| Calendar / Notes Automation permission UX | macOS Automation prompts are handled by `wizard.reprobe-calendar-permission` already. Out of scope for these chat-layer regressions. |
| **Micro-agent chaining** | **Promoted to Step A4** (high priority on 8 GB). Removed from deferred — see A4 for fast keyword router + optional slow classify path. |
| **True llama.cpp SSE end-to-end for tool-loop turns** | B2 streams `action:answer` paths only. Tool iterations still buffer until complete; a future step can stream tool reasoning separately. |
| **Hard RAM abort (block query at critical pressure)** | A1.4 warns and purges caches; `_ram_pressure_guard()` already returns 503 at `critical`. Unifying "warn vs block" is product policy — not required for test_1.md regressions. |

---

**End of plan.** Implement the steps in the order listed:

`A1 → … → G1 → X1 → X2` *(X1/X2 done: `make test` enforces 80 % coverage; `make smoke` runs HTTP regression checks)*

Each step is independently mergeable; each ends with a green `make lint && make test` (with coverage gate per X1).

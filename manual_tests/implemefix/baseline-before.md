# ImplemeFIX — Pre-flight baseline (Phase 1)

| Field | Value |
|--------|--------|
| Date | 2026-05-19 (Tuesday, EDT) |
| Branch | `fix-1-ram-containment` (active working branch; plan suggested `fix/8gb-perf-overhaul`) |
| Machine | MacBook Pro, Apple M1, **8 GB** RAM (`hw.memsize=8589934592`) |
| macOS | 26.3.1 |
| Chat model | `bin/models/llama-3.2-3b-instruct-q4_k_m.gguf` — **1.9 GiB** on disk |
| Embed model | `v5-nano-retrieval-Q4_K_M.gguf` — **~150 MiB** (lives under `cerebro/bin/models/`; symlinked into root `bin/models/` for this session) |
| Backend | `make run` → `http://127.0.0.1:7842` |
| Chat engine | `make engine` → `:8080` |
| Embed engine | `make engine-embed` → `:8082` (failed until symlink; see below) |

---

## 1. Repo / branch

- Working branch exists: **`fix-1-ram-containment`** (tracks `origin/fix-1-ram-containment`).
- Large in-flight diff on this branch (RAM containment, parser, prompt cache scaffolding, etc.) — baseline taken **before** ImplemeFIX module work.

---

## 2. Models & engines

| Check | Result |
|--------|--------|
| Chat GGUF present | Yes — `llama-3.2-3b-instruct-q4_k_m.gguf` (1.87 GiB reported by llama.cpp) |
| `make engine` | OK — listening `http://127.0.0.1:8080`, health `{"status":"ok"}` |
| `make engine-embed` (initial) | **Failed** — embed GGUF missing at `bin/models/v5-nano-retrieval-Q4_K_M.gguf` |
| `make engine-embed` (after symlink) | OK — listening `http://127.0.0.1:8082`, health `{"status":"ok"}` |

**Pre-flight symlink (session only):**  
`bin/models/v5-nano-retrieval-Q4_K_M.gguf` → `../../cerebro/bin/models/v5-nano-retrieval-Q4_K_M.gguf`  
Consider copying or documenting download path in Module 3 / docs so embed works without the mirror tree.

---

## 3. RAM — `llama-server` processes

Captured while **both** chat and embed servers were running:

| Process | Port | RSS (approx.) |
|---------|------|----------------|
| Chat `llama-server` | 8080 | **~2126 MiB** (~2.1 GB) |
| Embed `llama-server` | 8082 | **~234 MiB** |
| **Combined** | | **~2.36 GB** for inference alone |

Chat profile: `config/chat.args` — ctx 4096, q4_0 KV cache, GPU layers 99, temp 0.7.  
Embed profile: `config/embed.args` — ctx 512, embedding mode, 2 threads.

No prompt-cache **disk** flags in `chat.args` yet (Module 1). Server log shows built-in RAM prompt cache enabled by llama.cpp default.

---

## 4. API baseline (`POST /api/query`, agent `general`)

System time at start of run: **Tuesday, 2026-05-19 19:15:28 EDT**

| # | Prompt | Wall time | Answer (truncated) | Notes |
|---|--------|-----------|-------------------|--------|
| 1 | Say hello in one sentence. | **20.92 s** | Spanish greeting | Cold / first turn in new conversation |
| 2 | What is 2+2? (same `conversation_id`) | **~0 s** | `4` | Likely **math fast path**, not representative LLM warm latency |
| 3 | What time is it right now? | **18.74 s** | `La hora actual es las 19:15.` | System was 19:15:28 — **within ±1 min** this run |
| 4 | Write hello.py in CerebroFiles with `print("hi")` | **7.70 s** | Raw JSON leaked to user | **Fail** — parser did not convert to tool execution |
| 5 | Warm follow-up (sky color → grass color, same conv) | **15.06 s** | `verde` | Still **multi-second**; no on-disk prompt cache yet |

**Symptoms confirmed for later modules:**

- **Latency:** first real LLM turn ~**21 s**; follow-up non-math turn ~**15 s** (targets in plan: &lt;8 s cold, &lt;1 s warm after Module 1).
- **JSON leak:** file-write request returned malformed/tool JSON as the **answer** string (Module 5).
- **Time:** acceptable in this single run; preamble still Spanish/locale-dependent (`_date_preamble` in `runtime.py` ~159) — Module 4 will harden.

---

## 5. Files inspected (no code changes in Phase 1)

| File | Baseline notes |
|------|----------------|
| `main.py` | `AUTHORIZED_WRITE_PATHS = [CEREBRO_FILES_PATH]` only; read includes repo + CerebroFiles |
| `config/chat.args` | Llama 3.2 3B, ctx 4096, no `--prompt-cache` file flags |
| `config/embed.args` | Jina v5 nano retrieval, port 8082 via `start_engine.sh` |
| `bin/start_engine.sh` | Chat 8080, embed 8082; health skip if already up |
| `core/agents/runtime.py` | `_date_preamble()` Spanish; three date formats; `sync_prompt_cache` called but cache args not on server |
| `core/tools/handlers/filesystem.py` | `PathNotAuthorizedError` without allowed-roots detail |
| `core/inference/prompt_cache.py` | Fingerprint + `sync_prompt_cache` implemented; default `bin/cache/chat.cache` |
| `core/inference/providers/llamacpp_provider.py` | Grammar kwarg supported (used by agent path) |

**Conversation log:** `ui/tray/server.py` persists `req.question` (original query), not `_date_preamble() + query` — preamble should not appear in tray history when using the HTTP API.

---

## 6. Prior manual test cross-reference

`manual_tests/implemefix/session-1.md` (earlier session) already recorded:

- Arithmetic errors, raw JSON in UI, calendar create mis-routed, filesystem write failures, ~18–30 s latencies.

This API baseline aligns with those findings.

---

## 7. Screenshots

Activity Monitor / `top` screenshots were **not** captured in this automated run. RAM table above substitutes numeric evidence; add screenshots in a follow-up manual pass if needed for the PR.

---

## 8. Next step (plan order)

Proceed with **Module 4** (temporal awareness) → Module 5 → Module 1 → … per `docs/plans/stabilization/impleme-fix-implementation.md` §0.

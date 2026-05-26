# Cerebro → Cognitive Operating Layer · Implementation Future Plan

> Phase 0 of the future plan starts only after [`docs/plans/stabilization/fix-cerebro.md`](docs/plans/stabilization/fix-cerebro.md) Phase 8 is merged.

> **Audience:** Claude Code (CLI agent)or any ai agent executing this plan autonomously.
> **Authoring role:** Principal Software Architect — local-first AI OS, extreme resource optimization.
> **Source documents:** [`docs/README.md`](docs/README.md) (current state) and [`docs/plans/vision/ideas-future.md`](docs/plans/vision/ideas-future.md) (target vision).
> **Goal:** Migrate Cerebro from "local agentic assistant" to a **Cognitive Operating Layer**: persistent cognitive graph, multi-layer memory, event-driven proactive intelligence, ambient computing, AI-native workspace and a skill/capability marketplace — without breaking the 8 GB RAM budget on MacBook Pro M1.

---

## 0. Hard constraints (read before every phase)

| # | Constraint | Operational rule |
|---|-----------|-----------------|
| C1 | **Hardware floor:** MacBook Pro M1, 8 GB unified RAM. | Process resident set + llama.cpp + embed server **must stay under 6.0 GB** combined. Swap is forbidden in green-path workflows. |
| C2 | **No new ML model weights** beyond what already ships (chat GGUF + embed GGUF). | All new NLP work (NER, relation extraction, summarization) reuses the existing llama.cpp / MLX provider via structured prompts. Adding `spacy`, `sentence-transformers`, `transformers`, etc. is **forbidden in Phases 1–9**. |
| C3 | **No new long-running processes.** | Everything new must live inside the existing FastAPI process (`uvicorn` on port `7842`) or use `asyncio` background tasks. The only allowed *subprocesses* are the existing llama.cpp servers managed by `core/inference/model_manager.py`. |
| C4 | **Embedded databases only.** | Allowed: LanceDB (already present), SQLite via `aiosqlite`, Kùzu (embedded graph DB). **Forbidden:** Neo4j, Postgres, Redis, Elasticsearch, Qdrant, Weaviate, MongoDB, any service requiring a separate daemon. |
| C5 | **Lazy + mmap.** | Stores opened only when first used; closed under RAM pressure. Use `mmap`-backed file formats. |
| C6 | **No LangChain leakage.** | `langchain-core` may remain as a transitive dep of `langgraph`; **no new imports from `langchain` or `langchain_*`** are allowed in `core/`. Replace any existing direct use with thin custom adapters. |
| C7 | **Cross-platform later.** | Phases 1–9 are macOS-first (Apple Silicon). Linux + Windows ports are confined to **Phase 10** and are explicitly optional. |
| C8 | **Atomic + verifiable.** | Every step in this plan ends with a copy-pasteable verification command whose exit code is `0` on success. Claude Code MUST NOT advance to the next step until verification passes. |
| C9 | **Branch hygiene.** | One git branch per phase: `phase-N-<slug>`. Squash-merge to `main` only after the phase's exit gate. |

### RAM budget cheat sheet (for runtime gating)

```
macOS baseline         ≈ 3.5 GB
llama.cpp chat (Q4_K_M 4B)  ≈ 2.8 GB
llama.cpp embed (Q4)        ≈ 0.2 GB
Cerebro Python backend ≤ 0.5 GB  ← gate enforced in Phase 0
Tauri UI              ≤ 0.2 GB
─────────────────────────────────
Headroom for user apps ≈ 0.8 GB  (this is what we protect)
```

---

## 1. Operating protocol for the executing agent

For **every step** below the agent MUST:

1. **Read** the file(s) named in `Files touched` before editing.
2. **Apply** the change atomically (a single commit per step where reasonable).
3. **Run** the `Verification` command exactly. Exit code 0 = pass.
4. **Log** the step ID + verification stdout into `docs/plans/roadmaps/cognitive-layer-progress.log` (created in Step 0.1).
5. **Stop and surface** any failure instead of mutating extra files to work around it.

Global verification commands re-used across phases:

```bash
# Lint+type gate
make lint

# Full pytest gate
make test

# Backend health gate (assumes `make run` is up)
curl -fsS http://localhost:7842/api/status | python -m json.tool

# RAM gate (defined in Step 0.2)
python scripts/ram_gate.py --max-gb 6.0
```

---

## Phase 0 — Pre-flight, safety net & RAM gating

**Goal:** Freeze a known-good baseline, install RAM telemetry, and create the per-phase progress log so the agent can resume safely after interruption.

### Step 0.1 — Create progress log and phase branch infrastructure

* **Files touched:** `docs/plans/roadmaps/cognitive-layer-progress.log` (new), `docs/plans/roadmaps/PHASES.md` (new).
* **Action:**

```bash
mkdir -p roadmaps
touch docs/plans/roadmaps/cognitive-layer-progress.log
cat > docs/plans/roadmaps/PHASES.md <<'EOF'
# Cognitive Layer migration — phase index
Each phase has its own branch `phase-N-<slug>` and ends with an exit gate.
EOF
git checkout -b phase-0-safety-net
git add docs/plans/roadmaps/ && git commit -m "phase-0: add cognitive-layer progress scaffolding"
```

* **Verification:**

```bash
test -f docs/plans/roadmaps/cognitive-layer-progress.log && \
test -f docs/plans/roadmaps/PHASES.md && \
git rev-parse --abbrev-ref HEAD | grep -q '^phase-0-safety-net$'
```

### Step 0.2 — RAM gate script

* **Files touched:** `scripts/ram_gate.py` (new), `pyproject.toml` (no change — `psutil` is already a dep).
* **Action:** create `scripts/ram_gate.py`:

```python
"""Fail (exit 1) if current process tree RSS exceeds budget. Used in CI + manual gates."""
from __future__ import annotations
import argparse, os, sys
import psutil

def total_rss_gb(pid: int) -> float:
    p = psutil.Process(pid)
    rss = p.memory_info().rss
    for child in p.children(recursive=True):
        try:
            rss += child.memory_info().rss
        except psutil.NoSuchProcess:
            continue
    return rss / (1024 ** 3)

def system_used_gb() -> float:
    vm = psutil.virtual_memory()
    return (vm.total - vm.available) / (1024 ** 3)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=None,
                    help="Process to measure; default is system-wide used memory.")
    ap.add_argument("--max-gb", type=float, required=True)
    args = ap.parse_args()
    used = total_rss_gb(args.pid) if args.pid else system_used_gb()
    print(f"used={used:.2f}GB max={args.max_gb}GB")
    sys.exit(0 if used <= args.max_gb else 1)
```

* **Verification:**

```bash
python scripts/ram_gate.py --max-gb 64.0 && echo "ram_gate ok"
```

### Step 0.3 — Baseline tests must be green

* **Action:** run the existing test suite to lock the baseline; if any test fails, **stop the migration** and triage instead of advancing.
* **Verification:**

```bash
make test 2>&1 | tee /tmp/phase0-baseline.log | tail -5
grep -E "passed|failed" /tmp/phase0-baseline.log | tail -1 | grep -vq "failed"
```

### Step 0.4 — RAM telemetry endpoint

* **Files touched:** `core/observability/ram_monitor.py` (new), `ui/tray/server.py` (extend `/api/status`).
* **Action:** add a small `RamMonitor` class that exposes `snapshot()` returning `{used_gb, available_gb, swap_in_mb, swap_out_mb, pressure: "ok"|"warn"|"critical"}`. Compute `pressure`:
  * `available_gb < 1.0` → `critical`
  * `available_gb < 1.8` → `warn`
  * else → `ok`
* Wire `app_state.ram_monitor = RamMonitor()` in `main.py::_build_app_state`. Extend the `StatusResponse` Pydantic model to include `ram_pressure: Literal["ok","warn","critical"]` and `swap_in_mb_per_s: float`.
* **Verification:**

```bash
python -c "from core.observability.ram_monitor import RamMonitor; s=RamMonitor().snapshot(); assert 'pressure' in s and s['pressure'] in {'ok','warn','critical'}, s; print(s)"
```

### Step 0.5 — RAM pressure circuit breaker for background work

* **Files touched:** `core/observability/ram_monitor.py` (extend), `core/observability/__init__.py`.
* **Action:** add `RamMonitor.allow_background() -> bool` (returns False when pressure is `critical`; returns False for 30 s after a `warn`). All Phase 3–7 background workers MUST call `app_state.ram_monitor.allow_background()` before doing batch work and yield/sleep otherwise.
* **Verification:**

```bash
python - <<'PY'
from core.observability.ram_monitor import RamMonitor
m = RamMonitor()
assert isinstance(m.allow_background(), bool)
print("ok")
PY
```

### Phase 0 exit gate

```bash
make lint && make test && python scripts/ram_gate.py --max-gb 64.0
git commit -am "phase-0: ram monitor + circuit breaker"
```

---

## Phase 1 — Core hardening & dependency containment

**Goal:** Pay down the technical debt that would otherwise sabotage every later phase: cap LangChain surface, lock memory budgets, and make every store explicitly lifecycled.

### Step 1.1 — Inventory and quarantine LangChain imports

* **Files touched:** `docs/plans/roadmaps/langchain-audit.md` (new).
* **Action:**

```bash
mkdir -p roadmaps
{
  echo "# LangChain / LangGraph import audit"
  echo
  echo "## Direct \`langchain\` / \`langchain_*\` imports (target: 0)"
  grep -rEn "^(from|import) langchain(_|\b)" core/ ui/ main.py || echo "(none)"
  echo
  echo "## \`langgraph\` imports (allowed)"
  grep -rEn "^(from|import) langgraph" core/ ui/ main.py || echo "(none)"
} > docs/plans/roadmaps/langchain-audit.md
```

* **Verification:** the audit file must exist and contain a zero-direct-langchain report **OR** a follow-up ticket section listing each offender.

```bash
test -f docs/plans/roadmaps/langchain-audit.md && \
( ! grep -rEn "^(from|import) langchain(_|\b)" core/ ui/ main.py | grep -v "langchain_core" )
```

(`langchain_core` is whitelisted because `langgraph` ships it transitively.)

### Step 1.2 — Memory store lifecycle protocol

* **Files touched:** `core/memory/__init__.py`, `core/memory/vector_store.py`, `core/memory/long_term.py`.
* **Action:** add an explicit `async def close(self) -> None` to `VectorStore` and `LongTermStore`, plus a class-level `is_open` flag. In `ui/tray/server.py` `lifespan` shutdown, call `await app_state.vector_store.close()`.
* **Verification:**

```bash
python - <<'PY'
import inspect
from core.memory.vector_store import VectorStore
from core.memory.long_term import LongTermStore
for cls in (VectorStore, LongTermStore):
    assert hasattr(cls, "close"), cls
    assert inspect.iscoroutinefunction(cls.close), cls
print("ok")
PY
```

### Step 1.3 — Token budget audit

* **Files touched:** `core/memory/context_builder.py` (extend `AssembledContext` to include `budget_remaining`), `tests/test_memory.py` (add an assertion that `budget_remaining >= 0`).
* **Verification:**

```bash
.venv/bin/pytest tests/test_memory.py -q
```

### Step 1.4 — Process-RSS gate at startup

* **Files touched:** `main.py`.
* **Action:** right after `_build_app_state()` and before `uvicorn.run`, run `RamMonitor().snapshot()` and refuse to start if `available_gb < 1.2` (configurable via `CEREBRO_MIN_AVAILABLE_GB`). Log a clear message and exit `2`.
* **Verification:**

```bash
CEREBRO_MIN_AVAILABLE_GB=9999 python main.py 2>&1 | grep -q "insufficient RAM" \
  && echo "startup gate ok"
```

### Phase 1 exit gate

```bash
git checkout -b phase-1-core-hardening
make lint && make test && python scripts/ram_gate.py --max-gb 64.0
git commit -am "phase-1: core hardening, langchain quarantined, store lifecycle"
```

---

## Phase 2 — Unified multi-layer memory

**Goal:** Replace the "chunks-and-embeddings = memory" model with the **seven memory types** from `docs/plans/vision/ideas-future.md`: Semantic, Episodic, Procedural, Temporal, Project, Tool, Preference. Each lives in the right backing store (LanceDB or SQLite) — never as a separate process.

### Step 2.1 — Memory type taxonomy

* **Files touched:** `core/memory/types.py` (new).
* **Action:** define a `MemoryKind` enum and a `MemoryRecord` dataclass:

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Any

class MemoryKind(str, Enum):
    SEMANTIC   = "semantic"     # facts, document chunks (LanceDB)
    EPISODIC   = "episodic"     # events, sessions     (LanceDB existing table)
    PROCEDURAL = "procedural"   # workflows, recipes   (SQLite)
    TEMPORAL   = "temporal"     # timelines, deadlines (SQLite)
    PROJECT    = "project"      # long-running project state (SQLite)
    TOOL       = "tool"         # tool success/latency stats (SQLite)
    PREFERENCE = "preference"   # user style/policies  (SQLite)

@dataclass
class MemoryRecord:
    id: str
    kind: MemoryKind
    content: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0
    confidence: float = 1.0
    tags: list[str] = field(default_factory=list)
```

* **Verification:**

```bash
python -c "from core.memory.types import MemoryKind, MemoryRecord; assert len(MemoryKind) == 7"
```

### Step 2.2 — SQLite-backed memory store

* **Files touched:** `core/memory/structured_store.py` (new). Add `aiosqlite>=0.20` to `pyproject.toml`.
* **Action:** implement `StructuredMemoryStore(db_path: str)` with:
  * `async def upsert(record: MemoryRecord) -> None`
  * `async def get(record_id: str) -> MemoryRecord | None`
  * `async def list(kind: MemoryKind, *, limit: int = 50, tag: str | None = None) -> list[MemoryRecord]`
  * `async def delete(record_id: str) -> None`
  * `async def close() -> None`
* The schema is a single `memory` table with `(id PK, kind, content, payload_json, created_at, updated_at, confidence, tags_json)` plus indexes on `(kind, updated_at)` and `(kind, tag)`. Default DB path: `${CEREBRO_STATE}/structured_memory.sqlite`.
* **Verification:**

```bash
.venv/bin/pip install "aiosqlite>=0.20"
python - <<'PY'
import asyncio, tempfile, os
from core.memory.types import MemoryKind, MemoryRecord
from core.memory.structured_store import StructuredMemoryStore

async def main():
    d = tempfile.mkdtemp()
    s = StructuredMemoryStore(os.path.join(d, "m.sqlite"))
    await s.upsert(MemoryRecord(id="r1", kind=MemoryKind.PREFERENCE, content="dark mode"))
    got = await s.get("r1"); assert got and got.kind == MemoryKind.PREFERENCE
    await s.close()
    print("ok")
asyncio.run(main())
PY
```

### Step 2.3 — Unified memory router

* **Files touched:** `core/memory/router.py` (new).
* **Action:** `MemoryRouter` dispatches reads/writes by `MemoryKind`:
  * `SEMANTIC` and `EPISODIC` → existing `LongTermStore` (LanceDB)
  * everything else → `StructuredMemoryStore` (SQLite)
* Public API: `store(record)`, `retrieve(query, kinds, limit)`, `recent(kind, n)`, `forget(id)`.
* **Verification:** add a test file `tests/test_memory_router.py` covering one write+read per kind.

```bash
.venv/bin/pytest tests/test_memory_router.py -q
```

### Step 2.4 — Wire MemoryRouter into AppState

* **Files touched:** `main.py`, `ui/tray/server.py` (AppState dataclass).
* **Action:** construct `MemoryRouter` after `LongTermStore` and inject as `app_state.memory_router`. Refuse to start if SQLite path is on a read-only filesystem.
* **Verification:**

```bash
python -c "from main import _build_app_state; _build_app_state(); from ui.tray.server import app_state; assert app_state.memory_router is not None; print('ok')"
```

### Step 2.5 — Tool memory hook

* **Files touched:** `core/agents/runtime.py` (post-tool block), `core/memory/types.py`.
* **Action:** after every executed tool, append a `MemoryRecord(kind=TOOL, payload={"name":..., "success":..., "latency_ms":...})`. Schedule a daily rollup (deferred to Phase 4) — for now just write rows.
* **Verification:**

```bash
.venv/bin/pytest tests/test_tool_confirmation.py tests/test_agent_runtime.py -q
```

### Step 2.6 — Preference + project memory CRUD endpoints

* **Files touched:** `ui/tray/server.py`, `ui/tray/src/api/client.ts`, `ui/tray/src/api/types.ts`.
* **Action:** add `GET/PUT /api/memory/preferences`, `GET/POST /api/memory/projects`, `GET /api/memory/projects/{id}`. Each returns / accepts `MemoryRecord` payloads.
* **Verification:**

```bash
# expects backend running on :7842
curl -fsS -X PUT http://localhost:7842/api/memory/preferences \
  -H 'Content-Type: application/json' \
  -d '{"content":"prefers concise answers","tags":["tone"]}' \
  | python -m json.tool
curl -fsS http://localhost:7842/api/memory/preferences | python -m json.tool
```

### Phase 2 exit gate

```bash
git checkout -b phase-2-multi-memory
make lint && make test && python scripts/ram_gate.py --max-gb 64.0
git commit -am "phase-2: 7-layer memory router (LanceDB + SQLite)"
```

---

## Phase 3 — Persistent cognitive graph

**Goal:** Add the **cognitive graph** layer (entities, relationships, projects, timelines, causality) without spinning up a database server. This is the single biggest leap toward the "Cognitive Operating Layer" framing.

### Step 3.1 — Pick and pin the embedded graph engine

* **Decision:** **Kùzu** — embedded property-graph DB written in C++, low RSS (~50 MB idle), single-file storage, cross-platform binary wheels for macOS arm64. License: MIT. No daemon.
* **Files touched:** `pyproject.toml`.
* **Action:** add `kuzu>=0.7,<0.10`.
* **Verification:**

```bash
.venv/bin/pip install "kuzu>=0.7,<0.10"
python -c "import kuzu; print(kuzu.__version__)"
```

### Step 3.2 — Graph schema

* **Files touched:** `core/graph/__init__.py`, `core/graph/schema.cypher` (raw Cypher-like DDL), `core/graph/store.py`.
* **Schema (initial):**

```cypher
CREATE NODE TABLE Entity (
  id STRING PRIMARY KEY,
  label STRING,              -- person | document | repo | concept | tool | event | location
  name STRING,
  description STRING,
  created_at DOUBLE,
  confidence DOUBLE
);
CREATE NODE TABLE Project (
  id STRING PRIMARY KEY,
  name STRING,
  status STRING,             -- active | paused | done | dropped
  goal STRING,
  created_at DOUBLE,
  deadline DOUBLE
);
CREATE NODE TABLE Event (
  id STRING PRIMARY KEY,
  kind STRING,               -- mirror of EventBus event types (Phase 4)
  at DOUBLE,
  payload_json STRING
);
CREATE REL TABLE RELATED_TO  (FROM Entity TO Entity, weight DOUBLE, reason STRING);
CREATE REL TABLE PART_OF     (FROM Entity TO Project);
CREATE REL TABLE OCCURRED_IN (FROM Event  TO Project);
CREATE REL TABLE CAUSES      (FROM Event  TO Event, weight DOUBLE);
CREATE REL TABLE MENTIONS    (FROM Event  TO Entity);
```

* **Files touched:** add `core/graph/store.py` exposing a `CognitiveGraph` class:
  * `async def upsert_entity(id, label, name, **kwargs)`
  * `async def upsert_project(id, name, status, **kwargs)`
  * `async def log_event(id, kind, at, payload)`
  * `async def link(src, rel, dst, **props)`
  * `async def neighbors(entity_id, hops=1) -> list[dict]`
  * `async def query(cypher, params) -> list[dict]`
  * `async def close()`
* Default DB path: `${CEREBRO_STATE}/graph.kuzu/`.
* **Verification:**

```bash
python - <<'PY'
import asyncio, tempfile
from core.graph.store import CognitiveGraph
async def main():
    d = tempfile.mkdtemp()
    g = CognitiveGraph(db_path=d)
    await g.upsert_entity("e1", "person", "Javier")
    await g.upsert_entity("e2", "repo", "SecondBrain")
    await g.link("e1", "RELATED_TO", "e2", weight=0.9, reason="author")
    n = await g.neighbors("e1")
    assert len(n) >= 1, n
    await g.close()
    print("ok")
asyncio.run(main())
PY
```

### Step 3.3 — LLM-driven extraction pipeline (no extra models)

* **Files touched:** `core/graph/extractor.py` (new).
* **Action:** an `ExtractionPipeline` that takes a chunk of text + chat provider and asks the existing model to emit JSON like:

```json
{
  "entities": [{"label":"person","name":"Javier"},{"label":"concept","name":"cognitive graph"}],
  "relationships": [{"src":"Javier","rel":"RELATED_TO","dst":"cognitive graph","reason":"author"}],
  "events": [{"kind":"note_added","payload":{"path":"foo.md"}}]
}
```

The pipeline:
1. Asks the chat provider in **structured-output mode** (system prompt + JSON-only response).
2. Validates with a Pydantic model `ExtractionResult`.
3. Upserts into `CognitiveGraph` and writes a mirror `MemoryRecord(kind=EPISODIC)` for retrievability.
4. Skips work if `app_state.ram_monitor.allow_background()` is False.

* **Verification:**

```bash
# Uses a mocked chat provider returning a canned JSON.
.venv/bin/pytest tests/test_graph_extractor.py -q
```

### Step 3.4 — Graph-aware retrieval

* **Files touched:** `core/memory/context_builder.py`.
* **Action:** when building context, after the vector retrieval step, take the top-K entity names from the query (via the same structured-output prompt or a cheap keyword fallback) and pull `neighbors(entity_id, hops=1)` from the graph; budget at most **600 tokens** for graph-derived context. Append a "Related entities" section to the assembled prompt. Always respect `AssembledContext.budget_remaining`.
* **Verification:**

```bash
.venv/bin/pytest tests/test_memory.py tests/test_context_enricher.py -q
```

### Step 3.5 — Graph REST surface (read-only first)

* **Files touched:** `ui/tray/server.py`, `ui/tray/src/api/client.ts`, `ui/tray/src/api/types.ts`.
* **Endpoints:**
  * `GET /api/graph/entity/{id}?hops=1` → `{entity, neighbors}`
  * `GET /api/graph/search?q=<text>&limit=20` → `[entity, ...]`
  * `GET /api/graph/projects` → `[project, ...]`
* **Verification:**

```bash
curl -fsS "http://localhost:7842/api/graph/projects" | python -m json.tool
```

### Step 3.6 — Background re-indexing

* **Files touched:** `core/watcher/file_watcher.py`, `core/graph/extractor.py`.
* **Action:** when the watcher publishes a "file changed" event, queue an extraction job into a `BoundedAsyncQueue(maxsize=8)`. A single asyncio worker drains the queue with `await asyncio.sleep(0.1)` between items and pauses while `ram_monitor.allow_background()` is False.
* **Verification:**

```bash
.venv/bin/pytest tests/test_graph_extractor.py::test_watcher_integration -q
```

### Phase 3 exit gate

```bash
git checkout -b phase-3-cognitive-graph
make lint && make test && python scripts/ram_gate.py --max-gb 6.5
git commit -am "phase-3: cognitive graph (Kùzu) + extraction pipeline"
```

---

## Phase 4 — Event-driven backbone

**Goal:** Replace the implicit "user asks → AI answers" loop with an in-process **EventBus** so any subsystem (watcher, scheduler, ingestor, graph, tools) can publish events, and proactive intelligence can subscribe.

### Step 4.1 — EventBus core

* **Files touched:** `core/events/__init__.py`, `core/events/bus.py`, `core/events/types.py`.
* **Action:** define `Event(BaseModel)` with `id, kind, at, source, payload, correlation_id`. Implement `EventBus` with:
  * `async def publish(event: Event) -> None`
  * `def subscribe(kind: str | None, handler: Callable[[Event], Awaitable[None]]) -> Subscription`
  * Internal `asyncio.Queue(maxsize=1024)` with a single dispatcher task. Handler exceptions are caught + logged; the bus never deadlocks.
* **Verification:**

```bash
.venv/bin/pytest tests/test_event_bus.py -q
```

### Step 4.2 — Append-only SQLite event log

* **Files touched:** `core/events/log.py` (new).
* **Action:** `EventLog(db_path)` writes every published event into a SQLite table (`events(id PK, kind, at, source, payload_json, correlation_id)`); exposes `tail(kind=None, since=None, limit=100)`. Default path: `${CEREBRO_STATE}/events.sqlite`. WAL mode + `PRAGMA synchronous=NORMAL` for low latency.
* **Verification:**

```bash
python - <<'PY'
import asyncio, tempfile, os
from core.events.bus import EventBus
from core.events.log import EventLog
from core.events.types import Event
async def main():
    d = tempfile.mkdtemp()
    log = EventLog(os.path.join(d, "events.sqlite"))
    bus = EventBus(); bus.subscribe(None, log.write)
    await bus.publish(Event(id="1", kind="test", at=0, source="t", payload={}))
    await asyncio.sleep(0.05)
    assert len(await log.tail()) == 1
    print("ok")
asyncio.run(main())
PY
```

### Step 4.3 — Wire existing sources

* **Files touched:** `core/watcher/file_watcher.py`, `scheduler/proactive.py`, `core/ingestion/pipeline.py`, `main.py`.
* **Action:** every existing trigger that today calls a callback now also `await bus.publish(...)`. Map:
  * Watcher → `event.kind = "fs.changed"`
  * Scheduler `CALENDAR_REMINDER` → `"calendar.upcoming"`
  * Scheduler `FILE_CHECKPOINT` → `"fs.hot_file"`
  * Scheduler `RESUME_CONTEXT` → `"session.idle_resume"`
  * Scheduler `NEW_DOCUMENT` → `"index.new_doc"`
  * Ingestor → `"index.completed"`
  * Tool execution → `"tool.executed"` (from Phase 2.5)
  * Graph extractor → `"graph.entity_upserted"`, `"graph.event_logged"`
* **Verification:**

```bash
.venv/bin/pytest tests/test_event_bus.py::test_existing_sources_wired -q
```

### Step 4.4 — Replace direct callbacks where useful

* **Files touched:** `scheduler/proactive.py` (delete unused callback plumbing once subscribers exist), `core/agents/runtime.py`.
* **Action:** mark legacy callback dispatch as deprecated by leaving a single `EventBus`-based path. Keep both for one release; tests cover both paths.
* **Verification:**

```bash
make test
```

### Phase 4 exit gate

```bash
git checkout -b phase-4-event-bus
make lint && make test && python scripts/ram_gate.py --max-gb 6.5
git commit -am "phase-4: in-process EventBus + persistent event log"
```

---

## Phase 5 — Ambient intelligence (macOS-first)

**Goal:** Make Cerebro **context-aware** of time, active app, focused window title, recent files — strictly via macOS-supported, opt-in APIs. No accessibility scraping, no keystroke capture.

### Step 5.1 — Privacy switch

* **Files touched:** `ui/tray/server.py` (`Config` model), `ui/tray/src/components/settings/SettingsPanel.tsx`.
* **Action:** add a config field `ambient_enabled: bool = False` and a UI toggle. When False, ambient observers MUST NOT publish events. Persisted in `${CEREBRO_STATE}/config.json`.
* **Verification:**

```bash
curl -fsS -X PATCH http://localhost:7842/api/config -H 'Content-Type: application/json' \
  -d '{"ambient_enabled":true}' | python -c "import sys,json;d=json.load(sys.stdin);assert d['ambient_enabled'] is True;print('ok')"
```

### Step 5.2 — Active app + window title observer (AppleScript)

* **Files touched:** `core/ambient/__init__.py`, `core/ambient/macos.py`.
* **Action:** subprocess wrapper around:

```bash
osascript -e 'tell application "System Events"
    set frontApp to name of first process whose frontmost is true
    set frontWin to ""
    try
        tell process frontApp
            set frontWin to name of front window
        end tell
    end try
    return frontApp & "||" & frontWin
end tell'
```

Poll every 30 s (configurable). Publish `event.kind = "ambient.focus_changed"` with `payload = {"app": ..., "window": ...}` only when the value changes.

* **Verification:**

```bash
osascript -e 'tell application "System Events" to return name of first process whose frontmost is true' >/dev/null && \
python -m core.ambient.macos --once
```

### Step 5.3 — Recent files via Spotlight (mdfind)

* **Files touched:** `core/ambient/macos.py` (extend).
* **Action:** every 5 minutes, run `mdfind -onlyin "$HOME" 'kMDItemFSContentChangeDate > $time.now(-300)'` (top 50 results) and emit one `ambient.recent_files` event with the path list. Excludes paths starting with `~/Library`, `~/.Trash`, app caches.
* **Verification:**

```bash
mdfind -onlyin "$HOME" 'kMDItemFSContentChangeDate > $time.now(-3600)' | head -3 || true
```

### Step 5.4 — Calendar context (reuse existing reader)

* **Files touched:** `core/ambient/macos.py` (extend).
* **Action:** every 15 minutes, call the existing calendar tool's `get_upcoming_events(hours_ahead=4)` and emit `ambient.calendar_window`.
* **Verification:**

```bash
.venv/bin/pytest tests/test_ambient_macos.py -q
```

### Step 5.5 — Hook ambient into ContextEnricher

* **Files touched:** `core/agents/context_enricher.py`.
* **Action:** when assembling context, append an "Ambient context" block (≤ 200 tokens) summarizing the most recent `ambient.*` events from the event log. This is the **only** path by which ambient signals reach the LLM prompt.
* **Verification:**

```bash
.venv/bin/pytest tests/test_context_enricher.py -q
```

### Phase 5 exit gate

```bash
git checkout -b phase-5-ambient
make lint && make test && python scripts/ram_gate.py --max-gb 6.5
git commit -am "phase-5: ambient intelligence (macOS, opt-in)"
```

---

## Phase 6 — Proactive intelligence

**Goal:** Turn the event stream into **suggestions** the user can act on, while never sending spam. This is what makes Cerebro stop feeling like a chat box.

### Step 6.1 — Suggestion model + store

* **Files touched:** `core/proactive/__init__.py`, `core/proactive/suggestion.py`.
* **Action:** define `Suggestion(BaseModel)` with `id, kind, title, body, action_hint, evidence_event_ids, score, created_at, status: Literal["pending","accepted","dismissed","stale"]`. Persisted as `MemoryRecord(kind=PROCEDURAL, payload={"suggestion": ...})` via `MemoryRouter`.
* **Verification:**

```bash
python -c "from core.proactive.suggestion import Suggestion; print(Suggestion.model_json_schema()['title'])"
```

### Step 6.2 — Pattern rules (rule-engine first, LLM later)

* **Files touched:** `core/proactive/rules.py`.
* **Action:** small composable rules subscribed to `EventBus`:
  * **deadline_near**: emits when `ambient.calendar_window` contains an event within 60 min.
  * **repo_stale**: when `graph.entity_upserted{label=repo}` has no `OCCURRED_IN` event in 30 days, emit.
  * **paper_relates_to_project**: when `index.new_doc` shares ≥ 2 entities with an active `Project`, emit.
  * **hot_file_checkpoint**: on `fs.hot_file`, emit a "consider committing".
  * **idle_resume**: on `session.idle_resume`, emit a "where were you?" with last 3 active entities.
* Each rule has a per-kind cooldown (`min_interval_seconds`) to prevent spam.
* **Verification:**

```bash
.venv/bin/pytest tests/test_proactive_rules.py -q
```

### Step 6.3 — Suggestion REST surface

* **Endpoints:**
  * `GET /api/suggestions?status=pending&limit=20`
  * `POST /api/suggestions/{id}/accept` → may schedule a tool call
  * `POST /api/suggestions/{id}/dismiss`
* **Verification:**

```bash
curl -fsS "http://localhost:7842/api/suggestions?status=pending" | python -m json.tool
```

### Step 6.4 — Frontend: SuggestionsPanel

* **Files touched:** `ui/tray/src/components/chat/SuggestionsPanel.tsx` (new), `ui/tray/src/stores/suggestions.ts` (new), `ui/tray/src/layouts/MainLayout.tsx`.
* **Action:** a non-blocking right-side drawer that polls `/api/suggestions` every 30 s when `ambient_enabled` is true. Each card has Accept / Dismiss buttons. Dismissed suggestions never resurface within 24 h.
* **Verification:**

```bash
cd ui/tray && npm run lint && npm run build
```

### Step 6.5 — Notification quietness budget

* **Files touched:** `core/proactive/quietness.py`.
* **Action:** at most **3 pending suggestions** at any time and **at most 10 emitted per hour**. Excess go to a "later" buffer in SQLite and surface when older ones are dismissed. DND mode (`config.dnd_enabled`) silences all.
* **Verification:**

```bash
.venv/bin/pytest tests/test_proactive_quietness.py -q
```

### Phase 6 exit gate

```bash
git checkout -b phase-6-proactive
make lint && make test && python scripts/ram_gate.py --max-gb 6.5
cd ui/tray && npm run build
git commit -am "phase-6: proactive intelligence + suggestion drawer"
```

---

## Phase 7 — AI-native filesystem & workspace

**Goal:** Make the local filesystem itself feel like part of the cognitive layer: a dedicated `CerebroFiles/` workspace with AI-native operations (capture, summarize-on-save, link-to-project, generate-companion-notes).

### Step 7.1 — Workspace bootstrap

* **Files touched:** `core/workspace/__init__.py`, `core/workspace/layout.py`.
* **Action:** ensure on startup the workspace tree exists:

```
${CEREBRO_FILES_PATH}/
  inbox/         # everything captured lives here briefly
  notes/         # markdown notes (auto + manual)
  projects/<id>/ # per-project folders, linked to graph
  research/      # imported papers & summaries
  artifacts/     # tool outputs (scripts, plots, exports)
  .cerebro/      # internal manifests (NEVER shown in UI)
```

* **Verification:**

```bash
python - <<'PY'
import os
from core.workspace.layout import ensure_workspace
root = ensure_workspace("/tmp/CerebroFiles")
for sub in ("inbox","notes","projects","research","artifacts",".cerebro"):
    assert os.path.isdir(os.path.join(root, sub)), sub
print("ok")
PY
```

### Step 7.2 — Capture tool

* **Files touched:** `core/tools/handlers/workspace.py` (new), `core/tools/registry.py`.
* **New tool:** `capture(content: str, hint: str | None = None) -> str` writes a markdown file into `inbox/` with frontmatter `{id, created_at, hint}` and publishes `event.kind = "workspace.captured"`. The agent uses this when the user says "remember this", "save that", etc.
* **Verification:**

```bash
.venv/bin/pytest tests/test_workspace_tools.py -q
```

### Step 7.3 — Auto-companion summaries

* **Files touched:** `core/workspace/companion.py`.
* **Action:** on `workspace.captured` and `index.new_doc`, schedule (with `allow_background()` gate) a short summary and 3 candidate tags using the existing chat provider. Write `notes/<id>.summary.md` next to the original.
* **Verification:**

```bash
.venv/bin/pytest tests/test_workspace_companion.py -q
```

### Step 7.4 — Project ↔ filesystem binding

* **Files touched:** `core/workspace/projects.py`.
* **Action:** when a `Project` node is created in the graph, mkdir `projects/<id>/` and write `projects/<id>/PROJECT.md` containing the project's `name`, `goal`, `status`, and a "How to use this folder" preamble. When the user drops a file into `projects/<id>/`, the watcher emits `workspace.project_file_added` and the graph extractor links the resulting entities `PART_OF` the project.
* **Verification:**

```bash
.venv/bin/pytest tests/test_workspace_projects.py -q
```

### Phase 7 exit gate

```bash
git checkout -b phase-7-workspace
make lint && make test && python scripts/ram_gate.py --max-gb 6.5
git commit -am "phase-7: AI-native workspace (capture, summarize, project binding)"
```

---

## Phase 8 — Skill / capability marketplace

**Goal:** Make every capability (coding, PDF analysis, research, planning, automation) a **pluggable skill** discoverable at runtime. Local-first registry; remote marketplace is just a fetcher.

### Step 8.1 — Skill manifest spec

* **Files touched:** `docs/skills/SKILL_MANIFEST.md`, `core/skills/manifest.py`.
* **Manifest example (`SKILL.toml`):**

```toml
[skill]
id = "research.pdf-analyzer"
name = "PDF Analyzer"
version = "0.1.0"
description = "Summarizes and extracts entities from PDFs."
entrypoint = "skills/research_pdf_analyzer/plugin.py:Plugin"
min_ram_gb = 0.05
permissions = ["read_file", "search_documents"]

[[skill.tools]]
name = "summarize_pdf"
description = "Summarize a PDF at <= 200 words."

[[skill.events]]
subscribes = ["index.new_doc"]
```

* `core/skills/manifest.py` parses + validates with Pydantic.
* **Verification:**

```bash
python -c "from core.skills.manifest import load_manifest; m=load_manifest('docs/skills/example/SKILL.toml'); print(m.id)"
```

### Step 8.2 — Plugin loader

* **Files touched:** `core/skills/loader.py`.
* **Action:** at startup, scan `${CEREBRO_STATE}/skills/*/SKILL.toml`, import the entrypoint, instantiate `Plugin(cerebro_api)` where `cerebro_api` is a tiny facade exposing `tool_registry`, `event_bus`, `memory_router`, `graph` — never `app_state` directly. Each skill MUST declare `min_ram_gb`; loader refuses if `ram_monitor` reports less available.
* **Verification:**

```bash
.venv/bin/pytest tests/test_skill_loader.py -q
```

### Step 8.3 — Reference skill: research-summarizer

* **Files touched:** `skills/research_summarizer/` (new).
* **Action:** ships in-tree as the canonical example: implements `summarize_pdf` and subscribes to `index.new_doc` to autogenerate a 200-word abstract written into `workspace/research/`.
* **Verification:**

```bash
.venv/bin/pytest tests/test_skill_research_summarizer.py -q
```

### Step 8.4 — Skill management REST + UI

* **Endpoints:**
  * `GET /api/skills` → installed skills with status (`enabled`, `disabled`, `incompatible_ram`)
  * `POST /api/skills/{id}/enable` and `/disable`
  * `POST /api/skills/install` (local zip path or git URL — git path stays disabled until Phase 8.5)
* **UI:** `ui/tray/src/components/settings/SkillsPanel.tsx` listing skills with toggles.
* **Verification:**

```bash
curl -fsS http://localhost:7842/api/skills | python -m json.tool
cd ui/tray && npm run build
```

### Step 8.5 — Marketplace fetcher (optional)

* **Files touched:** `core/skills/marketplace.py`.
* **Action:** read-only client for a future `cerebro-skills` GitHub org index (`https://raw.githubusercontent.com/<org>/index/main/index.json`). Downloads a verified-by-sha256 zip into `${CEREBRO_STATE}/skills/<id>/`. **Network is opt-in** (config flag `marketplace_enabled: false` by default).
* **Verification:**

```bash
.venv/bin/pytest tests/test_skill_marketplace.py -q
```

### Phase 8 exit gate

```bash
git checkout -b phase-8-skills
make lint && make test && python scripts/ram_gate.py --max-gb 6.5
git commit -am "phase-8: skill marketplace (local loader + reference skill)"
```

---

## Phase 9 — Branding, docs & open-source readiness

**Goal:** Stop calling Cerebro an "assistant". Make the public surface (README, API metadata, UI) say **Cognitive Operating Layer** and ready the repo for outside contributors.

### Step 9.1 — Rename the public concepts

* **Files touched:** `README.md`, `docs/README.md`, `CLAUDE.md`, `ui/tray/src/layouts/Header.tsx`, `ui/tray/index.html`, FastAPI `app = FastAPI(title=...)`.
* **Action:** "personal assistant" → "cognitive operating layer". Tagline: *"A local-first cognitive operating layer for one human."* Keep "Cerebro" as the product name.
* **Verification:**

```bash
! grep -rEi "personal assistant" README.md docs/README.md CLAUDE.md ui/tray/index.html ui/tray/src/layouts/Header.tsx
```

### Step 9.2 — Public architecture diagram

* **Files touched:** `docs/architecture/cognitive-layer.md` (new), `docs/architecture/cognitive-layer.svg` (export from Mermaid).
* **Action:** write the document showing the planes: Desktop UI → REST API → AppState → (Inference, Memory router, Cognitive graph, EventBus, Skills, Ambient). Render the SVG via `npx -y @mermaid-js/mermaid-cli` if available.
* **Verification:**

```bash
test -f docs/architecture/cognitive-layer.md
```

### Step 9.3 — Contributor docs + plugin API reference

* **Files touched:** `CONTRIBUTING.md`, `docs/skills/PLUGIN_API.md`.
* **Action:** document the `cerebro_api` facade, how to publish a skill, branch/PR rules, the 8 GB RAM contract.
* **Verification:**

```bash
test -f CONTRIBUTING.md && test -f docs/skills/PLUGIN_API.md
```

### Step 9.4 — License + security policy

* **Files touched:** confirm `LICENSE` is present (already MIT). Add `SECURITY.md`.
* **Verification:**

```bash
test -f LICENSE && test -f SECURITY.md
```

### Phase 9 exit gate

```bash
git checkout -b phase-9-branding
make lint && make test
git commit -am "phase-9: rebrand to Cognitive Operating Layer + contributor docs"
```

---

## Phase 10 — Cross-platform (OPTIONAL, runs only on request)

> Skip unless explicitly green-lit. macOS quality bar must hold even with 16+ GB Macs as a happy path.

### Step 10.1 — RAM profile for ≥ 16 GB Macs

* **Files touched:** `config/profiles/mac-16gb.toml` (new), `core/inference/fleet/orchestrator.py`.
* **Action:** when `psutil.virtual_memory().total >= 14 * 1024**3`, load a larger chat model (e.g. 7–8B Q4_K_M) and double the embedding cache. Profile is selected at startup by `FleetOrchestrator`.
* **Verification:**

```bash
.venv/bin/pytest tests/test_fleet_orchestrator.py -q
```

### Step 10.2 — Linux port

* **Files touched:** `core/ambient/linux.py`, `core/ambient/__init__.py` (platform router), `pyproject.toml`.
* **Action:** replace AppleScript polling with `xdotool` (X11) and `swaymsg` / `hyprctl` (Wayland) probes guarded by `shutil.which`. Replace Spotlight `mdfind` with `recoll` if installed, else a fallback that walks `~` with `pathlib` and an mtime filter. **No new mandatory deps.** Linux skips ambient observers if no supported window manager is detected.
* **Verification (on Linux machine only):**

```bash
python -m core.ambient.linux --once
```

### Step 10.3 — Windows port

* **Files touched:** `core/ambient/windows.py`.
* **Action:** use `ctypes.windll.user32.GetForegroundWindow` + `GetWindowTextW` for active-window detection; `pywin32` is **NOT** added — we stick to `ctypes`. Recent files via `WIN32_FIND_DATA` over `%USERPROFILE%`. Calendar integration via Outlook MAPI is **out of scope** for v1.
* **Verification (on Windows VM only):**

```powershell
python -m core.ambient.windows --once
```

### Step 10.4 — Cross-platform CI matrix

* **Files touched:** `.github/workflows/test.yml`.
* **Matrix:** `os: [macos-latest, ubuntu-latest, windows-latest]`, `python-version: ["3.11"]`. Ambient tests on Linux/Windows are marked `pytest.mark.platform_specific` and only run on their host.
* **Verification:**

```bash
gh workflow run test.yml --ref $(git rev-parse --abbrev-ref HEAD) || true
gh run list --workflow=test.yml --limit 1
```

### Phase 10 exit gate

```bash
git checkout -b phase-10-cross-platform
make lint && make test
git commit -am "phase-10: cross-platform ambient + 16GB Mac profile"
```

---

## Appendix A — Definition of Done per phase

A phase is **done** when ALL of the following are true:

1. `make lint` exits 0.
2. `make test` exits 0 and the new tests for the phase are present in the diff.
3. `python scripts/ram_gate.py --max-gb 6.5` exits 0 on M1 8 GB while the backend is running with default model.
4. The phase branch is merged (squash) into `main` and `docs/plans/roadmaps/cognitive-layer-progress.log` has the phase's final entry.
5. The relevant section of `docs/architecture/cognitive-layer.md` is updated (Phase 9 backfills this).
6. No new dependency outside the table in Appendix B was added.

## Appendix B — Allowed new dependencies (locked)

| Dep | Version | Phase | Reason |
|-----|---------|-------|--------|
| `aiosqlite` | `>=0.20` | 2 | async wrapper for SQLite memory + event log |
| `kuzu` | `>=0.7,<0.10` | 3 | embedded property graph DB |
| (none else) | — | 4–9 | everything reuses existing deps |

Anything outside this table requires a written architectural exception logged in `docs/plans/roadmaps/exceptions.md` before installation.

## Appendix C — Failure-handling protocol for Claude Code

* **A test fails after a step:** revert just that step's changes (`git checkout -- <files>`), append the failure to `docs/plans/roadmaps/cognitive-layer-progress.log` as `STEP <id> FAILED`, and stop. Do not start the next step.
* **RAM gate fails:** identify the heaviest in-process store via `RamMonitor.snapshot()`; if it is a new Phase 2+ store, close it and retry. If still failing, treat as a step failure and stop.
* **Network is needed (e.g. installing a wheel):** request the `full_network` permission once per phase and explain why; do not request indefinitely.
* **Ambiguity in the spec:** prefer the **smallest, reversible** interpretation and surface the question in `docs/plans/roadmaps/cognitive-layer-progress.log` rather than guessing aggressively.

---

*End of plan. Begin with Phase 0, Step 0.1.*

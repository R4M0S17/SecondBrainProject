# Documentation index

Canonical technical docs live under **`docs/`** at the repository root (not under `cerebro/`).

| Area | Path | Contents |
|------|------|----------|
| **Architecture & ops** | [`../CLAUDE.md`](../CLAUDE.md) | Stack overview, make targets, env vars, REST API sketch |
| **Connection checklist** | [`connection/progress.md`](connection/progress.md) | Backend ↔ frontend wiring modules and smoke-test notes |
| **HTTP / API usage** | [`connection/api-guide.md`](connection/api-guide.md) | REST examples |
| **Runbooks** | [`guides/howToRun.md`](guides/howToRun.md) · [`guides/running-es.md`](guides/running-es.md) · [`guides/llamacpp-run-guide.md`](guides/llamacpp-run-guide.md) | English / Spanish startup, llama.cpp notes |
| **Inference** | [`inference/`](inference/) | llama.cpp, MLX, RAM notes |
| **Frontend** | [`frontend/`](frontend/) | Design, roadmap, pending changes |
| **Product / spec** | [`project/`](project/) | Specs, current state, Obsidian inspiration |
| **Model efficiency experiment** | [`testing/`](testing/) | PLAN, EXECUTION_GUIDE, QUICK_START, EXPERIMENTAL_SUMMARY |
| **Pytest remediation (known failures)** | [`testing/PYTEST_REMEDIATION_PATH.md`](testing/PYTEST_REMEDIATION_PATH.md) | Ordered fixes for fleet monitor / phase7 args / planner parsing |
| **Issues & playbook** | [`PROJECT_ISSUES_AND_SOLUTIONS.md`](PROJECT_ISSUES_AND_SOLUTIONS.md) | Long-form troubleshooting ledger |

Supporting material elsewhere:

- **`features/`** — integration plans (e.g. Claude API, fleet orchestrator)
- **`bugs/`** — incident write-ups and migration logs
- **`roadmaps/`** — phased optimization notes

Duplicate copies under **`cerebro/`** were removed on purpose; use this tree or [`cerebro/docs/README.md`](../cerebro/docs/README.md) for the short pointer.

---

## Cerebro — what this program is

**Cerebro** is a **local-first, agentic personal assistant** packaged as a desktop application. A **Python (FastAPI)** backend and a **React + TypeScript** UI (with **Tauri** for the desktop shell) talk over **HTTP** on a fixed port (by default **7842**). The product is meant to sit on your machine like a second brain: you ask questions, the system reasons with **retrieval-augmented memory** over your own files, and it can use **tools** (filesystem, search, calendar, controlled execution) when the agent decides they are needed—sometimes pausing for **your explicit approval** before risky actions.

Under the hood, **LangGraph-style agent runtimes** route work between specialized behaviors (for example general chat, code-oriented help, or calendar-aware flows). **Short-term** context keeps the current session coherent; **long-term** storage (vector search, for example over **LanceDB**) brings back relevant chunks from documents you have indexed. **Indexing** ingests PDFs and office-style documents, chunks them, embeds them, and keeps them searchable as your library changes (with optional filesystem watching to re-index). The stack is designed so that **inference** is pluggable: **llama.cpp** on GGUF models, **MLX** on Apple Silicon when enabled, and optionally **Anthropic Claude** for cloud chat—while **embeddings** for RAG typically remain **local** so your knowledge base does not depend on a single vendor’s embedding API.

---

## Why it is innovative (relative to a generic chatbot)

Most assistants are either **cloud-only** (data leaves your machine) or **single-model notepads** (no durable memory over your files, no tool loop, no clear policy). Cerebro combines several ideas that are still uncommon in one coherent desktop product:

- **Privacy and ownership by default.** Your primary path can keep weights and document embeddings on hardware you control, with optional cloud chat only when you opt in and configure keys.
- **Agentic loop with governance.** The system is built around **tools and policies**: dangerous operations can surface as **pending confirmations** in the UI instead of silently executing.
- **Personal knowledge, not just prompts.** RAG, watched folders, and indexing tie answers to **your** corpus rather than only the model’s training cutoff.
- **Operational realism for laptops.** Support for **multiple inference backends**, model swapping, and documentation around **RAM and latency** reflects real constraints on personal machines—not only datacenter assumptions.
- **Transparent plumbing for builders.** A documented **REST API**, typed contracts between backend and frontend, and modular stages (intent, context, prompt, policy, audit) make the system **inspectable and extensible** for people who want to fork or integrate.

Innovation here is **architectural and product-shaped**: it is less about a single novel algorithm and more about **integrating** local inference, memory, agents, and desktop UX responsibly.

---

## Limitations (honest scope)

- **Hardware and setup.** Local GGUF models need **RAM, disk, and sometimes GPU layers**; wrong sizing means slow replies or failures. MLX is **Apple-centric**; other platforms depend on llama.cpp behavior and drivers.
- **Model quality vs frontier cloud.** On-device models will **not always match** the best hosted models on reasoning, coding, or long-context tasks unless you route chat to Claude (which introduces **cost** and **external dependency**).
- **Embeddings and engines.** Even in API chat mode, **embedding / index** paths often expect a **local embed server**—so “fully cloud” operation is not the default story.
- **Safety is best-effort, not certification.** Tool policies and confirmation flows **reduce risk** but do not replace enterprise security review, DLP, or formal compliance programs.
- **Single-user desktop assumptions.** The app is oriented around **one user on one machine**; multi-tenant admin, SSO, and org-wide deployment are not the core design center.
- **Complexity for non-technical users.** Power features (env vars, engine scripts, model files, wizard skips) assume a reader who is comfortable following **runbooks** or asking a technical friend.

---

## Who this is for

**Primary audience**

- **Developers and technical power users** who want a **hackable** local assistant with RAG, agents, and a real API.
- **Privacy-conscious individuals** (researchers, writers, lawyers in personal workflows, etc.) who prefer **on-device** processing for sensitive notes, with optional cloud only when they choose.
- **Apple Silicon power users** who can benefit from **MLX** and unified-memory patterns documented in this repo.

**Secondary audience**

- **Local-AI enthusiasts** comparing stacks (llama.cpp vs MLX vs hybrid with API fallback).
- **Small teams or prototypes** where one machine runs Cerebro as a **personal knowledge cockpit**—not as a replacement for org-wide IT-managed assistants.

**Not the primary fit**

- Organizations needing **guaranteed SLAs**, centralized audit without local ops, or **non-technical** rollouts with zero setup.
- Users who only want a **single-button** consumer chat with no model files, no ports, and no reading of environment or engine documentation—unless they stay on a fully guided path and accept defaults someone else configures for them.

If you are unsure whether Cerebro matches you: it rewards people who are willing to **read the docs**, run **make** targets, and treat the assistant as **software they operate**, not only a website they visit.

---

## Architecture (system view)

Cerebro is split into three cooperating planes: **desktop UI**, **HTTP API**, and **local services** (inference engines and on-disk stores). The UI never talks to llama.cpp or MLX directly; it only talks to the **FastAPI** process. That process owns **agent execution**, **memory**, **tool dispatch**, and **provider selection**. External binaries (llama.cpp server processes started via scripts or `ModelManager`) are treated as **dependencies**: the backend probes health, sends chat and embedding requests, and surfaces status to the UI.

**Request path (conceptual).** A user message enters through `POST /api/query` or `POST /api/query/stream`. The server resolves **conversation** identity, runs or skips **pipeline stages** (intent, context assembly, prompt construction, policy, audit—depending on build and configuration), and hands a prepared prompt to the **agent runtime**. The runtime drives a **LangGraph**-style graph: model turns alternate with **tool** turns when the model emits tool calls. Tool results feed back into the graph until a final answer is produced. **Response metadata** (latency, model, provider, tools used, RAG hits, optional pending tool approval) is attached to every reply. Streaming uses **Server-Sent Events** over the same API port so tokens can arrive incrementally without opening a second protocol.

**Memory and knowledge.** **Short-term** memory is in-process / session-oriented conversation state. **Long-term** recall uses **vector search** (LanceDB in this codebase) over chunks produced by **ingestion** (PDF, DOCX, etc.). Embeddings are produced by a dedicated **embedding provider** (typically the same llama.cpp ecosystem with an embed-capable GGUF). **Watchers** can trigger re-indexing when watched folders change. This separation keeps “chat weights” and “document index” as two different operational concerns you can size independently.

**Inference abstraction.** A **provider registry** holds one **primary** chat provider and optional **fallbacks** (for example MLX on Apple Silicon, or failure-driven fallback). Chat providers implement a common contract: availability checks, model identity, completion and streaming. **Model manager** mode can spawn **multiple** llama.cpp subprocesses (router model vs specialist models) and swap specialists by agent or task, which is how the stack balances RAM versus capability on a laptop.

---

## Implementation (repository layout and responsibilities)

**Entry and wiring.** `main.py` is the composition root: it constructs inference providers (llama.cpp, optional MLX, optional Claude API), embedding helpers, vector store, agent runtime with tool registry, optional model manager and fleet/orchestrator hooks, and injects the resulting **`AppState`** into the FastAPI app defined in **`ui/tray/server.py`**. Uvicorn serves the app on **`CEREBRO_PORT`** (default **7842**). Tests replace pieces of `AppState` so the server can be exercised without live models.

**Backend (`core/`).** The Python package is organized by concern:

- **`core/inference/`** — `registry.py` coordinates providers; `model_manager.py` supervises llama.cpp child processes and ports; **`providers/`** implements `llamacpp_provider`, `mlx_provider`, and **`claude_api_provider`** for cloud chat when enabled. Fleet-related helpers (hardware snapshot, orchestration) live alongside when present.
- **`core/agents/`** — `runtime.py` runs the graph; `specialized.py` and **`llm_router.py`** route queries to general / code / calendar-style profiles; conversation and agent state persist under **`CEREBRO_STATE`**.
- **`core/memory/`** and **`core/rag/`** — assemble retrieved chunks into prompts and expose vector query primitives.
- **`core/ingestion/`** — document parsing, chunking, embedding writes into the DB path under **`CEREBRO_DB`**.
- **`core/tools/`** — registry plus handlers (filesystem, search, calendar, restricted execution); **`policy.py`** marks which tools require user confirmation in the UI.
- **`core/pipeline/stages/`** — per-request transforms (intent, context, prompt, policy, audit) when the pipeline is active for a build.
- **`core/watcher/`**, **`core/scheduler/`**, **`core/observability/`** — filesystem-driven refresh, periodic jobs, and response metadata collection.

**REST surface.** All routes are mounted under **`/api`** on the FastAPI **`APIRouter`**. Notable groups: **`/api/query`** and **`/api/query/stream`**, **`/api/tool-confirm`** for the confirmation handshake, **`/api/index`** and **`/api/index/status`**, **`/api/status`**, **`/api/config`** (GET/PATCH), **`/api/conversations`**, **`/api/models`**, and **`/api/wizard/*`** for onboarding (llama.cpp reachability and on-disk model checks, with Claude-mode skips where applicable). Optional **`X-Cerebro-Key`** header auth is supported when environment variables are set on both client and server.

**Frontend (`ui/tray/`).** **React 18** with **TypeScript** and **Zustand** stores (`chat`, `history`, `settings`, `system`, `wizard`). **`src/api/client.ts`** centralizes HTTP calls; **`types.ts`** mirrors Pydantic shapes so drift is visible at compile time. Components are grouped by feature (**`components/chat`**, **`settings`**, **`status`**, **`wizard`**). **Tauri** wraps the web bundle as a desktop shell while development often uses **Vite** directly against the local API origin.

**Configuration and assets.** Runtime settings merge **environment variables** (inference backend, URLs, model names, API keys) with persisted JSON under the state directory. **GGUF** weights and prompt-cache paths are expected under conventions such as **`bin/models/`** and **`bin/cache/`**; **`config/*.args`** files feed llama.cpp launch profiles (chat, coding, deep). A parallel **`cerebro/`** tree in the repo can mirror subsets of the same layout for packaging experiments—treat **`core/`** + **`ui/tray/`** at the repo root as the primary implementation path unless your branch documentation says otherwise.

**Quality gates.** **`make test`** runs **pytest** with heavy mocking at `AppState` boundaries so CI does not require GPUs or live inference. **`make lint`** runs formatter, **Ruff**, and **Mypy** on the Python side; the tray app has its own **npm** scripts for type-check and build.

Together, this architecture implements a **single-user, local-first agent shell**: one HTTP backend coordinates models, memory, and tools, while the desktop UI focuses on chat, settings, status, and safe approval of high-risk operations.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/logo-light.svg">
  <img alt="Cerebro" src="docs/assets/cerebro-logo.svg" width="400">
</picture>

**Cerebro** (SecondBrain) is a **local-first, agentic personal operating system** for your machine. It combines a private LLM, persistent vector memory, intelligent agents, and a desktop UI into a single application — no cloud dependency required.

Ask questions, search your files, manage your calendar, and automate tasks. Cerebro reasons over *your* data using local models, keeps everything on-device, and only reaches for cloud APIs when you explicitly enable them.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB)](https://react.dev/)
[![Tauri](https://img.shields.io/badge/Tauri-2.0-FFC131)](https://tauri.app/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![macOS](https://img.shields.io/badge/platform-macOS-000?logo=apple)](https://www.apple.com/macos/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## Table of Contents

- [What Makes Cerebro Different](#-what-makes-cerebro-different)
- [Key Features](#-key-features)
- [Architecture Overview](#-architecture-overview)
- [Quick Start](#-quick-start)
- [Models & Hardware](#-models--hardware)
- [Configuration](#-configuration)
- [Project Structure](#-project-structure)
- [Documentation](#-documentation)
- [Testing](#-testing)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🧠 What Makes Cerebro Different

Most AI assistants are either **cloud-only** — your data leaves your machine — or **stateless chatbots** with no durable memory. Cerebro is neither.

| Cerebro | Cloud assistants | Local chatbots |
|---------|-----------------|----------------|
| ✅ Fully local (optional cloud) | ❌ Data leaves your machine | ✅ Fully local |
| ✅ Persistent vector memory | ❌ No long-term memory | ❌ Session-only |
| ✅ Agentic tool loop | ❌ No tool execution | ❌ No tools |
| ✅ Desktop UI + API | ✅ Polished UI | ❌ CLI only |
| ✅ Calendar, files, reminders | ❌ Limited integrations | ❌ None |
| ✅ Deterministic fast paths | ❌ LLM for everything | ❌ LLM for everything |

---

## ✨ Key Features

### 🤖 Local Agentic Runtimes
Four specialized agents — **General**, **Academic**, **Code**, and **Calendar** — each with tailored system prompts, tool sets, and memory retrieval strategies. Powered by a **LangGraph**-style execution graph that alternates between LLM reasoning and deterministic tool calls.

### 📚 Persistent Vector Memory
All your indexed documents, conversations, and notes are embedded into a local **LanceDB** vector store. Every query retrieves relevant chunks across sessions — the system remembers what you've asked and what you've written.

### 🛠️ Deterministic Fast Paths
Common queries skip the LLM entirely for speed and reliability:
- **Time/Date** — current time, date, timezone
- **Weather** — real-time forecast via wttr.in
- **Dictionary** — word definitions via free API
- **Unit Conversion** — length, weight, temperature, volume
- **System Info** — RAM, CPU, disk, uptime
- **Math** — arithmetic via AST evaluator (no eval)
- **Web Search** — with LLM-based query classifier
- **File Search** — local file content search
- **Calendar** — event lookup and scheduling
- **File Write** — file creation with content generation

These fast paths resolve queries in milliseconds, reserving the LLM only for complex reasoning.

### 📅 Calendar Integration
Read and write Apple Calendar events, search by keyword, expand recurring events (daily, weekly, monthly, yearly), and manage reminders — all via JXA/AppleScript bridges.

### 🔍 RAG Over Your Documents
Index PDFs, DOCX, Markdown, Python, and plain text files. The **SemanticCompressor** reduces context by ~70% while preserving relevance, using sentence-level TF-IDF scoring (or neural embeddings when available).

### 🔐 Privacy-First Design
- No data leaves your machine by default
- All inference runs locally via **llama.cpp** or **MLX**
- Tool execution requires user confirmation for risky operations
- Optional **Claude API** for cloud models when you need them

### 🖥️ Desktop UI (Tauri + React)
Polished chat interface with real-time token streaming, conversation history, settings panel, system status, model selector, and first-launch wizard.

### 🔌 REST API
Every feature is accessible via HTTP on port 7842 — build your own clients, automations, or integrations on top of Cerebro's agent runtime.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Desktop UI (Tauri)                    │
│            React 18 · TypeScript · Zustand              │
│       Chat · Settings · Status · Wizard · History       │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP :7842
┌──────────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                        │
│                                                         │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌────────┐ │
│  │   Fast   │  │  Agent   │  │   Tools   │  │Config  │ │
│  │  Paths   │  │ Runtime  │  │  Registry │  │Manager │ │
│  │ (10+)    │  │(LangGraph)│  │ (20+)    │  │        │ │
│  └─────────┘  └────┬─────┘  └───────────┘  └────────┘ │
│                    │                                    │
│  ┌─────────────────▼──────────────────────────────────┐ │
│  │              Memory & Knowledge Layer              │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │ │
│  │  │ Short-   │  │  Long-   │  │   Vector Store   │ │ │
│  │  │ Term     │  │  Term    │  │   (LanceDB)      │ │ │
│  │  └──────────┘  └──────────┘  └──────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────┐ │ │
│  │  │         Ingestion Pipeline                   │ │ │
│  │  │  PDF · DOCX · MD · TXT · PY → Chunks → Vec │ │ │
│  │  └──────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │          Provider Registry                       │  │
│  │  llama.cpp :8080  ·  MLX (Apple Silicon)        │  │
│  │  Claude API (optional)  ·  Embedding Engine      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        llama-server               Apple Calendar
        (GGUF models)              (JXA bridge)
```

### Request Flow

```
User Message → Fast Path Router → Context Assembly → LLM
                                                      │
          ┌──────────────────────────────────────────┘
          ▼
    Agent Runtime (LangGraph graph)
    ┌──────────────────────────────┐
    │  Reason Node → LLM decides   │
    │       ↓ (tool) / ↓ (answer)  │
    │  Tool Node → execute tool    │
    │       ↓                      │
    │  Observe Node → ingest result│
    │       ↓                      │
    │  Repeat until final answer   │
    └──────────────────────────────┘
          ↓
    Response + Metadata → UI
```

### Inference Abstraction

Cerebro decouples chat models from embedding models. The **ProviderRegistry** selects the optimal backend based on available RAM and task type:

```python
# Example: RAM-aware provider selection
> 1.0 GB free → llama.cpp primary (2B-4B params)
0.3–1.0 GB   → MLX fallback (Apple Silicon)
< 0.3 GB     → Emergency fallback (Claude API)
```

Embeddings default to **local sentence-transformers** (384d) on ≤10GB RAM, falling back to **llama.cpp embed server** on capable hardware.

---

## 🚀 Quick Start

### Prerequisites

- macOS (Apple Silicon or Intel)
- Python 3.11+
- Node.js 18+
- Rust toolchain (for Tauri)
- [llama.cpp](https://github.com/ggerganov/llama.cpp) (`brew install llama.cpp`)
- 8 GB+ RAM (16 GB recommended)

### Installation

```bash
# Clone and enter
git clone https://github.com/your-org/cerebro.git
cd cerebro

# Install Python deps + dev tools
make install

# Download a model (or place your own GGUF in bin/models/)
# See Models section below

# Start the inference engine
make engine          # llama-server on :8080

# In another terminal, start the backend
make run             # FastAPI on :7842

# In a third terminal, start the UI
cd ui/tray && npm run dev   # Vite dev server
```

### 8 GB Mac Profile

For machines with limited RAM, use the lite profile:

```bash
make lite        # Sets CEREBRO_PROACTIVE_CONTEXT=false,
                 # CEREBRO_MLX_ENABLED=false,
                 # CEREBRO_EMBEDDINGS_BACKEND=local
make run
```

### Production Desktop Build

```bash
cd ui/tray && npm run build   # Creates .dmg in src-tauri/target/release
```

---

## 📦 Models & Hardware

### Recommended Models

| Role | Model | Size | RAM Usage |
|------|-------|------|-----------|
| Chat (default) | Qwen3.5-2B-UD-Q4_K_XL | ~1.5 GB | ~2 GB |
| Chat (8 GB) | Qwen2.5-Coder-3B-Instruct-Q4_K_M | ~2 GB | ~2.5 GB |
| Chat (16 GB+) | Llama-3.2-3B-Instruct-Q4_K_M | ~2 GB | ~2.5 GB |
| Embeddings (local) | all-MiniLM-L6-v2 | ~90 MB | ~200 MB |
| Embeddings (llama.cpp) | v5-nano-retrieval-Q4_K_M | ~30 MB | ~150 MB |
| Router (optional) | SmolLM2-135M-Instruct-Q4_K_M | ~70 MB | ~100 MB |

### Download Models

**From Hugging Face:**
```bash
mkdir -p bin/models
curl -L -o bin/models/qwen3.5-2b-ud-q4_k_xl.gguf \
  "https://huggingface.co/owner/qwen3.5-2b-UD-Q4_K_XL.gguf/resolve/main/qwen3.5-2b-UD-Q4_K_XL.gguf"
```

**Or using huggingface_hub:**
```bash
pip install huggingface-hub
python -c "
from huggingface_hub import hf_hub_download
hf_hub_download(repo_id='owner/repo', filename='model.gguf',
                local_dir='bin/models')
"
```

### Environment Variables

Core configuration is done via env vars (all optional, sensible defaults):

```bash
export CEREBRO_LLAMACPP_MODEL="Qwen3.5-2B-UD-Q4_K_XL.gguf"
export CEREBRO_INFERENCE_BACKEND="llamacpp"    # llamacpp | mlx | claude
export CEREBRO_EMBEDDINGS_BACKEND="local"      # local | llamacpp
export CEREBRO_PORT=7842
export CEREBRO_DB="$HOME/.cerebro/db"
export CEREBRO_STATE="$HOME/.cerebro/state"
export ANTHROPIC_API_KEY=""                    # Required for Claude backend
```

See [config/profiles/lite-8gb.env](config/profiles/lite-8gb.env) for the full 8 GB Mac profile.

---

## 📁 Project Structure

```
cerebro/
├── main.py                         # Composition root — wires everything
├── core/                           # Python backend
│   ├── agents/                     # Agent runtimes, fast paths, state
│   │   ├── runtime.py              # LangGraph agent execution loop
│   │   ├── fast_path_router.py     # 10+ deterministic fast paths
│   │   ├── math_fast_path.py       # Pure arithmetic evaluator
│   │   ├── weather_fast_path.py    # Weather via wttr.in
│   │   ├── dictionary_fast_path.py # Word definitions
│   │   ├── unit_conversion_fast_path.py
│   │   ├── system_info_fast_path.py
│   │   ├── calendar_fast_path.py   # Calendar read fast path
│   │   ├── file_search_fast_path.py
│   │   ├── file_write_fast_path.py
│   │   └── ...
│   ├── memory/                     # Short-term, long-term, vector store
│   │   ├── context_builder.py      # Context assembly with compression
│   │   ├── vector_store.py         # LanceDB wrapper
│   │   └── ...
│   ├── inference/                  # Providers, registry, engines
│   │   ├── providers/              # llama.cpp, MLX, Claude
│   │   ├── registry.py             # Provider selection by RAM
│   │   └── ...
│   ├── rag/                        # RAG query engine
│   │   └── query_engine.py
│   ├── knowledge_sync/             # RSS, arXiv, YouTube, PubMed sync
│   │   ├── orchestrator.py
│   │   ├── content_filter.py       # Dedup + relevance + SLM novelty
│   │   └── sources/                # 6 source types
│   ├── tools/                      # Tool registry + handlers
│   │   └── handlers/               # calendar.py, filesystem.py, math.py, web.py
│   ├── ingestion/                  # PDF, DOCX, MD, TXT, PY parser
│   └── utils/                      # Semantic compressor, etc.
├── integrations/
│   └── calendar_reader.py          # Apple Calendar JXA/AppleScript bridge
├── scheduler/
│   └── proactive.py                # Background cron scheduler
├── config/                         # Settings TOML, engine profiles
├── ui/tray/                        # React + Tauri desktop app
├── tests/                          # Pytest (mocked inference)
└── docs/                           # Full documentation tree
    ├── architecture/               # System design, fast paths, memory
    ├── plans/                      # Roadmaps, features, optimization
    ├── guides/                     # How-to, quickstarts
    ├── testing/                    # Test reports, QA sessions
    └── reference/                  # Benchmarks, changelogs
```

---

## 📖 Documentation

| Area | What You'll Find |
|------|-----------------|
| [docs/README.md](docs/README.md) | Complete documentation index |
| [docs/architecture/](docs/architecture/) | System design, fast paths, memory, evolution plans |
| [docs/guides/](docs/guides/) | How to run, 8 GB quickstart, merge/sync guides |
| [docs/plans/](docs/plans/) | Feature roadmaps, stabilization, optimization, future vision |
| [docs/testing/](docs/testing/) | Test reports, manual QA, E2E sessions |
| [docs/reference/](docs/reference/) | Benchmarks, comparisons, changelogs, issues ledger |
| [AGENTS.md](AGENTS.md) | Developer reference for AI-assisted coding |

### Key Documents

- **[Architecture Overview](docs/architecture/program-overview.md)** — Deep dive into system design
- **[Fast Paths](docs/architecture/fast-paths.md)** — Complete reference for deterministic query routing
- **[Knowledge Sync](docs/guides/knowledge-sync.md)** — How to set up content sources
- **[8 GB Mac Quickstart](docs/guides/8gb-mac-quickstart.md)** — Optimized for limited RAM
- **[Current State](docs/project/current-state.md)** — What's implemented vs planned

---

## 🧪 Testing

```bash
make test            # Full pytest suite (mocked inference)
make test-stable     # Fast path regression suite
make lint            # black --check + ruff check + mypy core/
```

All tests mock inference backends — no live llama.cpp/MLX/Claude required.
CI runs on every PR.

**Test coverage:** `tests/test_knowledge_sync.py` (13) · `tests/test_memory.py` (7) · `tests/test_rag.py` (6) · `tests/test_fast_path_router.py` (6) · `tests/test_fast_paths_new.py` (21+) · `tests/test_calendar_*.py` (40+) · `tests/test_api.py` (14+) · + more.

---

## 🗺️ Roadmap

### Implemented

- ✅ Local LLM inference (llama.cpp, MLX, Claude API)
- ✅ Document ingestion and vector indexing (LanceDB)
- ✅ RAG query engine with semantic compression
- ✅ Agent runtime with LangGraph orchestration
- ✅ 10+ deterministic fast paths (math, weather, dictionary, etc.)
- ✅ Calendar integration (read, write, recurring events)
- ✅ Knowledge sync (RSS, arXiv, YouTube, PubMed, GitHub, Web)
- ✅ File watcher and automatic re-indexing
- ✅ Conversational memory (short-term + long-term)
- ✅ Tool execution with user confirmation
- ✅ Proactive scheduler with cron support
- ✅ Desktop UI (Tauri + React)
- ✅ Fleet orchestrator (model swapping by task)
- ✅ Inference engine suspender (SIGSTOP on idle)

### In Progress

- 📝 Calendar recurring event expansion for all frequencies
- 📝 Semantic compressor wired into production context assembly

### Planned

- 🔮 **Cognitive Graph** — Persistent property graph (Kuzu) for entities and relationships
- 🔮 **Event-Driven Architecture** — EventBus for proactive system behavior
- 🔮 **LoRA Fine-Tuning** — Tool-calling accuracy improvement via Qwen3.5-2B LoRA
- 🔮 **0.8B Secondary Worker** — Small model for fast routing and simple queries
- 🔮 **Ambient Intelligence** — macOS context observers (active app, window title)
- 🔮 **Skill Marketplace** — Pluggable capabilities with SKILL.toml manifests
- 🔮 **Cross-Platform** — Linux and Windows desktop builds

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Areas we especially need help with:**
- Windows port (ambient observers, calendar bridge)
- Additional inference providers (Ollama, vLLM)
- Frontend polish (accessibility, dark mode refinement)
- Test coverage for edge cases

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Built on the shoulders of [llama.cpp](https://github.com/ggerganov/llama.cpp), [FastAPI](https://fastapi.tiangolo.com/), [LanceDB](https://lancedb.github.io/), [LangGraph](https://github.com/langchain-ai/langgraph), and [Tauri](https://tauri.app/)
- Inspired by Obsidian's knowledge graph philosophy
- Optimized for Apple Silicon via [MLX](https://github.com/ml-explore/mlx)

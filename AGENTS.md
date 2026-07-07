# Cerebro (SecondBrain) — Agent guide

Local-first personal assistant. **Python backend (FastAPI) + React/Tauri frontend** on port 7842. 8GB M1 Mac.

## Commands (always from repo root, via `.venv`)

**How to run (human):** [`docs/guides/howToRun.md`](docs/guides/howToRun.md) · [`docs/guides/running-es.md`](docs/guides/running-es.md)

```bash
make install          # venv + ".[dev]" + pre-commit
make desktop-config   # first time — ~/.cerebro/desktop.json
make run              # FastAPI :7842 (motor off by default)
make dev-full         # backend + auto-start motor (legacy)
make engine           # llama-server :8080 only
make test             # pytest tests/ --cov=core --cov-fail-under=80
make test-stable      # fast-path regression suite
make lint             # black + ruff + mypy
cd ui/tray && npm run tauri:dev   # Tauri UI — Start engine in header for LLM
cd ui/tray && npm run build       # production desktop build
```

## File content generation (`core/agents/file_content_generator.py`)

When the user asks to create a file with a description (not literal content), the
fast path calls `generate_file_content()`. It has two layers:

1. **Heuristic fallback** (regex patterns) — instant, covers common patterns like
   names, recipes, games. Only for **speed** — adds no correctness.
2. **LLM call** — if no fallback matches, calls the chat provider with **no
   artificial timeout**. The provider's own HTTP timeout (60s llamacpp) is the
   only bound. This guarantees any content type works.

Do NOT add timeouts here. See `docs/records/content_generator_design.md`.

## Architecture

**Entry point**: `main.py:_build_app_state()` wires everything → `app_state` singleton → `uvicorn.run(app, host="0.0.0.0", port=PORT)`. `load_dotenv()` runs before all other imports — env vars are visible to all modules on first import.

**Backend lives in `core/`** — this is the single source of truth. The old `cerebro/` copy was deleted. See `docs/architecture/UNIFICACION_CEREBRO.md`.

## Active plan

Execution backlog: [`docs/plans/CURRENT_FOCUS.md`](docs/plans/CURRENT_FOCUS.md). Ambitious plans archived in [`docs/plans/maybe-later/`](docs/plans/maybe-later/).

## Low Power mode — frozen (maybe later)

Low Power (Qwen2.5-0.5B) is **disabled** in production builds. Normal mode (Qwen3.5-2B) is the focus until v0.2. Design doc: [`docs/plans/maybe-later/LOW_POWER_V2_NANO_MODE.md`](docs/plans/maybe-later/LOW_POWER_V2_NANO_MODE.md).

---

## Documentation structure (`docs/`)

```
docs/
├── README.md               ← índice general
├── architecture/           ← diseño del sistema, fast paths, memoria, unificación
├── connection/             ← guía de API REST y progreso de integración
├── frontend/               ← diseño UI, roadmap, redesign (cybernetic), changelog
├── guides/                 ← cómo ejecutar, quickstart 8GB, ports, merge, sync
├── implementation/         ← notas de implementación (RAG híbrido, injector local)
├── incidents/              ← post-mortems de bugs (calendario, llamacpp)
├── inference/              ← backends de inferencia (llama.cpp, MLX, RAM)
├── plans/                  ← plano (sin subdirectorios): features, roadmaps,
│                            estabilización, optimización, visión futura
├── project/                ← specs v1.0/v1.1, estado actual, inspiración Obsidian
├── records/                ← ADRs y decisiones técnicas (semantic compressor)
├── reference/              ← benchmarks, comparativas, issues ledger, changelogs
└── testing/                ← reportes de test, sesiones manuales QA, E2E, smoke
```

**Fast-path pipeline** (runs before LLM, in order): math → file write (+ calendar-to-file fusion) → reminder → calendar → file search → LangGraph graph. Reordering these in `core/agents/runtime.py` breaks stable features. Run `make test-stable` after any change to fast-path order or file/calendar modules.

**Inference backends** (env `CEREBRO_INFERENCE_BACKEND`): `llamacpp` (default, HTTP to :8080), `mlx` (in-process Apple Silicon), `claude` (Anthropic API, requires `ANTHROPIC_API_KEY`). `ProviderRegistry` auto-selects by free RAM (primary ≥1GB, fallback ≥0.3GB).

**Embeddings**: auto-selects `local` (sentence-transformers, 384d) on ≤10GB RAM, `llamacpp` otherwise. Override via `CEREBRO_EMBEDDINGS_BACKEND`.

**Runtime config precedence**: env vars > `config/settings.toml` > `~/.cerebro/state/config.json` (exposed at `/api/config`). `config/profiles/lite-8gb.env` has M1-friendly overrides (`make lite`).

**`config/chat.args` is rewritten** by `main.py` at startup to match `CEREBRO_LLAMACPP_MODEL` — if stale, it restarts the engine automatically (when `CEREBRO_AUTO_START_ENGINE=true`).

**Engine/backend split (✅ Fases 0–5):** App desktop arranca solo backend; **Start engine** / **Stop engine** en UI. API: `/api/engine/*`. Legacy: `make dev-full`. Ver [`docs/plans/engine-backend-split.md`](docs/plans/engine-backend-split.md).

## Testing quirks
- All tests **mock inference backends** — no live llama.cpp/MLX/Claude. Shared fixtures: `mock_provider`, `mock_registry`, `tmp_app_state` in `tests/conftest.py`.
- `asyncio_mode = auto` in `pyproject.toml`.
- Calendar tests patch `platform.system()` → `"Linux"` to avoid AppleScript.
- `tests/fixtures/stable_fast_path_prompts.yaml` contains canned LLM responses for deterministic fast-path tests.
- Ruff ignores `E501` (long lines) — Black handles wrapping at 100ch.
- Mypy runs only on `core/`, `warn_return_any=true`, `strict=false`.

## Code style
- Black: 100ch, py3.11
- Ruff: E,F,I,UP
- Pre-commit: black → ruff --fix → mypy (on `core/`, skip `cerebro/`)
- Frontend: React 18, TypeScript strict, Zustand stores, Tauri

## REST API (`ui/tray/server.py`)
All routes under `/api`. Key endpoints:
- `POST /api/query` — sync; `POST /api/query/stream` — SSE (`{token}` → `{metadata}` → `[DONE]`)
- `POST /api/tool-confirm` — approve/deny pending tool (sent via `metadata.pending_tool`)
- `POST /api/index` / `GET /api/index/status` — async file indexing
- `GET /api/status` — RAM, latency, model, provider
- `GET /api/config` / `PATCH /api/config` — persistent runtime config
- `GET /api/engine/status` — motor: desired, running, model, embed
- `POST /api/engine/start` / `POST /api/engine/stop` — control del llama-server

## Tools requiring confirmation
`write_file`, `execute_python`, `delete_file`, `run_script`, `create_calendar_event`, `add_reminder`, `delete_reminder` — agent pauses, frontend shows `ConfirmModal`.

## Key env vars
| Var | Default | Notes |
|-----|---------|-------|
| `CEREBRO_PORT` | 7842 | |
| `CEREBRO_INFERENCE_BACKEND` | llamacpp | llamacpp/mlx/claude |
| `CEREBRO_LLAMACPP_URL` | http://127.0.0.1:8080 | |
| `CEREBRO_LLAMACPP_SIMPLE` | true | false = ModelManager multi-server |
| `CEREBRO_LLAMACPP_MODEL` | Qwen3.5-2B-UD-Q4_K_XL.gguf | Default chat model (Low Power frozen — see `docs/plans/maybe-later/LOW_POWER_V2_NANO_MODE.md`) |
| `CEREBRO_LOW_POWER_ENABLED` | *(unset)* | Set `true` to enable Low Power profile in dev builds only |
| `CEREBRO_MLX_MODEL` | mlx-community/Qwen3.5-2B-MLX-4bit | MLX HF repo (used when MLX is enabled) |
| `CEREBRO_MLX_ENABLED` | auto | auto=true on Apple Silicon with mlx installed |
| `CEREBRO_DB` | ~/.cerebro/db | |
| `CEREBRO_STATE` | ~/.cerebro/state | |
| `CEREBRO_FILES_PATH` | ~/Desktop/CerebroFiles | default write root |
| `CEREBRO_PROACTIVE_CONTEXT` | true | ContextEnricher on every query |
| `CEREBRO_SKIP_LITE_PROMPT` | — | set to any value to skip the lite-8gb prompt at startup |
| `CEREBRO_AUTO_START_ENGINE` | false | If `true`, `main.py` spawns `:8080` on boot (`make dev-full`) |
| `ANTHROPIC_API_KEY` | — | required for claude backend |

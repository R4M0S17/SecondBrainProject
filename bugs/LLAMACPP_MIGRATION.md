# llama.cpp Migration Plan

Replace every Ollama reference in the project with llama.cpp equivalents.
Primary engine: llama.cpp. Secondary engine: MLX (Apple Silicon, auto-detected).
Ollama is fully removed from the stack.

Tick each checkbox when the step is complete and all related tests pass.

---

## Module A — Core Inference (DONE)

- [x] `main.py` — default backend changed from `"ollama"` to `"llamacpp"`
- [x] `main.py` — simple mode now uses `LlamaCppEmbeddingProvider` for embeddings (was `OllamaEmbeddingProvider`, silent bug)
- [x] `main.py` — MLX registered as secondary provider in both simple and model-swapping modes
- [x] `main.py` — `else` branch replaced: no longer starts Ollama; raises `RuntimeError` if no backend available
- [x] `main.py` — removed all `OllamaEmbeddingProvider` / `OllamaChatProvider` imports
- [x] `config/settings.toml` — `[providers]` and `[inference]` sections updated to llama.cpp URLs and GGUF model names
- [x] `.env` — `CEREBRO_LLAMACPP_EMBED_URL` added explicitly
- [x] `core/inference/providers/mlx_provider.py` — `MlxEmbeddingProviderStub` docstring and error message updated to reference llama.cpp

---

## Module B — Backend Status & Health API (DONE)

File: `ui/tray/server.py`

- [x] Remove the `_OLLAMA_BASE` module-level variable (line 861)
- [x] Replace `_ollama_running()` with `_llamacpp_running()` — check `GET /health` on `CEREBRO_LLAMACPP_URL` instead of Ollama's `/api/tags`
- [x] Rename `ollama_ok: bool` to `engine_ok: bool` in the status response Pydantic model (line 146)
- [x] Update the status endpoint that builds the response: replace `ollama_ok=engine_ok` with `engine_ok=engine_ok` (line 706)
- [x] Replace the two error strings "Start Ollama and reload." with "Start the llama.cpp server and reload." (lines 321, 412)
- [x] Remove `provider_name = "ollama"` hardcode — derive the provider name from `registry.primary_name` instead (lines 337, 427, 573)
- [x] `WizardStatusResponse`: renamed `ollama_running` → `engine_running`; updated wizard status/check/models endpoints to use llama.cpp (coupled cleanup required by `_OLLAMA_BASE` removal)

---

## Module C — Backend Models & Config API

File: `ui/tray/server.py`

- [x] Replace the `/api/models` endpoint (line 812): instead of querying Ollama's `/api/tags`, list GGUF files from `bin/models/` directory and return them with `provider: "llamacpp"`
- [x] Remove the `_OLLAMA_BASE` reference from the models endpoint (line 815)
- [x] Fix `/api/config` PATCH model-switching logic (lines 781–787): replace `target = "ollama"` with `target = "llamacpp"`; call `registry.get_chat("llamacpp").set_model(model_name)` instead of the Ollama variant
- [x] Remove the `OllamaModel` interface reference from the response — update to `LlamaCppModel` naming

---

## Module D — Backend Wizard

Files: `ui/tray/wizard.py`, `ui/tray/wizard_router.py`

### wizard.py

- [x] Remove `WizardStep.OLLAMA` — replace with `WizardStep.LLAMACPP`
- [x] Update `current_step()` — first step is now checking for llama.cpp server, not Ollama daemon
- [x] Remove `check_ollama()` — replace with `check_llamacpp()` that hits `GET /health` on `CEREBRO_LLAMACPP_URL`
- [x] Remove `_pull_model()` and `pull_all_models()` — llama.cpp uses pre-downloaded GGUF files; replace with `check_models()` that verifies required GGUF files exist in `bin/models/`
- [x] Update the module docstring (lines 1–5) to describe llama.cpp steps instead of Ollama steps

### wizard_router.py

- [x] Replace `POST /wizard/check-ollama` endpoint with `POST /wizard/check-llamacpp` — calls `check_llamacpp()`
- [x] Replace `POST /wizard/pull-models` endpoint with `POST /wizard/check-models` — calls `check_models()` to verify GGUF files exist (no download, files are placed manually in `bin/models/`)
- [x] Update wizard status endpoint: `ollama_running` field → `engine_running`

---

## Module E — Frontend Types & API Client

Files: `ui/tray/src/api/types.ts`, `ui/tray/src/api/client.ts`

### types.ts

- [x] Rename `ollama_ok: boolean` → `engine_ok: boolean` in the `SystemStatus` interface (line 90)
- [x] Rename `ollama_running: boolean` → `engine_running: boolean` in the wizard status interface (line 106)
- [x] Rename `OllamaModel` interface → `LocalModel` (line 124)
- [x] Update `provider` field type: `"ollama" | "mlx"` → `"llamacpp" | "mlx"` (line 127)

### client.ts

- [x] Update any function that calls `/wizard/check-ollama` → `/wizard/check-llamacpp`
- [x] Update any function that calls `/wizard/pull-models` → `/wizard/check-models`
- [x] Update any field access on status response that reads `ollama_ok` → `engine_ok`

---

## Module F — Frontend Status Bar

Files: `ui/tray/src/components/status/EngineIndicator.tsx`, `ui/tray/src/components/status/StatusBar.tsx`, `ui/tray/src/stores/system.ts`

### EngineIndicator.tsx

- [x] Rename file to `EngineIndicator.tsx`
- [x] Rename component from `OllamaIndicator` to `EngineIndicator`
- [x] Update the indicator label/icon to say "llama.cpp" instead of "Ollama"
- [x] Update the field it reads: `ollama_ok` → `engine_ok`

### StatusBar.tsx

- [x] Update import: `OllamaIndicator` → `EngineIndicator`
- [x] Update usage in JSX

### stores/system.ts

- [x] Update any state field or selector that reads `ollama_ok` → `engine_ok`

---

## Module G — Frontend Wizard

Files: `ui/tray/src/components/wizard/StepLlamaCpp.tsx`, `ui/tray/src/components/wizard/WizardShell.tsx`, `ui/tray/src/components/wizard/StepModel.tsx`, `ui/tray/src/stores/wizard.ts`

### StepLlamaCpp.tsx

- [x] Rename file to `StepLlamaCpp.tsx`
- [x] Rename component to `StepLlamaCpp`
- [x] Replace the UI: instead of instructing the user to install/start Ollama, instruct them to start the llama.cpp server with `make engine`
- [x] Replace the action button: instead of "Check Ollama", call `POST /wizard/check-llamacpp`
- [x] Remove the model-pull step UI (no more `ollama pull`) — replace with model verification (checking GGUF files exist)

### WizardShell.tsx

- [x] Replace import `StepOllama` → `StepLlamaCpp`
- [x] Update the step routing to render `StepLlamaCpp` for the first wizard step

### StepModel.tsx

- [x] Update model list source: models now come from `GET /api/llama-cpp/models` (GGUF files) instead of Ollama model list

### stores/wizard.ts

- [x] Replace any `ollama` step name → `llamacpp` in wizard state machine (store used only numeric steps — no string step names to rename)
- [x] Update API calls that referenced Ollama check/pull endpoints

---

## Module H — Tests

Files: `tests/test_providers.py`, `tests/test_api.py`, `tests/test_llamacpp_provider.py`, `tests/test_packaging.py`

### test_providers.py

- [x] Remove `OllamaChatProvider` / `OllamaEmbeddingProvider` imports (line 6)
- [x] Replace `_make_chat_provider()` and `_make_embed_provider()` helpers with `LlamaCppChatProvider` / `LlamaCppEmbeddingProvider` equivalents
- [x] Update all registry tests that register `"ollama"` → register `"llamacpp"` instead
- [x] Rename `test_is_available_returns_false_when_ollama_down` → `test_is_available_returns_false_when_llamacpp_down`
- [x] Update `test_get_embedding_provider_falls_back_to_ollama_when_no_model_manager` — rename and switch to llamacpp embed

### test_api.py

- [x] Update `test_status_reports_ollama_unavailable_when_no_registry` — rename and update field from `ollama_ok` → `engine_ok` (lines 91–94)
- [x] Update `test_config_model_change_switches_ollama_provider` (line 241) — replace `OllamaChatProvider` fixture with `LlamaCppChatProvider`, update registry key from `"ollama"` → `"llamacpp"`
- [x] Update the streaming model-switch test (line 356) — same replacement as above
- [x] Update `test_status` field assertion: `"ollama_ok"` → `"engine_ok"` (line 81)

### test_llamacpp_provider.py

- [x] Rename `test_registry_llamacpp_primary_ollama_fallback` (line 207) — replace Ollama fallback with MLX fallback or just remove the fallback from the test
- [x] Remove `OllamaChatProvider` / `OllamaEmbeddingProvider` imports (line 209)
- [x] Update registry setup to use `LlamaCppEmbeddingProvider` instead of `OllamaEmbeddingProvider`

### test_packaging.py

- [x] Replace `WizardStep.OLLAMA` references → `WizardStep.LLAMACPP` (lines 79–80, 256, 259)
- [x] Rename `TestCheckOllama` → `TestCheckLlamaCpp`
- [x] Replace `check_ollama()` calls → `check_llamacpp()` (lines 92–107)
- [x] Replace `pull_model` / `pull_all_models` import and tests with `check_models` (lines 5, 120, 152–153)
- [x] Update wizard step endpoint tests: `/wizard/step/ollama` → `/wizard/step/llamacpp` (lines 272, 279)

---

## Module I — Final Cleanup (DONE)

- [x] `core/inference/providers/ollama_provider.py` — delete file (no longer imported anywhere after all above steps are done; verify with `grep -r "ollama_provider" .` returning zero results)
- [x] `core/inference/engine.py` — rename `OllamaUnavailableError` → `LlamaCppUnavailableError`; update `InferenceEngine` class which is Ollama-specific (consider removing or repurposing)
- [x] `CLAUDE.md` — remove the "Pending Ollama migration" section and update the Testing line
- [x] `docs/guides/running-es.md` — verify no Ollama setup instructions remain
- [x] `docs/guides/howToRun.md` — English runbook (replaces stray `HowToRunIt.md` fragment)
- [x] Run `grep -rn "ollama\|Ollama\|OLLAMA" . --include="*.py" --include="*.ts" --include="*.tsx" --include="*.toml" --include="*.md"` — result is zero (excluding this migration doc and docs/ history files)

---

## Verification after all modules complete

- [x] `make test` — 377 passed, 1 pre-existing failure (test_args_files_contain_prompt_cache — unrelated to Ollama migration)
- [ ] `make lint` — black pre-existing across 61 files (not caused by migration); ruff/mypy clean on changed files
- [ ] Start `make engine` (llama.cpp on port 8080) then `make run` — status bar shows engine as online
- [ ] Open the app fresh (delete `~/.cerebro/wizard_complete` sentinel) — wizard walks through llama.cpp setup, not Ollama
- [ ] Send a query — response arrives from llama.cpp, not Ollama

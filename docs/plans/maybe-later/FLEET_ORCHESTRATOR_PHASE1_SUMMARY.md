> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


# Fleet Orchestrator Phase 1 — Implementation Summary

**Date Completed:** 2026-05-12  
**Status:** ✅ Complete and tested

---

## Overview

Phase 1 of the Local Model Fleet Orchestrator has been successfully implemented. This subsystem intelligently selects the best local model and quantization level at application startup based on available hardware (RAM, VRAM, CPU) and task complexity.

**Key achievement:** Never run out of memory — Cerebro automatically picks the right model for the available hardware.

---

## Files Created

### Fleet Module (`core/inference/fleet/`)

| File | Lines | Purpose |
|---|---|---|
| `__init__.py` | 0 | Module marker |
| `hardware_monitor.py` | 70 | Hardware snapshot (RAM, VRAM, CPU, GPU backend detection) |
| `model_registry.py` | 90 | Load/parse `~/.cerebro/models.toml` with ModelConfig dataclass |
| `task_classifier.py` | 110 | Classify task complexity (TRIVIAL→MAXIMUM) via keyword heuristics |
| `orchestrator.py` | 130 | Core selection logic: `FleetOrchestrator.select_on_startup()` |
| `script_writer.py` | 45 | Generate llama-server and MLX launch commands |

### Test Files (`tests/`)

| File | Tests | Coverage |
|---|---|---|
| `test_fleet_hardware_monitor.py` | 5 | Apple Silicon, NVIDIA, CPU-only, graceful fallback |
| `test_fleet_model_registry.py` | 6 | TOML parsing, missing files, invalid TOML, defaults |
| `test_fleet_orchestrator.py` | 10 | RAM filtering, capability filtering, critical RAM, HEAVY task selection |
| `test_fleet_script_writer.py` | 6 | Command generation for llama-server and MLX |

**Total: 26 new tests, all passing**

---

## Files Modified

### `main.py`
- Added `FleetOrchestrator` initialization before `ProviderRegistry` setup
- Logs selected model and rationale
- Gracefully falls back if no models found

### `ui/tray/server.py`
- Added `fleet_orchestrator` field to `AppState`
- Extended `StatusResponse` with 5 new fields:
  - `current_model_id`, `current_model_quant`, `current_model_params_b`
  - `hardware_snapshot` (dict with RAM, VRAM, GPU backend, unified memory)
  - `selection_rationale` (why this model was chosen)
- Extended `/api/status` endpoint to populate fleet data

---

## Configuration

### `~/.cerebro/models.toml`
Default template created at startup with 4 reference models:
- `qwen2.5-7b-q4` — 7B parameters, Q4 quantization (5.5GB RAM)
- `qwen2.5-7b-q8` — 7B parameters, Q8 quantization (9GB RAM)
- `qwen2.5-32b-q4` — 32B parameters, Q4 quantization (22GB RAM)
- `smollm2-360m-q8` — 360M parameters, Q8 quantization (0.8GB RAM)

Users can edit this file to add/remove models or point to their own quantizations.

---

## Selection Algorithm

Given task complexity and available hardware:

1. **Filter by RAM/VRAM** — 15% safety margin, exclude models that won't fit
2. **Filter by capabilities** — Only consider models with required features (chat, code, reasoning, analysis)
3. **Pick largest** — Among eligible, choose highest params_b
4. **Prefer higher quant for HEAVY tasks** — If HEAVY/MAXIMUM and memory allows, prefer Q8 over Q4 of same size
5. **Critical RAM override** — If <20% free RAM, force smallest eligible model + CPU-only (gpu_layers=0)

### Decision Tree Examples

```
32GB RAM + HEAVY task → qwen2.5-32b-q4 (prefer Q8 if available)
8GB RAM + MEDIUM task → qwen2.5-7b-q4 with GPU offload
4GB RAM + LIGHT task → qwen2.5-7b-q4 with partial GPU offload
<1GB RAM + any task → smollm2-360m-q8 (CPU-only)
```

---

## Hardware Detection

**Apple Silicon (M1/M2/M3):**
- GPU backend: `"metal"`
- Unified memory: `True` (GPU RAM = system RAM)
- Detection: `platform.processor()` returns "arm64"

**NVIDIA GPUs:**
- GPU backend: `"cuda"`
- VRAM detection: `nvidia-smi --query-gpu=memory.total,memory.free`
- Graceful fallback if `nvidia-smi` not found

**CPU-only:**
- GPU backend: `"none"`
- Falls back cleanly if no GPU detected

---

## Test Results

```
✓ test_fleet_hardware_monitor.py       5/5 tests passing
✓ test_fleet_model_registry.py        6/6 tests passing
✓ test_fleet_orchestrator.py          10/10 tests passing
✓ test_fleet_script_writer.py         6/6 tests passing

Total: 26 new tests, 0 failures
Existing tests: 26/26 API tests still passing (no regressions)
```

---

## API Changes

### GET `/api/status` response now includes:

```json
{
  "current_model_id": "qwen2.5-7b-q4",
  "current_model_quant": "Q4_K_M",
  "current_model_params_b": 7.0,
  "selection_rationale": "Selected qwen2.5-7b-q4 (7.0B, Q4_K_M) for medium task",
  "hardware_snapshot": {
    "ram_total_gb": 16.0,
    "ram_available_gb": 12.5,
    "cpu_count": 8,
    "cpu_percent": 45.2,
    "gpu_backend": "metal",
    "gpu_vram_total_gb": 16.0,
    "gpu_vram_available_gb": 12.5,
    "unified_memory": true
  }
}
```

---

## What Phase 1 Does NOT Include

These are reserved for Phase 2 (mid-request swapping):
- ❌ Hot-swap between requests
- ❌ Per-request task classification
- ❌ Automatic model downloads
- ❌ Multi-model parallel inference
- ❌ Fine-tuning or quantization

---

## Dependencies

**New package added:**
- `psutil >=5.9` — already in requirements, for RAM/CPU monitoring

**Stdlib (no new packages):**
- `tomllib` (Python 3.11+) — TOML parsing
- `platform` — processor detection
- `subprocess` — nvidia-smi

---

## Next Steps (Phase 2)

When ready to implement mid-request swapping:
1. Add `ProcessManager` for llama-server lifecycle (kill/restart/health-check)
2. Integrate `TaskClassifier` into pipeline stage "intent"
3. Add `FleetOrchestrator.maybe_swap(task_profile)` with latency tracking
4. Wire SSE notifications to UI during swap
5. UI indicator showing current model + swap reason

---

## Usage

**For users:**
1. Edit `~/.cerebro/models.toml` to add your GGUF models
2. Update `path`, `params_b`, `ram_required_gb`, `capabilities` for each model
3. On startup, Cerebro logs which model was selected
4. Check `/api/status` to see selection rationale and hardware state

**For developers:**
```python
from core.inference.fleet.orchestrator import FleetOrchestrator

fleet = FleetOrchestrator()
selection = fleet.select_on_startup()
if selection:
    print(f"Selected: {selection.model.id}")
    print(f"Rationale: {selection.rationale}")
```

---

## Testing Notes

All tests use:
- Unit tests for individual components (hardware, registry, task classifier)
- Integration tests for orchestrator selection logic
- Mocking of subprocess calls (nvidia-smi) for portability
- Real `psutil` calls in tests (not mocked) to catch regressions

Run all fleet tests:
```bash
.venv/bin/python -m pytest tests/test_fleet_*.py -v
```

---

## Files Ready for Review

- ✅ `core/inference/fleet/*` — All modules with docstrings
- ✅ `tests/test_fleet_*.py` — 26 comprehensive tests
- ✅ `main.py` — Integration point
- ✅ `ui/tray/server.py` — Status endpoint extension
- ✅ `~/.cerebro/models.toml` — User config template

---

## Verification Checklist

- [x] All 26 fleet tests passing
- [x] No regressions in existing 26 API tests
- [x] Hardware detection works on Apple Silicon
- [x] NVIDIA detection gracefully falls back
- [x] CPU-only mode tested
- [x] TOML parsing handles missing files
- [x] Selection respects RAM/VRAM constraints
- [x] Capability filtering works
- [x] Critical RAM logic forces smallest model
- [x] HEAVY task prefers Q8 over Q4
- [x] `/api/status` returns fleet fields
- [x] Graceful fallback if no models in registry
- [x] `main.py` imports work
- [x] `server.py` imports work
- [x] Models.toml template created

---

## Architecture Notes

Fleet Orchestrator **wraps around** the existing `ProviderRegistry`:
```
main.py startup:
  → FleetOrchestrator.select_on_startup()  [Phase 1: startup only]
  → Stores selection in app_state.fleet_orchestrator
  → ProviderRegistry initialized normally
  → No changes to existing provider registry logic
```

This keeps Phase 1 minimal and non-invasive. Phase 2 will integrate task classification into the request pipeline, enabling mid-request swapping.

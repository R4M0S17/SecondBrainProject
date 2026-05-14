# Model Efficiency Testing — Execution Guide
**Date:** May 12, 2026
**Status:** ✅ Testing infrastructure ready

---

## Overview

This guide walks through executing the complete model efficiency testing cycle, comparing Qwen-3-4B (current) vs Llama-3.2-3B (proposed) inference models.

**Total time:** ~3 hours (mostly model download)
**Risk level:** LOW (no code changes, fully reversible)

---

## Prerequisites

### System Requirements
- ✅ 4GB+ available disk space (for model storage)
- ✅ 8GB+ RAM (for inference)
- ✅ Internet connection (for model download)
- ✅ Existing Qwen model in `bin/models/`

### Files Created
```
tests/test_model_efficiency.py          # Benchmark test suite (11 tests)
scripts/download_model.py               # Model download script
docs/testing/MODEL_EFFICIENCY_PLAN.md   # Detailed testing plan
docs/testing/EXECUTION_GUIDE.md         # This file
docs/testing/QUICK_START.md             # Quick reference
bin/models/                             # Models directory (auto-created)
```

### Test Status
```
✅ 11/11 tests passing (test infrastructure verified)
✅ Configuration switching tested
✅ Success criteria validation framework ready
✅ Rollback plan in place
```

---

## Phase 1: Baseline Testing (Qwen Model)

### 1.1 Prepare Environment
```bash
# Navigate to project directory
cd /Users/mb/Desktop/Javier/SecondBrain

# Ensure venv is set up
make install          # Creates venv if needed

# Verify current configuration
cat config/settings.toml | grep "model ="
# Expected: model = "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
```

### 1.2 Start Inference Engine
```bash
# Terminal 1: Start llama.cpp server
make engine

# Expected output:
# [main] ggml_metal_init: ggml_metal_init: allocating...
# [main] compute_imatrix: tokenizing the input...
# Loading model...
# main: loaded model in X seconds
# main: listening on http://127.0.0.1:8080
```

**Note:** Keep this terminal open for all testing.

### 1.3 Run Baseline Tests
```bash
# Terminal 2: Run test suite
pytest tests/test_model_efficiency.py -v

# Expected: 11 passed in <1 second
```

### 1.4 Record Baseline Metrics

Create `BASELINE_RESULTS.txt`:
```
BASELINE TESTING RESULTS (Qwen Model)
=====================================
Date: 2026-05-12
Model: Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf

Test Results:
✅ test_embedding_cache_latency_baseline PASSED
✅ test_cache_hit_rate_consistency PASSED
✅ test_model_availability_qwen PASSED
✅ test_success_criteria_latency_target PASSED
✅ test_success_criteria_memory_efficiency PASSED
✅ test_success_criteria_quality_preservation PASSED
✅ test_fallback_model_configuration PASSED
✅ test_qwen_model_revert PASSED
✅ test_configuration_persistence PASSED

Result: 11/11 PASSED ✅

Benchmark Metrics (from test output):
- Avg latency: [record from test output]
- P95 latency: [record from test output]
- Cache operations: [record measurements]
- Memory usage: [monitor with `top` during test]

System Status:
- Engine running at: http://127.0.0.1:8080
- Model loaded: ✅
- All tests passing: ✅
```

---

## Phase 2: Model Download

### 2.1 Download Llama-3.2-3B Model
```bash
# Terminal 2: Run download script
python scripts/download_model.py llama

# Expected output:
# === Cerebro Model Efficiency Testing ===
# Available models:
# 1. Llama-3.2-3B-Instruct-Q4_K_M (NEW - for efficiency testing)
# 2. Qwen-3-4B (CURRENT - baseline)
#
# Downloading Llama-3.2-3B model...
# Downloading llama-3.2-3b-instruct-q4_k_m.gguf...
# [=====>          ] 35% | 1.2GB / 2.3GB
# [==========>     ] 65% | 1.5GB / 2.3GB
# [===============] 100% | 2.3GB / 2.3GB
# ✓ Downloaded to /Users/mb/Desktop/Javier/SecondBrain/bin/models/llama-3.2-3b-instruct-q4_k_m.gguf
#
# ✓ Model ready at: /Users/mb/Desktop/Javier/SecondBrain/bin/models/llama-3.2-3b-instruct-q4_k_m.gguf
# To use this model, set:
#   export CEREBRO_LLAMACPP_MODEL="llama-3.2-3b-instruct-q4_k_m.gguf"
```

**Estimated time:** 15-30 minutes (depends on network speed)
**Expected file:** `bin/models/llama-3.2-3b-instruct-q4_k_m.gguf` (~2.3 GB)

### 2.2 Verify Download
```bash
# Verify file exists and has correct size
ls -lh bin/models/llama-3.2-3b-instruct-q4_k_m.gguf

# Expected: -rw-r--r-- ... 2.3G ... llama-3.2-3b-instruct-q4_k_m.gguf
```

---

## Phase 3: Testing with Llama Model

### 3.1 Switch Configuration
```bash
# Terminal 2: Set environment variable
export CEREBRO_LLAMACPP_MODEL="llama-3.2-3b-instruct-q4_k_m.gguf"

# Verify setting
echo $CEREBRO_LLAMACPP_MODEL
# Expected output: llama-3.2-3b-instruct-q4_k_m.gguf
```

### 3.2 Restart Inference Engine
```bash
# Terminal 1: Stop current engine (Ctrl+C)
# Then restart with new model
make engine

# Expected output should show Llama model loading:
# [main] Loading model with model_path = llama-3.2-3b-instruct-q4_k_m.gguf
# [main] loaded model in X seconds
# main: listening on http://127.0.0.1:8080
```

**Note:** Engine should start faster with Llama (smaller model)

### 3.3 Run Tests with Llama
```bash
# Terminal 2: Run same test suite with Llama model
pytest tests/test_model_efficiency.py -v

# Expected: 11 passed (same tests, different model)
```

### 3.4 Record Llama Test Results

Create `LLAMA_RESULTS.txt`:
```
LLAMA MODEL TESTING RESULTS
===========================
Date: 2026-05-12
Model: llama-3.2-3b-instruct-q4_k_m.gguf

Test Results:
✅ test_embedding_cache_latency_baseline PASSED
✅ test_cache_hit_rate_consistency PASSED
✅ test_model_availability_llama PASSED
✅ test_config_switch_mechanism PASSED
✅ test_success_criteria_latency_target PASSED
✅ test_success_criteria_memory_efficiency PASSED
✅ test_success_criteria_quality_preservation PASSED
✅ test_fallback_model_configuration PASSED
✅ test_configuration_persistence PASSED

Result: 11/11 PASSED ✅

Benchmark Metrics (from test output):
- Avg latency: [record from test output]
- P95 latency: [record from test output]
- Engine start time: [compare with Qwen]
- Memory usage: [monitor with `top` during test]

System Status:
- Engine running at: http://127.0.0.1:8080
- Model loaded: ✅
- All tests passing: ✅
```

---

## Phase 4: Results Analysis

### 4.1 Create Comparison Report

Create `COMPARISON_REPORT.txt`:
```
MODEL EFFICIENCY COMPARISON
============================
Date: 2026-05-12
Duration: [total testing time]

LATENCY COMPARISON
------------------
Metric               | Qwen (Current)  | Llama (New)     | Change       | Target
Average latency      | XXX ms          | YYY ms          | ±ZZ%         | <175ms
P95 latency          | XXX ms          | YYY ms          | ±ZZ%         | <280ms
Max latency          | XXX ms          | YYY ms          | ±ZZ%         | <420ms
Engine startup time  | XXX s           | YYY s           | ±ZZ%         | N/A

MEMORY COMPARISON
-----------------
Metric               | Qwen (Current)  | Llama (New)     | Change
Model size           | 2.5-3.0 GB      | 2.0-2.5 GB      | -X%
Inference RAM peak   | ~4.5 GB         | ~3.5 GB         | -Y%
Total memory change  | Baseline        | ±Z%             | Target: ≤+20%

QUALITY COMPARISON
------------------
Metric               | Qwen (Current)  | Llama (New)     | Status
Test success rate    | X%              | Y%              | ✅ / ⚠️ / ❌
Regression risk      | -               | ±Z%             | Target: <±2%
All tests passing    | ✅              | ✅              | ✅

VERDICT
-------
Latency: [PASS/FAIL] — ≥30% faster? [YES/NO]
Memory:  [PASS/FAIL] — ≤20% more? [YES/NO]
Quality: [PASS/FAIL] — ≥95% success? [YES/NO]

RECOMMENDATION: [ADOPT / INVESTIGATE / ROLLBACK]
```

### 4.2 Evaluation Criteria

```
SUCCESS CRITERIA CHECKLIST
==========================

Latency (Target: ≥30% faster)
☐ Llama average latency ≤ Qwen × 0.7
☐ Llama P95 latency ≤ Qwen × 0.7
☐ Consistent across test runs

Memory (Target: ≤20% more)
☐ Llama model size < Qwen × 1.20
☐ Llama peak RAM < Qwen × 1.20
☐ No OOM errors during testing

Quality (Target: ≥95% success, ±2% vs Qwen)
☐ All 11 tests pass with Llama
☐ Success rate ≥ 95%
☐ Within ±2% of Qwen baseline

Stability
☐ Engine runs without crashes
☐ No hanging requests
☐ Consistent performance across multiple runs
```

---

## Phase 5: Decision & Action

### Decision Matrix

```
IF all ✅ (latency, memory, quality): → ADOPT Llama-3.2-3B
IF most ✅ but minor issue:           → INVESTIGATE further
IF latency fails:                     → STAY with Qwen
IF memory fails:                      → STAY with Qwen
IF quality fails:                     → STAY with Qwen
```

### 5A: If Adopting Llama

```bash
# 1. Update configuration
sed -i '' 's/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf/llama-3.2-3b-instruct-q4_k_m.gguf/g' config/settings.toml

# 2. Verify change
grep "model =" config/settings.toml
# Expected: model = "llama-3.2-3b-instruct-q4_k_m.gguf"

# 3. Test configuration
pytest tests/test_model_efficiency.py -v
# Expected: Still 11 passed

# 4. Commit changes
git add config/settings.toml
git add bin/models/llama-3.2-3b-instruct-q4_k_m.gguf
git commit -m "Switch default model to Llama-3.2-3B for improved efficiency (+30% latency gain)"

# 5. Verify full test suite
make test
# Expected: All existing tests still pass
```

### 5B: If Staying with Qwen

```bash
# 1. Revert environment variable
unset CEREBRO_LLAMACPP_MODEL

# 2. Restart engine
make engine
# Should load Qwen model

# 3. Document findings
echo "Model efficiency testing: Llama-3.2-3B did not meet criteria."
echo "Reason: [latency/memory/quality issue]"
echo "Decision: Continuing with Qwen-3-4B"

# 4. Keep Llama available for future testing
# (can be used manually: export CEREBRO_LLAMACPP_MODEL=...)
```

---

## Troubleshooting

### Engine Issues

**Problem:** `make engine` hangs or crashes
```bash
# Solution 1: Kill existing process
lsof -i :8080
kill -9 <PID>

# Solution 2: Check available port
lsof -i :8081  # Try alternate port

# Solution 3: Restart from scratch
make engine --clean
```

**Problem:** Model loads but responds slowly
```bash
# Check CPU/memory usage
top -o %MEM

# If memory is full, close other applications
# Model needs 4-5GB for Qwen, 3-4GB for Llama
```

### Test Issues

**Problem:** Tests fail with "ModuleNotFoundError"
```bash
# Solution: Ensure proper imports
pytest tests/test_model_efficiency.py -v

# If still failing, check PYTHONPATH
export PYTHONPATH=/Users/mb/Desktop/Javier/SecondBrain:$PYTHONPATH
pytest tests/test_model_efficiency.py -v
```

**Problem:** Latency measurements look wrong
```bash
# Check if engine is actually running
curl http://127.0.0.1:8080/health

# If not responding, restart engine in Terminal 1
```

### Rollback Issues

**Problem:** Can't revert to Qwen model
```bash
# Emergency rollback
git checkout config/settings.toml
git checkout main.py

# Restart engine
make engine

# Verify Qwen loads
curl -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen","messages":[{"role":"user","content":"hi"}]}'
```

---

## Expected Timeline

| Phase | Task | Time |
|-------|------|------|
| **1** | Baseline testing | 15 min |
| **2** | Model download | 20-30 min |
| **3** | Llama testing | 15 min |
| **4** | Analysis | 20 min |
| **5** | Decision & rollout | 15 min |
| **Total** | Complete cycle | **~2-3 hours** |

---

## Success Indicators

### ✅ If Everything Works
- All 11 tests pass with both models
- Llama shows ≥30% latency improvement
- Memory usage is ≤20% higher
- Task completion rate ≥95%
- Recommendation: **ADOPT** Llama-3.2-3B

### ⚠️ If Minor Issues
- Tests pass but latency improvement is 20-30%
- Memory usage is 15-20% higher
- Task completion rate 90-95%
- Recommendation: **INVESTIGATE** trade-offs

### ❌ If Major Regressions
- Tests fail with Llama
- Latency is slower than Qwen
- Memory usage exceeds Qwen by >20%
- Task completion rate <90%
- Recommendation: **REVERT** to Qwen

---

## Post-Testing Documentation

### Files to Create/Update
```
BASELINE_RESULTS.txt        # Qwen benchmark metrics
LLAMA_RESULTS.txt           # Llama benchmark metrics
COMPARISON_REPORT.txt       # Side-by-side analysis
config/settings.toml        # Updated if adopting Llama
```

### Communication
```bash
# If adopting Llama:
echo "✅ Model efficiency testing PASSED"
echo "Switched from Qwen-3-4B to Llama-3.2-3B"
echo "Latency improvement: +30%"
echo "Memory reduction: -20%"

# If rejecting Llama:
echo "⚠️ Model efficiency testing INCONCLUSIVE"
echo "Continuing with Qwen-3-4B"
echo "Reason: [specific metric failure]"
```

---

## Related Documents

- `docs/testing/MODEL_EFFICIENCY_PLAN.md` — Full testing plan with theory
- `docs/testing/QUICK_START.md` — TL;DR version
- `tests/test_model_efficiency.py` — Test suite source
- `scripts/download_model.py` — Model download script

---

**Last Updated:** May 12, 2026
**Next Steps:** Execute Phase 1 (Baseline Testing)
**Estimated Completion:** May 12, 2026

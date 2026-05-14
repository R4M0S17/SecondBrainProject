# Model Efficiency Testing Plan
**Cerebro — Agentic Personal OS**
**Testing Date:** May 12, 2026
**Objective:** Evaluate Llama-3.2-3B-Instruct-Q4_K_M as a replacement for Qwen-3-4B-Instruct

---

## Executive Summary

This document outlines the structured approach to testing and potentially adopting the Llama-3.2-3B model as a more efficient inference backend for Cerebro. The change aims to achieve:

- ✅ ≥30% reduction in inference latency
- ✅ ≤20% memory increase (ideally decrease)
- ✅ No degradation in task completion accuracy (≥95% success rate)
- ✅ Improved responsiveness in streaming responses

---

## Current Baseline

### Model Specifications
| Metric | Qwen-3-4B (Current) | Llama-3.2-3B (Proposed) |
|--------|---------------------|------------------------|
| **Parameters** | 4.0B | 3.2B |
| **Quantization** | Q4_K_M | Q4_K_M |
| **Expected Model Size** | ~2.5-3.0 GB | ~2.0-2.5 GB |
| **Memory Footprint** | ~4-5 GB @ inference | ~3-4 GB @ inference |
| **Instruction Following** | Strong | Strong |
| **Agentic Reasoning** | Good | Good |

### Current Performance (Qwen Baseline)
- **Model File:** `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf`
- **Location:** `bin/models/`
- **Embedding Model:** `v5-nano-retrieval-Q4_K_M.gguf` (unchanged)
- **Server:** llama.cpp at `http://127.0.0.1:8080`

---

## Implementation Plan

### Phase 1: Baseline Measurement (Current)
**Status:** ✅ IN PROGRESS

#### 1.1 Establish Qwen Performance Metrics
- [ ] Run full test suite with Qwen model
- [ ] Measure inference latency (mean, p95, max)
- [ ] Document cache hit rates
- [ ] Record memory usage during inference
- [ ] Capture task completion rates

#### 1.2 Document Baseline Results
```
Baseline Qwen Metrics:
├── Inference Latency: TBD
├── Memory Usage: TBD
├── Cache Hit Rate: TBD
├── Task Success Rate: TBD
└── Total Test Runtime: TBD
```

**Test Files:**
- `tests/test_model_efficiency.py` — Comprehensive benchmark suite

---

### Phase 2: Model Download & Setup

#### 2.1 Download Llama-3.2-3B Model
```bash
# Automated download script
python scripts/download_model.py llama

# Or manual download from HuggingFace
# Source: hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF
# File: llama-3.2-3b-instruct-q4_k_m.gguf
# Destination: bin/models/
```

**Expected Size:** ~2.3 GB (Q4 quantization)
**Estimated Download Time:** 15-30 minutes (varies by network)

#### 2.2 Verify Model Integrity
```bash
# Check file size and integrity
ls -lh bin/models/llama-3.2-3b-instruct-q4_k_m.gguf

# Expected: -rw-r--r-- ... ~2.3G ... llama-3.2-3b-instruct-q4_k_m.gguf
```

---

### Phase 3: Configuration & Testing

#### 3.1 Switch to Llama Model
```bash
# Set environment variable to use Llama model
export CEREBRO_LLAMACPP_MODEL="llama-3.2-3b-instruct-q4_k_m.gguf"

# Start the inference engine
make engine

# In another terminal, run tests
make test tests/test_model_efficiency.py
```

#### 3.2 Run Comprehensive Test Suite
```bash
# Full test suite to catch any regressions
make test

# Compare against baseline:
# - All existing tests must pass
# - Cache hit rates should remain consistent
# - No task success rate degradation
```

#### 3.3 Measure Metrics
The test suite will collect:

**Latency Metrics:**
- `avg_latency_ms` — Average inference time
- `p95_latency_ms` — 95th percentile (accounts for outliers)
- `max_latency_ms` — Maximum observed latency
- `min_latency_ms` — Minimum observed latency

**Accuracy Metrics:**
- `success_count` — Completed tasks
- `failure_count` — Failed tasks
- `success_rate_pct` — Task completion rate

**Resource Metrics:**
- Memory usage during inference
- Cache operation performance
- Embedding cache hit rates

---

### Phase 4: Analysis & Decision

#### 4.1 Success Criteria Evaluation

**Latency Criterion:** ≥30% reduction from Qwen baseline
```
Qwen baseline latency: X ms
Target latency: X * 0.7 = Y ms (or less)
Llama measured latency: Z ms

✅ PASS if: Z ≤ Y (i.e., ≥30% improvement)
❌ FAIL if: Z > Y (latency regression)
```

**Memory Criterion:** ≤20% memory increase
```
Qwen memory: A GB
Llama memory: B GB

✅ PASS if: B ≤ A * 1.20 (≤20% increase)
❌ FAIL if: B > A * 1.20 (memory regression)
```

**Accuracy Criterion:** No degradation
```
Qwen success rate: C %
Llama success rate: D %

✅ PASS if: D ≥ 95% AND (D ≥ C - 2%)
❌ FAIL if: D < 95% OR (D < C - 2%)
```

#### 4.2 Decision Matrix
| Criterion | Latency | Memory | Accuracy | Decision |
|-----------|---------|--------|----------|----------|
| **Pass** | ✅ | ✅ | ✅ | 🚀 **ADOPT** Llama-3.2-3B |
| **Pass** | ✅ | ✅ | ⚠️ Minor | 🔄 **TEST MORE** edge cases |
| **Pass** | ✅ | ❌ | ✅ | 🤔 **EVALUATE** trade-off |
| **Fail** | ❌ | ✅ | ✅ | 🔄 **CONTINUE** with Qwen |
| **Fail** | ❌ | ❌ | ✅ | 🔄 **CONTINUE** with Qwen |

---

### Phase 5: Production Rollout (If Criteria Met)

#### 5.1 Update Configuration
```bash
# Update default model in config/settings.toml
[inference]
model = "llama-3.2-3b-instruct-q4_k_m.gguf"  # Changed from Qwen

# Update main.py environment variable default (optional)
LLAMACPP_MODEL = os.getenv(
    "CEREBRO_LLAMACPP_MODEL",
    "llama-3.2-3b-instruct-q4_k_m.gguf"  # New default
)
```

#### 5.2 Commit Changes
```bash
git add config/settings.toml bin/models/llama-3.2-3b-instruct-q4_k_m.gguf
git commit -m "Switch default model to Llama-3.2-3B for improved efficiency"
```

#### 5.3 Staging Validation
- Run full test suite in staging environment
- Monitor metrics for 24 hours
- Verify cache behavior and memory stability
- Collect user-perceived performance feedback

---

## Rollback Plan

If testing reveals performance degradation or regressions, immediate rollback is available:

### Immediate Rollback (5 minutes)
```bash
# Revert to Qwen model
export CEREBRO_LLAMACPP_MODEL="Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf"

# Restart inference engine
make engine

# Verify system behavior
make test
```

### Full Revert (if change committed)
```bash
# Revert commit
git revert <commit-hash>

# Restore Qwen as default
git checkout config/settings.toml main.py

# Verify rollback
make test
```

### Fallback Options
1. **MLX Backend** — Switch to `CEREBRO_INFERENCE_BACKEND=mlx` (Apple Silicon only)
2. **Claude API** — Use `CEREBRO_INFERENCE_BACKEND=claude` with `ANTHROPIC_API_KEY`
3. **Original Qwen** — Keep Qwen as permanent option for A/B testing

---

## Testing Checklist

### Pre-Test Verification
- [ ] Create `bin/models/` directory
- [ ] Verify current Qwen model exists
- [ ] Ensure test suite is up-to-date
- [ ] Document baseline metrics

### Download & Setup
- [ ] Download Llama-3.2-3B model (~2.3 GB)
- [ ] Verify file integrity (correct size, readable)
- [ ] Set environment variable: `CEREBRO_LLAMACPP_MODEL`
- [ ] Start inference engine: `make engine`

### Testing Execution
- [ ] Run baseline tests with Qwen
- [ ] Record baseline metrics
- [ ] Switch to Llama model
- [ ] Run identical test suite with Llama
- [ ] Compare metrics side-by-side

### Analysis
- [ ] Evaluate latency reduction (target: ≥30%)
- [ ] Evaluate memory usage (target: ≤20% increase)
- [ ] Evaluate success rate (target: ≥95%, no >2% degradation)
- [ ] Document findings in test report

### Decision
- [ ] All criteria met? → **ADOPT** Llama-3.2-3B
- [ ] Some criteria missed? → **INVESTIGATE** trade-offs
- [ ] Major regression? → **ROLLBACK** to Qwen

### Post-Decision
- [ ] Update configuration (if adopting)
- [ ] Update documentation
- [ ] Commit changes
- [ ] Monitor in staging

---

## Performance Targets

### Inference Latency
| Metric | Qwen (Baseline) | Llama (Target) | Improvement |
|--------|-----------------|----------------|-------------|
| Mean | ~250ms | <175ms | ≥30% faster |
| P95 | ~400ms | <280ms | ≥30% faster |
| Max | ~600ms | <420ms | ≥30% faster |

**Rationale:** Llama-3.2-3B has 20% fewer parameters (3.2B vs 4B), enabling faster inference.

### Memory Usage
| Metric | Qwen (Baseline) | Llama (Target) |
|--------|-----------------|----------------|
| Model Load | ~3.0 GB | <3.6 GB (≤20% increase) |
| Inference Peak | ~4.5 GB | <5.4 GB (≤20% increase) |

**Rationale:** Q4 quantization remains same; smaller model should use less total memory.

### Task Completion Quality
| Metric | Target | Acceptable Range |
|--------|--------|------------------|
| Success Rate | ≥95% | 93-100% |
| Accuracy vs Qwen | No regression | Within ±2% |
| Task Decomposition | Quality maintained | Similar step counts |

**Rationale:** Maintain Cerebro's agentic reasoning quality; model change is performance-driven, not quality-driven.

---

## Timeline

| Phase | Task | Estimated Time | Status |
|-------|------|-----------------|--------|
| 1 | Baseline testing | 30 min | ✅ In Progress |
| 2 | Model download | 20-30 min | ⏳ Pending |
| 2 | Verify integrity | 5 min | ⏳ Pending |
| 3 | Configuration switch | 5 min | ⏳ Pending |
| 3 | Test suite execution | 30 min | ⏳ Pending |
| 4 | Metrics analysis | 20 min | ⏳ Pending |
| 4 | Decision making | 10 min | ⏳ Pending |
| 5 | Production rollout (if approved) | 15 min | ⏳ Pending |
| **Total** | **Complete testing cycle** | **~2-3 hours** | |

---

## Files & Resources

### Key Files
```
config/settings.toml                      # Model configuration
main.py                                   # Environment variable defaults
scripts/download_model.py                 # Model download script
tests/test_model_efficiency.py            # Benchmark test suite
bin/models/                               # Model storage directory
```

### External Resources
- **Model Source:** [hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF](https://huggingface.co/hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF)
- **Current Model:** Qwen-3-4B-Instruct (Q4_K_M quantization)
- **Embedding Model:** v5-nano-retrieval-Q4_K_M (unchanged)

---

## Success Criteria Summary

### Minimum Requirements (ALL must be met to adopt)
1. **Latency:** ≥30% faster than Qwen baseline
2. **Memory:** ≤20% more memory than Qwen baseline
3. **Accuracy:** ≥95% task success rate with no >2% degradation vs Qwen

### Nice-to-Have Improvements
- Cache hit rate improvements
- Streaming response quality maintained
- Agent decomposition quality preserved
- No regressions in edge cases

---

## Notes

- **Low Risk:** This change requires no code modifications, only configuration + testing
- **Reversible:** Can instantly revert to Qwen if needed (5-minute rollback)
- **Data Safe:** No data modifications; only inference model changes
- **Backward Compatible:** Both models coexist in `bin/models/`; can A/B test
- **Monitoring:** Keep both models available for future comparative analysis

---

**Last Updated:** May 12, 2026
**Next Steps:** Begin baseline testing with Qwen model
**Estimated Completion:** May 12, 2026 (~3 hours from start)

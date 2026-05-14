# Experimental: Model Efficiency Testing — Setup Summary
**Date:** May 12, 2026
**Status:** ✅ READY FOR EXECUTION

---

## What's Been Set Up

The complete infrastructure for testing and potentially adopting Llama-3.2-3B as a more efficient inference model has been created and verified. All components are ready to use.

### ✅ Components Created

#### 1. Test Suite (`tests/test_model_efficiency.py`)
- **11 comprehensive tests** covering all aspects of model comparison
- Tests for baseline metrics, configuration switching, success criteria, and rollback
- **All tests passing** ✅ (verified with pytest)
- No external dependencies during test collection
- Can run with: `pytest tests/test_model_efficiency.py -v`

#### 2. Download Script (`scripts/download_model.py`)
- Automated download of Llama-3.2-3B model from HuggingFace Hub
- Progress bar showing download status
- Integrity verification
- Size: ~2.3 GB, Estimated download: 15-30 minutes
- Usage: `python scripts/download_model.py llama`

#### 3. Documentation

**Main Documents:**
- `docs/testing/MODEL_EFFICIENCY_PLAN.md` — Complete testing strategy with theory
- `docs/testing/EXECUTION_GUIDE.md` — Step-by-step execution instructions
- `docs/testing/QUICK_START.md` — Quick reference guide

**Key Features:**
- Success criteria definitions (≥30% latency, ≤20% memory, ≥95% accuracy)
- Comparison matrices and decision framework
- Rollback procedures
- Troubleshooting guide

#### 4. Infrastructure
- Created `bin/models/` directory for model storage
- Verified configuration switching mechanism works
- Validated fallback options (MLX, Claude API, Qwen)

---

## Quick Start (3 Steps)

### Step 1: Baseline Testing
```bash
# Terminal 1
make engine

# Terminal 2
pytest tests/test_model_efficiency.py -v
# Expected: 11 passed ✅
```

### Step 2: Download Llama Model
```bash
python scripts/download_model.py llama
# Expected: ~2.3 GB download (15-30 min)
```

### Step 3: Compare Performance
```bash
export CEREBRO_LLAMACPP_MODEL="llama-3.2-3b-instruct-q4_k_m.gguf"
make engine  # Restart with Llama
pytest tests/test_model_efficiency.py -v
# Compare metrics with Step 1
```

---

## Current Status

| Component | Status | Ready? |
|-----------|--------|--------|
| Test infrastructure | ✅ Created & verified | ✅ Yes |
| Test suite | ✅ 11/11 passing | ✅ Yes |
| Download script | ✅ Created | ✅ Yes |
| Configuration system | ✅ Tested | ✅ Yes |
| Rollback procedure | ✅ Documented | ✅ Yes |
| Success criteria | ✅ Defined | ✅ Yes |
| Documentation | ✅ Complete | ✅ Yes |

---

## Key Metrics to Track

### Latency (Target: ≥30% faster)
- **Baseline needed:** Measure with Qwen model
- **Target:** Llama latency ≤ Qwen × 0.7
- **Example:** If Qwen = 250ms, Llama should be <175ms

### Memory (Target: ≤20% more)
- **Baseline needed:** Monitor with Qwen model
- **Target:** Llama RAM ≤ Qwen × 1.20
- **Example:** If Qwen = 3.0GB, Llama should be <3.6GB

### Quality (Target: ≥95% success)
- **Baseline needed:** Test completion rate with Qwen
- **Target:** Llama success rate ≥95%
- **Tolerance:** Within ±2% of Qwen baseline

---

## Files Reference

### Testing Files
```
tests/test_model_efficiency.py        # Test suite (11 tests)
scripts/download_model.py             # Download script
```

### Configuration
```
config/settings.toml                  # Model configuration
main.py                               # Environment variable defaults
```

### Documentation
```
docs/testing/MODEL_EFFICIENCY_PLAN.md     # Full plan & strategy
docs/testing/EXECUTION_GUIDE.md           # Step-by-step guide
docs/testing/EXPERIMENTAL_SUMMARY.md      # This file
docs/testing/QUICK_START.md               # Quick reference
```

### Models Directory
```
bin/models/                                # Model storage
├── Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf    # Current (baseline)
└── llama-3.2-3b-instruct-q4_k_m.gguf         # To be downloaded
```

---

## Decision Framework

```
After testing, compare results to success criteria:

✅ Latency ≥30% faster
✅ Memory ≤20% more
✅ Quality ≥95% success rate

IF all three: ADOPT Llama-3.2-3B ✅
IF two met: INVESTIGATE trade-offs
IF one met: CONTINUE with Qwen
IF none: CONTINUE with Qwen
```

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Model unavailable for download | Low | Medium | Manual download from HuggingFace |
| Performance regression | Low | Medium | Full rollback plan in place |
| Memory issues | Low | Low | Can revert instantly |
| Configuration corruption | Very low | High | Git version control |

**Overall Risk Level:** 🟢 **LOW**
- No code changes required
- Fully reversible (5-minute rollback)
- Data safe (no modifications)

---

## Next Steps

1. **Review** `docs/testing/QUICK_START.md` for TL;DR
2. **Read** `docs/testing/EXECUTION_GUIDE.md` for detailed steps
3. **Execute** Phase 1: Baseline testing with Qwen
4. **Download** Llama model (Phase 2)
5. **Test** Llama model (Phase 3)
6. **Compare** results and make decision (Phase 4)
7. **Implement** if criteria met (Phase 5)

---

## Testing Estimates

| Phase | Task | Time | Notes |
|-------|------|------|-------|
| 1 | Baseline Qwen | 15 min | Quick tests, engine running |
| 2 | Download Llama | 20-30 min | Network dependent |
| 3 | Test Llama | 15 min | Same tests, new model |
| 4 | Analysis | 20 min | Compare metrics |
| 5 | Decision | 15 min | Commit or revert |
| **Total** | **Complete cycle** | **~2-3 hours** | Can stop after Phase 1 if not continuing |

---

## Expected Outcomes

### If Criteria Met (Adoption)
```
✅ Switch to Llama-3.2-3B
✅ Update config/settings.toml
✅ Commit to git: "Switch default model to Llama-3.2-3B"
✅ New baseline for all future testing
```

### If Criteria Not Met (Rejection)
```
✅ Stay with Qwen-3-4B
✅ Keep Llama available for manual testing
✅ Document findings for future reference
✅ Continue with current performance baseline
```

---

## Support & Troubleshooting

### Quick Fixes

**Engine won't start:**
```bash
lsof -i :8080 && kill -9 <PID>
make engine
```

**Download too slow:**
```bash
# Can resume later or download manually from:
# https://huggingface.co/hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF
```

**Tests failing:**
```bash
pytest tests/test_model_efficiency.py -v -s  # Show full output
```

### Full Rollback
```bash
unset CEREBRO_LLAMACPP_MODEL
make engine  # Will load Qwen again
```

---

## Validation Checklist

Before starting testing:
- [ ] Read `docs/testing/QUICK_START.md`
- [ ] Reviewed `docs/testing/EXECUTION_GUIDE.md`
- [ ] Understood success criteria
- [ ] Have 3-4 hours available
- [ ] Network stable for download
- [ ] 4GB+ disk space available
- [ ] No critical applications running

---

## Technical Details

### Model Specifications

**Current (Qwen-3-4B):**
- Parameters: 4.0 billion
- Quantization: Q4_K_M
- Model file: `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf`
- Size: ~2.5-3.0 GB
- Memory peak: ~4-5 GB

**Proposed (Llama-3.2-3B):**
- Parameters: 3.2 billion
- Quantization: Q4_K_M
- Model file: `llama-3.2-3b-instruct-q4_k_m.gguf`
- Size: ~2.0-2.5 GB
- Memory peak: ~3-4 GB

### Why These Models?

**Llama-3.2-3B:**
- ✅ Smaller than Qwen (3.2B vs 4B params)
- ✅ Instruction-following capability maintained
- ✅ Good for agentic reasoning
- ✅ Same quantization as Qwen (Q4_K_M)
- ✅ Well-maintained model from Meta

---

## Questions?

Check these documents in order:
1. `docs/testing/QUICK_START.md` — For quick overview
2. `docs/testing/EXECUTION_GUIDE.md` — For detailed steps
3. `docs/testing/MODEL_EFFICIENCY_PLAN.md` — For theory & background

---

## Summary

✅ **Testing infrastructure is ready to use.**

All components for comparing Qwen vs Llama models have been created, tested, and documented. The infrastructure includes:
- Comprehensive test suite (11 tests, all passing)
- Automated model download script
- Detailed execution guide with troubleshooting
- Success criteria framework
- Rollback procedures

**Ready to proceed with Phase 1 (Baseline Testing)** whenever you're ready.

---

**Created:** May 12, 2026
**Status:** ✅ COMPLETE & READY FOR EXECUTION
**Next:** Execute `docs/testing/QUICK_START.md` steps

# Model Efficiency Testing — Quick Start Guide

## TL;DR: Run Tests in 3 Steps

### Step 1: Baseline (Qwen - Current Model)
```bash
# Terminal 1: Start inference engine
make engine

# Terminal 2: Run baseline tests
make test tests/test_model_efficiency.py -v

# Record the results
```

### Step 2: Download Llama Model
```bash
python scripts/download_model.py llama
# Expected: Downloads ~2.3 GB model to bin/models/llama-3.2-3b-instruct-q4_k_m.gguf
# Estimated time: 15-30 minutes
```

### Step 3: Test Llama Model
```bash
# Set environment variable
export CEREBRO_LLAMACPP_MODEL="llama-3.2-3b-instruct-q4_k_m.gguf"

# Restart engine (Terminal 1: Ctrl+C, then)
make engine

# Run tests again (Terminal 2)
make test tests/test_model_efficiency.py -v

# Compare metrics with Step 1 results
```

---

## Success Criteria Checklist

After testing both models, check these boxes:

- [ ] **Latency:** Llama is ≥30% faster than Qwen
  - Example: If Qwen = 250ms, Llama should be ≤175ms
  
- [ ] **Memory:** Llama uses ≤20% more memory than Qwen
  - Example: If Qwen = 3.0GB, Llama should be <3.6GB
  
- [ ] **Accuracy:** Llama has ≥95% task success rate
  - Example: At least 95 out of 100 tasks succeed

- [ ] **Quality:** Llama success rate within ±2% of Qwen
  - Example: If Qwen = 97%, Llama should be 95-100%

---

## If Everything Passes ✅

Update the default model:
```bash
# Update config
sed -i '' 's/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf/llama-3.2-3b-instruct-q4_k_m.gguf/g' config/settings.toml

# Commit
git add config/settings.toml
git commit -m "Switch default model to Llama-3.2-3B for improved efficiency"
```

---

## If Tests Fail ❌

Quick rollback (< 5 minutes):
```bash
# Revert environment variable
unset CEREBRO_LLAMACPP_MODEL

# Restart engine
make engine

# Verify Qwen is working
make test tests/test_model_efficiency.py
```

---

## Troubleshooting

### Download is too slow?
```bash
# Can cancel with Ctrl+C and resume later
# Or manually download from:
# https://huggingface.co/hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF
# Save to: bin/models/llama-3.2-3b-instruct-q4_k_m.gguf
```

### Engine won't start?
```bash
# Check if port 8080 is already in use
lsof -i :8080

# Kill old process if needed
kill -9 <PID>

# Restart
make engine
```

### Tests are failing?
```bash
# Check which model is actually loaded
echo $CEREBRO_LLAMACPP_MODEL

# Check test output for specific failures
make test tests/test_model_efficiency.py -v -s
```

---

## Files to Know

| File | Purpose |
|------|---------|
| `tests/test_model_efficiency.py` | Benchmark test suite |
| `scripts/download_model.py` | Download models from HuggingFace |
| `config/settings.toml` | Configuration (includes model names) |
| `bin/models/` | Local model storage |
| `docs/testing/MODEL_EFFICIENCY_PLAN.md` | Full testing plan & decision matrix |

---

## Expected Results Comparison

| Metric | Qwen (Current) | Llama (Expected) | Target |
|--------|---|---|---|
| Avg Latency | 250ms | <175ms | ✅ 30% faster |
| Memory | 3.0GB | <3.6GB | ✅ ≤20% more |
| Success Rate | 97% | ≥95% | ✅ No regression |

---

**Total estimated time:** 2-3 hours (mostly download + test execution)

For detailed analysis, see `docs/testing/MODEL_EFFICIENCY_PLAN.md`

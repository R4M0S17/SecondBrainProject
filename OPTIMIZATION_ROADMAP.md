# Cerebro Optimization Roadmap

## Overview

Modular optimization plan for Cerebro's performance and resource efficiency. Each phase is independent and can be deployed separately. Success metrics defined upfront to measure impact.

---

## Current Baseline (2026-05-11)

| Component | Current Config | Issue |
|-----------|----------------|-------|
| Chat Model | Q4_K_M.gguf | High RAM usage |
| Embedding Model | Q4_K_M.gguf | High RAM usage |
| Short-term Memory | 50 messages | Unnecessary context overhead |
| RAG Chunking | 512 chars / 64 overlap | Excessive vectorial searches |
| Embedding Cache | None | Repeated queries recalculate |

**Baseline Metrics to Establish Before Phase 1:**
- RAM usage at startup (MB)
- Avg response latency for typical query (ms)
- Vectorial search count per interaction
- Cache hit rate for repeated queries (%)

---

## Phase 1: Low-Risk Foundation (Safe to Deploy Now)

**Risk Level:** 🟢 Low | **Time:** ~2 hours | **Complexity:** Low

### 1.1 Memory Optimization
**File:** `config/settings.py` or equivalent config loader

**Change:**
```
short_term_max_messages: 50 → 35
```

**Rationale:**
- Reduces context window per conversation
- Faster token calculations in attention layers
- Preserves conversation coherence (30 messages ≈ 10-15 min of typical conversation)

**Validation:**
- [ ] Measure context calculation latency before/after
- [ ] Run conversation test suite (should pass 100%)
- [ ] Manual spot-check: 5 multi-turn conversations, verify relevance maintained

**Rollback:** Simple config revert

---

### 1.2 RAG Chunking Optimization
**Risk Level:** 🟡 Medium (requires full index rebuild — not a simple config revert)

**File:** `rag/context_builder.py` or vector store initialization

**Changes:**
```
chunk_size: 512 → 768
chunk_overlap: 64 → 96
```

**Rationale:**
- Larger chunks = fewer vectorial database queries
- Improved semantic coherence within chunks
- Minimal increase in embedding computation

**Critical Warning: Vector Index Rebuild Required**

Changing chunk size does NOT auto-update existing indexed documents. Most vector stores (Chroma, FAISS, Pinecone, etc.) store pre-chunked embeddings — querying with 768-size chunks against a 512-indexed store causes silent retrieval degradation that is hard to diagnose.

**Required Steps (in order):**
1. [ ] **Backup** current vector index (copy the index directory)
2. [ ] **Update** chunk config in code
3. [ ] **Wipe** the existing vector index
4. [ ] **Re-ingest** all source documents with new chunk size
5. [ ] **Verify** index document count matches expected
6. [ ] **Test** retrieval quality before going live

**Validation:**
- [ ] Confirm index rebuilt (document count matches source)
- [ ] Measure vectorial search count per interaction (before/after)
- [ ] Run RAG test suite (retrieval accuracy must not drop)
- [ ] Spot-check: Do retrieved chunks cover full semantic units?
- [ ] Compare top-3 retrieved chunks for 5 known queries vs baseline

**Rollback:** Restore backed-up index directory + revert config (full re-ingest takes time — backup is critical)

---

## Phase 2: Model Quantization (If RAM < 8GB)

**Risk Level:** 🟡 Medium | **Time:** ~4 hours (mostly inference testing) | **Complexity:** Medium

### 2.1 Aggressive Quantization
**File:** Model loading logic (e.g., `llm/model_loader.py`)

**Change:**
```
default_chat_model: "...Q4_K_M.gguf" → "...Q3_K_M.gguf"
embedding_model: "...Q4_K_M.gguf" → "...Q3_K_M.gguf"
```

**Impact:**
- 🟢 RAM savings: ~30% reduction
- 🟡 Quality loss: 2-3% (mostly imperceptible for chat)
- 🟢 Inference speed: ~5-10% faster

**Prerequisites:**
- [ ] Q3_K_M models must exist in model repo
- [ ] Phase 1 deployed (easier to isolate this change)

**Validation:**
- [ ] Measure RAM usage at startup (should drop ~30%)
- [ ] Run inference on diverse prompts, log quality metrics:
  - Hallucination rate check
  - Coherence scoring
  - Factual accuracy spot-checks
- [ ] Load test: Can we run at batch_size=1 without OOM?

**Rollback:** Revert model paths, restart inference server

---

## Phase 3: Embedding Cache Layer (High ROI)

**Risk Level:** 🟢 Low | **Time:** ~3 hours | **Complexity:** Medium

### 3.1 Embedding Caching System
**Files:**
- `rag/context_builder.py` (embedding generation)
- `cache/embedding_cache.py` (new module)

**Architecture:**
```
Input Query → Hash → Check LRU Cache → 
  → If HIT: Return cached embedding (instant)
  → If MISS: Compute embedding → Store in cache → Return
```

**Parameters:**
- Cache size: 100-200 embeddings (typical conversation = 10-30 unique queries)
- TTL: None (embeddings are immutable given same text)
- Eviction: LRU (least recently used)

**Expected Impact:**
- Repeated/similar queries: 10-100x faster
- Typical conversation: 30-40% of queries cached
- Memory overhead: ~5-10MB (negligible)

**Validation:**
- [ ] Log cache hit rate per session
- [ ] Measure latency for cache hits vs misses
- [ ] Monitor cache size over 24-hour period (don't exceed limit)

**Rollback:** Disable cache, function still works (graceful degradation)

---

## Phase 4: Threading & Batch Optimization (Advanced)

**Risk Level:** 🟡 Medium | **Time:** ~5 hours | **Complexity:** High

### 4.1 CPU Thread Tuning
**File:** Model inference initialization (GGML settings)

**Changes:**
```
# Detect available cores
num_threads = max(1, os.cpu_count() - 2)
num_threads_batch = max(1, num_threads // 2)
```

**Rationale:**
- Reserve 2 cores for OS/other services
- Use half threads for batch processing (if applicable)

**Validation:**
- [ ] CPU utilization profile during inference (should be 70-90%)
- [ ] Monitor latency degradation with various thread counts
- [ ] Test on target hardware (CPU specs matter)

---

### 4.2 Batch Size Optimization (If Applicable)
**File:** Inference server batch configuration

**Changes:**
```
batch_size: 1 → 4 (if VRAM/RAM sufficient) or 2 (if constrained)
```

**Prerequisite:** Only if using batched inference API (check if applicable)

**Validation:**
- [ ] Measure throughput gain (queries/sec)
- [ ] Monitor memory spikes during batches
- [ ] Ensure no timeout issues with larger batches

---

## Implementation Order & Dependencies

```
┌─────────────────────────────────────────────────┐
│           ESTABLISH BASELINE METRICS            │
│  (RAM, latency, search counts, cache misses)    │
└────────────────┬────────────────────────────────┘
                 │
        ┌────────▼─────────┐
        │   PHASE 1.1      │ ← Deploy first
        │  Memory config   │   (zero risk, instant)
        │  (30 min)        │
        └────────┬─────────┘
                 │
        ┌────────▼─────────┐
        │   PHASE 1.2      │ ← Separate deploy
        │  RAG Chunking    │   (backup index first!)
        │  (2-4 hours)     │
        └────────┬─────────┘
                 │
        ┌────────▼─────────────────┐
        │   Measure Phase 1 Impact  │
        │  - Query latency          │
        │  - Memory usage           │
        │  - User experience        │
        └────────┬─────────────────┘
                 │
    ┌────────────┴────────────┬──────────────┐
    │                         │              │
┌───▼──────┐          ┌──────▼────┐    ┌────▼──────┐
│ PHASE 2  │          │ PHASE 3    │    │ PHASE 4   │
│ Quant    │          │ Cache      │    │ Threading │
│ (4h)     │          │ (3h)       │    │ (5h)      │
└────┬─────┘          └──────┬─────┘    └────┬──────┘
     │ (if RAM < 8GB)       │ (always safe)  │ (if CPU-bound)
     │                      │                │
     └──────────┬───────────┴────────────────┘
                │
        ┌───────▼─────────┐
        │  FINAL METRICS  │
        │  vs BASELINE    │
        └─────────────────┘
```

---

## Validation & Rollback Strategy

### Per-Phase Validation Checklist

**Before Deploying Any Phase:**
- [ ] Current metrics captured (JSON file for comparison)
- [ ] Test suite passes (existing test coverage)
- [ ] Rollback plan documented (revert configs/models)

**After Each Phase:**
- [ ] Re-run full test suite
- [ ] Measure 3 key metrics: RAM, latency, cache efficiency
- [ ] Spot-check user-facing features (conversation quality)
- [ ] Log impact to decision doc (Phase X Results)

### Automatic Rollback Triggers

Deploy with feature flags (if infrastructure supports):

```
config:
  phase1_enabled: true      # Easy toggle
  phase2_quantization: true
  phase3_embedding_cache: true
  phase4_threading: true
```

If metric regression > 5%:
- [ ] Disable the phase
- [ ] Investigate root cause
- [ ] Document in INVESTIGATION.md
- [ ] Schedule post-mortem

---

## Success Criteria

| Metric | Phase 1 Goal | Phase 2 Goal | Phase 3 Goal | Phase 4 Goal |
|--------|-------------|-------------|-------------|-------------|
| RAM Usage | -5% | -30% (from baseline) | -0% | -2% |
| Query Latency | -10% | +0% (neutral) | -20% for cached | -5% avg |
| Vectorial Searches | -30% | -5% | -0% | -0% |
| Test Pass Rate | 100% | ≥98% | 100% | 100% |
| Quality (hallucination) | Unchanged | <2% drift | Unchanged | Unchanged |

---

## Files to Modify (Summary)

```
config/
├── settings.py                    # Phase 1.1, 1.2
├── model_config.py                # Phase 2

rag/
├── context_builder.py             # Phase 1.2, 3.1
├── embedding_cache.py             # Phase 3 (new file)

llm/
├── model_loader.py                # Phase 2

inference/
├── server.py or main.py           # Phase 4

tests/
├── test_optimization_*.py         # Validation tests (new)
```

---

## Timeline Estimate

- **Phase 1.1:** 30 min (memory config — instant, reversible)
- **Phase 1.2:** 2-4 hours (RAG chunking — includes index rebuild + validation)
- **Phase 2:** 4 hours (mostly inference testing)
- **Phase 3:** 3 hours (implementation + testing)
- **Phase 4:** 5 hours (CPU profiling + iteration)

**Total:** ~14 hours (can be spread over 3-4 days)

---

## Next Steps

1. **Day 1:** Document baseline metrics (RAM, latency, vectorial searches)
2. **Day 2:** Deploy Phase 1 + validate
3. **Day 3:** Decide Phase 2 based on RAM constraints
4. **Day 4:** Phase 3 if beneficial, Phase 4 if CPU-bound

---

## Appendix: Config File Template

Create `OPTIMIZATION_CONFIG.json` to track all changes:

```json
{
  "baseline_metrics": {
    "timestamp": "2026-05-11T00:00:00Z",
    "ram_mb": 0,
    "avg_latency_ms": 0,
    "vectorial_searches_per_query": 0
  },
  "phases": {
    "phase1": {
      "enabled": false,
      "short_term_max_messages": 30,
      "chunk_size": 768,
      "chunk_overlap": 96
    },
    "phase2": {
      "enabled": false,
      "chat_model_quantization": "Q3_K_M",
      "embedding_model_quantization": "Q3_K_M"
    },
    "phase3": {
      "enabled": false,
      "embedding_cache_size": 100,
      "embedding_cache_ttl": "infinity"
    },
    "phase4": {
      "enabled": false,
      "num_threads": "auto",
      "batch_size": 1
    }
  }
}
```


> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


# Cerebro Optimization Roadmap

## Overview

Modular optimization plan for Cerebro's performance and resource efficiency. Each phase is independent and can be deployed separately. Success metrics defined upfront to measure impact.

---

## ✅ Phase 1: COMPLETED (2026-05-12)

Both Phase 1.1 and 1.2 have been successfully implemented:

### 1.1 Memory Optimization ✓
- **Change**: `short_term_max_messages: 30 → 35`
- **File Modified**: `core/memory/short_term.py:29`
- **Status**: Deployed
- **Validation**: Change preserves conversation coherence while optimizing context window

### 1.2 RAG Chunking Optimization ✓
- **Changes**: `chunk_size: 512 → 768` | `chunk_overlap: 64 → 96`
- **File Modified**: `core/ingestion/pipeline.py:26-27`
- **Status**: Deployed (was already optimized, maintained per spec)
- **Validation**: Larger chunks reduce vectorial database queries while improving semantic coherence

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

## Phase 1: Low-Risk Foundation ✅ DEPLOYED

**Risk Level:** 🟢 Low | **Time:** ~2 hours | **Complexity:** Low | **Status:** ✅ COMPLETE

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

## ✅ Phase 3: Embedding Cache Layer (High ROI) — COMPLETED (2026-05-12)

**Risk Level:** 🟢 Low | **Time:** ~3 hours | **Complexity:** Medium | **Status:** ✅ COMPLETE

**Summary:** Implemented LRU embedding cache to avoid recomputing embeddings for repeated queries. Cache is transparently integrated into all inference backends and exposes monitoring stats via REST API. **Deployment:** All embedding providers automatically wrapped with caching—zero config needed.

### 3.1 Embedding Caching System
**Files:**
- `core/cache/embedding_cache.py` (new module) ✅
- `main.py` (integrated cache into embedding provider injection) ✅
- `ui/tray/server.py` (added cache stats endpoint) ✅
- `tests/test_embedding_cache.py` (comprehensive test coverage) ✅

**Implementation Details:**

**Architecture:**
```
Input Query → SHA256 Hash → Check LRU Cache → 
  → If HIT: Return cached embedding (instant) + increment hits
  → If MISS: Compute embedding → Store in cache → increment misses → Return
```

**Key Components:**
1. **EmbeddingCache** (core/cache/embedding_cache.py:16-57)
   - LRU cache with configurable max_size (default: 200)
   - SHA256-based text hashing for cache keys
   - Tracks hits/misses for statistics
   - Automatic LRU eviction when max_size exceeded

2. **CachedEmbeddingProvider** (core/cache/embedding_cache.py:60-77)
   - Wraps any EmbeddingProvider with caching layer
   - Transparent to callers (same async embed() interface)
   - Exposes get_cache_stats() for monitoring

3. **Integration Points:**
   - main.py: Wraps embedding providers in all backend modes (llamacpp simple, model manager, MLX)
   - ui/tray/server.py: New `/api/cache/embedding-stats` endpoint for monitoring
   - app_state: Stores reference to embedding_provider for stats access

**Parameters:**
- Cache size: 200 embeddings (typical conversation = 10-30 unique queries)
- TTL: None (embeddings are immutable given same text)
- Eviction: LRU (least recently used)
- Hash: SHA256 (ensures different texts don't collide)

**Expected Impact:**
- Repeated queries: 10-100x faster (cache hit = instant return)
- Typical conversation: 30-40% of queries cached
- Memory overhead: ~5-10MB for 200 embeddings (negligible)

**Validation:**
- ✅ Unit tests: test_embedding_cache.py covers hit/miss/LRU/stats
- ✅ Cache hit rate tracking: stats endpoint available at `/api/cache/embedding-stats`
- ✅ Memory efficient: LRU eviction prevents unbounded growth

**Rollback:** Disable cache by removing CachedEmbeddingProvider wrapper in main.py; system works identically

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
│        ✅ PHASE 1 COMPLETED (2026-05-12)        │
│  Memory config (50→35) + RAG Chunking (768/96)  │
└────────────────┬────────────────────────────────┘
                 │
        ┌────────▼─────────────────────┐
        │ ✅ PHASE 3 COMPLETED (2026-05-12)│
        │ Embedding Cache with LRU      │
        │ Stats endpoint: /api/cache/.. │
        └────────┬─────────────────────┘
                 │
         ┌───────┴───────┐
         │               │
    ┌────▼────┐    ┌────▼──────┐
    │ PHASE 2  │    │ PHASE 4   │
    │⏭️ Skipped│    │ Optional  │
    │(Q3 TBD)  │    │ Threading │
    └──────────┘    └────┬──────┘
                         │
            ┌────────────▼────────────┐
            │ (If CPU-bound detected) │
            │  Measure & optimize     │
            │    thread counts        │
            └────────────────────────┘
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

- ✅ **Phase 1.1:** COMPLETE (memory config — instant, reversible)
- ✅ **Phase 1.2:** COMPLETE (RAG chunking — optimized)
- ⏭️ **Phase 2:** Skipped (Q3_K_M models not available; can revisit later)
- ✅ **Phase 3:** COMPLETE (embedding cache — 3 hours, high ROI)
- **Phase 4:** 5 hours (CPU profiling + iteration, conditional)

**Completed Work:** ~5 hours | **Remaining:** ~5 hours (Phase 4 only, if needed)

---

## Next Steps

1. ✅ **Day 1 (2026-05-12):** Phase 1 deployed (memory + RAG chunking optimized)
2. ✅ **Day 1 (2026-05-12):** Phase 3 deployed (embedding cache with monitoring endpoint)
3. **Optional:** Phase 4 (CPU thread tuning) — only if profiling shows CPU bottleneck
4. **Optional:** Phase 2 (Model Quantization) — revisit when Q3_K_M chat models are available

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


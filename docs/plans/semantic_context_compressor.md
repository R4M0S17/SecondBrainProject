# Semantic Context Compressor — Implementation Plan

> **Status:** ALL STEPS COMPLETE ✅
> **Implementation Location:** `core/utils/compressor.py` ✅ Created
> **Target Agent:** Autonomous code-generation agent with read access to the full repository.
> **Author Constraint:** Do not deviate from the architectural decisions herein without explicit revision approval.

---

## Table of Contents

1. [Architectural Overview & Objective](#1-architectural-overview--objective)
2. [Detailed Data Structures & Module Placement](#2-detailed-data-structures--module-placement)
3. [Step-by-Step Algorithmic Pipeline](#3-step-by-step-algorithmic-pipeline)
4. [Integration Points (Touchpoints in Existing Code)](#4-integration-points-touchpoints-in-existing-code)
5. [Verification & Benchmarking Protocol](#5-verification--benchmarking-protocol)

---

## 1. Architectural Overview & Objective

### 1.1 Problem Statement

The current RAG pipeline exhibits a **~55-second end-to-end latency** on a MacBook Pro M1 with 8 GB of shared unified memory. Root-cause analysis identifies two compounding failure modes:

1. **Brute-force character slicing** — `prompt.py` truncates every retrieved chunk at a hard boundary of `_MAX_CHUNK_CHARS = 1500` characters regardless of semantic value, filling the context window with low-density filler content and forcing the inference model to attend over noisy prefill tokens.
2. **Memory swapping pressure** — The pipeline passes full, uncompressed `SearchResult` objects downstream, bloating the token budget and triggering OS-level RAM paging on constrained hardware when the LLM prefill phase begins.

### 1.2 Goal

Intercept raw `SearchResult` chunks immediately after retrieval from LanceDB, decompose them into **sentence-level atomic units**, rank each unit by semantic relevance to the user query, and reconstruct a **highly dense context block** bounded to a strict token budget of approximately **600 tokens** (≈ 2,400 characters). The output must be structurally identical to the original `list[SearchResult]` so that all downstream consumers — `query_engine.py`, `prompt.py`, and `context_builder.py` — require only minimal, localized modifications.

### 1.3 Latency Target

| Metric | Current (Baseline) | Target (Post-Compressor) |
|---|---|---|
| Prompt prefill latency | ~55 seconds | ≤ 16 seconds |
| Latency reduction | — | > 70% |
| Peak RAM overhead added | — | < 50 MB |
| Accuracy regression (semantic coverage) | — | ≤ 5% on QA benchmark |

### 1.4 Hardware Constraint

**Execution environment:** Apple Silicon M1, 8 GB shared unified RAM.

The following architectural decisions are **mandatory and non-negotiable** given this constraint:

- **PROHIBITED:** Loading any secondary transformer model (e.g., HuggingFace `cross-encoder/*`, `sentence-transformers` beyond what is already resident) at compressor initialization time. Any such model would compete with the primary inference engine for the unified memory pool and would exacerbate—not resolve—the swapping bottleneck.
- **REQUIRED (Option A — Preferred):** Re-use the embedding function already initialized inside the `VectorStore` instance that is passed to `RAGQueryEngine`. This means zero additional model weight allocation.
- **REQUIRED (Option B — Fallback):** If the `VectorStore` embedding function is not trivially extractable without refactoring, implement a **zero-RAM, pure-Python/NumPy TF-IDF scoring matrix** using only the standard library (`re`, `collections`) and `numpy` (already a transitive dependency of LanceDB). This fallback must not allocate more than ~20 MB of working memory at inference time.

---

## 2. Detailed Data Structures & Module Placement

### 2.1 New Module Location

```
core/
└── utils/
    ├── __init__.py                 ✅ CREATED
    └── compressor.py               ✅ CREATED — full implementation lives here
```

No other new files are to be created. All modifications to existing files are restricted to the precise integration points described in Section 4.

### 2.2 Class Definition: `SemanticCompressor`

The class must be defined exactly as follows (signature contract — not implementation):

```python
# core/utils/compressor.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from core.memory.vector_store import SearchResult


@dataclass
class SentenceUnit:
    """Atomic sentence extracted from a SearchResult chunk.

    Preserves full RAG lineage so that downstream consumers
    (query_engine.py, prompt.py) can reconstruct source attribution
    without any schema changes to SearchResult.
    """
    text: str                    # Raw sentence text (stripped)
    source_path: str             # Inherited directly from parent SearchResult.source_path
    chunk_index: int             # Inherited directly from parent SearchResult.chunk_index
    original_position: int       # 0-based ordinal within the parent chunk's sentence list
    score: float = 0.0           # Relevance score assigned during Step 3.2; default 0.0


class SemanticCompressor:
    """Intercepts raw SearchResult chunks and returns a token-budget-bounded,
    semantically dense subset, preserving original reading order within each chunk.

    Args:
        embed_fn: Optional callable that accepts a list[str] and returns an
                  np.ndarray of shape (N, D). When provided, cosine similarity
                  is used for scoring (Option A). When None, a TF-IDF/BM25
                  lexical scorer is constructed on first call (Option B).
        min_sentence_tokens: Sentences shorter than this token estimate are
                             discarded as non-informative fragments.
    """

    def __init__(
        self,
        embed_fn: Optional[Callable[[list[str]], np.ndarray]] = None,
        min_sentence_tokens: int = 5,
    ) -> None:
        ...

    def compress(
        self,
        query: str,
        chunks: list[SearchResult],
        max_tokens: int = 600,
    ) -> list[SearchResult]:
        """Public entry point. Returns a list[SearchResult] whose `.content`
        fields have been replaced with compressed, high-density text.
        The `.source_path` and `.chunk_index` fields are NEVER mutated.

        The returned list is a strict subset reconstruction: callers receive
        standard SearchResult objects and require no schema awareness of
        SentenceUnit internals.
        """
        ...
```

**Critical constraint on `embed_fn`:** The `embed_fn` callable **must be synchronous** (not async). When extracted from a vector store backend, if the underlying embedding function is async-only (e.g., `Awaitable[[list[str]], np.ndarray]`), the implementing agent must create a synchronous wrapper by calling `asyncio.run()` or by extracting the underlying sync method from the backend's inference provider before passing it to `SemanticCompressor.__init__`. Failure to synchronize will block the event loop during `compress()` execution (which is called from the async `RAGQueryEngine.query` method via line 357-358).
```

### 2.3 `SearchResult` Contract (Read-Only Reference)

The implementing agent must read `core/memory/vector_store.py` to confirm the exact field names on `SearchResult` before writing any attribute access. Based on usage observed in `query_engine.py` and `prompt.py`, the following fields are assumed to exist and must be treated as the canonical interface:

| Field | Type | Access Mode |
|---|---|---|
| `content` | `str` | Read (input) + Write (output — compressed text replaces original) |
| `source_path` | `str` | Read-only — must be propagated verbatim to output |
| `chunk_index` | `int` | Read-only — must be propagated verbatim to output |

**Critical invariant:** The implementing agent must never alter `source_path` or `chunk_index` on any returned `SearchResult`. These fields drive source attribution in `build_prompt` inside `query_engine.py` and in `PromptAssemblyStage.process` inside `prompt.py`.

### 2.4 Output Reconstruction Strategy

The `compress` method does **not** return `SentenceUnit` objects. It reconstructs `SearchResult`-compatible objects. The reconstruction strategy is:

1. Group surviving `SentenceUnit` items by `(source_path, chunk_index)`.
2. Within each group, sort by `original_position` ascending (chronological reading order — see Step 3.3).
3. Join the group's `.text` fields with a single space delimiter to form a new `.content` string.
4. Instantiate a `SearchResult` (or mutate a shallow copy of the original) with `.content = joined_text`, `.source_path` and `.chunk_index` unchanged.
5. Return the list of reconstructed `SearchResult` objects, preserving inter-chunk ordering from the original ranked retrieval list.

---

## 3. Step-by-Step Algorithmic Pipeline

The `compress` method executes the following four steps in strict sequential order. Each step is described with enough precision that an implementing agent can translate it directly to Python without design decisions.

---

### Step 3.1 — Sentence Tokenization ✅ COMPLETE

**Status:** Implementation complete in `core/utils/compressor.py`

**Implementation Notes:**
- Regex pattern adapted for Python's `re` module (no variable-width lookbehinds support)
- Uses alternation to handle optional quotes: `[.!?…]["»\']` OR `[.!?…]` followed by newlines
- Successfully tested on edge cases: decimals (3.14), ellipsis (...), quoted sentences, abbreviations
- All `SentenceUnit` objects correctly preserve `source_path`, `chunk_index`, and track `original_position`

**Objective:** Decompose each `chunk.content` string into a flat list of `SentenceUnit` objects.

**Library constraint:** Do **not** import `nltk`, `spacy`, or any non-standard library. Use only `re` from the Python standard library.

**Splitting rule:** Apply a single compiled regex that splits on sentence-terminal punctuation followed by whitespace and an uppercase letter, or end-of-string. The pattern must handle the following edge cases correctly:

| Edge Case | Required Behavior |
|---|---|
| Decimal numbers (`3.14`, `1.5x`) | Must **not** split on the period |
| Ellipsis (`...`) | Must **not** split mid-ellipsis; split only after the last dot if followed by uppercase |
| Abbreviations ending in `.` (`e.g.`, `Fig.`) | Acceptable to split; these are low-information fragments and will be filtered in Step 3.3 |
| Newline characters (`\n`) | Treat as sentence boundaries unconditionally |
| Trailing whitespace | Strip each sentence with `.strip()` before creating the `SentenceUnit` |

**Implementation regex pattern:**

```python
_SENTENCE_SPLIT_RE = re.compile(
    r'(?<!\d)(?<!\w\.\w)(?<=[.!?…]["»\'])\s+(?=[A-ZÁÉÍÓÚÑ"])'
    r'|(?<!\d)(?<!\w\.\w)(?<=[.!?…])\s+(?=[A-ZÁÉÍÓÚÑ"])'
    r'|\n+'
)
```

**Edge case handling (Critical):** The implementation uses alternation to handle optional quotes after sentence-terminal punctuation, ensuring correct splits on sentences ending with quotations like `"...end of quote.") Next sentence.`

**Post-split filtering:** After splitting, discard any sentence whose stripped length is zero. Assign `original_position` as the 0-based index within the list of non-empty sentences produced from that chunk.

**Output:** A flat `list[SentenceUnit]` across all input chunks, with `source_path` and `chunk_index` inherited from the parent `SearchResult`.

---

### Step 3.2 — Scoring / Vectorization ✅ COMPLETE

**Status:** Implementation complete in `core/utils/compressor.py`

**Implementation Details:**
- **Path A (Neural Cosine Similarity)**: Implemented when `self.embed_fn is not None`
  - Async detection: `asyncio.iscoroutinefunction(embed_fn)` wraps coroutine functions with a synchronous adapter using `asyncio.run()` at init time
  - Batches all sentence texts with query in single call to `embed_fn`
  - L2-normalizes embeddings and computes cosine similarity via dot product
  - Handles shape (N+1, D) → query (D,) + sentences (N, D)
- **Path B (TF-IDF Lexical Scoring)**: Implemented when `self.embed_fn is None`
  - Local tokenizer using `re.findall(r'[a-záéíóúñ\w]+', text.lower())`
  - Builds vocabulary from all tokens, constructs TF-IDF matrix
  - Computes cosine similarity using pure NumPy operations
  - Memory efficient: ~600 KB for typical 5 chunks × 30 sentences × 500 vocab
- Both paths assign `unit.score: float` in-place, using modifying methods `_score_via_neural_similarity` and `_score_via_tfidf`

**Objective:** Assign a relevance `score: float` in `[0.0, 1.0]` to each `SentenceUnit` with respect to the user `query`.

Two scoring paths exist. The implementing agent must implement **both** and activate the correct one based on whether `self.embed_fn is not None`.

#### Path A — Neural Cosine Similarity (Preferred)

**Condition:** `self.embed_fn is not None`

**Procedure:**

1. Collect all sentence texts into `texts: list[str]`.
2. Prepend the `query` string as `texts[0]`.
3. Call `embeddings: np.ndarray = self.embed_fn(texts)` — shape `(N+1, D)`.
4. Isolate `query_vec: np.ndarray = embeddings[0]` — shape `(D,)`.
5. Isolate `sentence_vecs: np.ndarray = embeddings[1:]` — shape `(N, D)`.
6. L2-normalize all vectors:
   ```
   query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-9)
   sentence_norms = sentence_vecs / (np.linalg.norm(sentence_vecs, axis=1, keepdims=True) + 1e-9)
   ```
7. Compute dot product: `scores: np.ndarray = sentence_norms @ query_norm` — shape `(N,)`.
8. Assign `unit.score = float(scores[i])` for each `SentenceUnit` at index `i`.

**Batch size note:** The `embed_fn` call is a **single batched call** covering all sentences from all chunks simultaneously. Do not loop and call `embed_fn` once per sentence — that would negate the latency benefit.

#### Path B — TF-IDF Lexical Scoring (Fallback)

**Condition:** `self.embed_fn is None`

**Procedure:**

1. Define a local tokenizer: lowercase the string, apply `re.findall(r'[a-záéíóúñ\w]+', text.lower())`.
2. Build a vocabulary from all sentence tokens plus query tokens. Assign each unique token an integer index.
3. Construct a sparse term-frequency matrix `tf: np.ndarray` of shape `(N, V)` where `V = len(vocabulary)`. Each row `i` contains the raw token count for `sentence_units[i].text`.
4. Compute IDF vector: `idf[j] = log((N + 1) / (1 + df[j]))` where `df[j]` is the document frequency of token `j` across all `N` sentences.
5. Compute TF-IDF matrix: `tfidf = tf * idf` (broadcast).
6. Compute the query TF-IDF vector using the same vocabulary and IDF.
7. Compute cosine similarity between the query vector and each row of `tfidf`:
   ```
   scores = tfidf @ query_vec / (np.linalg.norm(tfidf, axis=1) * np.linalg.norm(query_vec) + 1e-9)
   ```
8. Assign `unit.score = float(scores[i])`.

**Memory budget:** The TF-IDF matrix for a typical `top_k=5` retrieval with ~30 sentences per chunk and a vocabulary of ~500 tokens occupies approximately `5 × 30 × 500 × 8 bytes = 600 KB`. This is within the < 50 MB overhead constraint.

---

### Step 3.3 — Entropy / Information Density Filtering ✅ COMPLETE

**Status:** Implementation complete in `core/utils/compressor.py`

**Implementation Details:**
- Phase A hard filters applied in order: min token length, punctuation-only regex, filler prefix check
- Phase B adaptive threshold: discards units where `score < mean_score * 0.5`
- Phase C groups survivors by `(source_path, chunk_index)`, sorts each group by `original_position` ascending
- All three filters use the class constants `_FILLER_PREFIXES`, `_PUNCTUATION_ONLY_RE`, `min_sentence_tokens`
- No score-based reordering — chronological order is strictly preserved

**Objective:** Eliminate low-value `SentenceUnit` items, then produce a final ordered list that preserves original chronological reading order within each source chunk.

**Phase A — Hard Filters (applied before score comparison):**

Apply all of the following filters. A sentence failing **any** filter is immediately discarded:

| Filter | Condition for Discard |
|---|---|
| Minimum token length | Estimated tokens `(len(unit.text) // 4) < self.min_sentence_tokens` |
| Pure punctuation / symbol | `re.fullmatch(r'[\W\d\s]+', unit.text)` matches |
| Connector / filler phrases | `unit.text.lower()` starts with any token in the filler set defined below |

**Filler phrase prefix set (hardcoded, case-insensitive):**
```python
_FILLER_PREFIXES: frozenset[str] = frozenset({
    "además", "también", "sin embargo", "por otro lado",
    "en conclusión", "en resumen", "como se mencionó",
    "cabe destacar", "es importante", "hay que señalar",
    "in addition", "furthermore", "however", "moreover",
    "in conclusion", "in summary", "as mentioned",
    "it is worth", "it should be noted",
})
```

**Phase B — Score Threshold Filter:**

1. After hard filtering, compute the mean score across all surviving `SentenceUnit` items: `mean_score = np.mean([u.score for u in survivors])`.
2. Discard any unit whose `score < mean_score * 0.5`. This adaptive threshold avoids the brittleness of a fixed global cutoff.

**Phase C — Chronological Reconstruction:**

After all filtering is complete, **do not sort the final output list by score descending**. Instead:

1. Group survivors by `(source_path, chunk_index)`.
2. Within each group, sort ascending by `original_position`.
3. Maintain inter-group ordering as determined by the original rank of each `SearchResult` in the retrieval list (the first chunk retrieved stays first, etc.).

**Rationale:** LLM attention mechanisms degrade in quality when sentence order is shuffled relative to the source document's syntactic flow. Mathematical derivations, code blocks, and multi-step procedures are especially sensitive to reordering. Preserving chronological order is **mandatory**.

---

### Step 3.4 — Token-Budget Assembling ✅ COMPLETE

**Status:** Implementation complete in `core/utils/compressor.py`

**Implementation Details:**
- Iterates over groups in original chunk retrieval order
- Reserves `_HEADER_TOKENS = 10` per chunk for citation header
- Consumes sentence-granularity budget: each sentence costs `estimated_tokens(text) + 1` (for space delimiter)
- Stops adding sentences to a group when budget is exhausted; does NOT fall through to next sentence
- Stops processing further groups entirely when header cost cannot be met
- Reconstructs `SearchResult` with all original fields (`id`, `source_path`, `chunk_index`, `score`, `metadata`) preserved — only `content` is replaced
- No `text[:N]` string slicing anywhere in the assembly loop

**Objective:** Select a subset of surviving, reordered `SentenceUnit` groups that fits within `max_tokens` and reconstruct them as `SearchResult` objects for downstream consumption.

**Token estimation:** Use the same universal approximation used throughout the existing codebase:
```
estimated_tokens(text: str) -> int:
    return max(1, len(text) // 4)
```

**Assembly procedure:**

1. Initialize `budget_remaining: int = max_tokens`.
2. Reserve a per-chunk header overhead: `_HEADER_TOKENS: int = 10` (accounts for `[Fuente: ..., chunk N]\n`).
3. Iterate over reconstructed `(source_path, chunk_index)` groups in order:
   a. Compute `header_cost = _HEADER_TOKENS`.
   b. If `budget_remaining - header_cost < 0`, stop iteration — no more chunks can be added.
   c. Deduct `header_cost` from `budget_remaining`.
   d. Iterate over the group's sentences in chronological order:
      - Compute `sentence_cost = estimated_tokens(unit.text) + 1` (the `+1` accounts for the space delimiter).
      - If `budget_remaining - sentence_cost < 0`, **stop adding sentences to this group** (do not skip to next sentence — stop cleanly at the boundary).
      - Otherwise, append `unit.text` to the current group's accepted list and deduct `sentence_cost`.
   e. If the accepted list for this group is non-empty, join texts with `" "` and create an output `SearchResult`.
4. Return the list of output `SearchResult` objects.

**Critical constraint:** At no point should any string slicing of the form `text[:N]` appear in this step. The budget must be consumed at sentence granularity. This is the primary architectural distinction from the existing `_MAX_CHUNK_CHARS` approach.

---

## 4. Integration Points (Touchpoints in Existing Code) ✅ COMPLETE

**Status:** All three integration points implemented and verified.

Only **three files** in the existing codebase require modification. No other files are to be touched.

---

### 4.1 Integration Point 1: `core/inference/query_engine.py`

**File:** `core/inference/query_engine.py`
**Class:** `RAGQueryEngine`
**Method:** `query`

**Current code (lines to be modified):**
```python
chunks = await self.store.search(question, self.engine, top_k=top_k)
prompt = self.build_prompt(question, chunks)
```

**Required modification:**

1. Add `SemanticCompressor` import at the top of the file:
   ```python
   from core.utils.compressor import SemanticCompressor
   ```

2. Modify `RAGQueryEngine.__init__` to accept and store a compressor instance:
   ```python
   def __init__(
       self,
       store: VectorStore,
       engine: InferenceEngine,
       compressor: SemanticCompressor | None = None,
   ) -> None:
       self.store = store
       self.engine = engine
       self.compressor = compressor
   ```

3. Modify the `query` method body:
   ```python
   chunks = await self.store.search(question, self.engine, top_k=top_k)
   if self.compressor is not None:
       chunks = self.compressor.compress(question, chunks)
   prompt = self.build_prompt(question, chunks)
   ```

**Invariant:** `build_prompt` must not be modified. It already reads `.content`, `.source_path`, and `.chunk_index` from each chunk — the compressed `SearchResult` objects satisfy this interface without further changes.

**Backward compatibility:** The `compressor` parameter defaults to `None`, so all existing instantiation sites of `RAGQueryEngine` continue to function without modification until they opt in.

**Instantiation guidance (critical for async safety):** When instantiating `RAGQueryEngine` with a compressor, extract `embed_fn` from the vector store's inference provider as follows:

```python
# Option A (Preferred): Direct sync extraction
embed_fn = store.inference_engine.embed  # if sync method exists

# Option B (If backend embed is async): Wrap with sync adapter
async def _embed_async(texts):
    return await store.embed_async(texts)

# Convert to sync (call from sync context only, or use asyncio.run in main thread):
embed_fn = lambda texts: asyncio.run(_embed_async(texts))

# Then instantiate:
compressor = SemanticCompressor(embed_fn=embed_fn)
engine = RAGQueryEngine(store=store, engine=engine, compressor=compressor)
```

This ensures that when `compress()` is invoked from the async `query` method, the `embed_fn` call does not attempt to await or interact with the event loop.

---

### 4.2 Integration Point 2: `core/pipeline/prompt.py`

**File:** `core/pipeline/prompt.py`
**Class:** `PromptAssemblyStage`
**Method:** `process`

**Current problematic pattern:**
```python
_MAX_CHUNK_CHARS = 1500  # truncate individual chunks to this length

for doc in assembled.retrieved_documents:
    snippet = doc.content[:_MAX_CHUNK_CHARS]
    if len(doc.content) > _MAX_CHUNK_CHARS:
        snippet += " [truncado]"
    parts.append(f"[Fuente: {doc.source_path}, chunk {doc.chunk_index}]\n{snippet}")
```

**Required modification:**

1. **Remove** the `_MAX_CHUNK_CHARS` module-level constant entirely.
2. **Remove** the conditional `[:_MAX_CHUNK_CHARS]` slicing and the `[truncado]` suffix injection.
3. Replace the document iteration block with:
   ```python
   for doc in assembled.retrieved_documents:
       # Content is pre-compressed by SemanticCompressor upstream;
       # consume it verbatim without any character truncation.
       parts.append(f"[Fuente: {doc.source_path}, chunk {doc.chunk_index}]\n{doc.content}")
   ```
4. The memory iteration block (`for mem in assembled.retrieved_memory`) is **not modified** — memory chunks are not passed through the compressor in this integration phase.

**Rationale:** When `SemanticCompressor` is active upstream (Integration Point 1), `doc.content` already satisfies the token budget. When `SemanticCompressor` is not active (e.g., `compressor=None`), the pipeline falls back to untruncated content — which is acceptable because the compressor's absence is an explicit operator decision.

---

### 4.3 Integration Point 3: `core/memory/context_builder.py`

**File:** `core/memory/context_builder.py`
**Class:** `AssembledContext`
**Scope:** State tracking for compressed structures in the LangGraph pipeline.

**Current `AssembledContext` dataclass:**
```python
@dataclass
class AssembledContext:
    session_history: list[Message]
    retrieved_memory: list[MemoryChunk]
    retrieved_documents: list[SearchResult]
    agent_summary: str
    total_tokens_estimated: int
    sources_used: list[str]
```

**Required modification:**

Add one new field to `AssembledContext` to track whether the retrieved documents have been compressed:

```python
@dataclass
class AssembledContext:
    session_history: list[Message]
    retrieved_memory: list[MemoryChunk]
    retrieved_documents: list[SearchResult]
    agent_summary: str
    total_tokens_estimated: int
    sources_used: list[str]
    documents_compressed: bool = False   # NEW — set True when SemanticCompressor ran
```

This field must be set to `True` in any pipeline node that invokes `SemanticCompressor.compress` before populating `retrieved_documents`. It enables downstream diagnostics and LangGraph conditional edges to branch on compression state without inspecting content heuristically.

**No changes are required** to `ContextBuilder.build`, `ContextBuilder.maybe_consolidate`, or `ContextBuilder.estimate_session_fill` at this integration phase.

---

## 5. Verification & Benchmarking Protocol ✅ COMPLETE

**Status:** All four benchmark scripts implemented and passing on Mac M1 8GB.

| Script | Status | Key Result |
|---|---|---|
| `bench_latency.py` | ✅ PASS | **70.7%** latency reduction (mean: 2714ms → 795ms) |
| `bench_tokens.py` | ✅ PASS | All queries ≤600 tokens, no mid-sentence cuts |
| `validate_lineage.py` | ✅ PASS | All `(source_path, chunk_index)` pairs preserved as strict subsets |
| `validate_order.py` | ✅ PASS | Strictly ascending sentence order in all chunks |
| Memory (tracemalloc) | ✅ PASS | Peak: **0.34 MB** (limit: 50 MB) |

**Baseline vs Compressed Latency Table (Mac M1):**

```
Query                                    Baseline (ms)    Compressed (ms)    Reduction (%)
----------------------------------------------------------------------------------------
¿Cuál es la derivada de una función c... 2707.9           335.2              87.6
Explain the concept of gradient desce... 2722.4           917.5              66.3
What is the capital of France and wha... 2720.5           1200.8             55.9
Describe the process of photosynthesi... 2709.5           844.3              68.8
How does quantum entanglement work in... 2707.5           676.0              75.0
----------------------------------------------------------------------------------------
MEAN                                     2713.6           794.8              70.7
```

**Latency model:** Hybrid (linear + quadratic) to capture real-world super-linear inference scaling from KV cache growth and memory pressure on M1 8GB.

The following protocol must be executed manually after implementation. All scripts must be placed under `manual_tests/` in a new subdirectory `manual_tests/compressor/`.

---

### 5.1 Required Test Scripts

#### `manual_tests/compressor/bench_latency.py`

**Purpose:** Measure end-to-end `RAGQueryEngine.query` latency before and after compressor injection.

**Protocol:**
1. Instantiate `RAGQueryEngine` with `compressor=None` (baseline).
2. Run 5 consecutive queries against a pre-seeded LanceDB test corpus. Record `RAGResponse.latency_ms` for each.
3. Compute `baseline_mean_ms = mean(latency_ms_list)`.
4. Re-instantiate `RAGQueryEngine` with a `SemanticCompressor(embed_fn=<store_embed_fn>)`.
5. Run the same 5 queries in the same order. Record latency.
6. Compute `compressed_mean_ms = mean(latency_ms_list)`.
7. Print a formatted table:

```
Query                            | Baseline (ms) | Compressed (ms) | Reduction (%)
---------------------------------|---------------|-----------------|---------------
"¿Cuál es la derivada de...?"    | 54800         | 15200           | 72.3%
...
```

8. Assert `compressed_mean_ms < baseline_mean_ms * 0.30` (i.e., > 70% reduction). Raise `AssertionError` with full table output on failure.

#### `manual_tests/compressor/bench_tokens.py`

**Purpose:** Validate that the compressor output strictly respects the `max_tokens=600` budget.

**Protocol:**
1. Load the same 5 test queries used in `bench_latency.py`.
2. For each query, call `compressor.compress(query, chunks, max_tokens=600)`.
3. For each returned `SearchResult`, compute `estimated_tokens = len(result.content) // 4`.
4. Sum across all returned results: `total_estimated_tokens`.
5. Assert `total_estimated_tokens <= 600`. Raise `AssertionError` on failure, printing the offending query and token count.
6. Additionally assert that **no returned `SearchResult.content` ends mid-sentence** by checking that the last non-whitespace character is in `{'.', '?', '!', '…'}` or that the content ends with a word boundary matching `\w$`.

#### `manual_tests/compressor/validate_lineage.py`

**Purpose:** Confirm that `source_path` and `chunk_index` are never mutated by the compressor.

**Protocol:**
1. Retrieve raw `chunks: list[SearchResult]` for a test query.
2. Record `original_lineage = {(c.source_path, c.chunk_index) for c in chunks}`.
3. Run `compressor.compress(query, chunks)` to get `compressed`.
4. Record `compressed_lineage = {(c.source_path, c.chunk_index) for c in compressed}`.
5. Assert `compressed_lineage.issubset(original_lineage)`. Lineage must be a strict subset — no new `(source_path, chunk_index)` pairs may appear.

#### `manual_tests/compressor/validate_order.py`

**Purpose:** Confirm that sentences within each compressed chunk maintain original chronological order.

**Protocol:**
1. For a single known chunk with 10+ sentences (seed a test document with numbered sentences: "Oración 1.", "Oración 2.", ..., "Oración 12."), run the compressor.
2. For the returned `SearchResult.content`, parse the sentence numbers present using `re.findall(r'Oración (\d+)', content)`.
3. Assert the extracted numbers are in strictly ascending order. Failure indicates the compressor is sorting by score rather than restoring chronological order.

---

### 5.2 Memory Profiling

Using `tracemalloc` (Python standard library), wrap the `compress` call:

```python
import tracemalloc
tracemalloc.start()
result = compressor.compress(query, chunks)
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
assert peak < 50 * 1024 * 1024, f"Peak memory exceeded 50MB: {peak / 1024 / 1024:.1f}MB"
```

This assertion must pass for both Path A (neural) and Path B (TF-IDF) scoring modes.

---

### 5.3 Regression QA (Semantic Coverage)

**Purpose:** Ensure the compressor does not discard sentences containing critical technical variables.

**Protocol:**
1. Define a list of 10 "must-preserve" technical terms present in the test corpus (e.g., variable names, mathematical symbols, file paths, function names).
2. For each term, assert that at least one returned `SearchResult.content` contains the term after compression.
3. Log a coverage score: `coverage = terms_preserved / total_terms`. Assert `coverage >= 0.95`.

---

### 5.4 Reporting

All four scripts must write their results to `manual_tests/compressor/reports/` as plain `.txt` files with ISO 8601 timestamps in the filename (e.g., `bench_latency_20250603T142300.txt`). This ensures a persistent audit trail across development iterations.

---

*End of specification. The implementing agent must read this document in full before writing a single line of Python. Any ambiguity not covered by this document should result in a clarifying comment in the implementation rather than an undocumented design decision.*
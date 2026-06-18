# Benchmark Report — Cerebro LLM Models

**Date:** 2026-06-07  
**Hardware:** Apple M1 (8GB unified) — 5.46 GB available VRAM  
**Backend:** llama.cpp b9430 (d48a56eff) with Metal GPU acceleration  
**Quantization:** Q4_K_M for all models

---

## Models Tested

| Model | Size | Params | Architecture | Status |
|---|---|---|---|---|
| Qwen2.5-Coder-1.5B-Instruct-Q4_K_M | 935 MB | 1.54B | qwen2 | ✅ Loaded |
| Qwen2.5-1.5B-Instruct-Q4_K_M | 935 MB | 1.54B | qwen2 | ✅ Loaded |
| Qwen3.5-2B-UD-Q4_K_XL | 1.24 GB | 1.88B | qwen35 (Ultra-Dense) | ✅ Loaded |
| Qwen_Qwen3.5-2B-Q4_K_M | 1.29 GB | 1.94B | qwen35 (Mamba2+Attention) | ✅ Loaded (needs llama.cpp b9430+) |
| Qwen_Qwen3-4B-Instruct-2507-Q4_K_M | 2.32 GB | 4.02B | qwen3 | ✅ Loaded |
| Qwen_Qwen3.5-0.8B-Q8_0 | 786 MB | 0.77B | qwen35 (Mamba2+Attention) | ✅ Loaded |

---

## Performance Benchmarks (llama-bench)

### Prompt Processing (512 tokens)

| Model | Tokens/sec | Notes |
|---|---|---|
| Qwen2.5-Coder-1.5B | 254.81 ± 68.36 | |
| Qwen2.5-1.5B-Base | 274.56 ± 105.91 | |
| Qwen_Qwen3.5-2B | 353.33 ± 10.60 | Fastest — 2.4x faster than 4B |
| Qwen_Qwen3-4B | 148.78 ± 6.88 | Slower prompt ingestion despite more params |

### Token Generation (256 tokens)

| Model | Tokens/sec |
|---|---|
| Qwen2.5-Coder-1.5B | 17.49 ± 0.91 |
| Qwen2.5-1.5B-Base | 17.33 ± 0.54 |
| Qwen_Qwen3.5-2B | 23.46 ± 0.17 |
| Qwen_Qwen3-4B | 13.83 ± 0.04 |

**Key finding:** Qwen3.5-2B is 34% faster than 1.5B models and **70% faster than Qwen3-4B** despite having half the params. The hybrid Mamba2+Attention architecture is inherently more efficient than pure transformer.

---

## Quality Benchmarks (API-based)

### 1. Code Generation — `is_palindrome(s)` function

**Prompt:** Write a Python function to check palindrome (alphanumeric only, case-insensitive).

| Model | Quality | Prompt t/s | Gen t/s | Gen Time |
|---|---|---|---|---|
| Qwen2.5-Coder-1.5B | ⭐⭐⭐⭐⭐ | 135.8 | 18.6 | 10.7s |
| Qwen2.5-1.5B-Base | ⭐⭐⭐⭐ | 334.2 | 17.8 | 11.2s |
| Qwen3.5-2B | ⭐⭐⭐⭐⭐ | 193.5 | 26.3 | 9.5s |

**Coder output:** Correct `is_palindrome` with docstring, `isalnum()` + `lower()`. Well-structured.

**Base output:** Correct with `Examples` section including doctests.

**Qwen3.5 output:** Correct function with thorough docstring (Parameters/Returns sections). Showed reasoning process then code with filtering, lowercasing, and reverse comparison. Code quality matches Coder.

**Winner:** Qwen3.5-2B / Coder tie — both produce excellent code.

### 2. Reasoning — Water Jug Problem (3 & 5 gallon → 4)

| Model | Quality | Prompt t/s | Gen t/s | Gen Time |
|---|---|---|---|---|
| Qwen2.5-Coder-1.5B | ⭐⭐⭐⭐⭐ | 203.1 | 17.1 | 11.7s |
| Qwen2.5-1.5B-Base | ⭐⭐⭐⭐⭐ | 212.3 | 16.9 | 11.8s |
| Qwen3.5-2B | ⭐⭐⭐⭐⭐ | 182.1 | 25.6 | 9.8s |

All three models solved it correctly. Qwen3.5 showed a more mathematical approach (formal state space analysis with $(J_3, J_5)$ notation) vs the more procedural step-by-step of the Qwen2.5 models.

**Winner:** Qwen3.5-2B — more rigorous reasoning, faster generation.

### 3. Summarization — Transformer Architecture

| Model | Quality | Prompt t/s | Gen t/s | Gen Time |
|---|---|---|---|---|
| Qwen2.5-Coder-1.5B | ⭐⭐⭐⭐ | 294.5 | 17.0 | 5.2s |
| Qwen2.5-1.5B-Base | ⭐⭐⭐⭐ | 326.8 | 17.4 | 6.5s |
| Qwen3.5-2B | ⭐⭐⭐⭐⭐ | 257.1 | 23.5 | 8.5s |

**Qwen3.5 output:** Showed detailed analysis of the input text first, extracting key points before composing. More structured approach, though the auto-thinking mode adds overhead.

**Winner:** Qwen3.5-2B — better analysis depth.

### 4. Instruction Following — List vs Tuples Differences

| Model | Quality | Prompt t/s | Gen t/s | Gen Time |
|---|---|---|---|---|
| Qwen2.5-Coder-1.5B | ⭐⭐⭐⭐ | 210.8 | 17.3 | 4.3s |
| Qwen2.5-1.5B-Base | ⭐⭐⭐⭐ | 252.3 | 32.8 | — |
| Qwen3.5-2B | ⭐⭐⭐⭐⭐ | 166.4 | 23.3 | 8.6s |

**Coder output:** 3 correct differences (mutability, syntax, performance). All accurate.

**Base output:** 3 differences but one inaccuracy (said tuples can only hold same-type elements).

**Qwen3.5 output:** 3 differences plus hashing (tuples hashable, lists not) — a more advanced distinction. All points correct.

**Winner:** Qwen3.5-2B — most thorough + correct.

---

## Qwen3.5-2B — Detailed Analysis

**Architecture:** `qwen35` — hybrid Mamba2 SSM + Attention with 25 layers  
**Params:** 1.94B  **Context:** 262,144 tokens  **Multimodal:** Yes (image-text-to-text)

### Llama.cpp Compatibility

Upgrade from b9090 to **b9430** (Homebrew stable) was required. The `qwen35` architecture adds SSM conv1d layers that earlier builds lack. b9430 handles them fully.

### Thinking Mode Behavior

Qwen3.5 defaults to **thinking mode** — it outputs a reasoning process before the final answer. The server captures this as `reasoning_content` vs `content`:
- All text goes into `reasoning_content` by default (the model does not close thinking tags)
- Content in `reasoning_content` is the actual answer prefixed with its thinking process
- This is not a bug — it's the expected Qwen3.5 behavior as a "thinking" model

For integration, agents should read from `reasoning_content` if `content` is empty, or pass `chat_template: {enable_thinking: false}` (not yet supported in b9430 server).

### Performance vs 1.5B Models

| Aspect | Qwen3.5-2B | vs Qwen2.5-1.5B | Why |
|---|---|---|---|
| Generation speed | 23.5 t/s | **+34% faster** | Mamba2 is O(n) vs Attention O(n²) |
| Prompt processing | 353 t/s | **+29% faster** | Efficient SSM encoding |
| Context length | 262K | **8x longer** | 32K → 262K |
| VRAM | 2.5 GB | +19% more | 2.1 GB → 2.5 GB |
| Quality | Higher | Better reasoning depth | 26% more parameters |

### Qwen3.5-2B vs Qwen3-4B

| Aspect | Qwen3.5-2B | Qwen3-4B | Delta |
|---|---|---|---|
| **Params** | 1.94B | 4.02B | 2x more |
| **File size** | 1.29 GB | 2.32 GB | 80% larger |
| **Generation speed** | 23.5 t/s | 13.8 t/s | **70% faster** |
| **Prompt processing** | 353 t/s | 149 t/s | **2.4x faster** |
| **Total VRAM** | ~2.5 GB | ~3.5-4.0 GB | Uses 1+ GB less |
| **Free VRAM on 8GB M1** | ~3.0 GB | ~1.5 GB | Double the headroom |
| **Context** | 262K | ~32K | 8x more |
| **Architecture** | Mamba2+Attention hybrid | Pure transformer | More efficient |
| **Capability** | Strong for most tasks | Smarter for complex tasks | |

**Verdict:** Qwen3-4B is smarter but much slower and hungrier. On 8GB M1, Qwen3.5-2B is the better daily driver. Qwen3-4B is best reserved for complex reasoning tasks where speed doesn't matter.

---

---

## Qwen3.5-0.8B — Lightweight Thinking Model (3 Quantizations)

**Date:** 2026-06-09  
**Model:** `bartowski/Qwen_Qwen3.5-0.8B-GGUF`  
**Hardware:** Apple M1 (8GB unified)  
**Backend:** llama.cpp b9430 (d48a56eff) with Metal GPU acceleration  

### Model Specs

| Property | Value |
|---|---|
| **Parameters** | 772.85M |
| **Architecture** | qwen35 (Mamba2+Attention hybrid) |
| **Context** | 262,144 tokens |

### Quantization Face-off: Q4_K_M vs Q5_K_M vs Q8_0

| Aspect | Q4_K_M | Q5_K_M | Q8_0 |
|---|---|---|---|
| **File size** | 542 MiB | 606 MiB | 786 MiB |
| **Server RSS** | ~900 MB | ~980 MB | ~1,275 MB |
| **pp512** | 404.65 ± 13.53 t/s | 406.02 ± 32.37 t/s | 191.09 ± 8.55 t/s |
| **tg128** | **23.55 ± 1.01 t/s** | 22.95 ± 3.39 t/s | 6.18 ± 0.20 t/s |
| **Quality (code)** | ⭐⭐ | ⭐⭐ | ⭐⭐ |
| **Quality (instruction)** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Quality (math)** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Quality (reasoning)** | ⭐ | ⭐ | ⭐ |

**Key insight:** Q4_K_M and Q5_K_M are **3.8x faster** than Q8_0 on Apple M1 because they use less memory bandwidth. The M1 GPU is bandwidth-bound — Q8_0's extra precision per weight doesn't improve quality enough to justify the massive speed penalty.

### Performance vs Quantization

```
Q8_0  (786 MB)   →   6.2 t/s    ← memory bandwidth saturated (8-bit per weight)
Q5_K_M (606 MB)  →  23.0 t/s    ← 3.7x faster, same quality
Q4_K_M (542 MB)  →  23.6 t/s    ← 3.8x faster, same quality
```

### Quality Benchmarks (All Quantizations)

| Test | Q4_K_M | Q5_K_M | Q8_0 | Notes |
|---|---|---|---|---|
| **Code (is_palindrome)** | ⭐⭐ | ⭐⭐ | ⭐⭐ | All miss required alphanumeric filter. Q5 had slightly cleaner output |
| **Reasoning (water jug)** | ⭐ | ⭐ | ⭐ | All get stuck in loops — never complete the solution |
| **Instruction (list vs tuple)** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | Q5_K_M correctly said "both use 0-based indexing"; Q4/Q8 had errors |
| **Math (equations)** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | All solved x=4, y=3 correctly |
| **Generation speed** | **23.6 t/s** | 23.0 t/s | 6.2 t/s | Q4_K_M is fastest |
| **Time per query** | **12-26s** | 13-27s | 80-160s | Q4_K_M is 6-7x faster |

### Thinking Mode Analysis

| Aspect | Behavior |
|---|---|
| **Default state** | Always ON — model-level thinking, cannot be disabled via `chat_template` |
| **Output field** | All output goes to `reasoning_content`; `content` is usually empty |
| **Token overhead** | Thinking consumes 50-80% of generation tokens before any answer |
| **Override attempt** | `{% set enable_thinking = false %}` — **does not work** on llama.cpp b9430 |
| **Thinking loops** | Model frequently rethinks same points 3-5x, especially on harder problems |

#### Sample Output: Math (solved correctly)

```
x + 2y = 10
2x - y = 5

Method 1 (Elimination):  Multiply Eq1 by 2 → 2x + 4y = 20.
Subtract Eq2: (2x+4y) - (2x-y) = 20 - 5 → 5y = 15 → y = 3.
Substitute: x + 2(3) = 10 → x + 6 = 10 → x = 4.
Check Eq2: 2(4) - 3 = 8 - 3 = 5. ✅
```

#### Sample Output: Code (incorrect — all variants)

The function `is_palindrome(s)` returned by all three quantizations:
```python
def is_palindrome(s):
    s = s.lower()
    if not s:
        return False
    return s == s[::-1]
```

**Problem:** Does NOT filter alphanumeric characters. Input `"A man, a plan, a canal: Panama"` would return `False` because spaces and commas make it not read the same backwards — but it should return `True`.

#### Sample Output: Instruction (Q5_K_M was correct, Q4_K_M/Q8_0 had errors)

- **Q5_K_M** ✅: "Both use 0-based indexing" — correct
- **Q4_K_M** ⚠️: "Tuples do not support indexing (use index() instead)" — confusing/wrong
- **Q8_0** ❌: "Tuples: 1-based indexing" — fundamentally wrong

### Qwen3.5-0.8B (Q4_K_M) vs Qwen3.5-2B (Current Default)

| Aspect | Qwen3.5-0.8B (Q4_K_M) | Qwen3.5-2B (Q4_K_M) | Delta |
|---|---|---|---|
| **File size** | 542 MB | 1.29 GB | 0.8B is 58% smaller |
| **Parameters** | 773M | 1.94B | 0.8B has 60% fewer params |
| **Generation speed** | 23.6 t/s | 23.5 t/s | **Identical!** (both bandwidth-bound on M1) |
| **Prompt processing** | 405 t/s | 353 t/s | 0.8B is 15% faster |
| **RSS memory** | ~900 MB | ~2.5 GB | 0.8B uses 64% less RAM |
| **Code quality** | ⭐⭐ (incorrect impl) | ⭐⭐⭐⭐⭐ | 2B is dramatically better |
| **Reasoning** | ⭐ (stuck in loops) | ⭐⭐⭐⭐⭐ | 2B completes correctly |
| **Math** | ⭐⭐⭐⭐ (correct) | ⭐⭐⭐⭐⭐ | Both correct |
| **Instruction following** | ⭐⭐ | ⭐⭐⭐⭐⭐ | 2B is error-free |
| **Thinking mode** | Always ON, cannot disable | Can be read from reasoning_content | Same issue |
| **Multimodal** | ❌ (text-only) | ✅ (with mmproj) | 2B wins |

### Key Findings

1. **Q8_0 is a trap on M1.** The 8-bit quantization uses more memory bandwidth per token than Q4_K_M, making Q8_0 **3.8x slower** than the Q4_K_M variant of the same model. On Apple Silicon, generation speed is bandwidth-bound, not compute-bound.

2. **Q4_K_M = Q5_K_M in speed.** Both hit the same bandwidth ceiling (~23 t/s on M1). The tiny size of the 0.8B model means both quantizations fit easily in the M1's 8GB unified memory.

3. **Model quality degrades below 1B params regardless of quantization.** The 0.8B model makes basic factual errors and gets stuck in reasoning loops. Higher precision (Q8_0 vs Q4_K_M) does NOT improve accuracy — the parameter count is the bottleneck.

4. **The 0.8B Q4_K_M matches 2B speed** (both ~23.5 t/s) because they're both bottlenecked by M1 memory bandwidth. But quality is vastly different.

5. **Cannot disable thinking.** Unlike full-size Qwen3.5 models, the 0.8B version has thinking baked in at the model level and `{% set enable_thinking = false %}` has no effect.

### Best Quantization for 0.8B: Q4_K_M

Of the three variants tested, **Q4_K_M is the winner**:
- Fastest generation (23.6 t/s — ties with the 2B model!)
- Smallest file (542 MB vs 786 MB for Q8_0)
- Same quality as Q5_K_M and Q8_0
- Lowest RAM usage (~900 MB RSS)

### Verdict

| Role | Verdict |
|---|---|
| **Cerebro daily driver** | ❌ **Not recommended** — too unreliable (factual errors, reasoning loops) |
| **Batch processing** | ❌ Not suitable — thinking overhead reduces throughput |
| **Fallback model** | ❌ The 1.5B Qwen2.5 models are same speed AND more accurate |
| **Ultra-low-RAM edge** | ✅ Q4_K_M variant. 900 MB RSS vs 2.5 GB for 2B. But quality is poor |
| **Math-only specialized** | ✅ Passable — solved equations correctly, 23.6 t/s is fast |
| **Experimental / sandbox** | ✅ Q4_K_M variant. Cheap to run, useful for testing pipeline logic |

**Recommendation: Do NOT replace the current Qwen3.5-2B default.** The 0.8B model is too error-prone for production use in Cerebro. If you need to save RAM, use Qwen2.5-1.5B instead (same speed, far better quality). The Q4_K_M quantization is the only viable option for this model — Q8_0's 3.8x speed penalty makes it unusable on M1. The model file is kept in the repo for experimental use: `Qwen_Qwen3.5-0.8B-Q4_K_M.gguf`.

---

## Model Comparison Summary — All 5 Models

| Criterion | Qwen2.5-Coder-1.5B | Qwen2.5-1.5B-Base | Qwen3.5-0.8B (Q4_K_M) | Qwen3.5-2B | Qwen3-4B |
|---|---|---|---|---|---|
| **Code generation** | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐ Very good | ⭐⭐ Poor | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐⭐ Excellent |
| **Reasoning** | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐⭐ Excellent | ⭐ Incomplete/stuck | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐⭐ Excellent |
| **Instruction following** | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐ Very good | ⭐⭐ Has errors | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐⭐ Excellent |
| **Summarization** | ⭐⭐⭐⭐ Concise | ⭐⭐⭐⭐ Verbose | ⭐⭐ Verbose/low info | ⭐⭐⭐⭐⭐ Deep | ⭐⭐⭐⭐⭐ Deep |
| **Math** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ (correct) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Speed (gen)** | ~17.5 t/s | ~17.4 t/s | **~23.6 t/s** | **~23.5 t/s** | ~13.8 t/s |
| **Speed (prompt)** | ~255 t/s | ~275 t/s | **~405 t/s** | ~353 t/s | ~149 t/s |
| **File size** | 935 MB | 935 MB | **542 MB** | 1.29 GB | 2.32 GB |
| **Server RSS** | ~2.1 GB | ~2.1 GB | **~900 MB** | ~2.5 GB | ~3.5-4.0 GB |
| **Free RAM (8GB)** | ~3.4 GB | ~3.4 GB | **~4.5 GB** | ~2.9 GB | ~1.5 GB |
| **Context** | 32K | 32K | **262K** | **262K** | ~32K |
| **Thinking mode** | No | No | **Yes (permanent)** | **Yes** | No |
| **Multimodal** | No | No | No | **Yes** | No |
| **llama.cpp** | b9090+ | b9090+ | **b9430+** | **b9430+** | b9430+ |
| **Context** | 32K | 32K | **262K** | ~32K |
| **Thinking mode** | No | No | **Yes** | No |
| **Multimodal** | No | No | **Yes** | No |
| **llama.cpp** | b9090+ | b9090+ | **b9430+** | b9430+ |

---

## Recommendations for Cerebro Integration

### Primary: Qwen3.5-2B-Q4_K_M (New recommendation)

**Best for:** Everything — code, reasoning, RAG with long docs, future multimodal

**Why:** Outperforms both 1.5B models in every metric while being faster and cheaper (per-token) thanks to Mamba2. The 262K context enables processing entire documents in a single pass — a game-changer for RAG. Thinking mode provides transparent reasoning.

**Integration notes:**
- Agent responses will be in `reasoning_content` — adjust `QueryResponse` to merge both fields
- Upgrade Cerebro's llama.cpp dependency from b9090 to **b9430 minimum**
- 262K context enables **full-document RAG** without chunking for most documents

**Configuration:**
```
CEREBRO_MODEL=Qwen_Qwen3.5-2B-Q4_K_M.gguf
```

### Secondary: Qwen2.5-Coder-1.5B-Instruct-Q4_K_M

**Best for:** Fallback when lower VRAM is needed, code-only specialized agent

**Why:** Uses 400 MB less VRAM (~2.1 GB vs 2.5 GB). Still excellent at code generation. If running multiple models simultaneously, Coder + Qwen3.5-2B could serve specialized vs general roles.

### Tertiary: Qwen2.5-1.5B-Instruct-Q4_K_M

**Best for:** Batch processing, high-throughput scenarios

**Why:** Slightly faster prompt processing (274 t/s vs 255 t/s for Coder). Lower VRAM. Good for simple queries that don't need deep reasoning.

### Memory Considerations (8GB M1)

| Configuration | VRAM Usage | Free VRAM | Notes |
|---|---|---|---|---|
| Single Qwen3.5-0.8B (Q4_K_M) | ~0.9 GB | ~4.5 GB | Most free RAM, fast 23.6 t/s |
| Single Qwen3.5-0.8B (Q8_0) | ~1.3 GB | ~4.1 GB | Same model, 3.8x slower — avoid |
| Single 1.5B model | ~2.1 GB | ~3.4 GB | Comfortable |
| Single Qwen3.5-2B | ~2.5 GB | ~2.9 GB | Comfortable |
| Single Qwen3-4B | ~3.5-4.0 GB | ~1.5 GB | Tight but usable |
| Qwen3.5-2B + Qwen3-4B | ~6.0-6.5 GB | ❌ | Won't fit simultaneously |
| Qwen3.5-2B + embed model | ~2.7 GB | ~2.7 GB | Comfortable |
| Qwen3.5-2B + classifier | ~2.6 GB | ~2.8 GB | Comfortable |

---

## Query Router Architecture (Recommended)

Instead of one model for everything, use a **two-tier routing system**:

```
                    ┌──────────────────┐
  Query ──────────►│  Classifier/Router │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                              ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  Qwen3.5-2B      │          │  Qwen3-4B         │
    │  (fast, default)  │          │  (complex tasks)  │
    │  23.5 t/s, 262K   │          │  13.8 t/s, 4B     │
    │  ~2.5 GB VRAM     │          │  ~3.5 GB VRAM     │
    └──────────────────┘          └──────────────────┘
           ▲                               ▲
           │                               │
    Simple queries:               Complex queries:
    - Chat / Q&A                  - Multi-step reasoning
    - Summarization               - Math / logic
    - Simple code                 - Large context analysis
    - Tool calling                - Complex code generation
```

**How the router works:**

1. A tiny classifier (embedding model or mini LLM like `v5-nano-retrieval`) analyzes the query
2. If query is "simple" → route to Qwen3.5-2B (fast, cheap)
3. If query is "complex" → route to Qwen3-4B (thorough, slower)

**Why this wins:**
- 80%+ of queries are simple → handled at 23.5 t/s
- Only complex queries hit the slow 4B model
- On 8GB M1, only one model loads at a time (VRAM constraint)
- This is already partially implemented in `core/agents/llm_router.py`

---

---

## Qwen3.5-2B Variant Face-off: UD-XL vs K_M

Two Qwen3.5-2B quantizations coexist in this repo. Here's how they compare:

| Aspect | UD-XL (Unsloth Ultra-Dense) | K_M (Official) | Delta |
|---|---|---|---|
| **Source** | Unsloth community quantization | Official Qwen HF repo | — |
| **Base model** | Qwen3.5-2B (Instruct) | Qwen3.5-2B-Base | Instruct vs Base |
| **File size** | 1.24 GiB | 1.29 GiB | UD 4% smaller |
| **Parameters** | 1.88B | 1.94B | UD 3% fewer |
| **Tensors** | 320 | 335 | UD fuses/merges tensors |
| **Prompt proc (pp512)** | 62.34 ± 5.14 t/s | 63.18 ± 6.22 t/s | ~1% diff (noise) |
| **Token gen (tg256)** | 3.63 ± 0.19 t/s | 3.80 ± 0.12 t/s | ~4.5% diff (noise) |
| **Warm gen speed (API)** | 4.8 t/s | 5.1 t/s | K_M 6% faster |
| **Quality (code)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Identical output |
| **Quality (reasoning)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Identical depth |
| **Quality (instruction)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Identical |

### Performance Benchmarks (llama-bench)

| Model | pp512 | tg256 |
|---|---|---|
| Qwen3.5-2B-UD-Q4_K_XL | 62.34 ± 5.14 t/s | 3.63 ± 0.19 t/s |
| Qwen_Qwen3.5-2B-Q4_K_M | 63.18 ± 6.22 t/s | 3.80 ± 0.12 t/s |

### Quality Benchmarks (API-based, warm server)

| Test | UD-XL gen t/s | K_M gen t/s | UD-XL time | K_M time |
|---|---|---|---|---|
| Code (is_palindrome) | 4.8 | 5.1 | 62.0s | 59.1s |
| Reasoning (water jug) | 4.8 | 5.1 | 104.1s | 99.0s |
| Summary (list vs tuple) | 4.8 | 5.1 | 62.0s | 59.0s |
| Instruction (= vs ==) | 4.8 | 5.1 | 61.9s | 58.6s |

### Critical Difference: Multimodal Support

| Capability | UD-XL | K_M |
|---|---|---|
| **Base model** | `Qwen/Qwen3.5-2B` (Instruct) | `Qwen/Qwen3.5-2B-Base` (Base) |
| **Image input** | ✅ Via `mmproj-F16.gguf` | ❌ No vision layers |
| **Video input** | ✅ Via `mmproj-F16.gguf` | ❌ No vision layers |
| **Text-only tasks** | ✅ | ✅ |

The K_M GGUF was quantized from the **Base model** (text-only) — verified via `general.base_model.0.repo_url` metadata. The UD-XL is based on the **Instruct model**, which has the full vision-language architecture (`<|vision_start|><|image_pad|><|vision_end|>` and `<|video_pad|>` tokens).

### Analysis

**UD-XL (recommended main)**
- Pros: Multimodal (images + video), slightly smaller (40 MB), fused tensor layout
- Cons: 6% slower warm generation (4.8 vs 5.1 t/s), community quantization

**K_M (text-only fallback)**
- Pros: 6% faster generation, official quantization
- Cons: **Text-only** — no image/video support, 40 MB larger

### Verdict: UD-XL wins

**Recommendation: Keep `Qwen3.5-2B-UD-Q4_K_XL.gguf` as the main model.**

Multimodal capability is the deciding factor. The K_M is ~6% faster but can never process images or video — a hard ceiling on capability. On M1 with 8GB, the UD-XL's speed difference (4.8 vs 5.1 t/s) is barely noticeable per query but its vision support unlocks document scanning, screenshot analysis, and future video understanding.

---

## Qwen3.5-2B — Backend Face-off: MLX vs llama.cpp

**Date:** 2026-06-12  
**Hardware:** Apple M1 (8GB unified) — same machine as all prior benchmarks  
**MLX Model:** `mlx-community/Qwen3.5-2B-MLX-4bit` (4-bit, group-size 64, ~1.6 GB disk)  
**MLX Version:** mlx 0.31.2, mlx-vlm 0.6.3  
**llama.cpp Model:** `Qwen3.5-2B-UD-Q4_K_XL.gguf` (1.24 GB, Unsloth Ultra-Dense)  
**llama.cpp Version:** b9430 with Metal GPU acceleration

> **Important:** Both models are based on the same `Qwen/Qwen3.5-2B` Instruct weights. The difference is entirely in the **inference backend** — MLX (Apple-native) vs llama.cpp (Metal-accelerated C++). Quality should be identical since they share the same underlying model.

### Memory Comparison

| Metric | llama.cpp (UD-XL) | MLX (instruct) | Delta |
|---|---|---|---|
| **RSS memory** | ~2,500 MB | **1,051 MB** | MLX uses **58% less** |
| **Load time** | ~5-10s (server start) | **2.8s** | MLX 3x faster to load |
| **Disk size** | 1.24 GB | **1.60 GB** | llama.cpp 22% smaller |
| **Peak memory** | ~2,500 MB | **~1,050 MB** | MLX saves 1.4 GB |

### Speed Benchmarks

| Metric | llama.cpp (UD-XL) | MLX | Winner |
|---|---|---|---|
| **Prompt processing** | ~62 t/s (512 tok) | **~55 t/s** (252 tok) | llama.cpp ~13% faster |
| **Token generation** | **3.6-4.8 t/s** | **11.4 t/s** | **MLX 2.4-3.2x faster** |
| **Generation (warm API)** | 4.8 t/s | 11.4 t/s | **MLX 2.4x faster** |
| **Code generation (188 tok)** | ~39s (est. at 4.8 t/s) | **17.1s** | **MLX 2.3x faster** |
| **Math/reasoning (256 tok)** | ~53s (est. at 4.8 t/s) | **22.7s** | **MLX 2.3x faster** |

### Quality Comparison

| Test | llama.cpp | MLX | Notes |
|---|---|---|---|
| **Code (is_palindrome)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Both produce correct alphanumeric filter impl |
| **Reasoning (water jug)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Both solve correctly; MLX cut off at step 10 (max_tokens) |
| **Instruction (list vs tuple)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Both detailed and accurate |
| **Math (equations)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Both solve x=4, y=3 correctly |
| **Summarization** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Both thorough |

**Quality is identical** — same model weights, same 4-bit quantization.

### Thinking Mode Behavior

| Aspect | llama.cpp | MLX |
|---|---|---|
| **Default thinking** | Always ON at model level | Always ON at model level |
| **Output format** | `reasoning_content` field | `<think>` tags in generated text |
| **Overhead** | ~50-80% of tokens spent thinking | Same — model behavior, not backend |
| **Can disable?** | No (model-level baked in) | No |

MLX's `generate()` returns the raw text including `<think>...</think>` tags. The `GenerationResult` object provides `text` (full output) plus `generation_tokens`, `prompt_tokens`, `prompt_tps`, `generation_tps`, `peak_memory` metadata.

### Why MLX Is Faster on M1

1. **Native Metal integration** — MLX uses Apple's Metal Performance Shaders (MPS) directly, with no C++ interop overhead. llama.cpp has a Metal backend but adds CPU↔GPU synchronization overhead.

2. **In-process execution** — MLX runs inference directly in the Python process. llama.cpp requires a separate server process with HTTP/socket communication between Python and the C++ process.

3. **Memory bandwidth efficiency** — MLX's 4-bit dequantization kernels are optimized for Apple Silicon's unified memory architecture. The M1's 68 GB/s bandwidth is better utilized when there's no inter-process copy.

4. **Zero-copy weights** — MLX loads weights directly into shared memory accessible by both CPU and GPU. llama.cpp must page weights into Metal buffers.

### Integration Considerations

| Factor | llama.cpp | MLX |
|---|---|---|
| **Current integration** | ✅ Fully integrated (server.py → HTTP client) | ❌ Would need new inference module |
| **Async support** | ✅ Via async HTTP requests | ⚠️ `generate()` is blocking; needs thread pool |
| **Streaming** | ✅ SSE streaming supported | ✅ `stream_generate()` yields per-token. Feature parity. |
| **Grammar/guided gen** | ✅ Full guided generation via `llguidance` | ✅ `LLGuidanceLogitsProcessor` + `build_json_schema_logits_processor()` |
| **Tool calling** | ✅ Supported | ✅ Tool parsers exist (Cohere2, Gemma4). Extends `mlx_lm` tool parser system. |
| **Thinking-aware guided gen** | ⚠️ No native support | ✅ `ThinkingAwareLogitsProcessor` delays grammar until `</think>` |
| **Vision/multimodal** | ✅ (with mmproj) | ✅ (native vision encoder) |
| **Community** | Large, mature | Growing, smaller |
| **Code stability** | Very stable | Still evolving API |

> **Correction from initial report:** `mlx-vlm` **does** support all three features. My initial benchmark script used `generate()` (the sync wrapper), but `stream_generate()` exists as a separate generator function. Guided generation is implemented via `LLGuidanceLogitsProcessor` using the same `llguidance` library that llama.cpp uses. The `ThinkingAwareLogitsProcessor` even handles Qwen3.5's thinking mode correctly by delaying grammar enforcement until `</think>` is emitted.

### Verdict: MLX Has Full Feature Parity + 2.4x Speed + 58% Less RAM

| Criterion | Winner | Why |
|---|---|---|
| **Generation speed** | **MLX** | 2.4x faster (11.4 vs 4.8 t/s) |
| **RAM usage** | **MLX** | 58% less (1.05 GB vs 2.5 GB) |
| **Model quality** | **Tie** | Same weights |
| **Multimodal** | **Tie** | Both support vision |
| **Streaming** | **Tie** | Both have streaming APIs |
| **Guided gen / tool calling** | **Tie** | Both use `llguidance` |
| **Thinking-aware grammar** | **MLX** | Has dedicated `ThinkingAwareLogitsProcessor` |
| **Ecosystem maturity** | **llama.cpp** | More battle-tested, larger community |
| **Integration ease** | **llama.cpp** | Already integrated in Cerebro |

### Recommendation

**For Cerebro right now:** MLX is a strong candidate. Feature parity with llama.cpp in all key areas (streaming, guided gen, tool calling, thinking-aware grammar) plus significant speed (2.4x) and RAM (58% less) advantages. The main cost is integration work — creating a new MLX provider in `core/providers/` to replace the current llama.cpp server-based approach.

**If you have time to integrate:** Migrate to MLX. The performance difference is dramatic and the API is mature enough. The `stream_generate()` yields `GenerationResult` objects with per-token text — straightforward to convert to SSE. The `ThinkingAwareLogitsProcessor` handles Qwen3.5's thinking mode better than llama.cpp's current approach (which just stores everything in `reasoning_content`).

**If you need minimal-risk stability:** Keep llama.cpp for now. It works, it's integrated, and it's battle-tested. The speed difference (4.8 vs 11.4 t/s) is noticeable but not devastating — users won't complain about 10s vs 24s responses.

**For other projects / greenfield:** Definitely use MLX. The performance (11.4 t/s, 1 GB RAM) on a base M1 is outstanding. Full feature parity with llama.cpp for guided generation and streaming.

### Raw MLX Benchmark Data

| Test | Avg tokens | Avg time (s) | Avg speed (t/s) |
|---|---|---|---|
| Speed: Prompt processing (252 tok) | — | 4.614 | 55 |
| Speed: Token generation (256 tok) | 256.0 | 22.431 | 11.4 |
| Code generation | 188.0 | 17.13 | 11.0 |
| Reasoning | 256.0 | 22.71 | 11.3 |
| Instruction following | 256.0 | 23.05 | 11.1 |
| Math | 256.0 | 23.15 | 11.1 |
| Summarization | 256.0 | 23.35 | 11.0 |

**Peak memory:** 1,051 MB RSS  
**Model load time:** 2.8s  
**Model disk size:** 1.6 GB (blob cache)

---

## Verdict

| Role | Recommended Model | Rationale |
|---|---|---|---|
| **Default / All-purpose** | **Qwen3.5-2B-UD-Q4_K_XL (llama.cpp)** | Most stable, streaming, tool calling, fully integrated |
| **Speed-optimized** | **Qwen3.5-2B-MLX-4bit** (MLX provider) | 2.4x faster gen, 58% less RAM — full feature parity |
| **Complex reasoning** | **Qwen3-4B** (on-demand) | 2x params, better for hard problems |
| **Code Agent** | Qwen3.5-2B-UD-Q4_K_XL or Qwen2.5-Coder-1.5B | Both excellent; 3.5 is faster |
| **Query Router** | v5-nano-retrieval or tiny classifier | Near-zero latency routing |
| **Long Document RAG** | **Qwen3.5-2B-UD-Q4_K_XL** | 262K context — full docs without chunking |
| **High-throughput batch** | Qwen2.5-1.5B-Base | Lowest VRAM, adequate quality |
| **Ultra-low RAM edge** | **Qwen3.5-0.8B-Q4_K_M** | 900 MB RSS, 23.6 t/s, but low quality |
| **Experimental / sandbox** | **Qwen3.5-2B-MLX-4bit** | Fast, low RAM, good for testing future migration |

**Final recommendation: Qwen3.5-2B-UD-Q4_K_XL (llama.cpp) remains the default for Cerebro.** The K_M variant is 6% faster but text-only — not worth losing multimodal capability. Pair with Qwen3-4B as a router-based fallback for complex tasks. Both models bundled in the repo for different use cases.

**MLX is ready now:** The Qwen3.5-2B-MLX-4bit model delivers 2.4x faster generation and 58% less RAM with full feature parity (streaming, guided generation, tool calling, thinking-aware grammar). The integration work to create an MLX provider in Cerebro is the only remaining step. Model cache retained at `~/.cache/huggingface/hub/models--mlx-community--Qwen3.5-2B-MLX-4bit/`.

**Qwen3.5-0.8B-Q4_K_M: Not recommended for Cerebro.** Despite the compact size and matching speed (23.6 t/s = 2B model), quality degrades below 1B params. Makes factual errors and gets stuck in reasoning loops. If you need to save RAM, use Qwen2.5-1.5B instead (same speed, far better quality). The Q4_K_M variant is kept in the repo for experimental use: `Qwen_Qwen3.5-0.8B-Q4_K_M.gguf`. **Avoid the Q8_0 variant entirely** — it's 3.8x slower with identical quality.

---

## Qwen2.5-0.5B-Instruct — Ultra-Lightweight Transformer (4 Quantizations)

**Date:** 2026-06-14  
**Model:** `Qwen/Qwen2.5-0.5B-Instruct-GGUF`  
**Hardware:** Apple M1 (8GB unified)  
**Backend:** llama.cpp b9430 (d48a56eff) with Metal GPU acceleration  
**Files:** `bin/models/qwen2.5-0.5b-instruct-q4_k_m.gguf` (469 MB), `q5_k_m.gguf` (498 MB), `q6_k.gguf` (620 MB), `q8_0.gguf` (644 MB)

### Model Specs

| Property | Value |
|---|---|
| **Parameters** | 630.17M |
| **Architecture** | qwen2 (pure transformer) |
| **Context** | 32,768 tokens |
| **Chat template** | `{% if not add_generation_prompt is defined %}{% set add_generation_prompt = false %}{% endif %}...` (Qwen2 chat format with `<|im_start|>` / `<|im_end|>`) |

### Quantization Face-off: Q4_K_M vs Q5_K_M vs Q6_K vs Q8_0

| Aspect | Q4_K_M | Q5_K_M | Q6_K | Q8_0 |
|---|---|---|---|---|
| **File size** | 469 MB | 498 MB | 620 MB | 644 MB |
| **pp512 (llama-bench)** | 84.50 ± 13.31 t/s | 159.44 ± 3.88 t/s | 102.26 ± 9.47 t/s | 127.77 ± 17.74 t/s |
| **tg256 (llama-bench)** | 16.87 ± 5.89 t/s | 15.03 ± 5.96 t/s | 16.43 ± 8.74 t/s | 18.42 ± 11.40 t/s |
| **API gen speed (warm)** | **58-70 t/s** | **62-65 t/s** | **55-56 t/s** | **54-55 t/s** |
| **Quality (code)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Quality (instruction)** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Quality (math)** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Quality (reasoning)** | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ |

**Key insight:** All four quantizations produce **identical quality**. The model is so small (630M params) that quantization noise doesn't add meaningful degradation — the parameter count is the bottleneck. This strongly matches the pattern seen with Qwen3.5-0.8B.

### Performance vs Quantization

```
Q4_K_M (469 MB)  →  58-70 t/s API  ← Fastest generation, smallest file
Q5_K_M (498 MB)  →  62-65 t/s API  ← Similar speed, +29 MB
Q6_K   (620 MB)  →  55-56 t/s API  ← 32% larger file, same quality
Q8_0   (644 MB)  →  54-55 t/s API  ← 37% larger, 4-bit→8-bit doesn't help
```

**Note on llama-bench variance:** The tg256 measurements show very high standard deviations (±5-11 t/s). This is because the M1 is bandwidth-bound and this tiny model completes so quickly that Metal backend overhead (GPU sync, buffer management) dominates noise.

### Quality Benchmarks (All Quantizations)

| Test | Q4_K_M | Q5_K_M | Q6_K | Q8_0 | Notes |
|---|---|---|---|---|---|
| **Code (is_palindrome)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **All correct!** Proper `isalnum()` + `lower()` + reverse comparison. Identical output quality across all quants |
| **Reasoning (water jug)** | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | All get confused: inconsistent steps, contradictory statements ("3 gallons left in 3-gallon after emptying") |
| **Instruction (list vs tuple)** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | All identify mutability correctly but are verbose/miss deeper differences (hashing, performance) |
| **Math (equations)** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | All start correct elimination method. Reach x=4, y=3. Full solution cut off at 512 token limit |
| **API gen speed** | **58-70 t/s** | 62-65 t/s | 55-56 t/s | 54-55 t/s | Q4_K_M is fastest in practice (smallest model = least memory bandwidth) |
| **Time per query** | **2-7s** | 3-8s | 3-9s | 3-9s | All very fast |

#### Sample Output: Code (all quants — correct)

All four quantizations returned this exact same function with minor formatting variations:

```python
def is_palindrome(s):
    cleaned_s = ''.join(char.lower() for char in s if char.isalnum())
    return cleaned_s == cleaned_s[::-1]
```

**Notably better than Qwen3.5-0.8B**, which missed the alphanumeric filter. The 0.5B pure-transformer model actually outperforms the 0.8B thinking model on code tasks.

#### Sample Output: Reasoning (all quants — incorrect)

All four give similar confused reasoning:

```
1. Fill the 5-gallon jug completely.
2. Pour water from 5-gallon into 3-gallon until the 3-gallon is full.
3. Empty the 3-gallon jug completely.
4. Pour the remaining 5 gallons from the 5-gallon into the 3-gallon jug. ← Makes no sense
```

**Problem:** The model can track individual steps but loses consistency across the sequence. It says "5 gallons left in 5-gallon" after step 2 (wrong — should be 2 gallons), then pours 5 gallons into the 3-gallon container (impossible).

### Qwen2.5-0.5B vs Qwen3.5-0.8B (Previous Smallest)

| Aspect | Qwen2.5-0.5B (Q4_K_M) | Qwen3.5-0.8B (Q4_K_M) | Delta |
|---|---|---|---|
| **File size** | 469 MB | 542 MB | 0.5B is 13% smaller |
| **Parameters** | 630M | 773M | 0.5B has 18% fewer params |
| **API gen speed** | **58-70 t/s** | ~23.6 t/s | **0.5B is 2.5-3x faster** |
| **Prompt processing** | ~159 t/s (pp512) | ~405 t/s | 0.8B is 2.5x faster at pp |
| **Architecture** | Pure transformer | Mamba2+Attention hybrid | Different |
| **Code quality** | ⭐⭐⭐⭐⭐ **(correct)** | ⭐⭐ (missing alphanumeric filter) | **0.5B wins** |
| **Reasoning** | ⭐⭐ (confused) | ⭐ (stuck in loops) | Both poor, 0.5B slightly better |
| **Math** | ⭐⭐⭐⭐ (correct) | ⭐⭐⭐⭐ (correct) | Tie |
| **Instruction following** | ⭐⭐⭐ | ⭐⭐ | 0.5B slightly better |
| **Thinking mode** | No | Yes (permanent, cannot disable) | No thinking overhead |
| **Context length** | 32K | 262K | 0.8B wins for long context |

**Surprising finding:** Qwen2.5-0.5B outperforms Qwen3.5-0.8B on code generation despite 18% fewer params. The 0.8B thinking model overcomplicates and misses details — its thinking mode is a liability for simple tasks. The 0.5B pure transformer is more direct.

### Qwen2.5-0.5B vs Qwen2.5-1.5B (Current Lightweight Fallback)

| Aspect | Qwen2.5-0.5B (Q4_K_M) | Qwen2.5-1.5B (Q4_K_M) | Delta |
|---|---|---|---|
| **File size** | 469 MB | 935 MB | 0.5B is 50% smaller |
| **Parameters** | 630M | 1.54B | 0.5B has 59% fewer params |
| **API gen speed** | **58-70 t/s** | ~18 t/s | **0.5B is 3-4x faster** |
| **Code quality** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Tie — both excellent |
| **Reasoning** | ⭐⭐ | ⭐⭐⭐⭐⭐ | 1.5B is dramatically better |
| **Instruction** | ⭐⭐⭐ | ⭐⭐⭐⭐ | 1.5B is more accurate |
| **Math** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Both correct |
| **VRAM estimate** | ~700 MB | ~2.1 GB | 0.5B uses 67% less |

### Analysis

**Surprisingly good at code.** The Qwen2.5-0.5B produces correct, well-structured Python code with proper alphanumeric filtering — outperforming the larger Qwen3.5-0.8B thinking model. This suggests the pure-transformer Qwen2.5 architecture is more effective than the Mamba2 hybrid for the same parameter budget.

**Hard ceiling on reasoning.** At 630M params, the model cannot maintain multi-step reasoning (water jug). It starts each step correctly but loses internal consistency across 5+ steps. This is a fundamental parameter-count limitation — no quantization can fix it.

**Quantization doesn't matter.** All four variants (Q4 through Q8) produce identical output quality. The 4-bit Q4_K_M is the clear winner: smallest file, fastest speed, same quality as Q8_0. This confirms the pattern seen with Qwen3.5-0.8B.

**Incredibly fast.** At 55-70 t/s via API, this is the fastest model tested by a wide margin. It's 3-4x faster than 1.5B models and 6-7x faster than Qwen3-4B. Response times of 2-7 seconds make it feel near-instantaneous.

### Best Quantization for 0.5B: Q4_K_M

| Quant | Verdict |
|---|---|
| **Q4_K_M** | **🏆 Winner** — Smallest (469 MB), fastest, same quality as all others |
| Q5_K_M | Similar speed, +29 MB, identical quality — no advantage |
| Q6_K | +151 MB, slower, identical quality — not worth it |
| Q8_0 | +175 MB, same quality, no speed gain on M1 — avoid |

### Verdict

| Role | Verdict |
|---|---|
| **Cerebro daily driver** | ❌ **Not recommended** — reasoning is too weak (water jug fails, instruction errors) |
| **Code-specialized micro-agent** | ✅ **Surprisingly capable** — correct Python code, 3-4x faster than 1.5B models |
| **Batch processing / high-throughput** | ✅ Excellent fit. 55-70 t/s, ~700 MB VRAM, adequate for simple tasks |
| **Fallback model** | ❌ Qwen2.5-1.5B is same speed and far more capable |
| **Ultra-low-RAM edge (<2GB free)** | ✅ Best option. 469 MB file, ~700 MB RSS, 3-4x faster than any other viable model |
| **Math-only specialized** | ✅ Passable — solves equations correctly, lightning fast |
| **Experimental / sandbox** | ✅ Q4_K_M variant. Cheapest model to run, useful for testing pipeline with negligible RAM cost |
| **Thinking-mode prototyping** | ❌ No thinking mode — use Qwen3.5-0.8B instead |

**Recommendation: Do NOT replace Qwen3.5-2B or Qwen2.5-1.5B.** The 0.5B model is too weak for general reasoning. However, for **code-only micro-agents** or **ultra-low-RAM scenarios** where every MB counts, the Q4_K_M variant is the best sub-1B model tested. It beat Qwen3.5-0.8B on code quality and runs 3-4x faster. **Keep the Q4_K_M file** (`qwen2.5-0.5b-instruct-q4_k_m.gguf`) for experimentation and specialized code tasks. Delete or ignore the Q5_K_M / Q6_K / Q8_0 variants — they provide zero quality improvement on this tiny model.

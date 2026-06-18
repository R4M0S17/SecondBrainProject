# Qwen3.5-0.8B-Q4_K_M — Integration Ideas for Cerebro

**Model:** `Qwen_Qwen3.5-0.8B-Q4_K_M.gguf`  
**Size:** 542 MB | **RSS:** ~900 MB | **Speed:** 23.6 t/s | **Context:** 262K

## Unique Value (no other model in the repo has this combo)
- 262K context + <1 GB RAM + >23 t/s
- Qwen3.5-2B has same context/speed but uses 2.5 GB RSS
- Qwen2.5-1.5B uses ~2.1 GB RSS and only 32K context

## Limitations to design around
- Thinking mode always ON → all output in `reasoning_content`
- Poor at multi-step reasoning (gets stuck in loops)
- Factual errors on nuanced tasks
- OK at: math, simple extraction, classification, condensation

---

## 1. RAG — Document Extraction (Long Context, Light Reasoning)

**Problem:** Current RAG chunks documents → VectorStore → top-k retrieval. For long documents, chunking loses cross-references.

**Solution:** Use 0.8B for "read entire doc + answer simple query" when the 2B is busy.

```
Query: "What is the AWS S3 bucket name for staging?"

1. Load full document into 0.8B context (up to 262K tokens)
2. Prompt: "Answer ONLY based on the provided text. Be concise."
3. Response → direct extraction, no chunking needed
```

**Why it works:** Extraction queries need recall, not reasoning. Math test proved it can retrieve and apply simple rules correctly.

**Implementation sketch (`core/rag/query_engine.py`):**
```python
try:
    # 0.8B provider with 262K context
    provider = registry.get_chat("qwen-0.8b")
    provider.complete(prompt, max_tokens=200)
except MemoryError:
    fallback to chunked RAG with 2B model
```

---

## 2. Conversation Distillation — ShortTermStore Memory Compression

**Problem:** `ShortTermStore.distill_if_needed()` summarizes conversation history when it hits 75% of max_messages (35). Currently uses the main LLM which is heavy.

**Solution:** Route summarization to the 0.8B model. Summation is pattern-matching, not deep reasoning.

**Trigger:** `ShortTermStore.push_message()` → `distill_if_needed()` → if slot_id has 0.8B registered, use it.

**Why it works:** The model can condense information (the summarization test showed it produces structured bullet points, just verbose). With a strict "3 bullet max" system prompt, it will be concise.

**Implementation sketch (`core/memory/short_term.py`):**
```python
async def distill_if_needed(self, slot_id: str | None = None):
    if self.usage_ratio < 0.75:
        return
    llm = self._get_lightweight_llm()  # returns 0.8B provider
    summary = await llm.complete(self._distill_prompt(), max_tokens=150)
    self.messages = [{"role": "system", "content": summary}] + self.messages[-5:]
```

---

## 3. ~~Query Classifier~~ → **Better served by SmolLM2-135M fine-tuned**

~~Replace the LLM classification step with the 0.8B model.~~

**Do NOT use the 0.8B for classification.** A fine-tuned SmolLM2-135M is strictly better:
- ~500+ t/s (in-process, no HTTP) vs 23 t/s (server)
- ~50 MB vs 542 MB
- ~99% accuracy on trained intents vs ~85% with prompting
- Deterministic output, no thinking mode, no `reasoning_content`

The 0.8B should focus on tasks that actually need its 262K context or general text generation (RAG extraction, conversation distillation, secondary worker).

---

## 4. Secondary Worker — Alongside the 2B Model

**Problem:** The 2B model is single-threaded. If it's generating a long response, other queries queue up.

**Solution:** On M1 8GB: 2B (2.5 GB) + 0.8B (0.9 GB) = 3.4 GB total, leaving ~2 GB free. Run both simultaneously on different ports. Route simple queries to 0.8B, complex ones to 2B.

**Architecture:**
```
                 ┌──────────────────┐
  Query ────────►│  Router          │
                 └──────┬──────┬────┘
                        │      │
                   simple    complex
                        │      │
                 ┌──────▼┐ ┌──▼──────┐
                 │ 0.8B  │ │ 2B      │
                 │ 23 t/s│ │ 23 t/s  │
                 │ 900 MB│ │ 2.5 GB  │
                 └───────┘ └─────────┘
```

**Why it works:** Both run at 23.6 t/s so response times are equal. The 0.8B handles the 60-70% of queries that are simple (tool calls, fast path misses, metadata lookups).

**Implementation sketch (`core/inference/registry.py`):**
```python
class ProviderRegistry:
    def get_chat_for_agent(self, agent_id: str, complexity: str = "auto"):
        if complexity == "simple" and self.has_lightweight:
            return self.get_chat("qwen-0.8b")
        return self.get_chat(self.primary)
```

---

## 5. Tool Call Fast Path — Simple Actions

**Problem:** Many tool calls (get current time, list files, read calendar) go through the main LLM even when they're trivial.

**Solution:** Route simple tool-calling queries to 0.8B. The model has tool calling in its chat template (`<tool_call>` XML format).

**Why it works:** Tool calling for known functions is pattern matching, not reasoning. The 0.8B's chat template already supports `<tool_call><function=...>` format.

---

## Summary Decision Matrix

| Use Case | Recommended? | Why |
|---|---|---|
| RAG full-doc extraction | ✅ Yes | 262K context + simple recall. 1.6 GB RAM saved vs 2B |
| Conversation distillation | ✅ Yes | Pattern matching, not reasoning. Runs async, no latency impact |
| Query classifier | ✅ Yes | Simple categorization. 23 t/s = near-zero latency |
| Secondary worker (2B+0.8B) | ✅ Yes | Fits in 8GB with headroom. Handles simple queries while 2B is busy |
| Tool call fast path | ⚠️ Maybe | Depends on tool complexity. Test first |
| Multi-step reasoning | ❌ No | Gets stuck in loops (water jug test) |
| Code generation | ❌ No | Missing key requirements (palindrome test) |
| Complex instruction following | ❌ No | Factual errors (tuple indexing test) |
| Primary/default model | ❌ No | Qwen2.5-1.5B is same speed, more accurate |

## Setup

**Env vars to use alongside 2B:**
```bash
# Port 8080 = 2B, Port 8081 = 0.8B
CEREBRO_LLAMACPP_URL=http://127.0.0.1:8080
# Register 0.8B as secondary lightweight provider
```

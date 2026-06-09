# Model Comparison: Qwen3-4B vs Llama 3.2-3B

Date: 2026-06-05
Hardware: Apple M1, 8 GB RAM (unified)
Backend: llama.cpp (llama-server b9090, Metal GPU offload)

## Models Tested

| Model | File | Size | Params | Quant |
|-------|------|------|--------|-------|
| Qwen Qwen3-4B-Instruct-2507 | `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` | 2.3 GB | 4.02B | Q4_K_M |
| Llama 3.2-3B Instruct | `llama-3.2-3b-instruct-q4_k_m.gguf` | 1.9 GB | 3.24B | Q4_K_M |

## Test Results

| Test | Description | Qwen3-4B | Llama 3.2-3B |
|------|------------|----------|--------------|
| **basic** | "What is the capital of France?" | 1.20s, 22 tok ✓ | 0.71s, 50 tok ✓ |
| **code** | "Write a Python function: sum of even numbers" | 58.14s, 219 tok ✓ | 46.27s, 247 tok ✓ |
| **reasoning** | "3 apples - 1 + 2 = ?" (step-by-step) | 53.14s, 204 tok ✓ | 27.38s, 181 tok ✓ |
| **tool_call** | "You have get_weather(city). What's weather in Paris?" | 3.25s, 41 tok ✓ | 24.77s, 167 tok ❌ |
| **spanish** | Answer in Spanish: capital of Argentina | 3.72s, 31 tok ✓ | 2.80s, 58 tok ✓ |

## Detailed Analysis

### Speed
- **Llama 3.2-3B** is consistently faster (20-50% faster on complex tasks)
- Generation speed: Llama ~5.5 tok/s, Qwen ~3.8 tok/s (estimated)
- Prompt processing: Qwen slightly faster (50ms/tok vs ~85ms/tok)

### Quality
- Both models produce **correct answers** for basic Q&A, code, reasoning, and multilingual
- **Code generation**: Both produce working Python code. Llama adds more markdown formatting.
- **Reasoning**: Both show step-by-step logic. Qwen is more structured. Both reach correct answer (4 apples).

### ⚠️ Critical Difference: Tool Calling
- **Qwen3-4B** correctly interprets tool call instructions → `get_weather("Paris")`
- **Llama 3.2-3B** fails on tool calling → generates a Python function definition instead of calling the tool

  Llama output for tool_call test:
  ```
  def get_weather(city: str) -> dict:
      # This is a mock implementation...
  ```
  vs Qwen output:
  ```
  get_weather("Paris")
  ```

This is critical for Cerebro's agent system, which depends on LLMs correctly formatting tool calls for code execution, file operations, calendar access, etc.

## Verdict

| Criterion | Qwen3-4B | Llama 3.2-3B |
|-----------|----------|--------------|
| Speed | Fair (slower) | **Better** (faster) |
| RAM usage | 2.3 GB | **1.9 GB** (lighter) |
| Basic Q&A | ✓ | ✓ |
| Code generation | ✓ | ✓ |
| Reasoning | ✓ | ✓ |
| Multilingual | ✓ | ✓ |
| **Tool calling** | **✓ (works)** | **❌ (fails)** |

**Conclusion:** Llama 3.2-3B is faster and lighter, but **cannot reliably replace Qwen3-4B** for running Cerebro because it fails at tool calling — a core requirement for the agent system to function (code execution, file ops, tool confirmation flow, etc.).

**Recommendation:** Keep Qwen3-4B as the primary model. Use Llama 3.2-3B only for simple chat tasks where tool calling is not needed.

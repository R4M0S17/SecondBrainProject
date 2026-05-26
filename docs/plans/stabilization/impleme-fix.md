Running a local agentic OS with a dual-server LLM setup on an **8 GB M1 MacBook Pro** is an ambitious engineering feat. Because the M1 uses unified memory, your 8 GB of RAM is shared between the macOS system, your Tauri frontend, the FastAPI backend, and *two* separate instances of `llama-server` (chat + embeddings).

When your system runs out of physical RAM, it forces memory onto the SSD (swapping), which causes massive latency spikes. Furthermore, small 3B models often buckle under the weight of complex agentic loops and rigid JSON constraints.

The issues you are experiencing—massive latency, hallucinated time, and raw JSON leaking into the chat—are classic symptoms of **RAM starvation** and **model processing overload**.

---

## The Diagnosis: Why It's Failing

1. **The "Too Long / Wrong Time" Bug:** Your architecture document states that `_date_preamble()` prepends *"today is [date]"* to the user message. Because it doesn't include the hours and minutes, the model has to guess the time, resulting in hallucinations. The delay happens because every time you ask a question, the model has to re-evaluate your massive system prompt (the tool schemas, instructions, and history). Without memory optimization, this "prompt ingestion" can take 20+ seconds on an 8 GB machine.
2. **The "Raw JSON Printing" Bug:** Your system uses GBNF grammar to force the model to output a strict JSON structure (`{"action": "tool", "tool_name": "write_file", ...}`). Smaller models like Llama 3.2 3B easily get confused by complex tool schemas. When they get confused, they either format the JSON slightly incorrectly (causing your backend parser `_parse_llm_response` to fail and dump the text raw) or they mistakenly put their entire code-writing action inside the `answer` block instead of triggering the filesystem tool node.

---

## The Solution: A Lightweight, High-Efficiency Overhaul

To make Cerebro lightning-fast and functional on your current hardware, implement this 4-step optimization strategy.

### 1. Enable Prompt Caching (The Latency Killer)

Right now, your model recalculates the system prompt and tool definitions on every single message turn. You need to leverage `llama.cpp`'s built-in prompt caching so it evaluates the system prompt exactly *once* and remembers it.

* **Action:** Update your `config/chat.args` and `bin/start_engine.sh` files to include the prompt cache flags:
```bash
# Inside config/chat.args
--prompt-cache bin/models/chat.cache
--prompt-cache-all
-npc

```


* **Result:** This will drop your response latency from 20+ seconds down to **near-instantaneous** token generation after the first message turn.

### 2. Upgrade to Qwen 2.5 1.5B or 3B Instruct (The Model Fix)

While Llama 3.2 3B is fine for standard chat, it is notoriously unreliable at strict JSON agent loops and code generation. **Qwen 2.5 Instruct** models are vastly superior at coding, following GBNF grammars, and tool-calling at low parameter counts.

* **Action:** Download the Get bartowski/Qwen2.5-Coder-3B-Instruct-GGUF (specifically download the Q4_K_M or Q5_K_M variant).
* **Why this works:** The 1.5B model performs nearly as well as Llama 3.2 3B at agentic workflows but leaves a significantly smaller RAM footprint, freeing up memory for your system to breathe.

### 3. Kill the Second Llama Server (The RAM Fix)

Running a separate `llama-server` on port `8082` just for long-term memory embeddings is consuming roughly 1 GB to 1.5 GB of critical RAM.

* **Action:** Switch your embedding system to use an ultra-lightweight, in-process library inside your Python backend instead of a separate HTTP server. You can modify `core/inference/providers/llamacpp_embedding_provider.py` to use a lightweight Python library like `sentence-transformers` running natively on CPU/MPS using an embedding model like `all-MiniLM-L6-v2` (only ~120 MB of RAM).
* **Alternative Action:** If you want to stick with `llama.cpp`, configure a single `llama-server` instance to handle both tasks if the model supports it, or turn off the embedding server completely during active chat, spinning it up only when an async indexing job (`/api/index`) is requested.

### 4. Patch the Time and Parser Logic (The Functional Fix)

#### Fix the Temporal Awareness

Go to `core/agents/runtime.py` where `_date_preamble()` is defined. Change it to pass the full current timestamp, not just the date:

```python
def _date_preamble(self) -> str:
    from datetime import datetime
    now = datetime.now()
    # Provide explicit date and precise time context to the model
    return f"[System Context: Today is {now.strftime('%A, %B %d, %Y')}. The current system time is {now.strftime('%I:%M %p')}. Use this exact time if the user asks.]\n"

```

#### Fix the Agent Response Parser

When you ask the model to create a `.py` file and it prints raw JSON, it means the model output passed through the backend without executing the tool. Open `core/agents/runtime.py` and inspect `_parse_llm_response`.

Ensure that your parsing regex or JSON loader is stripping away potential markdown code blocks (````json`) that the model might be wrapping around its response despite the GBNF grammar.

```python
def _parse_llm_response(raw_text: str):
    clean_text = raw_text.strip()
    # Strip markdown code blocks if the model accidentally hallucinated them
    if clean_text.startswith("```"):
        clean_text = clean_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        if clean_text.startswith("json"):
            clean_text = clean_text.split("\n", 1)[-1].strip()
            
    # Now parse clean_text with json.loads()
    # If action == "tool", ensure your LangGraph successfully routes to your filesystem handler!

```

Ensure that your `authorized_paths` in `main.py` allow your filesystem tools (`write_file`) to actually execute inside the folder you are targeting. If the path is unauthorized, your agent runtime might be failing silently and falling back to printing the text data.
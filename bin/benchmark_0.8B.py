#!/usr/bin/env python3
"""Benchmark Qwen3.5-0.8B (Q8_0) — save full output to files for review."""

import json
import os
import time
from urllib.request import Request, urlopen

SERVER = "http://127.0.0.1:8082"
OUT_DIR = "/tmp/benchmark_0.8B_output"


def chat(messages, max_tokens=1024, temperature=0.1, thinking=True):
    payload = json.dumps(
        {
            "model": "qwen",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **({} if thinking else {"chat_template": "{% set enable_thinking = false %}"}),
        }
    ).encode()

    t0 = time.time()
    req = Request(
        f"{SERVER}/v1/chat/completions", data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        resp = urlopen(req, timeout=120)
        elapsed = time.time() - t0
        data = json.loads(resp.read())
    except Exception as e:
        elapsed = time.time() - t0
        return {"error": str(e), "elapsed": elapsed}

    choice = data["choices"][0]
    msg = choice["message"]
    content = msg.get("content", "") or ""
    reasoning = msg.get("reasoning_content", "") or ""
    usage = data.get("usage", {})
    pt = usage.get("prompt_tokens", 0)
    ct = usage.get("completion_tokens", 0)

    return {
        "content": content,
        "reasoning": reasoning,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "elapsed": elapsed,
        "gen_tps": ct / elapsed if elapsed > 0 else 0,
        "prompt_tps": pt / elapsed if elapsed > 0 else 0,
    }


TESTS = {
    "code": {
        "name": "Code (is_palindrome)",
        "system": "You are a helpful coding assistant.",
        "user": "Write a Python function `is_palindrome(s)` that checks if a string is a palindrome (alphanumeric only, case-insensitive). Include a docstring.",
    },
    "reasoning": {
        "name": "Reasoning (water jug)",
        "system": "You are a helpful assistant.",
        "user": "You have a 3-gallon jug and a 5-gallon jug. How do you measure exactly 4 gallons? Walk through step by step.",
    },
    "summarization": {
        "name": "Summarization",
        "system": "You are a helpful assistant. Summarize the key points concisely.",
        "user": "Summarize this text in 3-4 bullet points:\n\nThe Transformer architecture revolutionized natural language processing by introducing a self-attention mechanism that processes all tokens in parallel rather than sequentially. Unlike RNNs and LSTMs that process sequences step by step, Transformers can capture long-range dependencies more effectively. The architecture consists of an encoder and decoder, each made up of multiple layers of multi-head self-attention and feed-forward neural networks. Positional encodings are added to input embeddings because the model has no inherent sense of token order. Layer normalization and residual connections help stabilize training. The original Transformer paper (Vaswani et al., 2017) achieved state-of-the-art results on machine translation tasks. Since then, the architecture has been adapted into models like BERT (encoder-only), GPT (decoder-only), and T5 (encoder-decoder). Key innovations include scaled dot-product attention, multi-head attention allowing the model to focus on different representation subspaces, and parallel processing that enables efficient GPU utilization.",
    },
    "instruction": {
        "name": "Instruction (list vs tuple)",
        "system": "You are a helpful assistant.",
        "user": "Explain the difference between lists and tuples in Python. Give 3 key differences.",
    },
    "math": {
        "name": "Math (system of equations)",
        "system": "You are a helpful assistant.",
        "user": "If x + 2y = 10 and 2x - y = 5, solve for x and y. Show your work.",
    },
    "knowledge": {
        "name": "Knowledge (ML concepts)",
        "system": "You are a helpful assistant.",
        "user": "What are the key differences between supervised and unsupervised learning? Give examples of each.",
    },
}


def run_all(mode_label, thinking):
    os.makedirs(f"{OUT_DIR}/{mode_label}", exist_ok=True)
    results = []
    for key, cfg in TESTS.items():
        name = cfg["name"]
        msgs = [
            {"role": "system", "content": cfg["system"]},
            {"role": "user", "content": cfg["user"]},
        ]
        print(f"\n  [{mode_label}] {name} ...", flush=True)
        r = chat(msgs)
        if "error" in r:
            print(f"    ERROR: {r['error']}")
            results.append({"test": name, **r})
            continue

        with open(f"{OUT_DIR}/{mode_label}/{key}.txt", "w") as f:
            f.write(f"=== REASONING ===\n{r['reasoning']}\n\n=== CONTENT ===\n{r['content']}\n")
            f.write("\n\n=== METRICS ===\n")
            f.write(f"Prompt tokens: {r['prompt_tokens']}\n")
            f.write(f"Completion tokens: {r['completion_tokens']}\n")
            f.write(f"Time: {r['elapsed']:.1f}s\n")
            f.write(f"Gen t/s: {r['gen_tps']:.1f}\n")

        display = r["reasoning"] or r["content"]
        print(
            f"    Tokens: {r['prompt_tokens']}p + {r['completion_tokens']}g = {r['prompt_tokens']+r['completion_tokens']}t | "
            f"Time: {r['elapsed']:.1f}s | Gen: {r['gen_tps']:.1f} t/s"
        )
        preview = display[:120].replace("\n", " ").strip()
        print(f"    Preview: {preview}...")

        results.append({"test": name, "key": key, **r})
    return results


if __name__ == "__main__":
    all_results = {}

    print("=" * 70)
    print("  BENCHMARK: Qwen3.5-0.8B-Q8_0 on Apple M1 (8GB)")
    print("=" * 70)

    # Mode 1: Thinking ON (default)
    print("\n>>> MODE 1: Thinking ON (default) <<<")
    all_results["thinking_on"] = run_all("thinking_on", thinking=True)

    # Mode 2: Thinking OFF
    print("\n>>> MODE 2: Thinking OFF (chat_template) <<<")
    all_results["thinking_off"] = run_all("thinking_off", thinking=False)

    # Summary
    print("\n\n" + "=" * 70)
    print("  SUMMARY TABLE")
    print("=" * 70)
    print(f"{'Test':35s} {'Mode':14s} {'Gen t/s':8s} {'Time':8s} {'Tokens':7s} {'Reasoning':9s}")
    print("-" * 85)
    for mode_key, mode_label in [("thinking_on", "Thinking ON"), ("thinking_off", "Thinking OFF")]:
        for tr in all_results[mode_key]:
            if "error" in tr:
                print(
                    f"{tr['test']:35s} {mode_label:14s} {'ERR':>8s} {tr.get('elapsed',0):7.1f}s {'':7s} {'':9s}"
                )
            else:
                rl = f"{len(tr['reasoning'])}ch" if tr["reasoning"] else "none"
                print(
                    f"{tr['test']:35s} {mode_label:14s} {tr['gen_tps']:8.1f} {tr['elapsed']:7.1f}s {tr['completion_tokens']:5d}t {rl:>9s}"
                )

    print("-" * 85)

    with open(f"{OUT_DIR}/results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull outputs saved to {OUT_DIR}/")

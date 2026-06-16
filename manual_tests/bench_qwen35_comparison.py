#!/usr/bin/env python3
"""Benchmark Qwen3.5-2B-UD-Q4_K_XL vs Qwen_Qwen3.5-2B-Q4_K_M."""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

API_URL = "http://127.0.0.1:8080/v1/chat/completions"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = {}
MODEL_LABELS = {"UD-XL": "Qwen3.5-2B-UD-Q4_K_XL", "K_M": "Qwen_Qwen3.5-2B-Q4_K_M"}

BASE_ARGS = [
    "llama-server",
    "--host",
    "127.0.0.1",
    "--port",
    "8080",
    "--ctx-size",
    "4096",
    "--n-gpu-layers",
    "99",
    "--flash-attn",
    "on",
    "--temp",
    "0.5",
    "--repeat-penalty",
    "1.1",
    "--threads",
    "4",
]


def wait_for_server(timeout=90):
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(
                API_URL,
                data=json.dumps(
                    {
                        "model": "t",
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    }
                ).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=3)
            return True
        except:
            time.sleep(1)
    return False


def query(messages, max_tokens=512):
    payload = {"model": "t", "messages": messages, "max_tokens": max_tokens, "temperature": 0.3}
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    resp = urllib.request.urlopen(req, timeout=120)
    elapsed = time.time() - t0
    data = json.loads(resp.read())
    content = data["choices"][0]["message"].get("content") or data["choices"][0]["message"].get(
        "reasoning_content", ""
    )
    usage = data.get("usage", {})
    tok_in = usage.get("prompt_tokens", 0)
    tok_out = usage.get("completion_tokens", 0)
    prompt_t_s = tok_in / elapsed if elapsed > 0 and tok_in > 0 else 0
    gen_t_s = tok_out / elapsed if elapsed > 0 and tok_out > 0 else 0
    return content, tok_in, tok_out, elapsed, prompt_t_s, gen_t_s


TEST_CASES = {
    "code": {
        "messages": [
            {
                "role": "user",
                "content": "Write a Python function is_palindrome(s) that checks if a string is a palindrome (alphanumeric only, case-insensitive). Return only the function code.",
            }
        ],
        "max_tokens": 300,
    },
    "reasoning": {
        "messages": [
            {
                "role": "user",
                "content": "You have a 3-gallon jug and a 5-gallon jug. How do you measure exactly 4 gallons? Think step by step.",
            }
        ],
        "max_tokens": 500,
    },
    "summary": {
        "messages": [
            {
                "role": "user",
                "content": "Explain the key differences between lists and tuples in Python in 3-4 bullet points. Be concise.",
            }
        ],
        "max_tokens": 300,
    },
    "instruction": {
        "messages": [
            {
                "role": "user",
                "content": "Explain the difference between = and == in Python. Be concise.",
            }
        ],
        "max_tokens": 300,
    },
}


def run_model(label):
    model_path = os.path.join(ROOT, "bin/models", f"{MODEL_LABELS[label]}.gguf")
    print(f"\n{'='*60}\n  MODEL: {label} ({MODEL_LABELS[label]})\n{'='*60}")
    cmd = BASE_ARGS + ["--model", model_path]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_for_server():
        proc.kill()
        print("  FAILED: server didn't start")
        return {}

    print("  Warming up...")
    try:
        query([{"role": "user", "content": "Say ready"}], max_tokens=5)
    except:
        pass
    time.sleep(1)

    results = {}
    for name, tc in TEST_CASES.items():
        print(f"\n  --- {name.upper()} ---")
        try:
            content, tok_in, tok_out, elapsed, pt_s, gt_s = query(tc["messages"], tc["max_tokens"])
            print(f"  Tokens: {tok_in} in → {tok_out} out | Time: {elapsed:.1f}s")
            print(f"  Prompt: {pt_s:.1f} t/s | Gen: {gt_s:.1f} t/s")
            print(f"  Output preview: {content[:150].strip()}")
            results[name] = {
                "prompt_t_s": round(pt_s, 1),
                "gen_t_s": round(gt_s, 1),
                "elapsed": round(elapsed, 1),
                "tokens_in": tok_in,
                "tokens_out": tok_out,
            }
        except Exception as e:
            print(f"  ERROR: {e}")
            results[name] = {"error": str(e)}

    proc.terminate()
    proc.wait()
    time.sleep(2)
    return results


if __name__ == "__main__":
    subprocess.run("lsof -ti :8080 | xargs kill -9 2>/dev/null", shell=True)
    time.sleep(1)
    for label in ["UD-XL", "K_M"]:
        RESULTS[label] = run_model(label)
        subprocess.run("lsof -ti :8080 | xargs kill -9 2>/dev/null", shell=True)
        time.sleep(1)

    print("\n\n" + "=" * 60)
    print("  COMPARISON SUMMARY")
    print("=" * 60)
    h = f"\n{'Test':<15} {'UD-XL Gen':<14} {'K_M Gen':<14} {'UD-XL Time':<14} {'K_M Time':<14}"
    print(h + "\n" + "-" * 71)
    for name in TEST_CASES:
        u = RESULTS.get("UD-XL", {}).get(name, {})
        k = RESULTS.get("K_M", {}).get(name, {})
        print(
            f"{name:<15} {str(u.get('gen_t_s','N/A'))+' t/s':<14} {str(k.get('gen_t_s','N/A'))+' t/s':<14} {str(u.get('elapsed','N/A'))+'s':<14} {str(k.get('elapsed','N/A'))+'s':<14}"
        )

    out = os.path.join(ROOT, "manual_tests/qwen35_comparison_results.json")
    with open(out, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\nResults saved to {out}")

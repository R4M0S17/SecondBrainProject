#!/usr/bin/env python3
"""Compare output quality between UD-XL and K_M models."""
import json
import os
import subprocess
import time
import urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def query(messages, max_tokens=400):
    payload = {"model": "t", "messages": messages, "max_tokens": max_tokens, "temperature": 0.3}
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=120)
    data = json.loads(resp.read())
    content = data["choices"][0]["message"].get("content") or data["choices"][0]["message"].get(
        "reasoning_content", ""
    )
    return content


def run_server(model_file):
    subprocess.run("lsof -ti :8080 | xargs kill -9 2>/dev/null", shell=True)
    time.sleep(1)
    cmd = [
        "llama-server",
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
        "--model",
        f"bin/models/{model_file}",
        "--ctx-size",
        "4096",
        "--n-gpu-layers",
        "99",
        "--flash-attn",
        "on",
        "--temp",
        "0.3",
        "--repeat-penalty",
        "1.1",
        "--threads",
        "4",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        try:
            urllib.request.urlopen(
                urllib.request.Request(
                    API,
                    data=json.dumps(
                        {
                            "model": "t",
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 1,
                        }
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                ),
                timeout=3,
            )
            return proc
        except:
            time.sleep(1)
    return None


prompt = [
    {
        "role": "user",
        "content": "Write a Python function is_palindrome(s) that checks if a string is a palindrome (alphanumeric only, case-insensitive). Return only the function code with a brief docstring.",
    }
]

for label, model_file in [
    ("UD-XL", "Qwen3.5-2B-UD-Q4_K_XL.gguf"),
    ("K_M", "Qwen_Qwen3.5-2B-Q4_K_M.gguf"),
]:
    proc = run_server(model_file)
    if not proc:
        print(f"{label}: SERVER FAILED")
        continue
    output = query(prompt, 400)
    proc.terminate()
    proc.wait()
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    # Strip thinking preamble
    clean = output.split("Here's the")[-1] if "Here's the" in output else output
    clean = clean.split("**Final Code:**")[-1] if "**Final Code:**" in clean else clean
    clean = clean.split("```")[1] if "```" in clean else clean
    print(clean[:600])

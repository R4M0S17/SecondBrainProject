"""Verify which GGUF files referenced by config and ModelManager actually exist."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = Path(os.environ.get("CEREBRO_MODELS_DIR", str(ROOT / "bin" / "models")))
EXPECTED = {
    "router": os.environ.get("CEREBRO_ROUTER_MODEL", "SmolLM2-135M-Instruct-Q4_K_M.gguf"),
    "general": os.environ.get("CEREBRO_GENERAL_MODEL", "Llama-3.2-3B-Instruct-Q4_K_M.gguf"),
    "code": os.environ.get("CEREBRO_CODE_MODEL", "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf"),
    "embed": os.environ.get("CEREBRO_EMBED_MODEL", "v5-nano-retrieval-Q4_K_M.gguf"),
    "chat.args": "Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf",  # config/chat.args
}

print(f"models dir: {MODELS_DIR}")
present = {p.name.lower(): p for p in MODELS_DIR.glob("*.gguf")} if MODELS_DIR.is_dir() else {}
missing: list[tuple[str, str]] = []
for role, name in EXPECTED.items():
    hit = name.lower() in present
    flag = "OK " if hit else "MISS"
    print(f"  [{flag}] {role:10}  {name}")
    if not hit:
        missing.append((role, name))
print("\nfiles actually present:")
for n in sorted(present):
    print(f"  - {present[n].name}  ({present[n].stat().st_size / 2**30:.2f} GB)")
sys.exit(0 if not missing else 2)

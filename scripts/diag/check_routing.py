"""Send a fixed query against the running backend and report which agent + tools answered."""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get("CEREBRO_URL", "http://localhost:7842")
QUERIES = [
    ("date", "¿Qué día es hoy?"),
    ("calendar", "¿Cuál es mi próximo evento del calendario?"),
    ("birthday", "¿Cuál es el próximo cumpleaños?"),
]
fail = 0
for tag, q in QUERIES:
    body = json.dumps({"question": q, "agent": "auto"}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/query",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"[FAIL] {tag}: {e}")
        fail += 1
        continue
    tools = [t["name"] for t in data["metadata"]["tools_called"]]
    print(f"[{tag}] tools={tools}")
    print(f"  answer: {data['answer'][:300]}")
sys.exit(0 if not fail else 5)

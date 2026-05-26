#!/usr/bin/env python3
"""Live smoke: file search with llama.cpp engine running on :8080.

Starts llama-server if needed, verifies /health, runs the file-search fast path,
then stops llama-server (pkill) so the port is free when finished.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LLAMA_BASE = os.getenv("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080").rstrip("/")
LLAMA_HEALTH = f"{LLAMA_BASE}/health"


def _llama_up() -> bool:
    try:
        return httpx.get(LLAMA_HEALTH, timeout=2.0).status_code == 200
    except Exception:
        return False


def _start_engine() -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        ["./bin/start_engine.sh", "chat"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop_llama(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is not None and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    subprocess.run(["pkill", "-f", "llama-server"], check=False)


def _run_fast_path(tmp_dir: Path) -> None:
    from core.agents.file_search_fast_path import try_file_search_fast_path

    # Probe in ~/Desktop to validate that the fast path is authorized there
    # by default (without requiring CEREBRO_AUTHORIZED_READ_PATHS).
    desktop_dir = Path.home() / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    probe = desktop_dir / "llama_search_probe_desktop.txt"
    probe.write_text("llama_cpp_file_search_ok", encoding="utf-8")

    os.environ.pop("CEREBRO_AUTHORIZED_READ_PATHS", None)

    try:
        answer = try_file_search_fast_path(
            f"busca el archivo llamado {probe.name}",
            ["search_files"],
        )
        if not answer or probe.name not in answer:
            raise SystemExit(f"FAIL: fast path did not find probe file:\n{answer!r}")
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            # Best-effort cleanup; don't fail the test if Desktop is read-only.
            pass
    print("OK: file search fast path (llama.cpp was up for stack readiness)")
    print(answer[:500])


def main() -> int:
    started: subprocess.Popen[bytes] | None = None
    if not _llama_up():
        print("Starting llama.cpp engine…")
        started = _start_engine()
        for _ in range(90):
            if _llama_up():
                break
            time.sleep(1)
        else:
            _stop_llama(started)
            raise SystemExit("FAIL: llama-server not healthy on :8080")
    else:
        print("llama.cpp already running on", LLAMA_BASE)

    tmp = ROOT / ".tmp_file_search_live"
    tmp.mkdir(exist_ok=True)
    try:
        _run_fast_path(tmp)
    finally:
        print("Stopping llama-server…")
        _stop_llama(started)
        if _llama_up():
            print("WARN: llama-server still responding after stop")
        else:
            print("llama.cpp stopped (port 8080 free)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

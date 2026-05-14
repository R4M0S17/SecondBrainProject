"""Print per-process RSS for everything Cerebro-related plus system memory."""

from __future__ import annotations

import sys

import psutil

CEREBRO_HINTS = ("llama-server", "uvicorn", "python", "main.py", "tauri", "WebKit")


def main() -> int:
    vm = psutil.virtual_memory()
    print(
        f"system: total={vm.total / 2**30:.2f}GB used={(vm.total - vm.available) / 2**30:.2f}GB "
        f"available={vm.available / 2**30:.2f}GB pressure="
        f"{'critical' if vm.available / 2**30 < 1.0 else 'warn' if vm.available / 2**30 < 1.8 else 'ok'}"
    )
    rows: list[tuple[float, int, str]] = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or [p.info.get("name") or ""])
            if not any(h in cmd for h in CEREBRO_HINTS):
                continue
            rss = p.memory_info().rss / 2**20
            rows.append((rss, p.info["pid"], cmd[:120]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(reverse=True)
    print(f"{'RSS_MB':>8}  {'PID':>6}  CMD")
    for rss, pid, cmd in rows[:20]:
        print(f"{rss:8.1f}  {pid:6}  {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

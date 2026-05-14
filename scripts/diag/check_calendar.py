"""Probe Apple Calendar Automation permission without crashing the agent."""

from __future__ import annotations

import json
import platform
import subprocess
import sys

if platform.system() != "Darwin":
    print("not-macos")
    sys.exit(0)

JXA = r"""
(function () {
    var app = Application("Calendar");
    try {
        var names = app.calendars().map(function (c) { return c.name(); });
        return JSON.stringify({ ok: true, calendars: names });
    } catch (e) {
        return JSON.stringify({ ok: false, error: e.toString() });
    }
})()
"""

try:
    r = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", JXA],
        capture_output=True,
        text=True,
        timeout=5,
    )
    raw = (r.stdout or "").strip() or (r.stderr or "").strip()
    print(raw)
    if r.returncode != 0:
        sys.exit(3)
    try:
        data = json.loads(r.stdout.strip() or "{}")
    except json.JSONDecodeError:
        data = {"ok": False, "error": "invalid-json"}
    sys.exit(0 if data.get("ok") else 3)
except subprocess.TimeoutExpired:
    print(json.dumps({"ok": False, "error": "timeout-after-5s"}))
    sys.exit(4)

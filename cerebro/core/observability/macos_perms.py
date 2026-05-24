"""One-shot macOS Automation / Calendar permission probes (no core.inference imports)."""

from __future__ import annotations

import asyncio
import json
import platform
import re

# Same JXA shape as scripts/diag/check_calendar.py (IIFE returns JSON string).
_CALENDAR_PROBE_JXA = r"""
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


def _automation_denied_hint(text: str) -> bool:
    t = text.lower()
    return bool(
        re.search(r"\(-1743\)|\b1743\b", text)
        or "not allowed" in t
        or "isn't allowed to send" in t
        or "not authorized" in t
        or "privilege" in t
    )


async def probe_calendar_permission() -> str:
    """Return ok | denied | unknown | not_macos for Apple Calendar read access."""
    if platform.system() != "Darwin":
        return "not_macos"

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript",
            "-l",
            "JavaScript",
            "-e",
            _CALENDAR_PROBE_JXA,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except TimeoutError:
                pass
            return "unknown"
    except (FileNotFoundError, OSError):
        return "unknown"

    stderr = (stderr_b or b"").decode(errors="replace")
    stdout = (stdout_b or b"").decode(errors="replace").strip()
    if proc.returncode != 0:
        return "denied" if _automation_denied_hint(stderr or stdout) else "unknown"

    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return "unknown"

    if data.get("ok"):
        return "ok"
    err = str(data.get("error", ""))
    return "denied" if _automation_denied_hint(err) else "unknown"

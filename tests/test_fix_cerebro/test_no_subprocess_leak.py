"""Phase 8.6 — Hung osascript child must be killed (same path ContextEnricher uses)."""

from __future__ import annotations

import asyncio
import sys

import psutil
import pytest

from integrations.calendar_reader import AppleCalendarBackend


@pytest.mark.asyncio
async def test_apple_calendar_async_timeout_kills_child_no_sentinel_leak(
    tmp_path, monkeypatch
) -> None:
    """Simulate hung osascript via slow python script; Apple backend kills on timeout — no leaked child."""
    monkeypatch.setattr("integrations.calendar_reader.platform.system", lambda: "Darwin")

    sentinel = "CEREBRO_PHASE8_SENTINEL_SLEEP"
    script = tmp_path / f"{sentinel}.py"
    script.write_text("import time\ntime.sleep(999)\n", encoding="utf-8")

    real_exec = asyncio.create_subprocess_exec

    async def tracing_exec(program: str, *args: object, **kwargs: object):
        if program == "osascript":
            return await real_exec(
                sys.executable,
                str(script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        return await real_exec(program, *args, **kwargs)

    monkeypatch.setattr(
        "integrations.calendar_reader.asyncio.create_subprocess_exec",
        tracing_exec,
    )

    backend = AppleCalendarBackend()
    result = await backend.get_upcoming_events_async(24, communicate_timeout=0.25)
    assert result.status == "timeout"

    await asyncio.sleep(0.4)
    needle = str(script)
    try:
        for p in psutil.process_iter(["cmdline"]):
            try:
                cl = p.info.get("cmdline") or []
                joined = " ".join(str(x) for x in cl)
                if needle in joined or sentinel in joined:
                    pytest.fail(f"subprocess still alive: pid={p.pid} cmdline={cl}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except PermissionError:
        pytest.skip("psutil.process_iter blocked in this environment")

"""Tests for core.observability.macos_perms."""

from __future__ import annotations

import platform

import pytest

from core.observability.macos_perms import probe_calendar_permission


@pytest.mark.asyncio
async def test_probe_calendar_not_macos():
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(platform, "system", lambda: "Linux")
        out = await probe_calendar_permission()
    assert out == "not_macos"


@pytest.mark.asyncio
async def test_probe_calendar_returns_allowed_status_on_macos(monkeypatch):
    if platform.system() != "Darwin":
        pytest.skip("macOS-only live probe")

    out = await probe_calendar_permission()
    assert out in {"ok", "denied", "unknown"}

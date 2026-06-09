from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.inference.inference_warnings import clear_inference_warnings, consume_inference_warnings
from core.inference.providers.llamacpp_provider import LlamaCppChatProvider
from core.inference.ram_preflight import RAM_WARNING_CRITICAL, RAM_WARNING_WARN, run_ram_preflight
from core.observability.ram_monitor import RamMonitor


def test_run_ram_preflight_critical_records_warning_and_purges_cache(tmp_path, monkeypatch):
    clear_inference_warnings()
    cache = tmp_path / "chat.cache"
    cache.write_text("warm", encoding="utf-8")
    monkeypatch.setenv("CEREBRO_PROMPT_CACHE_PATH", str(cache))

    monitor = MagicMock(spec=RamMonitor)
    monitor.snapshot.return_value = {
        "pressure": "critical",
        "used_gb": 7.2,
        "available_gb": 0.4,
        "total_gb": 8.0,
    }

    codes = run_ram_preflight(monitor)

    assert codes == [RAM_WARNING_CRITICAL]
    assert consume_inference_warnings() == [RAM_WARNING_CRITICAL]
    assert not cache.exists()


def test_run_ram_preflight_warn_only():
    clear_inference_warnings()
    monitor = MagicMock(spec=RamMonitor)
    monitor.snapshot.return_value = {
        "pressure": "warn",
        "used_gb": 6.5,
        "available_gb": 1.2,
        "total_gb": 8.0,
    }

    codes = run_ram_preflight(monitor)

    assert codes == [RAM_WARNING_WARN]
    assert consume_inference_warnings() == [RAM_WARNING_WARN]


def test_run_ram_preflight_sets_ram_pressure_contextvar(monkeypatch):
    from core.observability.ram_monitor import (
        current_ram_pressure,
        set_ram_pressure,
    )

    set_ram_pressure("ok")
    assert current_ram_pressure() == "ok"

    monitor = MagicMock(spec=RamMonitor)
    monitor.snapshot.return_value = {
        "pressure": "critical",
        "used_gb": 7.2,
        "available_gb": 0.4,
        "total_gb": 8.0,
    }

    run_ram_preflight(monitor)

    assert current_ram_pressure() == "critical"


def test_run_ram_preflight_sets_warn_pressure(monkeypatch):
    from core.observability.ram_monitor import current_ram_pressure, set_ram_pressure

    set_ram_pressure("ok")

    monitor = MagicMock(spec=RamMonitor)
    monitor.snapshot.return_value = {
        "pressure": "warn",
        "used_gb": 6.5,
        "available_gb": 1.2,
        "total_gb": 8.0,
    }

    run_ram_preflight(monitor)

    assert current_ram_pressure() == "warn"


@pytest.mark.asyncio
async def test_complete_still_returns_under_ram_critical(mocker):
    clear_inference_warnings()

    provider = LlamaCppChatProvider(model="test.gguf", profile="chat")
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"total_tokens": 10},
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)

    mock_preflight = mocker.patch(
        "core.inference.providers.llamacpp_provider.run_ram_preflight",
        return_value=[RAM_WARNING_CRITICAL],
    )

    result = await provider.complete([{"role": "user", "content": "hi"}])

    assert result == "ok"
    mock_preflight.assert_called_once()

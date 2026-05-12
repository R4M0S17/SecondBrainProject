from __future__ import annotations

import asyncio
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.inference.model_manager as mm_module
from core.inference.model_manager import ModelManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(pid: int = 1234) -> MagicMock:
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = pid
    proc.terminate = MagicMock()
    proc.wait = MagicMock()
    proc.kill = MagicMock()
    return proc


def _patch_healthy():
    """Patch _wait_healthy so it returns immediately."""
    return patch.object(
        ModelManager, "_wait_healthy", new_callable=lambda: lambda self, *a, **k: asyncio.sleep(0)
    )


# ---------------------------------------------------------------------------
# test_start_launches_router
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_launches_router():
    manager = ModelManager()
    router_proc = _make_proc()

    with (
        patch("subprocess.Popen", return_value=router_proc) as mock_popen,
        patch.object(ModelManager, "_wait_healthy", new=AsyncMock()),
        patch("asyncio.create_task"),
    ):
        await manager.start()

    # call_args_list[0] = router, call_args_list[1] = embed server
    args = mock_popen.call_args_list[0][0][0]
    assert args[0] == mm_module._LLAMA_SERVER
    assert "--model" in args
    model_arg = args[args.index("--model") + 1]
    assert mm_module._ROUTER_MODEL in model_arg
    assert "--port" in args
    port_arg = args[args.index("--port") + 1]
    assert port_arg == str(mm_module._ROUTER_PORT)


# ---------------------------------------------------------------------------
# test_ensure_specialist_general
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_specialist_general():
    manager = ModelManager()
    spec_proc = _make_proc(pid=2000)

    with (
        patch("subprocess.Popen", return_value=spec_proc) as mock_popen,
        patch.object(ModelManager, "_wait_healthy", new=AsyncMock()),
    ):
        port = await manager.ensure_specialist("general")

    assert port == mm_module._SPECIALIST_PORT
    args = mock_popen.call_args[0][0]
    model_arg = args[args.index("--model") + 1]
    assert mm_module._GENERAL_MODEL in model_arg
    port_arg = args[args.index("--port") + 1]
    assert port_arg == str(mm_module._SPECIALIST_PORT)


# ---------------------------------------------------------------------------
# test_ensure_specialist_code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_specialist_code():
    manager = ModelManager()
    spec_proc = _make_proc(pid=2001)

    with (
        patch("subprocess.Popen", return_value=spec_proc) as mock_popen,
        patch.object(ModelManager, "_wait_healthy", new=AsyncMock()),
    ):
        port = await manager.ensure_specialist("code")

    assert port == mm_module._SPECIALIST_PORT
    args = mock_popen.call_args[0][0]
    model_arg = args[args.index("--model") + 1]
    assert mm_module._CODE_MODEL in model_arg


# ---------------------------------------------------------------------------
# test_ensure_specialist_unknown_role_falls_back_to_general
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_specialist_unknown_role_falls_back_to_general():
    manager = ModelManager()
    spec_proc = _make_proc()

    with (
        patch("subprocess.Popen", return_value=spec_proc) as mock_popen,
        patch.object(ModelManager, "_wait_healthy", new=AsyncMock()),
    ):
        await manager.ensure_specialist("calendar")

    args = mock_popen.call_args[0][0]
    model_arg = args[args.index("--model") + 1]
    assert mm_module._GENERAL_MODEL in model_arg


# ---------------------------------------------------------------------------
# test_swap_kills_old_before_loading_new
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_swap_kills_old_before_loading_new():
    manager = ModelManager()
    first_proc = _make_proc(pid=3000)
    second_proc = _make_proc(pid=3001)

    popen_side_effects = [first_proc, second_proc]

    with (
        patch("subprocess.Popen", side_effect=popen_side_effects),
        patch.object(ModelManager, "_wait_healthy", new=AsyncMock()),
    ):
        await manager.ensure_specialist("general")
        await manager.ensure_specialist("code")

    first_proc.terminate.assert_called_once()
    assert manager._specialist_role == "code"
    assert manager._specialist_proc is second_proc


# ---------------------------------------------------------------------------
# test_ensure_specialist_same_role_skips_reload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_specialist_same_role_skips_reload():
    manager = ModelManager()
    proc = _make_proc()

    with (
        patch("subprocess.Popen", return_value=proc) as mock_popen,
        patch.object(ModelManager, "_wait_healthy", new=AsyncMock()),
    ):
        await manager.ensure_specialist("general")
        await manager.ensure_specialist("general")

    assert mock_popen.call_count == 1


# ---------------------------------------------------------------------------
# test_watchdog_unloads_after_timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watchdog_unloads_after_timeout():
    manager = ModelManager()
    proc = _make_proc(pid=4000)
    manager._specialist_proc = proc
    manager._specialist_role = "general"

    # Put last_activity far enough in the past
    manager._last_activity = 0.0

    with patch("time.monotonic", return_value=mm_module._SWAP_TIMEOUT + 1):
        with patch("asyncio.sleep", new=AsyncMock(side_effect=[None, asyncio.CancelledError()])):
            try:
                await manager._watchdog()
            except asyncio.CancelledError:
                pass

    proc.terminate.assert_called_once()
    assert manager._specialist_proc is None
    assert manager._specialist_role is None


# ---------------------------------------------------------------------------
# test_stop_kills_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_kills_all():
    manager = ModelManager()
    router_proc = _make_proc(pid=5000)
    spec_proc = _make_proc(pid=5001)
    manager._router_proc = router_proc
    manager._specialist_proc = spec_proc

    mock_task = MagicMock()
    mock_task.cancel = MagicMock()

    async def fake_await():
        raise asyncio.CancelledError()

    mock_task.__await__ = fake_await
    manager._watchdog_task = asyncio.ensure_future(asyncio.sleep(0))
    manager._watchdog_task.cancel()

    await manager.stop()

    router_proc.terminate.assert_called_once()
    spec_proc.terminate.assert_called_once()
    assert manager._router_proc is None
    assert manager._specialist_proc is None


# ---------------------------------------------------------------------------
# test_start_launches_embed_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_launches_embed_server():
    manager = ModelManager()
    router_proc = _make_proc(pid=7000)
    embed_proc = _make_proc(pid=7001)
    call_count = 0

    def _side_effect(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        return router_proc if call_count == 1 else embed_proc

    with (
        patch("subprocess.Popen", side_effect=_side_effect) as mock_popen,
        patch.object(ModelManager, "_wait_healthy", new=AsyncMock()),
        patch("asyncio.create_task"),
    ):
        await manager.start()

    assert mock_popen.call_count == 2
    embed_cmd = mock_popen.call_args_list[1][0][0]
    assert "--embedding" in embed_cmd
    port_idx = embed_cmd.index("--port")
    assert embed_cmd[port_idx + 1] == str(mm_module._EMBED_PORT)
    assert mm_module._EMBED_MODEL in embed_cmd[embed_cmd.index("--model") + 1]


# ---------------------------------------------------------------------------
# test_stop_kills_embed_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_kills_embed_server():
    manager = ModelManager()
    router_proc = _make_proc(pid=8000)
    embed_proc = _make_proc(pid=8001)
    manager._router_proc = router_proc
    manager._embed_proc = embed_proc

    manager._watchdog_task = asyncio.ensure_future(asyncio.sleep(0))
    manager._watchdog_task.cancel()

    await manager.stop()

    embed_proc.terminate.assert_called_once()
    assert manager._embed_proc is None

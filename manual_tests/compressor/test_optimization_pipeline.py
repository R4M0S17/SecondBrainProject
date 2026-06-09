"""Integration tests for the async connection pool and disconnection safety routines.

Tests:
  1. Injected shared client is used and survives engine operations.
  2. _guarded_token_iter raises InferenceTimeoutError on stall.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from core.inference.engine import (
    InferenceEngine,
    InferenceTimeoutError,
    _guarded_token_iter,
)

# ── Test 1: Injected shared client lifecycle ──────────────────────────────────


@pytest.mark.asyncio
async def test_injected_shared_client_not_closed(mocker):
    """Engine must use the injected client and NOT close it after complete/embed."""

    shared = AsyncMock(spec=httpx.AsyncClient)
    shared.is_closed = False

    engine = InferenceEngine(model="test-model", http_client=shared)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "ok", "done": True}
    mock_response.raise_for_status = MagicMock()

    shared.post = AsyncMock(return_value=mock_response)

    # complete() uses the shared client
    result = await engine.complete("hello")
    assert result == "ok"
    assert shared.post.called
    # Client must NOT be closed — lifespan owns the lifecycle
    assert not shared.is_closed

    # embed() uses the shared client too
    mock_emb = MagicMock()
    mock_emb.status_code = 200
    mock_emb.json.return_value = {"embedding": [0.1] * 384}
    mock_emb.raise_for_status = MagicMock()
    shared.post = AsyncMock(return_value=mock_emb)

    emb = await engine.embed("text")
    assert len(emb) == 384
    assert not shared.is_closed


# ── Test 2: Stall guard raises InferenceTimeoutError ──────────────────────────


@pytest.mark.asyncio
async def test_guarded_token_iter_stall_raises_timeout():
    """_guarded_token_iter raises InferenceTimeoutError after stall_timeout_s."""

    async def stall_generator():
        yield "tok1\n"
        await asyncio.sleep(999)

    with pytest.raises(InferenceTimeoutError, match="stalled"):
        async for _ in _guarded_token_iter(
            stall_generator().__aiter__(),
            stall_timeout_s=0.05,
        ):
            pass


@pytest.mark.asyncio
async def test_guarded_token_iter_passes_tokens():
    """_guarded_token_iter yields lines normally when tokens arrive in time."""

    async def fast_generator():
        yield "foo\n"
        yield "bar\n"

    collected: list[str] = []
    async for line in _guarded_token_iter(
        fast_generator().__aiter__(),
        stall_timeout_s=5.0,
    ):
        collected.append(line)

    assert collected == ["foo\n", "bar\n"]


# ── Test 3: stream() propagates CancelledError ────────────────────────────────


@pytest.mark.asyncio
async def test_stream_cancelled_error_propagates(mocker):
    """CancelledError inside stream() must not be swallowed."""

    engine = InferenceEngine(model="test-model")

    async def _break_stream(*args, **kwargs):
        yield "tok1"
        raise asyncio.CancelledError

    mocker.patch.object(engine, "stream", _break_stream)

    with pytest.raises(asyncio.CancelledError):
        async for _ in engine.stream("prompt"):
            pass

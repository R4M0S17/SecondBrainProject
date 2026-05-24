"""Tests for Phase 7 — Context Distillation, Sliding Window, Prompt Cache."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.memory.short_term import ShortTermStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_provider(summary: str = "Resumen de sesión.") -> MagicMock:
    p = MagicMock()
    p.complete = AsyncMock(return_value=summary)
    return p


def _mock_long_term() -> MagicMock:
    lt = MagicMock()
    lt.store_episode = AsyncMock(return_value="fake-chunk-id")
    return lt


def _push_messages(store: ShortTermStore, n: int, chars_each: int = 400) -> None:
    for i in range(n):
        store.push_message({"role": "user", "content": "x" * chars_each})
        store.push_message({"role": "assistant", "content": "y" * chars_each})


# ---------------------------------------------------------------------------
# 7.1 — Context Distillation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distill_triggers_when_above_75_percent():
    store = ShortTermStore()
    # ctx_size=2048 → threshold = 1536 tokens → 6144 chars
    # push enough to exceed: 5 pairs × 2 × 400 chars = 4000 chars → ~1000 tokens (below)
    # push more: 10 pairs × 2 × 400 = 8000 chars → ~2000 tokens (above 75% of 2048)
    _push_messages(store, n=10, chars_each=400)
    provider = _mock_provider("Summary of past conversation.")

    triggered = await store.distill_if_needed(provider, ctx_size=2048)

    assert triggered is True
    provider.complete.assert_called_once()


@pytest.mark.asyncio
async def test_distill_does_not_trigger_when_below_75_percent():
    store = ShortTermStore()
    # 1 pair × 2 × 20 chars = 40 chars → ~10 tokens — well below threshold
    _push_messages(store, n=1, chars_each=20)
    provider = _mock_provider()

    triggered = await store.distill_if_needed(provider, ctx_size=2048)

    assert triggered is False
    provider.complete.assert_not_called()


@pytest.mark.asyncio
async def test_distill_collapses_messages_to_single_system_message():
    store = ShortTermStore()
    _push_messages(store, n=10, chars_each=400)
    provider = _mock_provider("Resumen comprimido.")

    await store.distill_if_needed(provider, ctx_size=2048)

    ctx = store.get_context()
    assert len(ctx.active_messages) == 1
    assert ctx.active_messages[0]["role"] == "system"
    assert "Resumen comprimido." in ctx.active_messages[0]["content"]


@pytest.mark.asyncio
async def test_distill_empty_store_does_not_trigger():
    store = ShortTermStore()
    provider = _mock_provider()

    triggered = await store.distill_if_needed(provider, ctx_size=2048)

    assert triggered is False
    provider.complete.assert_not_called()


# ---------------------------------------------------------------------------
# 7.3 — Sliding Window / RAG Handoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slide_archives_oldest_messages():
    store = ShortTermStore()
    for i in range(15):
        store.push_message({"role": "user", "content": f"message {i}"})

    long_term = _mock_long_term()
    archived = await store.slide_to_long_term(long_term, keep_last_n=5)

    assert archived == 10
    long_term.store_episode.assert_called_once()
    # Verify archived text contains old messages, not recent ones
    call_args = long_term.store_episode.call_args
    episode_text = call_args.args[0] if call_args.args else call_args.kwargs["summary"]
    assert "message 0" in episode_text
    assert "message 14" not in episode_text


@pytest.mark.asyncio
async def test_slide_keeps_last_n_messages_in_memory():
    store = ShortTermStore()
    for i in range(15):
        store.push_message({"role": "user", "content": f"message {i}"})

    long_term = _mock_long_term()
    await store.slide_to_long_term(long_term, keep_last_n=5)

    ctx = store.get_context()
    assert len(ctx.active_messages) == 5
    assert ctx.active_messages[-1]["content"] == "message 14"
    assert ctx.active_messages[0]["content"] == "message 10"


@pytest.mark.asyncio
async def test_slide_does_nothing_when_below_keep_threshold():
    store = ShortTermStore()
    for i in range(3):
        store.push_message({"role": "user", "content": f"message {i}"})

    long_term = _mock_long_term()
    archived = await store.slide_to_long_term(long_term, keep_last_n=10)

    assert archived == 0
    long_term.store_episode.assert_not_called()
    assert len(store.get_context().active_messages) == 3


@pytest.mark.asyncio
async def test_slide_tags_archived_episode_correctly():
    store = ShortTermStore()
    for i in range(12):
        store.push_message({"role": "user", "content": f"msg {i}"})

    long_term = _mock_long_term()
    await store.slide_to_long_term(long_term, keep_last_n=5)

    call_kwargs = long_term.store_episode.call_args.kwargs
    tags = call_kwargs.get("tags") or long_term.store_episode.call_args.args[1]
    assert "archived" in tags
    assert "session" in tags


# ---------------------------------------------------------------------------
# 7.2 — Prompt cache files exist
# ---------------------------------------------------------------------------


def test_prompt_cache_dir_exists():
    import os

    cache_dir = os.path.join(os.path.dirname(__file__), "..", "bin", "cache")
    assert os.path.isdir(cache_dir), "bin/cache/ directory must exist"


def test_args_files_enable_prompt_caching():
    import os

    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    for profile in ("coding", "deep"):
        args_path = os.path.join(config_dir, f"{profile}.args")
        content = open(args_path).read()
        assert (
            "--cache-prompt" in content
        ), f"{profile}.args missing --cache-prompt (llama-server CLI)"
        assert "--prompt-cache" not in content, f"{profile}.args uses removed --prompt-cache flag"
    chat_path = os.path.join(config_dir, "chat.args")
    chat = open(chat_path).read()
    assert "--mlock" not in chat, "chat.args must not use --mlock (low-RAM default)"
    assert "--cache-prompt" in chat, "chat.args must enable --cache-prompt for warm-turn latency"
    assert "--cache-ram" in chat, "chat.args should cap in-RAM prompt cache on 8 GB hosts"

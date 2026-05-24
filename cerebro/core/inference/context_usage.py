"""Token usage estimation and logging for llama.cpp chat completions."""

from __future__ import annotations

from typing import Any

from loguru import logger

from core.inference.registry import Message

_CHARS_PER_TOKEN = 4


def estimate_tokens_from_messages(messages: list[Message]) -> int:
    return sum(max(1, len(str(m.get("content", ""))) // _CHARS_PER_TOKEN) for m in messages)


def resolve_token_usage(data: dict[str, Any], messages: list[Message]) -> tuple[int, str]:
    usage = data.get("usage") or {}
    total = usage.get("total_tokens")
    if total is not None:
        return int(total), "usage.total_tokens"
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    if prompt or completion:
        return prompt + completion, "usage.prompt+completion"
    estimated = estimate_tokens_from_messages(messages)
    return estimated, "estimated_from_messages"


def format_context_usage(tokens_used: int, context_window: int, source: str) -> str:
    return f"Context usage: {tokens_used}/{context_window} (source={source})"


def log_context_usage(tokens_used: int, context_window: int, source: str) -> None:
    logger.info(format_context_usage(tokens_used, context_window, source))

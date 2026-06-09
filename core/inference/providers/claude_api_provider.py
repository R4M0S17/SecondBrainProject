from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterable
from typing import cast

import anthropic

from core.inference.registry import Message

_DEFAULT_MODEL = "claude-sonnet-4-6"
_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-opus-4-7": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
}


class ClaudeApiUnavailableError(Exception):
    pass


class ClaudeApiChatProvider:
    supports_vision = False

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        timeout: int = 120,
        max_tokens: int = 4096,
    ) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ClaudeApiUnavailableError("ANTHROPIC_API_KEY is not set")

        self._model = model
        self._max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)

    async def complete(self, messages: list[Message], **kwargs) -> str:
        system, user_messages = _split_system(messages)
        request: dict[str, object] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": user_messages,
            "temperature": kwargs.get("temperature", 0.7),
        }
        if system:
            request["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        try:
            response = await self._client.messages.create(**request)
            return _first_text_block(response.content).strip()
        except anthropic.AuthenticationError as e:
            raise ClaudeApiUnavailableError("Invalid ANTHROPIC_API_KEY") from e
        except anthropic.APIConnectionError as e:
            raise ClaudeApiUnavailableError("Cannot reach Anthropic API") from e

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        system, user_messages = _split_system(messages)
        request: dict[str, object] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": user_messages,
        }
        if system:
            request["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        try:
            async with self._client.messages.stream(**request) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIConnectionError as e:
            raise ClaudeApiUnavailableError("Cannot reach Anthropic API") from e

    def model_id(self) -> str:
        return self._model

    def context_window(self) -> int:
        return _CONTEXT_WINDOWS.get(self._model, 200_000)

    def is_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _split_system(messages: list[Message]) -> tuple[str, list[dict[str, str]]]:
    """Separate the first system message from the rest for Anthropic."""
    system = ""
    rest: list[dict[str, str]] = []
    for message in messages:
        if message["role"] == "system" and not system:
            system = message["content"]
            continue
        rest.append({"role": message["role"], "content": message["content"]})
    return system, rest


def _first_text_block(content: object) -> str:
    """Return the first text block from an Anthropic response."""
    if not hasattr(content, "__iter__"):
        return ""

    for block in cast(Iterable[object], content):
        text = getattr(block, "text", "")
        if isinstance(text, str) and text:
            return text
    return ""

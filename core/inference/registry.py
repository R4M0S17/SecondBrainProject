from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, TypedDict, cast, runtime_checkable

import psutil
from loguru import logger

if TYPE_CHECKING:
    from core.inference.model_manager import ModelManager


class Message(TypedDict):
    role: str
    content: str


class TaskHint(StrEnum):
    CHAT = "chat"
    EMBEDDING = "embedding"
    CODE = "code"
    SUMMARY = "summary"


class InsufficientResourcesError(Exception):
    pass


@runtime_checkable
class ChatProvider(Protocol):
    async def complete(self, messages: list[Message], **kwargs) -> str: ...

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]: ...

    def model_id(self) -> str: ...

    def context_window(self) -> int: ...

    def is_available(self) -> bool: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    def dimensions(self) -> int: ...


@dataclass
class _ProviderEntry:
    chat: ChatProvider
    embed: EmbeddingProvider


_AGENT_TO_ROLE: dict[str, str] = {
    "code-v1": "code",
}


class ProviderRegistry:
    def __init__(
        self,
        ram_threshold_primary_gb: float = 4.0,
        ram_threshold_fallback_gb: float = 2.0,
    ) -> None:
        self._providers: dict[str, _ProviderEntry] = {}
        self._primary_name: str | None = None
        self._fallback_name: str | None = None
        self._ram_threshold_primary = ram_threshold_primary_gb
        self._ram_threshold_fallback = ram_threshold_fallback_gb

    def register(self, name: str, chat: ChatProvider, embed: EmbeddingProvider) -> None:
        self._providers[name] = _ProviderEntry(chat=chat, embed=embed)
        if self._primary_name is None:
            self._primary_name = name
        elif self._fallback_name is None:
            self._fallback_name = name

    def get_chat(self, name: str | None = None) -> ChatProvider:
        key = name or self._primary_name
        if key is None or key not in self._providers:
            raise KeyError(f"Provider '{key}' not registered")
        return self._providers[key].chat

    def get_embed(self, name: str | None = None) -> EmbeddingProvider:
        key = name or self._primary_name
        if key is None or key not in self._providers:
            raise KeyError(f"Provider '{key}' not registered")
        return self._providers[key].embed

    def available_providers(self) -> list[str]:
        return list(self._providers.keys())

    def set_primary(self, name: str) -> None:
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' not registered")
        if self._primary_name != name:
            self._fallback_name = self._primary_name
            self._primary_name = name
            logger.info("Primary provider switched to '{}'", name)

    @property
    def primary_name(self) -> str:
        return self._primary_name or "unknown"

    def select_for_task(self, task: TaskHint) -> str:
        if not self._providers:
            raise KeyError("No providers registered")

        if task == TaskHint.EMBEDDING:
            # Embedding always uses the primary provider's embed model (nomic-embed-text by convention)
            return self._primary_name  # type: ignore[return-value]

        ram_available_gb = psutil.virtual_memory().available / (1024**3)
        logger.debug("RAM available: {:.2f} GB", ram_available_gb)

        if ram_available_gb >= self._ram_threshold_primary:
            return self._primary_name  # type: ignore[return-value]

        if ram_available_gb >= self._ram_threshold_fallback:
            fallback = self._fallback_name or self._primary_name
            return fallback  # type: ignore[return-value]

        raise InsufficientResourcesError(
            f"Only {ram_available_gb:.1f} GB RAM available "
            f"(minimum {self._ram_threshold_fallback} GB required for inference)"
        )

    async def get_chat_for_agent(self, agent_id: str, model_manager: ModelManager) -> ChatProvider:
        from core.inference.providers.llamacpp_provider import LlamaCppChatProvider

        role = _AGENT_TO_ROLE.get(agent_id, "general")
        port = await model_manager.ensure_specialist(role)
        profile = "coding" if role == "code" else "chat"
        return cast(
            ChatProvider,
            LlamaCppChatProvider(
                model=agent_id,
                base_url=f"http://127.0.0.1:{port}",
                profile=profile,
            ),
        )

    async def get_embedding_provider(
        self, model_manager: ModelManager | None = None
    ) -> EmbeddingProvider:
        if model_manager is not None:
            from core.inference.providers.llamacpp_embedding_provider import (
                LlamaCppEmbeddingProvider,
            )

            return LlamaCppEmbeddingProvider(base_url=model_manager.embed_url)
        return self.get_embed()

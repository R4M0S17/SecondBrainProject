from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from core.knowledge_sync.models import FetchedItem, SyncSourceConfig, SyncState


class SyncSource(ABC):
    def __init__(self, config: SyncSourceConfig) -> None:
        self._config = config

    @property
    def config(self) -> SyncSourceConfig:
        return self._config

    @abstractmethod
    async def fetch(self, state: SyncState) -> AsyncIterator[FetchedItem]: ...

    @abstractmethod
    async def validate(self) -> str | None: ...

    @abstractmethod
    async def estimate_next(self) -> int: ...

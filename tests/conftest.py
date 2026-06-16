"""Shared test fixtures for the Cerebro test suite.

All tests mock inference backends — no live llama.cpp/MLX/Claude.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_provider() -> MagicMock:
    """Return a mock ChatProvider with an async complete()."""
    provider = MagicMock()
    provider.complete = AsyncMock(return_value="mock response")
    return provider


@pytest.fixture
def mock_registry(mock_provider: MagicMock) -> MagicMock:
    """Return a mock ProviderRegistry with get_chat()."""
    registry = MagicMock()
    registry.get_chat = MagicMock(return_value=mock_provider)
    registry.select_for_task = MagicMock(return_value="primary")
    registry.primary_name = "mock"
    registry.available_providers = MagicMock(return_value=["mock"])
    return registry


@pytest.fixture
def tmp_app_state(tmp_path: Path) -> Any:
    """Create a minimal app_state-like object for tests that need it."""
    from unittest.mock import MagicMock

    state = MagicMock()
    state.db_path = str(tmp_path / "db")
    state.state_dir = str(tmp_path / "state")
    state.cerebro_files_path = str(tmp_path / "files")
    state.authorized_read_paths = [str(tmp_path)]
    state.authorized_write_paths = [str(tmp_path / "files")]
    state.rag_engine = MagicMock()
    state.rag_engine.query = AsyncMock(return_value=MagicMock(answer="mock", sources=[]))
    state.vector_store = MagicMock()
    state.provider_registry = MagicMock()
    state.embedding_provider = MagicMock()
    state.embedding_provider.dimensions = MagicMock(return_value=384)
    state.macos_permissions = MagicMock()
    state.macos_permissions.has_calendar_permission = False
    state.macos_permissions.has_files_permission = True
    state._config = {}
    return state

"""Tests for file search fast path and improved search_files handler."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.agents.file_search_fast_path import (
    parse_file_search_intent,
    try_file_search_fast_path,
)
from core.agents.runtime import AgentRuntime
from core.agents.specialized import GENERAL_TOOLS
from core.agents.state_store import AgentStateStore
from core.inference.registry import ProviderRegistry
from core.tools.handlers.filesystem import search_files


def test_search_files_all_authorized_roots(tmp_path):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "alpha.txt").write_text("a")
    (root_b / "beta.txt").write_text("b")

    result = search_files("*.txt", [str(root_a), str(root_b)], max_results=10)
    assert "alpha.txt" in result
    assert "beta.txt" in result


def test_search_files_name_contains(tmp_path):
    (tmp_path / "report_q1.pdf").write_text("x")
    (tmp_path / "notes.txt").write_text("y")
    result = search_files(
        "*",
        [str(tmp_path)],
        base_path=str(tmp_path),
        name_contains="report",
    )
    assert "report_q1.pdf" in result
    assert "notes.txt" not in result


def test_search_files_content_filter(tmp_path):
    (tmp_path / "has_token.txt").write_text("unique_marker_xyz")
    (tmp_path / "other.txt").write_text("nothing here")
    result = search_files(
        "*",
        [str(tmp_path)],
        base_path=str(tmp_path),
        query_text="unique_marker_xyz",
    )
    assert "has_token.txt" in result
    assert "other.txt" not in result


def test_search_files_skips_node_modules(tmp_path):
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "secret.txt").write_text("hidden")
    (tmp_path / "visible.txt").write_text("ok")
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path))
    assert "visible.txt" in result
    assert "node_modules" not in result


def test_search_files_spanish_no_results(tmp_path):
    result = search_files("*.zzz", [str(tmp_path)], base_path=str(tmp_path))
    assert "No se encontraron archivos" in result


def test_parse_file_search_intent_extension():
    intent = parse_file_search_intent("busca archivos con extensión py en mis carpetas")
    assert intent is not None
    assert intent.extension == ".py"


def test_parse_file_search_intent_named_file():
    intent = parse_file_search_intent("busca el archivo llamado README.md")
    assert intent is not None
    assert intent.name_contains == "README.md"


def test_try_file_search_fast_path_skips_write_intent(tmp_path, monkeypatch):
    monkeypatch.setenv("CEREBRO_AUTHORIZED_READ_PATHS", str(tmp_path))
    (tmp_path / "demo.txt").write_text("x")
    assert try_file_search_fast_path("crea un archivo demo.txt con hola", GENERAL_TOOLS) is None


def test_try_file_search_fast_path_finds_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CEREBRO_AUTHORIZED_READ_PATHS", str(tmp_path))
    (tmp_path / "demo.txt").write_text("hello")
    result = try_file_search_fast_path("busca el archivo demo.txt", GENERAL_TOOLS)
    assert result is not None
    assert "demo.txt" in result


def test_try_file_search_fast_path_desktop_base_path(tmp_path, monkeypatch):
    desktop = tmp_path / "Desktop"
    other = tmp_path / "other"
    desktop.mkdir()
    other.mkdir()

    (desktop / "solo_escritorio.txt").write_text("desk", encoding="utf-8")
    (other / "fuera_escritorio.txt").write_text("other", encoding="utf-8")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "CEREBRO_AUTHORIZED_READ_PATHS",
        f"{desktop}{os.pathsep}{other}",
    )

    result = try_file_search_fast_path(
        "busca en el escritorio archivos .txt",
        GENERAL_TOOLS,
    )
    assert result is not None
    assert "solo_escritorio.txt" in result
    assert "fuera_escritorio.txt" not in result


@pytest.mark.asyncio
async def test_runtime_file_search_fast_path_skips_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("CEREBRO_AUTHORIZED_READ_PATHS", str(tmp_path))
    (tmp_path / "findme.md").write_text("# doc")

    registry = MagicMock(spec=ProviderRegistry)
    registry.select_for_task = MagicMock(return_value="llamacpp")
    registry.get_chat = MagicMock()

    context_builder = MagicMock()
    context_builder.maybe_consolidate = AsyncMock(return_value=False)
    context_builder.build = AsyncMock(
        return_value=MagicMock(session_history=[], memory_context="", sources=[])
    )

    runtime = AgentRuntime(
        registry=registry,
        state_store=AgentStateStore(state_dir=str(tmp_path / "state")),
        context_builder=context_builder,
        tool_registry={},
        tool_definitions={},
    )

    answer, _state = await runtime.run("busca archivos findme.md", "general-v1")
    assert "findme.md" in answer
    registry.get_chat.assert_not_called()


@pytest.mark.asyncio
async def test_runtime_file_search_fast_path_uses_live_authorized_paths(tmp_path, monkeypatch):
    """Verify that watched_folders (passed via authorized_read_paths_getter) are searched."""
    # Only set env to "tmp_path/a" initially
    path_a = tmp_path / "a"
    path_b = tmp_path / "b"
    path_a.mkdir()
    path_b.mkdir()
    (path_a / "from_a.txt").write_text("aaa")
    (path_b / "from_b.txt").write_text("bbb")

    monkeypatch.setenv("CEREBRO_AUTHORIZED_READ_PATHS", str(path_a))

    # Mock app_state.authorized_read_paths to include path_b (simulates watched_folders merge)
    merged_paths = [str(path_a), str(path_b)]
    registry = MagicMock(spec=ProviderRegistry)
    registry.select_for_task = MagicMock(return_value="llamacpp")
    registry.get_chat = MagicMock()

    context_builder = MagicMock()
    context_builder.maybe_consolidate = AsyncMock(return_value=False)
    context_builder.build = AsyncMock(
        return_value=MagicMock(session_history=[], memory_context="", sources=[])
    )

    runtime = AgentRuntime(
        registry=registry,
        state_store=AgentStateStore(state_dir=str(tmp_path / "state")),
        context_builder=context_builder,
        tool_registry={},
        tool_definitions={},
        authorized_read_paths_getter=lambda: merged_paths,
    )

    # This file is only in path_b — not in env CEREBRO_AUTHORIZED_READ_PATHS
    answer, _state = await runtime.run("busca archivos from_b.txt", "general-v1")
    assert "from_b.txt" in answer, (
        "file in watched_folders (path_b) should be found even though "
        "it's not in CEREBRO_AUTHORIZED_READ_PATHS"
    )

"""Tests for Phase 1 — Filesystem Agent Tools."""

from __future__ import annotations

from functools import partial

import pytest

from core.tools.handlers.filesystem import (
    PathNotAuthorizedError,
    search_files,
    write_file,
)
from core.tools.registry import ToolRegistry, register_filesystem_tools

# ---------------------------------------------------------------------------
# search_files — basic pattern match
# ---------------------------------------------------------------------------


def test_search_files_finds_matching_files(tmp_path):
    (tmp_path / "report.txt").write_text("data")
    (tmp_path / "notes.txt").write_text("other")
    result = search_files("report*", [str(tmp_path)], base_path=str(tmp_path))
    assert "report.txt" in result
    assert "notes.txt" not in result


def test_search_files_extension_filter(tmp_path):
    (tmp_path / "script.py").write_text("print(1)")
    (tmp_path / "README.md").write_text("# docs")
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path), extension=".py")
    assert "script.py" in result
    assert "README.md" not in result


def test_search_files_max_results_respected(tmp_path):
    for i in range(10):
        (tmp_path / f"file{i}.txt").write_text("x")
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path), max_results=3)
    assert result.count("\n") < 3  # ≤ 3 lines means ≤ 3 results


def test_search_files_no_matches_returns_message(tmp_path):
    result = search_files("*.xyz", [str(tmp_path)], base_path=str(tmp_path))
    assert "No files found" in result


def test_search_files_rejects_unauthorized_base_path(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(PathNotAuthorizedError):
        search_files("*", [str(allowed)], base_path=str(outside))


def test_search_files_missing_directory_returns_message(tmp_path):
    result = search_files("*", [str(tmp_path)], base_path=str(tmp_path / "nonexistent"))
    assert "not found" in result.lower() or "Directory not found" in result


# ---------------------------------------------------------------------------
# register_filesystem_tools — all 5 tools are registered
# ---------------------------------------------------------------------------


def test_register_filesystem_tools_registers_expected_tools(tmp_path):
    registry = ToolRegistry()
    register_filesystem_tools(
        registry,
        authorized_read_paths=[str(tmp_path)],
        authorized_write_paths=[str(tmp_path)],
    )
    registered = set(registry.definitions().keys())
    assert {
        "read_file",
        "write_file",
        "create_directory",
        "list_directory",
        "search_files",
    } <= registered


def test_write_file_via_partial_creates_file(tmp_path):
    handler = partial(write_file, authorized_paths=[str(tmp_path)])
    target = str(tmp_path / "output.txt")
    ok = handler(path=target, content="hello phase 1")
    assert ok is True
    assert (tmp_path / "output.txt").read_text() == "hello phase 1"

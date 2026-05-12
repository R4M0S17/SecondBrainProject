"""Tests for Phase 2 — Script Creation & Real Execution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.tools.handlers.execution import run_script
from core.tools.handlers.filesystem import (
    PathNotAuthorizedError,
    create_python_file,
    delete_file,
)
from core.tools.registry import ToolRegistry, register_filesystem_tools

# ---------------------------------------------------------------------------
# create_python_file
# ---------------------------------------------------------------------------


def test_create_python_file_saves_to_authorized_path(tmp_path):
    result = create_python_file("hello.py", "print('hi')", [str(tmp_path)])
    assert (tmp_path / "hello.py").exists()
    assert (tmp_path / "hello.py").read_text() == "print('hi')"
    assert "hello.py" in result


def test_create_python_file_rejects_non_py_extension(tmp_path):
    result = create_python_file("evil.sh", "rm -rf /", [str(tmp_path)])
    assert "Error" in result
    assert not (tmp_path / "evil.sh").exists()


def test_create_python_file_rejects_path_separators(tmp_path):
    result = create_python_file("sub/evil.py", "x=1", [str(tmp_path)])
    assert "Error" in result


# ---------------------------------------------------------------------------
# run_script
# ---------------------------------------------------------------------------


def test_run_script_captures_stdout(tmp_path):
    script = tmp_path / "greet.py"
    script.write_text("print('hello from script')")
    result = run_script(str(script), [str(tmp_path)])
    assert "hello from script" in result


def test_run_script_rejects_unauthorized_path(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "bad.py").write_text("print('nope')")
    with pytest.raises(PathNotAuthorizedError):
        run_script(str(outside / "bad.py"), [str(allowed)])


def test_run_script_returns_error_for_missing_file(tmp_path):
    result = run_script(str(tmp_path / "missing.py"), [str(tmp_path)])
    assert "not found" in result.lower() or "Error" in result


def test_run_script_respects_timeout(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(60)")
    result = run_script(str(script), [str(tmp_path)], timeout_seconds=1)
    assert "Timeout" in result or "timeout" in result.lower()


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------


def test_delete_file_rejects_unauthorized_path(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "target.txt").write_text("data")
    with pytest.raises(PathNotAuthorizedError):
        delete_file(str(outside / "target.txt"), [str(allowed)])


def test_delete_file_returns_error_for_missing_file(tmp_path):
    result = delete_file(str(tmp_path / "ghost.txt"), [str(tmp_path)])
    assert "not found" in result.lower() or "Error" in result


@patch("core.tools.handlers.filesystem.subprocess.run")
def test_delete_file_moves_to_trash(mock_run, tmp_path):
    target = tmp_path / "bye.txt"
    target.write_text("content")
    mock_run.return_value = MagicMock(returncode=0)
    result = delete_file(str(target), [str(tmp_path)])
    assert mock_run.called
    assert "Trash" in result or "moved" in result.lower()


# ---------------------------------------------------------------------------
# registry — all Phase 2 tools are registered
# ---------------------------------------------------------------------------


def test_register_filesystem_tools_includes_phase2_tools(tmp_path):
    registry = ToolRegistry()
    register_filesystem_tools(
        registry,
        authorized_read_paths=[str(tmp_path)],
        authorized_write_paths=[str(tmp_path)],
    )
    registered = set(registry.definitions().keys())
    assert {"create_python_file", "run_script", "delete_file"} <= registered


def test_run_script_and_delete_file_require_confirmation(tmp_path):
    registry = ToolRegistry()
    register_filesystem_tools(
        registry,
        authorized_read_paths=[str(tmp_path)],
        authorized_write_paths=[str(tmp_path)],
    )
    assert registry.get("run_script").requires_confirmation is True
    assert registry.get("delete_file").requires_confirmation is True
    assert registry.get("create_python_file").requires_confirmation is False

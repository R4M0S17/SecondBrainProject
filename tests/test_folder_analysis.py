"""Tests for core/tools/folder_analysis.py and POST /api/folder/analyze."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from core.tools.folder_analysis import analyze_folder, count_indexed_under
from ui.tray.server import app, app_state


# ── Pure unit tests ──────────────────────────────────────────────


def test_analyze_simple_tree(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.py").write_text("print(1)")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("# hi")

    result = analyze_folder(str(tmp_path), [str(tmp_path)], max_depth=4)
    assert result.total_files == 3
    assert result.total_dirs == 1
    assert ".txt" in result.by_extension
    assert ".py" in result.by_extension
    assert ".md" in result.by_extension
    assert result.total_size_bytes > 0
    assert len(result.largest_files) == 3


def test_analyze_respects_authorized_paths(tmp_path: Path):
    outside = tmp_path.parent / "outside-folder-analysis"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("secret")
    with pytest.raises(Exception):  # PathNotAuthorizedError
        analyze_folder(str(outside), [str(tmp_path)], max_depth=4)
    shutil.rmtree(outside, ignore_errors=True)


def test_analyze_skips_git(tmp_path: Path):
    (tmp_path / "file.txt").write_text("data")
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("fake")
    result = analyze_folder(str(tmp_path), [str(tmp_path)])
    assert result.total_files == 1
    assert ".git" not in str(result.tree_preview)


def test_analyze_truncation_warning(tmp_path: Path):
    for i in range(15):
        (tmp_path / f"file{i}.txt").write_text("x")
    result = analyze_folder(str(tmp_path), [str(tmp_path)], max_files=5)
    assert result.total_files == 5
    assert any("Truncated" in w for w in result.warnings)


def test_analyze_non_existent_path(tmp_path: Path):
    with pytest.raises(ValueError, match="does not exist"):
        analyze_folder(str(tmp_path / "nope"), [str(tmp_path)])


def test_analyze_file_not_dir(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    with pytest.raises(ValueError, match="not a directory"):
        analyze_folder(str(f), [str(tmp_path)])


def test_count_indexed_under(tmp_path: Path):
    indexed = {str(tmp_path / "a.md"): 0.5, str(tmp_path / "sub" / "b.md"): 0.3}
    sub = tmp_path / "sub"
    sub.mkdir()
    count, paths = count_indexed_under(str(tmp_path), indexed)
    assert count == 2
    assert len(paths) == 2


# ── API integration tests ────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_state():
    app_state._config = {}
    app_state.authorized_read_paths = []
    app_state.vector_store = None
    yield


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_api_folder_analyze(client, tmp_path: Path):
    app_state.authorized_read_paths = [str(tmp_path)]
    (tmp_path / "note.md").write_text("# Hello")
    async with client as c:
        resp = await c.post("/api/folder/analyze", json={"path": str(tmp_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_files"] == 1
    assert data["path"] == str(tmp_path)
    assert data["total_size_mb"] >= 0


@pytest.mark.asyncio
async def test_api_folder_analyze_403(client, tmp_path: Path):
    app_state.authorized_read_paths = [str(tmp_path / "allowed")]
    (tmp_path / "allowed").mkdir()
    async with client as c:
        resp = await c.post(
            "/api/folder/analyze",
            json={"path": str(tmp_path / "not-allowed")},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_folder_analyze_404(client, tmp_path: Path):
    app_state.authorized_read_paths = [str(tmp_path)]
    async with client as c:
        resp = await c.post(
            "/api/folder/analyze",
            json={"path": str(tmp_path / "nope")},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_folder_analyze_with_extensions(client, tmp_path: Path):
    app_state.authorized_read_paths = [str(tmp_path)]
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("y")
    (tmp_path / "c.md").write_text("z")
    async with client as c:
        resp = await c.post("/api/folder/analyze", json={"path": str(tmp_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["by_extension"][".py"] == 2
    assert data["by_extension"][".md"] == 1
    assert len(data["largest_files"]) == 3
    assert data["tree_preview"]

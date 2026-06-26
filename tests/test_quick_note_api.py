"""Tests for POST /api/quick-note."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ui.tray.server import app, app_state


@pytest.fixture(autouse=True)
def _reset_config():
    app_state._config = {}
    yield


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_quick_note_with_content_returns_200_and_md_path(client, tmp_path):
    app_state._config["cerebro_files_path"] = str(tmp_path)
    async with client as c:
        resp = await c.post("/api/quick-note", json={"content": "Hello world"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["path"].endswith(".md")


@pytest.mark.asyncio
async def test_quick_note_with_title_uses_title_in_filename(client, tmp_path):
    app_state._config["cerebro_files_path"] = str(tmp_path)
    async with client as c:
        resp = await c.post("/api/quick-note", json={"content": "Hello", "title": "My Note"})
    assert resp.status_code == 200
    data = resp.json()
    path = Path(data["path"])
    assert path.stem == "My Note" or "My-Note" in path.stem


@pytest.mark.asyncio
async def test_quick_note_empty_content_returns_422(client):
    async with client as c:
        resp = await c.post("/api/quick-note", json={"content": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_quick_note_writes_correct_format(client, tmp_path):
    app_state._config["cerebro_files_path"] = str(tmp_path)
    async with client as c:
        resp = await c.post(
            "/api/quick-note", json={"content": "Body text", "title": "Test Title"}
        )
    assert resp.status_code == 200
    data = resp.json()
    path = Path(data["path"])
    assert path.exists()
    content = path.read_text()
    assert "# Test Title" in content
    assert "Body text" in content

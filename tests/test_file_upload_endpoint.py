from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from ui.tray.server import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_files_upload_endpoint_processes_and_returns_json(client, monkeypatch):
    # Patch the processor to avoid heavy dependencies during unit tests
    def _fake_processor(path, authorized_paths=None):
        return {"metadata": {"mime_type": "text/plain"}, "content": "hello", "type": "text"}

    monkeypatch.setattr("ui.tray.server.process_uploaded_file", _fake_processor)

    async with client as c:
        files = {"files": ("test.txt", b"hello world", "text/plain")}
        resp = await c.post("/api/files/upload", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["filename"] == "test.txt"
    assert data[0]["mime_type"] == "text/plain"


@pytest.mark.asyncio
async def test_files_upload_endpoint_rejects_oversized_file(client):
    # Create a large payload (> MAX_SINGLE_FILE in server) to trigger 413
    large = b"0" * (11 * 1024 * 1024)  # 11 MB
    async with client as c:
        files = {"files": ("big.bin", large, "application/octet-stream")}
        resp = await c.post("/api/files/upload", files=files)

    assert resp.status_code in (413, 400)
    # Either 413 Payload Too Large or 400 if rejected by mime-type checks

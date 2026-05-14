"""Phase 8.7 — RAM pressure 503 on /api/query."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.test_fix_cerebro.conftest import install_runtime_for_query_e2e, make_stub_chat_complete
from ui.tray.server import app_state


@pytest.mark.asyncio
async def test_ram_critical_returns_503(api_client, tmp_path):
    mock_chat = make_stub_chat_complete(['{"action": "answer", "answer": "should not run"}'])
    install_runtime_for_query_e2e(tmp_path, mock_chat)

    mon = MagicMock()
    mon.snapshot.return_value = {
        "pressure": "critical",
        "used_gb": 14.0,
        "available_gb": 0.5,
        "total_gb": 16.0,
    }
    app_state.ram_monitor = mon

    async with api_client as c:
        resp = await c.post(
            "/api/query",
            json={"question": "hola", "agent": "general-v1"},
        )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Out of RAM. Lite profile recommended."
    mock_chat.complete.assert_not_called()

"""Phase 8.4 — Date question E2E via FastAPI."""

from __future__ import annotations

from datetime import datetime

import pytest

from tests.test_fix_cerebro.conftest import install_runtime_for_query_e2e, make_stub_chat_complete


@pytest.mark.asyncio
async def test_query_date_contains_current_year(api_client, tmp_path):
    year = str(datetime.now().year)
    mock_chat = make_stub_chat_complete(
        [f'{{"action": "answer", "answer": "Hoy es un día cualquiera en el año {year}."}}']
    )
    install_runtime_for_query_e2e(tmp_path, mock_chat)

    async with api_client as c:
        resp = await c.post(
            "/api/query",
            json={"question": "¿Qué día es hoy?", "agent": "general-v1"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert year in body["answer"]

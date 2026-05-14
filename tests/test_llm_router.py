"""Tests for LLMRouter intent prefilter (Phase 2)."""

from __future__ import annotations

import pytest

from core.agents.llm_router import LLMRouter


@pytest.mark.asyncio
async def test_classify_regex_routes_before_llm() -> None:
    r = LLMRouter()
    cases = [
        ("¿Cuál es mi próximo cumpleaños?", "calendar"),
        ("¿Qué día es hoy?", "calendar"),
        ("Arregla este bug en typescript", "code"),
        ("Resume este pdf", "academic"),
    ]
    for q, want in cases:
        assert await r.classify(q) == want, (q,)

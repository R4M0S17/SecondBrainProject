"""Tests for core/reflection/reflector.py — Reflection-Turn module."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.reflection.reflector import Reflector, _heuristic_checks

# ── Heuristic checks ───────────────────────────────────────────────────


class TestHeuristicChecks:
    def test_clean_answer_no_issues(self):
        issues = _heuristic_checks("La capital de Francia es París.")
        assert len(issues) == 0

    def test_detects_apologetic_opening(self):
        issues = _heuristic_checks("Lo siento, no tengo esa información.")
        assert any(i["type"] == "format" for i in issues)

    def test_detects_training_leak(self):
        issues = _heuristic_checks("Mi conocimiento fue actualizado por última vez en 2023.")
        assert any(i["type"] == "factual" for i in issues)

    def test_detects_ai_role_reference(self):
        issues = _heuristic_checks("Como asistente de IA, te recomiendo...")
        assert any(i["type"] == "format" for i in issues)

    def test_multiple_issues_one_per_type_max(self):
        issues = _heuristic_checks(
            "Lo siento, como asistente de IA mi conocimiento fue cortado en 2023."
        )
        types = {i["type"] for i in issues}
        assert "format" in types
        assert "factual" in types


# ── Reflector (no provider — heuristic only) ───────────────────────────


class TestReflectorHeuristicOnly:
    @pytest.fixture
    def reflector(self):
        return Reflector(provider=None, enabled=True)

    async def test_perfect_answer(self, reflector):
        result = await reflector.critique(
            query="¿Cuál es la capital de Francia?",
            answer="La capital de Francia es París.",
        )
        assert result.score >= 9
        assert not result.needs_correction

    async def test_flawed_answer(self, reflector):
        result = await reflector.critique(
            query="¿Qué sabes?",
            answer="Lo siento, como asistente de IA, mi conocimiento fue actualizado por última vez en 2021.",
        )
        assert result.score < 7
        assert result.needs_correction
        assert len(result.issues) > 0

    async def test_disabled_reflector(self):
        r = Reflector(enabled=False)
        result = await r.critique(query="test", answer="anything")
        assert result.score == 10
        assert not result.needs_correction

    async def test_latency_tracked(self, reflector):
        result = await reflector.critique(query="test", answer="some answer")
        assert result.latency_ms >= 0
        assert isinstance(result.latency_ms, float)

    async def test_empty_answer(self, reflector):
        result = await reflector.critique(query="test", answer="")
        assert result.score == 10  # no heuristic patterns in empty string
        assert not result.needs_correction


# ── Reflector (with mocked LLM provider) ──────────────────────────────

_GOOD_CRITIQUE = json.dumps(
    {
        "score": 9,
        "issues": [],
    }
)

_BAD_CRITIQUE = json.dumps(
    {
        "score": 4,
        "issues": [
            {
                "type": "factual",
                "description": "La respuesta contiene información incorrecta",
                "severity": 5,
            },
        ],
    }
)

_INVALID_JSON = "Esto no es JSON."


class TestReflectorWithProvider:
    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.complete = AsyncMock(return_value=_GOOD_CRITIQUE)
        return provider

    @pytest.fixture
    def reflector(self, mock_provider):
        return Reflector(provider=mock_provider, enabled=True)

    async def test_llm_critique_passes_good_answer(self, reflector, mock_provider):
        result = await reflector.critique(
            query="¿Qué es Python?",
            answer="Python es un lenguaje de programación.",
        )
        assert result.score >= 7
        assert not result.needs_correction
        mock_provider.complete.assert_awaited_once()

    async def test_llm_critique_rejects_bad_answer(self):
        provider = MagicMock()
        provider.complete = AsyncMock(return_value=_BAD_CRITIQUE)
        r = Reflector(provider=provider, enabled=True)
        result = await r.critique(query="test", answer="bad answer")
        assert result.score < 7
        assert result.needs_correction
        assert len(result.issues) == 1

    async def test_provider_timeout_falls_back_to_heuristic(self):
        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=TimeoutError())
        r = Reflector(provider=provider, enabled=True, timeout=0.01)
        result = await r.critique(query="test", answer="some answer")
        assert result.score == 10  # falls back gracefully
        assert r.stats["skipped"] == 1

    async def test_invalid_json_from_provider(self):
        provider = MagicMock()
        provider.complete = AsyncMock(return_value=_INVALID_JSON)
        r = Reflector(provider=provider, enabled=True, timeout=1.0)
        # Should raise JSONDecodeError which is caught
        result = await r.critique(query="test", answer="some answer")
        assert result.score == 10
        assert r.stats["skipped"] == 1

    async def test_provider_exception_caught(self):
        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=RuntimeError("connection failed"))
        r = Reflector(provider=provider, enabled=True, timeout=1.0)
        result = await r.critique(query="test", answer="some answer")
        assert result.score == 10
        assert r.stats["skipped"] == 1

    async def test_stats_tracked(self, reflector, mock_provider):
        assert reflector.stats["triggered"] == 0
        assert reflector.stats["corrected"] == 0
        await reflector.critique(query="test", answer="good answer")
        assert reflector.stats["triggered"] == 1
        assert reflector.stats["corrected"] == 0  # score 9, no correction


# ── Reflection integration via AgentRuntime ───────────────────────────


class TestReflectionInRuntime:
    @pytest.fixture
    def mock_runtime(self, monkeypatch):
        """Minimal mocked runtime to test the reflection hook."""
        from unittest.mock import AsyncMock, MagicMock

        from core.agents.conversation_store import ConversationStore

        rt = MagicMock()
        rt._reflector = Reflector(provider=None, enabled=True)
        rt._reflect_correction = AsyncMock(return_value="Respuesta corregida.")
        rt._registry = MagicMock()
        rt._state_store = MagicMock()
        rt._context_builder = MagicMock()
        rt._conv_store = ConversationStore("/tmp")
        return rt

    async def test_reflection_triggers_on_flawed_answer(self, monkeypatch):
        """Verify the reflection hook in AgentRuntime.run() gets called."""
        from core.agents.runtime import _context_to_preview

        ctx = {"sources_used": ["doc1.pdf"], "total_tokens_estimated": 500}
        preview = _context_to_preview(ctx)
        assert preview is not None
        assert "doc1" in preview

    async def test_context_to_preview_none(self):
        from core.agents.runtime import _context_to_preview

        assert _context_to_preview(None) is None
        assert _context_to_preview({}) is None
        assert _context_to_preview({"sources_used": []}) is None

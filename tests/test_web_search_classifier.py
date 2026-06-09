"""Tests for web search classifier and hybrid summary flow."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agents.state_store import AgentProfile, AgentState
from core.agents.web_search_classifier import (
    _heuristic_fallback,
    classify_needs_web_search,
    is_follow_up_query,
)

# ── Fixtures ──


@pytest.fixture
def mock_registry():
    """Mock ProviderRegistry with a chat provider."""
    registry = MagicMock()
    chat = AsyncMock()
    chat.complete = AsyncMock(return_value="yes")
    registry.select_for_task.return_value = "mock"
    registry.get_chat.return_value = chat
    return registry


@pytest.fixture
def mock_registry_no():
    """Mock ProviderRegistry that returns 'no'."""
    registry = MagicMock()
    chat = AsyncMock()
    chat.complete = AsyncMock(return_value="no")
    registry.select_for_task.return_value = "mock"
    registry.get_chat.return_value = chat
    return registry


@pytest.fixture
def mock_registry_timeout():
    """Mock ProviderRegistry that times out."""
    registry = MagicMock()
    chat = AsyncMock()

    async def slow_complete(*args, **kwargs):
        await asyncio.sleep(10)
        return "yes"

    chat.complete = slow_complete
    registry.select_for_task.return_value = "mock"
    registry.get_chat.return_value = chat
    return registry


@pytest.fixture
def agent_state():
    """Basic agent state with web_search authorized."""
    profile = AgentProfile(
        id="general-v1",
        name="General",
        domain_tags=["general"],
        authorized_tools=["web_search", "web_fetch"],
        preferences={"instructions": "test"},
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )
    return AgentState(
        profile=profile,
        session_summary="",
        working_memory={},
        tool_trace=[],
        semantic_memory_refs=[],
        execution_count=0,
        last_active="2024-01-01",
    )


# ── Follow-up detection tests ──


class TestFollowUpDetection:
    def test_spanish_explain_more(self):
        assert is_follow_up_query("explícame más") is True
        assert is_follow_up_query("explícame más sobre eso") is True
        assert is_follow_up_query("puedes explicarme más") is True

    def test_spanish_summarize(self):
        assert is_follow_up_query("resúmelo") is True
        assert is_follow_up_query("resúmeme los resultados") is True

    def test_spanish_more_details(self):
        assert is_follow_up_query("dame más detalles") is True
        assert is_follow_up_query("más información por favor") is True
        assert is_follow_up_query("qué más hay") is True

    def test_english_explain_more(self):
        assert is_follow_up_query("tell me more") is True
        assert is_follow_up_query("explain more please") is True
        assert is_follow_up_query("can you elaborate") is True

    def test_english_summarize(self):
        assert is_follow_up_query("summarize this") is True
        assert is_follow_up_query("give me a summary") is True

    def test_english_more_details(self):
        assert is_follow_up_query("more details please") is True
        assert is_follow_up_query("I need more info") is True

    def test_not_follow_up(self):
        assert is_follow_up_query("what is python") is False
        assert is_follow_up_query("busca en la web noticias") is False
        assert is_follow_up_query("hello") is False
        assert is_follow_up_query("") is False


# ── Heuristic fallback tests ──


class TestHeuristicFallback:
    def test_question_words_trigger(self):
        assert _heuristic_fallback("qué es python") is True
        assert _heuristic_fallback("what is machine learning") is True
        assert _heuristic_fallback("who is the president") is True
        assert _heuristic_fallback("how does it work") is True
        assert _heuristic_fallback("where is paris") is True
        assert _heuristic_fallback("when was it founded") is True
        assert _heuristic_fallback("why is the sky blue") is True

    def test_calendar_excluded(self):
        assert _heuristic_fallback("qué tengo en el calendario") is False
        assert _heuristic_fallback("what is my next meeting agenda") is False
        assert _heuristic_fallback("crea un recordatorio") is False

    def test_file_excluded(self):
        assert _heuristic_fallback("dónde está el archivo") is False
        assert _heuristic_fallback("find my document") is False

    def test_math_excluded(self):
        assert _heuristic_fallback("2+2") is False
        assert _heuristic_fallback("17 * 23") is False

    def test_short_query(self):
        assert _heuristic_fallback("hello") is False
        assert _heuristic_fallback("hi") is False


# ── LLM classifier tests ──


class TestLLMClassifier:
    @pytest.mark.asyncio
    async def test_returns_true_when_llm_says_yes(self, mock_registry):
        result = await classify_needs_web_search("what is python", mock_registry)
        assert result is True
        mock_registry.get_chat.return_value.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_llm_says_no(self, mock_registry_no):
        result = await classify_needs_web_search("hello", mock_registry_no)
        assert result is False

    @pytest.mark.asyncio
    async def test_falls_back_on_timeout(self, mock_registry_timeout):
        # With a very short timeout, should fall back to heuristic
        result = await classify_needs_web_search(
            "qué es python", mock_registry_timeout, timeout_seconds=0.1
        )
        # Heuristic should return True for "qué es"
        assert result is True

    @pytest.mark.asyncio
    async def test_falls_back_on_no_provider(self):
        registry = MagicMock()
        registry.select_for_task.side_effect = Exception("No provider")
        result = await classify_needs_web_search("qué es python", registry)
        # Heuristic should return True for "qué es"
        assert result is True

    @pytest.mark.asyncio
    async def test_empty_query_returns_false(self, mock_registry):
        result = await classify_needs_web_search("", mock_registry)
        assert result is False

    @pytest.mark.asyncio
    async def test_short_query_returns_false(self, mock_registry):
        result = await classify_needs_web_search("hi", mock_registry)
        assert result is False
        # Should not even call LLM for very short queries
        mock_registry.get_chat.return_value.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_ambiguous_response_uses_heuristic(self):
        registry = MagicMock()
        chat = AsyncMock()
        chat.complete = AsyncMock(return_value="maybe")  # Ambiguous
        registry.select_for_task.return_value = "mock"
        registry.get_chat.return_value = chat

        result = await classify_needs_web_search("qué es python", registry)
        # Heuristic should return True for "qué es"
        assert result is True


# ── Integration tests with fast path router ──


class TestWebSearchFastPathIntegration:
    @pytest.mark.asyncio
    async def test_explicit_trigger_bypasses_classifier(self, mock_registry, agent_state):
        """Explicit 'busca en la web' should trigger without calling classifier."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)

        with patch("core.tools.handlers.web.web_search") as mock_search:
            mock_search.return_value = "1. Result\n---"
            result = await router._try_web_search("busca en la web python", agent_state)

        assert result is not None
        assert result.kind == "web_search"
        assert result.answer == "1. Result\n---"
        # Classifier should NOT be called for explicit triggers
        mock_registry.get_chat.return_value.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_news_trigger_bypasses_classifier(self, mock_registry, agent_state):
        """News keywords should trigger without calling classifier."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)

        with patch("core.tools.handlers.web.web_search") as mock_search:
            mock_search.return_value = "1. News result\n---"
            result = await router._try_web_search("noticias de hoy", agent_state)

        assert result is not None
        assert result.kind == "web_search"
        mock_registry.get_chat.return_value.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_weather_trigger_bypasses_classifier(self, mock_registry, agent_state):
        """Weather keywords should trigger without calling classifier."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)

        with patch("core.tools.handlers.web.web_search") as mock_search:
            mock_search.return_value = "1. Weather result\n---"
            result = await router._try_web_search("climate in miami", agent_state)

        assert result is not None
        assert result.kind == "web_search"
        mock_registry.get_chat.return_value.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_calendar_excluded(self, mock_registry, agent_state):
        """Calendar queries should be excluded even with classifier."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)
        result = await router._try_web_search("qué tengo en el calendario esta semana", agent_state)
        assert result is None

    @pytest.mark.asyncio
    async def test_calendar_context_excluded(self, mock_registry, agent_state):
        """'mi próxima reunión' should be excluded (calendar context)."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)
        result = await router._try_web_search("cuál es mi próxima reunión", agent_state)
        assert result is None

    @pytest.mark.asyncio
    async def test_file_excluded(self, mock_registry, agent_state):
        """File queries should be excluded."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)
        result = await router._try_web_search("dónde está el archivo de notas", agent_state)
        assert result is None

    @pytest.mark.asyncio
    async def test_math_excluded(self, mock_registry, agent_state):
        """Math expressions should be excluded."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)
        result = await router._try_web_search("2+2", agent_state)
        assert result is None

    @pytest.mark.asyncio
    async def test_classifier_triggers_search(self, mock_registry, agent_state):
        """When classifier says yes, web search should execute."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)

        with patch("core.tools.handlers.web.web_search") as mock_search:
            mock_search.return_value = "1. Python result\n---"
            result = await router._try_web_search("qué es python", agent_state)

        assert result is not None
        assert result.kind == "web_search"
        assert "Python result" in result.answer
        # Classifier should have been called
        mock_registry.get_chat.return_value.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_classifier_says_no_skips_search(self, mock_registry_no, agent_state):
        """When classifier says no, web search should not execute."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry_no)

        with patch("core.tools.handlers.web.web_search") as mock_search:
            result = await router._try_web_search("hello how are you", agent_state)

        assert result is None
        mock_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_result_stored_in_working_memory(self, mock_registry, agent_state):
        """Web search result should be stored in working_memory for follow-up."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)

        with patch("core.tools.handlers.web.web_search") as mock_search:
            mock_search.return_value = "1. Python is a language\n---"
            await router._try_web_search("qué es python", agent_state)

        assert (
            agent_state.working_memory.get("last_web_search_result")
            == "1. Python is a language\n---"
        )
        assert agent_state.working_memory.get("last_web_search_query") == "qué es python"

    @pytest.mark.asyncio
    async def test_follow_up_returns_none_answer(self, mock_registry, agent_state):
        """Follow-up query should return FastPathResult with answer=None."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)

        # First, store a web search result
        agent_state.working_memory["last_web_search_result"] = "1. Python result\n---"
        agent_state.working_memory["last_web_search_query"] = "qué es python"

        result = await router._try_web_search("explícame más", agent_state)

        assert result is not None
        assert result.kind == "web_search"
        assert result.answer is None  # Signals follow-up
        assert "web_search_follow_up" in result.warnings

    @pytest.mark.asyncio
    async def test_follow_up_without_previous_result(self, mock_registry, agent_state):
        """Follow-up without previous result should fall through to normal search."""
        from core.agents.fast_path_router import FastPathRouter

        router = FastPathRouter(mock_registry)

        # No previous result stored
        with patch("core.tools.handlers.web.web_search") as mock_search:
            mock_search.return_value = "1. General result\n---"
            result = await router._try_web_search("explícame más", agent_state)

        # Should fall through and execute normal search (classifier may trigger)
        # The result depends on classifier behavior
        # Just verify it doesn't crash
        assert result is None or result.kind == "web_search"


# ── Runtime integration tests ──


class TestRuntimeFollowUpSummary:
    @pytest.mark.asyncio
    async def test_summarize_web_search_result(self, agent_state):
        """Test the LLM summarization of web search results."""
        from core.agents.runtime import AgentRuntime

        # Create a minimal runtime mock
        runtime = MagicMock(spec=AgentRuntime)
        runtime._registry = MagicMock()
        chat = AsyncMock()
        chat.complete = AsyncMock(return_value="Python es un lenguaje de programación...")
        runtime._registry.select_for_task.return_value = "mock"
        runtime._registry.get_chat.return_value = chat

        # Store a web search result
        agent_state.working_memory["last_web_search_result"] = (
            "1. Python - Wikipedia\nURL: ...\nPython is a programming language..."
        )
        agent_state.working_memory["last_web_search_query"] = "qué es python"

        # Call the actual method
        from core.agents.runtime import AgentRuntime

        summary = await AgentRuntime._summarize_web_search_result(
            runtime, "explícame más", agent_state
        )

        assert summary is not None
        assert "Python" in summary
        chat.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_returns_none_without_result(self, agent_state):
        """Summarization should return None if no previous result."""
        from core.agents.runtime import AgentRuntime

        runtime = MagicMock(spec=AgentRuntime)
        runtime._registry = MagicMock()

        # No previous result stored
        summary = await AgentRuntime._summarize_web_search_result(
            runtime, "explícame más", agent_state
        )

        assert summary is None

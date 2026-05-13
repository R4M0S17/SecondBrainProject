"""Tests for A8 — Context Enricher."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.agents.context_enricher import LOCALE_TEMPLATES, ContextEnricher


def _make_enricher(enabled: bool = True, language: str = "en") -> ContextEnricher:
    return ContextEnricher(
        authorized_read_paths=["/tmp/test"],
        cerebro_files_path="/tmp/test",
        enabled=enabled,
        language=language,
    )


@pytest.mark.asyncio
async def test_enrich_returns_string():
    """enrich() should return a non-empty string when enabled and sources available."""
    enricher = _make_enricher(enabled=True)
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        # First call returns events, second call returns files
        mock_to_thread.side_effect = [
            "Próximo evento: Reunión a las 14:00",
            "archivo.txt (5.2 KB, modified 2026-05-12 10:30)",
        ]
        result = await enricher.enrich("qué tengo que hacer hoy")
        assert isinstance(result, str)
        assert "Reunión" in result or "archivo" in result


@pytest.mark.asyncio
async def test_enrich_disabled_returns_empty():
    """enrich() should return empty string when disabled."""
    enricher = _make_enricher(enabled=False)
    result = await enricher.enrich("qué tengo que hacer hoy")
    assert result == ""


@pytest.mark.asyncio
async def test_enrich_empty_sources_returns_empty():
    """enrich() returns empty if both get_upcoming_events and search_files return nothing."""
    enricher = _make_enricher(enabled=True)
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        # Both calls return empty or "Sin eventos"
        mock_to_thread.side_effect = ["Sin eventos", ""]
        result = await enricher.enrich("qué tengo que hacer")
        assert result == ""


@pytest.mark.asyncio
async def test_enrich_handles_errors_gracefully():
    """enrich() should not crash if one or both handlers raise exceptions."""
    enricher = _make_enricher(enabled=True)
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        # First call raises, second returns files
        mock_to_thread.side_effect = [
            RuntimeError("Calendar unavailable"),
            "archivo.txt",
        ]
        result = await enricher.enrich("qué tengo que hacer")
        # Should return a string (not raise)
        assert isinstance(result, str)


@pytest.mark.asyncio
async def test_enrich_formats_both_sources():
    """When both sources return content, format them together."""
    enricher = _make_enricher(enabled=True)
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.side_effect = [
            "Próximo evento: Reunión a las 14:00",
            "archivo.txt (5.2 KB)",
        ]
        result = await enricher.enrich("qué tengo que hacer")
        assert LOCALE_TEMPLATES["en"]["events_heading"].format(hours=48) in result
        assert LOCALE_TEMPLATES["en"]["files_heading"] in result
        assert "Reunión" in result
        assert "archivo.txt" in result


@pytest.mark.asyncio
async def test_enrich_supports_spanish_locale():
    """Spanish labels remain available via the language setting."""
    enricher = _make_enricher(enabled=True, language="es")
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.side_effect = [
            "Próximo evento: Reunión a las 14:00",
            "archivo.txt (5.2 KB)",
        ]
        result = await enricher.enrich("qué tengo que hacer")
        assert LOCALE_TEMPLATES["es"]["events_heading"].format(hours=48) in result
        assert LOCALE_TEMPLATES["es"]["files_heading"] in result


@pytest.mark.asyncio
async def test_enrich_unsupported_locale_falls_back_to_english():
    """Unknown languages use English defaults instead of hard-coded labels."""
    enricher = _make_enricher(enabled=True, language="unknown")
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.side_effect = [
            "Next event: Standup at 14:00",
            "",
        ]
        result = await enricher.enrich("what is next")
        assert LOCALE_TEMPLATES["en"]["events_heading"].format(hours=48) in result


@pytest.mark.asyncio
async def test_enrich_timeout_returns_empty():
    """enrich() should return empty string on timeout."""
    enricher = _make_enricher(enabled=True)

    async def mock_to_thread_timeout(*args, **kwargs):
        await asyncio.sleep(10)  # Longer than ENRICH_TIMEOUT_SEC

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.side_effect = mock_to_thread_timeout
        result = await enricher.enrich("what is next")
        assert result == ""


@pytest.mark.asyncio
async def test_enrich_partial_results_on_exception():
    """enrich() should return partial results if one handler raises exception."""
    enricher = _make_enricher(enabled=True)
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        # First call raises RuntimeError, second returns files
        mock_to_thread.side_effect = [
            RuntimeError("Calendar unavailable"),
            "file1.txt\nfile2.txt",
        ]
        result = await enricher.enrich("what files do I have")
        # Should return files section (not empty)
        assert isinstance(result, str)
        assert LOCALE_TEMPLATES["en"]["files_heading"] in result
        assert "file1.txt" in result


@pytest.mark.asyncio
async def test_enrich_both_exceptions_returns_empty():
    """enrich() should return empty if both handlers raise exceptions."""
    enricher = _make_enricher(enabled=True)
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        # Both calls raise exceptions
        mock_to_thread.side_effect = [
            RuntimeError("Calendar error"),
            RuntimeError("Filesystem error"),
        ]
        result = await enricher.enrich("what is next")
        assert result == ""


@pytest.mark.asyncio
async def test_enrich_validates_handler_return_types():
    """enrich() should validate handler return types against schema."""
    enricher = _make_enricher(enabled=True)
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        # Both handlers return valid strings
        mock_to_thread.side_effect = [
            "Próximo evento: Reunión a las 14:00",
            "archivo.txt (5.2 KB)",
        ]
        result = await enricher.enrich("qué tengo que hacer")
        # Both handlers pass validation and return results
        assert isinstance(result, str)
        assert "Reunión" in result
        assert "archivo.txt" in result


@pytest.mark.asyncio
async def test_enrich_handles_unexpected_handler_return_type():
    """enrich() should gracefully handle non-string handler returns."""
    enricher = _make_enricher(enabled=True)
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        # Calendar returns dict (unexpected type), files return valid string
        mock_to_thread.side_effect = [
            {"unexpected": "dict"},  # Wrong type
            "archivo.txt",  # Valid string
        ]
        result = await enricher.enrich("what do I need to do")
        # Should skip calendar and return only files
        assert isinstance(result, str)
        assert "archivo.txt" in result
        # Calendar events should not appear
        assert "unexpected" not in result

"""Tests for A8 — Context Enricher."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.agents.context_enricher import ContextEnricher


def _make_enricher(enabled: bool = True) -> ContextEnricher:
    return ContextEnricher(
        authorized_read_paths=["/tmp/test"],
        cerebro_files_path="/tmp/test",
        enabled=enabled,
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
        assert ("Reunión" in result or "archivo" in result)


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
        assert "PRÓXIMOS EVENTOS" in result
        assert "ARCHIVOS RECIENTES" in result
        assert "Reunión" in result
        assert "archivo.txt" in result

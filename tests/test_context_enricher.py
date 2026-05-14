"""Tests for A8 — Context Enricher."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from core.agents.context_enricher import LOCALE_TEMPLATES, ContextEnricher
from integrations.calendar_reader import BackendResult, CalendarEvent


def _sample_event() -> CalendarEvent:
    t0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    return CalendarEvent(title="Meet", start=t0, end=t0 + timedelta(hours=1))


def _make_enricher(
    enabled: bool = True,
    language: str = "en",
    macos_permissions: dict[str, str] | None = None,
) -> ContextEnricher:
    return ContextEnricher(
        authorized_read_paths=["/tmp/test"],
        cerebro_files_path="/tmp/test",
        enabled=enabled,
        language=language,
        macos_permissions=macos_permissions,
    )


@pytest.mark.asyncio
async def test_enrich_returns_string():
    """enrich() should return a non-empty string when enabled and sources available."""
    enricher = _make_enricher(enabled=True)
    br = BackendResult(events=[_sample_event()], status="ok")

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
        return_value=br,
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "archivo.txt (5.2 KB, modified 2026-05-12 10:30)"
            result = await enricher.enrich("qué tengo que hacer hoy")
        assert isinstance(result, str)
        assert "archivo" in result
        assert "Meet" in result or "archivo" in result


@pytest.mark.asyncio
async def test_enrich_disabled_returns_empty():
    """enrich() should return empty string when disabled."""
    enricher = _make_enricher(enabled=False)
    result = await enricher.enrich("qué tengo que hacer hoy")
    assert result == ""


@pytest.mark.asyncio
async def test_enrich_empty_sources_returns_empty():
    """enrich() returns empty if both calendar is empty and search_files returns nothing."""
    enricher = _make_enricher(enabled=True)
    br = BackendResult(events=[], status="ok")

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
        return_value=br,
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = ""
            result = await enricher.enrich("qué tengo que hacer")
        assert result == ""


@pytest.mark.asyncio
async def test_enrich_handles_errors_gracefully():
    """enrich() should not crash if calendar raises and files return."""
    enricher = _make_enricher(enabled=True)

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Calendar unavailable"),
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "archivo.txt"
            result = await enricher.enrich("qué tengo que hacer")
        assert isinstance(result, str)
        assert "archivo" in result


@pytest.mark.asyncio
async def test_enrich_formats_both_sources():
    """When both sources return content, format them together."""
    enricher = _make_enricher(enabled=True)
    br = BackendResult(events=[_sample_event()], status="ok")

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
        return_value=br,
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "archivo.txt (5.2 KB)"
            result = await enricher.enrich("qué tengo que hacer")
        assert LOCALE_TEMPLATES["en"]["events_heading"].format(hours=48) in result
        assert LOCALE_TEMPLATES["en"]["files_heading"] in result
        assert "Meet" in result
        assert "archivo.txt" in result


@pytest.mark.asyncio
async def test_enrich_supports_spanish_locale():
    """Spanish labels remain available via the language setting."""
    enricher = _make_enricher(enabled=True, language="es")
    br = BackendResult(events=[_sample_event()], status="ok")

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
        return_value=br,
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "archivo.txt (5.2 KB)"
            result = await enricher.enrich("qué tengo que hacer")
        assert LOCALE_TEMPLATES["es"]["events_heading"].format(hours=48) in result
        assert LOCALE_TEMPLATES["es"]["files_heading"] in result


@pytest.mark.asyncio
async def test_enrich_unsupported_locale_falls_back_to_english():
    """Unknown languages use English defaults instead of hard-coded labels."""
    enricher = _make_enricher(enabled=True, language="unknown")
    t0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    ev = CalendarEvent(title="Standup", start=t0, end=t0 + timedelta(hours=1))
    br = BackendResult(events=[ev], status="ok")

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
        return_value=br,
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = ""
            result = await enricher.enrich("what is next")
        assert LOCALE_TEMPLATES["en"]["events_heading"].format(hours=48) in result


@pytest.mark.asyncio
async def test_enrich_timeout_returns_empty():
    """enrich() should return empty string on outer wait_for timeout."""

    async def slow_cal(*_a, **_k):
        await asyncio.sleep(10)

    async def slow_files(*args, **kwargs):
        await asyncio.sleep(10)

    enricher = _make_enricher(enabled=True)

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        side_effect=slow_cal,
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = slow_files
            result = await enricher.enrich("what is next")
    assert result == ""


@pytest.mark.asyncio
async def test_enrich_partial_results_on_exception():
    """enrich() should return partial results if calendar raises and files succeed."""
    enricher = _make_enricher(enabled=True)

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Calendar unavailable"),
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "file1.txt\nfile2.txt"
            result = await enricher.enrich("what files do I have")
        assert isinstance(result, str)
        assert LOCALE_TEMPLATES["en"]["files_heading"] in result
        assert "file1.txt" in result


@pytest.mark.asyncio
async def test_enrich_both_exceptions_returns_empty():
    """enrich() should return empty if both handlers raise exceptions."""
    enricher = _make_enricher(enabled=True)

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Calendar error"),
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = RuntimeError("Filesystem error")
            result = await enricher.enrich("what is next")
        assert result == ""


@pytest.mark.asyncio
async def test_enrich_validates_handler_return_types():
    """enrich() should validate filesystem handler return types against schema."""
    enricher = _make_enricher(enabled=True)
    br = BackendResult(events=[_sample_event()], status="ok")

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
        return_value=br,
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "archivo.txt (5.2 KB)"
            result = await enricher.enrich("qué tengo que hacer")
        assert isinstance(result, str)
        assert "Meet" in result
        assert "archivo.txt" in result


@pytest.mark.asyncio
async def test_enrich_handles_unexpected_handler_return_type():
    """enrich() should gracefully handle non-string filesystem returns."""
    enricher = _make_enricher(enabled=True)
    br = BackendResult(events=[_sample_event()], status="ok")

    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
        return_value=br,
    ):
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = {"unexpected": "dict"}
            result = await enricher.enrich("what do I need to do")
        assert isinstance(result, str)
        assert "Meet" in result
        assert "unexpected" not in result


@pytest.mark.asyncio
async def test_permission_gate_calendar_denied_skips_enricher():
    """Phase 4.5 — calendar denied in macos_permissions must short-circuit enrich()."""
    enricher = _make_enricher(
        enabled=True,
        macos_permissions={"calendar": "denied"},
    )
    with patch(
        "integrations.calendar_reader.CalendarReader.get_upcoming_events_async",
        new_callable=AsyncMock,
    ) as mock_cal:
        result = await enricher.enrich("hello")
    assert result == ""
    mock_cal.assert_not_called()

"""Tests for LLM-based reminder intent extraction."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from core.agents.reminder_intent_resolver import (
    _parse_extractor_json,
    extract_reminder_intent,
    heuristic_parse_reminder,
    is_reminder_write_query,
    resolve_reminder_intent,
)


def test_heuristic_delete_manana_que_se_llama():
    intent = heuristic_parse_reminder('borra el recordatorio de mañana que se llama "prueba1"')
    assert intent is not None
    assert intent.action == "delete"
    assert intent.title == "prueba1"
    assert intent.datetime_str.lower().startswith("ma")


def test_heuristic_parse_para_llamado():
    intent = heuristic_parse_reminder(
        'crea un recordatorio para mañana a las 3pm llamado "prueba1"'
    )
    assert intent is not None
    assert intent.action == "add"
    assert intent.title == "prueba1"
    assert intent.datetime_str == "mañana a las 3pm"


def test_resolve_prefers_llm_then_heuristic():
    llm = None
    intent = resolve_reminder_intent(
        'crea un recordatorio para mañana a las 3pm llamado "prueba1"',
        llm_intent=llm,
    )
    assert intent is not None
    assert intent.title == "prueba1"


def test_is_reminder_write_query_variants():
    assert is_reminder_write_query('crea un recordatorio para mañana a las 3pm llamado "prueba1"')
    assert is_reminder_write_query("recuérdame llamar mañana a las 3pm")
    assert not is_reminder_write_query("¿cuándo es mi próximo recordatorio?")


def test_parse_extractor_add():
    raw = '{"intent":"add","title":"prueba1","datetime_str":"mañana a las 3pm"}'
    intent = _parse_extractor_json(raw)
    assert intent is not None
    assert intent.action == "add"
    assert intent.title == "prueba1"
    assert intent.datetime_str == "mañana a las 3pm"


def test_parse_extractor_unquoted_repair():
    # repair only fixes tool/action identifiers; full string still needs valid JSON strings
    intent = _parse_extractor_json('{"intent":"add","title":"X","datetime_str":"mañana a las 3pm"}')
    assert intent is not None
    assert intent.action == "add"


@pytest.mark.asyncio
async def test_extract_reminder_intent_llm_call():
    chat = AsyncMock()
    chat.complete.return_value = (
        '{"intent":"add","title":"Reunión con Juan","datetime_str":"mañana a las 3pm"}'
    )
    intent = await extract_reminder_intent(
        'crea un recordatorio para mañana a las 3pm llamado "Reunión con Juan"',
        chat,
        current_date="Sunday, May 24, 2026",
    )
    assert intent is not None
    assert intent.action == "add"
    assert intent.title == "Reunión con Juan"
    chat.complete.assert_awaited_once()

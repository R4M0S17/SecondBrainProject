"""Tests for new deterministic fast paths: weather, dictionary, unit conversion, system info."""

from __future__ import annotations

import pytest

from core.agents.dictionary_fast_path import try_dictionary_fast_path
from core.agents.system_info_fast_path import try_system_info_fast_path
from core.agents.unit_conversion_fast_path import try_unit_conversion_fast_path
from core.agents.weather_fast_path import try_weather_fast_path

# ── Weather ─────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_weather_detects_spanish_query():
    result = try_weather_fast_path("Cómo está el clima en Madrid?")
    assert result is not None
    assert "Madrid" in result


def test_weather_matches_no_location():
    result = try_weather_fast_path("Qué tiempo hace?")
    assert result is not None
    assert "¿De qué ciudad" in result or "ciudad" in result


def test_weather_unrelated_query_returns_none():
    result = try_weather_fast_path("What is the meaning of life?")
    assert result is None


# ── Dictionary ───────────────────────────────────────────────────────────────


@pytest.mark.network
def test_dictionary_detects_define_query():
    result = try_dictionary_fast_path("define serendipity")
    assert result is not None


def test_dictionary_detects_meaning_query():
    result = try_dictionary_fast_path("what is the meaning of life")
    assert result is not None


def test_dictionary_no_word_returns_prompt():
    result = try_dictionary_fast_path("define")
    assert result is not None
    assert "palabra" in result or "word" in result or "definir" in result


def test_dictionary_unrelated_query_returns_none():
    result = try_dictionary_fast_path("How is the weather today?")
    assert result is None


# ── Unit Conversion ──────────────────────────────────────────────────────────


def test_conversion_km_to_miles():
    result = try_unit_conversion_fast_path("convertir 10 km a millas")
    assert result is not None
    assert "km" in result
    assert "millas" in result or "mi" in result


def test_conversion_celsius_to_fahrenheit():
    result = try_unit_conversion_fast_path("cuánto es 100 grados celsius en fahrenheit")
    assert result is not None
    assert "212" in result


def test_conversion_kg_to_lbs():
    result = try_unit_conversion_fast_path("convert 5 kg to pounds")
    assert result is not None
    assert "kg" in result or "lb" in result


def test_conversion_invalid_units():
    result = try_unit_conversion_fast_path("convert 10 apples to oranges")
    assert result is not None
    assert "No pude" in result or "sé convertir" in result


def test_conversion_unrelated_query():
    result = try_unit_conversion_fast_path("Tell me a joke")
    assert result is None


# ── System Info ──────────────────────────────────────────────────────────────


def test_system_info_ram_query():
    result = try_system_info_fast_path("How much RAM do I have?")
    assert result is not None
    assert "RAM" in result or "GB" in result


def test_system_info_cpu_query():
    result = try_system_info_fast_path("CPU info")
    assert result is not None
    assert "CPU" in result


def test_system_info_full_diagnostic():
    result = try_system_info_fast_path("System info please")
    assert result is not None


def test_system_info_spanish():
    result = try_system_info_fast_path("diagnóstico del sistema")
    assert result is not None


def test_system_info_unrelated():
    result = try_system_info_fast_path("What is the capital of France?")
    assert result is None


# ── Router integration ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_router_weather_in_canonical_order():
    from unittest.mock import MagicMock

    from core.agents.fast_path_router import FastPathRouter
    from core.agents.state_store import AgentProfile, AgentState

    now = "2026-06-15T00:00:00Z"
    state = AgentState(
        profile=AgentProfile(
            id="test",
            name="test",
            domain_tags=[],
            authorized_tools=[],
            preferences={},
            created_at=now,
            updated_at=now,
        ),
        session_summary="",
        working_memory={},
        tool_trace=[],
        semantic_memory_refs=[],
        execution_count=0,
        last_active=now,
    )
    registry = MagicMock()
    router = FastPathRouter(registry, {})
    result = await router.try_all("Qué clima hace en Paris?", state)
    assert result is not None
    assert result.kind == "weather"


@pytest.mark.asyncio
async def test_router_dictionary_in_canonical_order():
    from unittest.mock import MagicMock

    from core.agents.fast_path_router import FastPathRouter
    from core.agents.state_store import AgentProfile, AgentState

    now = "2026-06-15T00:00:00Z"
    state = AgentState(
        profile=AgentProfile(
            id="test",
            name="test",
            domain_tags=[],
            authorized_tools=[],
            preferences={},
            created_at=now,
            updated_at=now,
        ),
        session_summary="",
        working_memory={},
        tool_trace=[],
        semantic_memory_refs=[],
        execution_count=0,
        last_active=now,
    )
    registry = MagicMock()
    router = FastPathRouter(registry, {})
    result = await router.try_all("define love", state)
    assert result is not None
    assert result.kind == "dictionary"


@pytest.mark.asyncio
async def test_router_conversion_in_canonical_order():
    from unittest.mock import MagicMock

    from core.agents.fast_path_router import FastPathRouter
    from core.agents.state_store import AgentProfile, AgentState

    now = "2026-06-15T00:00:00Z"
    state = AgentState(
        profile=AgentProfile(
            id="test",
            name="test",
            domain_tags=[],
            authorized_tools=[],
            preferences={},
            created_at=now,
            updated_at=now,
        ),
        session_summary="",
        working_memory={},
        tool_trace=[],
        semantic_memory_refs=[],
        execution_count=0,
        last_active=now,
    )
    registry = MagicMock()
    router = FastPathRouter(registry, {})
    result = await router.try_all("convertir 100 km a millas", state)
    assert result is not None
    assert result.kind == "unit_conversion"


@pytest.mark.asyncio
async def test_router_system_info_in_canonical_order():
    from unittest.mock import MagicMock

    from core.agents.fast_path_router import FastPathRouter
    from core.agents.state_store import AgentProfile, AgentState

    now = "2026-06-15T00:00:00Z"
    state = AgentState(
        profile=AgentProfile(
            id="test",
            name="test",
            domain_tags=[],
            authorized_tools=[],
            preferences={},
            created_at=now,
            updated_at=now,
        ),
        session_summary="",
        working_memory={},
        tool_trace=[],
        semantic_memory_refs=[],
        execution_count=0,
        last_active=now,
    )
    registry = MagicMock()
    router = FastPathRouter(registry, {})
    result = await router.try_all("How much RAM do I have?", state)
    assert result is not None
    assert result.kind == "system_info"

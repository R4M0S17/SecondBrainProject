"""Regression tests for Phase 3 — date correctness in the agent runtime."""

from __future__ import annotations

from datetime import datetime

from core.agents.runtime import _date_preamble


def test_date_preamble_contains_current_year() -> None:
    p = _date_preamble()
    assert str(datetime.now().year) in p
    assert "hoy" in p.lower()


def test_date_preamble_spanish_context_marker() -> None:
    p = _date_preamble()
    assert "hoy es" in p.lower()
    assert p.startswith("[Contexto del sistema:")

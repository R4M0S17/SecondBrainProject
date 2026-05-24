"""Tests for deterministic evaluate_math tool (FIX_PLAN2 G1)."""

from __future__ import annotations

from core.tools.handlers.math import evaluate_math


def test_evaluate_math_basic():
    assert evaluate_math("17*23") == "391"
    assert evaluate_math("(1+2)**3") == "27"
    assert evaluate_math("10/0").startswith("Error:")


def test_evaluate_math_one_third_short_decimal():
    result = evaluate_math("1/3")
    assert result == "0.3333333333"
    assert len(result) <= 12


def test_evaluate_math_integer_not_float_string():
    assert evaluate_math("2+2") == "4"
    assert ".0" not in evaluate_math("17*23")


def test_evaluate_math_rejects_non_numeric_call():
    assert evaluate_math("__import__('os')").startswith("Error:")


def test_evaluate_math_rejects_invalid_syntax():
    assert evaluate_math("2 +").startswith("Error:")

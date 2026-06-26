"""Regression tests for sub-1B (lite) model detection."""

from __future__ import annotations

import pytest

from core.agents.runtime import _is_small_model


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("", False),
        ("Qwen3.5-2B-UD-Q4_K_XL.gguf", False),
        ("Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf", False),
        ("qwen2.5-0.5b-instruct-q5_k_m.gguf", True),
        ("Qwen2.5-0.5B-Instruct-Q5_K_M.gguf", True),
        ("SmolLM2-135M-Instruct-Q8_0.gguf", True),
        ("phi-0_8b-q4.gguf", True),
    ],
)
def test_is_small_model(monkeypatch: pytest.MonkeyPatch, model: str, expected: bool) -> None:
    if model:
        monkeypatch.setenv("CEREBRO_LLAMACPP_MODEL", model)
    else:
        monkeypatch.delenv("CEREBRO_LLAMACPP_MODEL", raising=False)
    assert _is_small_model() is expected

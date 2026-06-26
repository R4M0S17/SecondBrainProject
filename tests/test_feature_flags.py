"""Tests for Low Power feature flag (disabled by default)."""

from __future__ import annotations

import os

import pytest

from core.feature_flags import (
    MAIN_CHAT_MODEL,
    apply_profile_guard,
    auto_start_engine_enabled,
    config_needs_low_power_migration,
    low_power_mode_enabled,
)


@pytest.fixture(autouse=True)
def _clear_low_power_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CEREBRO_LOW_POWER_ENABLED", raising=False)
    monkeypatch.delenv("CEREBRO_AUTO_START_ENGINE", raising=False)


def test_low_power_disabled_by_default() -> None:
    assert low_power_mode_enabled() is False


def test_low_power_enabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CEREBRO_LOW_POWER_ENABLED", "true")
    assert low_power_mode_enabled() is True


def test_apply_profile_guard_migrates_low_power_profile() -> None:
    cfg = {"profile": "low-power", "model": "qwen2.5-0.5b-instruct-q5_k_m.gguf"}
    out = apply_profile_guard(cfg)
    assert out["profile"] == "normal"
    assert out["model"] == MAIN_CHAT_MODEL


def test_apply_profile_guard_noop_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CEREBRO_LOW_POWER_ENABLED", "1")
    cfg = {"profile": "low-power", "model": "qwen2.5-0.5b-instruct-q5_k_m.gguf"}
    assert apply_profile_guard(cfg) == cfg


def test_config_needs_migration() -> None:
    assert config_needs_low_power_migration({"profile": "low-power"}) is True
    assert config_needs_low_power_migration({"profile": "normal", "model": MAIN_CHAT_MODEL}) is False


def test_auto_start_engine_disabled_by_default() -> None:
    assert auto_start_engine_enabled() is False


def test_auto_start_engine_enabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CEREBRO_AUTO_START_ENGINE", "true")
    assert auto_start_engine_enabled() is True

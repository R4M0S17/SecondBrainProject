"""Phase 8.2 — ModelManager validation and simple-mode fallback."""

from __future__ import annotations

import importlib

import pytest

from core.inference import model_manager as mm_mod


def test_model_manager_raises_file_not_found_with_missing_ggufs(tmp_path, monkeypatch):
    monkeypatch.setenv("CEREBRO_MODELS_DIR", str(tmp_path))
    importlib.reload(mm_mod)
    try:
        with pytest.raises(FileNotFoundError) as ei:
            mm_mod.ModelManager()
        msg = str(ei.value)
        assert "Model swapping requires" in msg
        assert str(tmp_path) in msg
    finally:
        monkeypatch.delenv("CEREBRO_MODELS_DIR", raising=False)
        importlib.reload(mm_mod)


def test_build_app_state_falls_back_when_model_swap_files_missing(tmp_path, monkeypatch) -> None:
    """_build_app_state() must not crash when ModelManager cannot find GGUFs."""
    empty_models = tmp_path / "models"
    empty_models.mkdir()
    db = tmp_path / "db"
    state = tmp_path / "state"
    monkeypatch.setenv("CEREBRO_INFERENCE_BACKEND", "llamacpp")
    monkeypatch.setenv("CEREBRO_LLAMACPP_SIMPLE", "false")
    monkeypatch.setenv("CEREBRO_MODELS_DIR", str(empty_models))
    monkeypatch.setenv("CEREBRO_DB", str(db))
    monkeypatch.setenv("CEREBRO_STATE", str(state))
    monkeypatch.setenv("CEREBRO_MLX_ENABLED", "false")
    monkeypatch.delenv("CEREBRO_API_KEY", raising=False)
    monkeypatch.setattr(
        "core.tools.security_audit.audit_confirmation_gates",
        lambda _registry: [],
    )
    monkeypatch.setattr("core.security.secrets.SecretsManager", lambda *a, **k: None)

    import main

    importlib.reload(mm_mod)
    importlib.reload(main)
    try:
        main._build_app_state()
        assert main.app_state.model_manager is None
        assert main.app_state.runtime is not None
        assert main.app_state.provider_registry is not None
    finally:
        for key in (
            "CEREBRO_MODELS_DIR",
            "CEREBRO_LLAMACPP_SIMPLE",
            "CEREBRO_DB",
            "CEREBRO_STATE",
            "CEREBRO_INFERENCE_BACKEND",
            "CEREBRO_MLX_ENABLED",
            "CEREBRO_LLAMACPP_MODEL",
        ):
            monkeypatch.delenv(key, raising=False)
        importlib.reload(mm_mod)
        importlib.reload(main)


import pytest

from core.inference.fleet.model_registry import (
    create_default_registry_template,
    load_registry,
)


class TestModelRegistry:
    """Tests for model registry loading and parsing."""

    def test_load_registry_missing_file_returns_empty(self, tmp_path):
        """Verify graceful return of empty list when file doesn't exist."""
        missing_path = tmp_path / "nonexistent" / "models.toml"
        result = load_registry(missing_path)
        assert result == []

    def test_load_toml_parses_correctly(self, tmp_path):
        """Verify TOML parsing produces correct ModelConfig objects."""
        models_path = tmp_path / "models.toml"
        models_path.write_text(
            """
[[models]]
id = "test-7b"
path = "~/test-7b.gguf"
family = "test"
params_b = 7.0
quant = "Q4_K_M"
ram_required_gb = 5.0
vram_required_gb = 4.0
gpu_layers = 32
context_length = 8192
capabilities = ["chat", "code"]
speed_tokens_per_sec = 50.0
"""
        )

        models = load_registry(models_path)
        assert len(models) == 1
        assert models[0].id == "test-7b"
        assert models[0].params_b == 7.0
        assert models[0].quant == "Q4_K_M"
        assert models[0].capabilities == ["chat", "code"]
        assert models[0].speed_tokens_per_sec == 50.0

    def test_load_multiple_models(self, tmp_path):
        """Verify loading multiple models from TOML."""
        models_path = tmp_path / "models.toml"
        models_path.write_text(
            """
[[models]]
id = "small"
path = "~/small.gguf"
family = "smoll"
params_b = 0.36
quant = "Q8_0"
ram_required_gb = 0.5
vram_required_gb = 0.4
gpu_layers = -1
context_length = 2048
capabilities = ["chat"]

[[models]]
id = "large"
path = "~/large.gguf"
family = "qwen"
params_b = 32.0
quant = "Q4_K_M"
ram_required_gb = 22.0
vram_required_gb = 20.0
gpu_layers = 64
context_length = 32768
capabilities = ["chat", "code", "reasoning"]
"""
        )

        models = load_registry(models_path)
        assert len(models) == 2
        assert models[0].id == "small"
        assert models[1].id == "large"

    def test_invalid_toml_raises_error(self, tmp_path):
        """Verify error on malformed TOML."""
        models_path = tmp_path / "models.toml"
        models_path.write_text("[[models]]\ninvalid toml [[[")

        with pytest.raises(ValueError, match="Failed to parse"):
            load_registry(models_path)

    def test_missing_optional_fields_use_defaults(self, tmp_path):
        """Verify optional fields like capabilities have sensible defaults."""
        models_path = tmp_path / "models.toml"
        models_path.write_text(
            """
[[models]]
id = "test"
path = "~/test.gguf"
family = "test"
params_b = 7.0
quant = "Q4"
ram_required_gb = 5.0
vram_required_gb = 4.0
gpu_layers = 32
context_length = 8192
"""
        )

        models = load_registry(models_path)
        assert models[0].capabilities == []
        assert models[0].speed_tokens_per_sec == 0.0

    def test_template_creation(self):
        """Verify default template is valid TOML."""
        template = create_default_registry_template()
        assert "qwen2.5-7b-q4" in template
        assert "smollm2-360m-q8" in template
        assert "[[models]]" in template

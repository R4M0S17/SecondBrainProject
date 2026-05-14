import pytest

from core.inference.fleet.model_registry import ModelConfig
from core.inference.fleet.orchestrator import ModelSelection
from core.inference.fleet.script_writer import build_llamacpp_command, build_mlx_command


class TestScriptWriter:
    """Tests for command generation."""

    @pytest.fixture
    def sample_selection(self):
        """Create a sample ModelSelection for testing."""
        model = ModelConfig(
            id="qwen7b-q4",
            path="/home/user/.cerebro/models/qwen7b-q4.gguf",
            family="qwen2.5",
            params_b=7.0,
            quant="Q4_K_M",
            ram_required_gb=5.5,
            vram_required_gb=4.8,
            gpu_layers=33,
            context_length=8192,
            capabilities=["chat", "code"],
            speed_tokens_per_sec=45.0,
        )
        return ModelSelection(
            model=model,
            gpu_layers=33,
            context_length=8192,
            rationale="Selected for MEDIUM task",
        )

    def test_build_llamacpp_command_includes_required_flags(self, sample_selection):
        """Verify llama-server command includes all required flags."""
        cmd = build_llamacpp_command(sample_selection, port=8080)

        assert cmd[0] == "./llama-server"
        assert "--model" in cmd
        assert sample_selection.model.path in cmd
        assert "--port" in cmd
        assert "8080" in cmd
        assert "--ctx-size" in cmd
        assert "8192" in cmd
        assert "--n-gpu-layers" in cmd
        assert "33" in cmd
        assert "--threads" in cmd
        assert "--batch-size" in cmd
        assert "512" in cmd
        assert "--flash-attn" in cmd

    def test_build_llamacpp_command_with_custom_port(self, sample_selection):
        """Verify custom port is used in command."""
        cmd = build_llamacpp_command(sample_selection, port=9090)
        assert "9090" in cmd

    def test_build_llamacpp_command_cpu_only(self):
        """Verify CPU-only model gets gpu_layers=0."""
        model = ModelConfig(
            id="tiny-cpu",
            path="~/tiny.gguf",
            family="tiny",
            params_b=0.36,
            quant="Q8_0",
            ram_required_gb=0.5,
            vram_required_gb=0.4,
            gpu_layers=-1,
            context_length=2048,
            capabilities=["chat"],
            speed_tokens_per_sec=300.0,
        )
        selection = ModelSelection(
            model=model,
            gpu_layers=0,
            context_length=2048,
            rationale="CPU-only selection",
        )

        cmd = build_llamacpp_command(selection)
        assert "--n-gpu-layers" in cmd
        assert "0" in cmd

    def test_build_llamacpp_command_thread_count(self, sample_selection):
        """Verify thread count is set based on cpu_count."""
        cmd = build_llamacpp_command(sample_selection)
        assert "--threads" in cmd
        thread_idx = cmd.index("--threads")
        thread_count = int(cmd[thread_idx + 1])
        assert thread_count >= 1

    def test_build_mlx_command_structure(self):
        """Verify MLX command has correct structure."""
        cmd = build_mlx_command("mistral-7b", port=8080)

        assert cmd[0] == "python"
        assert "-m" in cmd
        assert "mlx_lm.server" in cmd
        assert "--model" in cmd
        assert "mistral-7b" in cmd
        assert "--port" in cmd
        assert "8080" in cmd

    def test_build_mlx_command_with_custom_port(self):
        """Verify custom port in MLX command."""
        cmd = build_mlx_command("qwen7b", port=9000)
        assert "9000" in cmd

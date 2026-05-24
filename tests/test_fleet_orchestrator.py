from unittest.mock import patch

import pytest

from core.inference.fleet.hardware_monitor import HardwareSnapshot
from core.inference.fleet.model_registry import ModelConfig
from core.inference.fleet.orchestrator import FleetOrchestrator, ModelSelection
from core.inference.fleet.task_classifier import TaskComplexity, TaskProfile


class TestFleetOrchestrator:
    """Tests for model selection logic."""

    @pytest.fixture
    def orchestrator(self):
        """Create a FleetOrchestrator instance."""
        return FleetOrchestrator()

    @pytest.fixture
    def sample_models(self):
        """Create sample model registry for testing."""
        return [
            ModelConfig(
                id="smollm2-360m",
                path="~/smollm2-360m.gguf",
                family="smollm2",
                params_b=0.36,
                quant="Q8_0",
                ram_required_gb=0.8,
                vram_required_gb=0.7,
                gpu_layers=-1,
                context_length=2048,
                capabilities=["chat", "classification"],
                speed_tokens_per_sec=300.0,
            ),
            ModelConfig(
                id="qwen7b-q4",
                path="~/qwen7b-q4.gguf",
                family="qwen2.5",
                params_b=7.0,
                quant="Q4_K_M",
                ram_required_gb=5.5,
                vram_required_gb=4.8,
                gpu_layers=33,
                context_length=8192,
                capabilities=["chat", "code", "reasoning"],
                speed_tokens_per_sec=45.0,
            ),
            ModelConfig(
                id="qwen7b-q8",
                path="~/qwen7b-q8.gguf",
                family="qwen2.5",
                params_b=7.0,
                quant="Q8_0",
                ram_required_gb=9.0,
                vram_required_gb=8.5,
                gpu_layers=33,
                context_length=8192,
                capabilities=["chat", "code", "reasoning"],
                speed_tokens_per_sec=35.0,
            ),
            ModelConfig(
                id="qwen32b-q4",
                path="~/qwen32b-q4.gguf",
                family="qwen2.5",
                params_b=32.0,
                quant="Q4_K_M",
                ram_required_gb=22.0,
                vram_required_gb=20.0,
                gpu_layers=64,
                context_length=32768,
                capabilities=["chat", "code", "reasoning", "analysis"],
                speed_tokens_per_sec=12.0,
            ),
        ]

    def test_select_empty_registry_returns_none(self, orchestrator):
        """Verify None is returned when registry is empty."""
        hw = HardwareSnapshot(
            ram_total_gb=16.0,
            ram_available_gb=8.0,
            cpu_count=4,
            cpu_percent=50.0,
            gpu_backend="none",
            gpu_vram_total_gb=0.0,
            gpu_vram_available_gb=0.0,
            unified_memory=False,
        )
        task = TaskProfile(
            complexity=TaskComplexity.MEDIUM,
            requires_code=False,
            context_length_estimate=2048,
            required_capabilities=["chat"],
        )

        result = orchestrator.select_model(task, hw, [])
        assert result is None

    def test_select_filters_by_ram_requirement(self, orchestrator, sample_models):
        """Verify models exceeding available RAM are filtered out."""
        hw = HardwareSnapshot(
            ram_total_gb=16.0,
            ram_available_gb=4.0,  # Only 4GB available
            cpu_count=4,
            cpu_percent=50.0,
            gpu_backend="none",
            gpu_vram_total_gb=0.0,
            gpu_vram_available_gb=0.0,
            unified_memory=False,
        )
        task = TaskProfile(
            complexity=TaskComplexity.LIGHT,
            requires_code=False,
            context_length_estimate=1024,
            required_capabilities=["chat"],
        )

        result = orchestrator.select_model(task, hw, sample_models)
        # Should pick the smallest model (smollm2) or qwen7b-q4
        assert result is not None
        assert result.model.id in ("smollm2-360m", "qwen7b-q4")

    def test_select_filters_by_capability(self, orchestrator, sample_models):
        """Verify models are filtered by required capabilities."""
        hw = HardwareSnapshot(
            ram_total_gb=32.0,
            ram_available_gb=16.0,
            cpu_count=8,
            cpu_percent=50.0,
            gpu_backend="cuda",
            gpu_vram_total_gb=24.0,
            gpu_vram_available_gb=12.0,
            unified_memory=False,
        )
        task = TaskProfile(
            complexity=TaskComplexity.MEDIUM,
            requires_code=True,
            context_length_estimate=2048,
            required_capabilities=["chat", "code"],
        )

        result = orchestrator.select_model(task, hw, sample_models)
        # smollm2 doesn't have "code" capability, should be excluded
        assert result is not None
        assert result.model.id != "smollm2-360m"

    def test_select_heavy_task_picks_largest_model(self, orchestrator, sample_models):
        """Verify HEAVY task with sufficient RAM picks largest model."""
        hw = HardwareSnapshot(
            ram_total_gb=64.0,
            ram_available_gb=32.0,
            cpu_count=8,
            cpu_percent=50.0,
            gpu_backend="cuda",
            gpu_vram_total_gb=48.0,
            gpu_vram_available_gb=24.0,
            unified_memory=False,
        )
        task = TaskProfile(
            complexity=TaskComplexity.HEAVY,
            requires_code=False,
            context_length_estimate=4096,
            required_capabilities=["chat"],
        )

        result = orchestrator.select_model(task, hw, sample_models)
        assert result is not None
        assert result.model.id == "qwen32b-q4"

    def test_select_prefers_higher_quant_for_heavy_task(self, orchestrator, sample_models):
        """Verify HEAVY task prefers Q8 over Q4 of same family."""
        hw = HardwareSnapshot(
            ram_total_gb=32.0,
            ram_available_gb=15.0,  # Enough for Q8
            cpu_count=8,
            cpu_percent=50.0,
            gpu_backend="cuda",
            gpu_vram_total_gb=24.0,
            gpu_vram_available_gb=12.0,
            unified_memory=False,
        )
        task = TaskProfile(
            complexity=TaskComplexity.HEAVY,
            requires_code=False,
            context_length_estimate=4096,
            required_capabilities=["chat"],
        )

        result = orchestrator.select_model(task, hw, sample_models)
        assert result is not None
        # Should prefer Q8 version of qwen7b
        assert result.model.id == "qwen7b-q8"

    def test_select_critical_ram_picks_smallest(self, orchestrator, sample_models):
        """Verify critical RAM (<20% free) triggers smallest model selection."""
        hw = HardwareSnapshot(
            ram_total_gb=16.0,
            ram_available_gb=1.0,  # Only 6% free
            cpu_count=4,
            cpu_percent=90.0,
            gpu_backend="none",
            gpu_vram_total_gb=0.0,
            gpu_vram_available_gb=0.0,
            unified_memory=False,
        )
        task = TaskProfile(
            complexity=TaskComplexity.MAXIMUM,
            requires_code=False,
            context_length_estimate=8192,
            required_capabilities=["chat"],
        )

        result = orchestrator.select_model(task, hw, sample_models)
        assert result is not None
        # Should pick smallest eligible model
        assert result.model.params_b < 7.0
        assert result.gpu_layers == 0  # Force CPU-only

    def test_select_no_suitable_model(self, orchestrator):
        """Verify None when no model meets requirements."""
        hw = HardwareSnapshot(
            ram_total_gb=2.0,
            ram_available_gb=0.5,  # Very low RAM
            cpu_count=1,
            cpu_percent=95.0,
            gpu_backend="none",
            gpu_vram_total_gb=0.0,
            gpu_vram_available_gb=0.0,
            unified_memory=False,
        )
        task = TaskProfile(
            complexity=TaskComplexity.HEAVY,
            requires_code=True,
            context_length_estimate=8192,
            required_capabilities=["chat", "code", "analysis"],
        )
        models = [
            ModelConfig(
                id="huge",
                path="~/huge.gguf",
                family="test",
                params_b=70.0,
                quant="Q4",
                ram_required_gb=50.0,
                vram_required_gb=40.0,
                gpu_layers=64,
                context_length=32768,
                capabilities=["chat", "code"],
                speed_tokens_per_sec=5.0,
            )
        ]

        result = orchestrator.select_model(task, hw, models)
        assert result is None

    @patch("core.inference.fleet.orchestrator.snapshot")
    @patch("core.inference.fleet.orchestrator.load_registry")
    def test_select_on_startup_returns_none_for_empty_registry(
        self, mock_load, mock_snapshot, orchestrator
    ):
        """Verify select_on_startup returns None if registry is empty."""
        mock_snapshot.return_value = HardwareSnapshot(
            ram_total_gb=16.0,
            ram_available_gb=8.0,
            cpu_count=4,
            cpu_percent=50.0,
            gpu_backend="none",
            gpu_vram_total_gb=0.0,
            gpu_vram_available_gb=0.0,
            unified_memory=False,
        )
        mock_load.return_value = []

        result = orchestrator.select_on_startup()
        assert result is None

    @patch("core.inference.fleet.orchestrator.snapshot")
    @patch("core.inference.fleet.orchestrator.load_registry")
    def test_select_on_startup_returns_selection(
        self, mock_load, mock_snapshot, orchestrator, sample_models
    ):
        """Verify select_on_startup returns a ModelSelection."""
        mock_snapshot.return_value = HardwareSnapshot(
            ram_total_gb=16.0,
            ram_available_gb=12.0,
            cpu_count=4,
            cpu_percent=50.0,
            gpu_backend="none",
            gpu_vram_total_gb=0.0,
            gpu_vram_available_gb=0.0,
            unified_memory=False,
        )
        mock_load.return_value = sample_models

        result = orchestrator.select_on_startup()
        assert result is not None
        assert isinstance(result, ModelSelection)
        assert orchestrator.current_selection is result

    def test_pin_model_updates_selection(self, orchestrator, sample_models, tmp_path):
        model = sample_models[0]
        model_path = tmp_path / "smollm2.gguf"
        model_path.write_text("x", encoding="utf-8")
        on_disk = ModelConfig(
            id=model.id,
            path=str(model_path),
            family=model.family,
            params_b=model.params_b,
            quant=model.quant,
            ram_required_gb=model.ram_required_gb,
            vram_required_gb=model.vram_required_gb,
            gpu_layers=0,
            context_length=model.context_length,
            capabilities=model.capabilities,
            speed_tokens_per_sec=model.speed_tokens_per_sec,
        )
        with patch("core.inference.fleet.orchestrator.load_registry", return_value=[on_disk]):
            orchestrator.pin_model(on_disk.id)
        assert orchestrator.mode == "pinned"
        assert orchestrator.current_selection is not None
        assert orchestrator.current_selection.model.id == on_disk.id

    def test_pin_model_rejects_missing_file(self, orchestrator):
        with pytest.raises(ValueError, match="Unknown fleet model"):
            orchestrator.pin_model("does-not-exist")

    def test_use_auto_selection_clears_pin(self, orchestrator, tmp_path):
        model_path = tmp_path / "smollm2.gguf"
        model_path.write_text("x", encoding="utf-8")
        pinned = ModelConfig(
            id="smollm2-360m",
            path=str(model_path),
            family="smollm2",
            params_b=0.36,
            quant="Q8_0",
            ram_required_gb=0.8,
            vram_required_gb=0.7,
            gpu_layers=0,
            context_length=2048,
            capabilities=["chat"],
            speed_tokens_per_sec=300.0,
        )
        with patch("core.inference.fleet.orchestrator.load_registry", return_value=[pinned]):
            orchestrator.pin_model(pinned.id)
        with (
            patch("core.inference.fleet.orchestrator.snapshot") as mock_snap,
            patch("core.inference.fleet.orchestrator.load_registry") as mock_load,
        ):
            mock_snap.return_value = HardwareSnapshot(
                ram_total_gb=16.0,
                ram_available_gb=8.0,
                cpu_count=8,
                cpu_percent=5.0,
                gpu_backend="metal",
                gpu_vram_total_gb=16.0,
                gpu_vram_available_gb=8.0,
                unified_memory=True,
            )
            mock_load.return_value = [pinned]
            orchestrator.use_auto_selection()
        assert orchestrator.mode == "auto"
        assert orchestrator._pinned_model_id is None

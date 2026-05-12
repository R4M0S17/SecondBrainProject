from dataclasses import dataclass
from pathlib import Path

from core.inference.fleet.hardware_monitor import HardwareSnapshot, snapshot
from core.inference.fleet.model_registry import ModelConfig, load_registry
from core.inference.fleet.task_classifier import TaskComplexity, TaskProfile


@dataclass
class ModelSelection:
    """Result of model selection."""

    model: ModelConfig
    gpu_layers: int
    context_length: int
    rationale: str


class FleetOrchestrator:
    """Intelligent model selection at startup based on hardware and task."""

    def __init__(self):
        self.current_selection: ModelSelection | None = None
        self._hw_snapshot: HardwareSnapshot | None = None

    def select_model(
        self,
        task: TaskProfile,
        hw: HardwareSnapshot,
        registry: list[ModelConfig],
    ) -> ModelSelection | None:
        """Select the best model for a task given hardware constraints.

        Algorithm:
        1. Filter models with available RAM/VRAM (15% safety margin)
        2. Filter by required capabilities
        3. Among eligible, pick highest params_b
        4. If HEAVY/MAXIMUM and memory allows, prefer higher quant
        5. If RAM critical (<20% free), pick smallest eligible

        Args:
            task: TaskProfile describing the task
            hw: HardwareSnapshot of current hardware
            registry: List of available ModelConfig objects

        Returns:
            ModelSelection or None if no suitable model found
        """
        if not registry:
            return None

        # Calculate available memory with 15% safety margin
        ram_margin = hw.ram_available_gb * 0.85
        vram_available = hw.gpu_vram_available_gb if hw.gpu_backend != "none" else float("inf")
        vram_margin = vram_available * 0.85

        # Filter by required capabilities
        candidates = [
            m for m in registry if all(cap in m.capabilities for cap in task.required_capabilities)
        ]

        # Filter by available RAM/VRAM
        eligible = []
        for model in candidates:
            # Check RAM requirement
            if model.ram_required_gb > ram_margin:
                continue
            # Check VRAM requirement if GPU layers are used
            if model.gpu_layers != 0 and model.vram_required_gb > vram_margin:
                continue
            eligible.append(model)

        if not eligible:
            return None

        # Critical RAM check: if <20% free, pick smallest model
        ram_percent_free = (hw.ram_available_gb / hw.ram_total_gb) * 100
        if ram_percent_free < 20:
            selected = min(eligible, key=lambda m: m.params_b)
            rationale = (
                f"Critical RAM ({ram_percent_free:.0f}% free); selected smallest: {selected.id}"
            )
            return ModelSelection(
                model=selected,
                gpu_layers=0,  # Force CPU-only in critical RAM
                context_length=selected.context_length,
                rationale=rationale,
            )

        # Try to pick highest param model first
        eligible.sort(key=lambda m: m.params_b, reverse=True)
        primary = eligible[0]

        # If HEAVY/MAXIMUM and memory allows, prefer Q8 over Q4 of same size
        if task.complexity in (TaskComplexity.HEAVY, TaskComplexity.MAXIMUM):
            same_size = [
                m for m in eligible if m.params_b == primary.params_b and m.family == primary.family
            ]
            if same_size:
                # Prefer Q8 (higher quality) if available
                q8_models = [m for m in same_size if "Q8" in m.quant]
                if q8_models:
                    primary = q8_models[0]

        rationale = f"Selected {primary.id} ({primary.params_b}B, {primary.quant}) for {task.complexity.value} task"

        # Adjust GPU layers based on available VRAM
        gpu_layers = primary.gpu_layers
        if hw.gpu_backend != "none" and primary.gpu_layers > 0:
            # Reduce GPU layers if VRAM is tight but model still fits
            if primary.vram_required_gb > vram_margin:
                gpu_layers = int(primary.gpu_layers * 0.5)
        elif hw.gpu_backend == "none":
            gpu_layers = 0

        return ModelSelection(
            model=primary,
            gpu_layers=gpu_layers,
            context_length=primary.context_length,
            rationale=rationale,
        )

    def select_on_startup(
        self,
        registry_path: Path | None = None,
        default_task_complexity: TaskComplexity = TaskComplexity.MEDIUM,
    ) -> ModelSelection | None:
        """Select model at application startup.

        Args:
            registry_path: Path to models.toml. Defaults to ~/.cerebro/models.toml
            default_task_complexity: Assumed task complexity at startup

        Returns:
            ModelSelection or None if no registry found (graceful fallback)
        """
        # Load hardware and registry
        hw = snapshot()
        self._hw_snapshot = hw

        registry = load_registry(registry_path)
        if not registry:
            return None

        # Use a default MEDIUM task profile at startup
        default_task = TaskProfile(
            complexity=default_task_complexity,
            requires_code=False,
            context_length_estimate=2048,
            required_capabilities=["chat"],
        )

        selection = self.select_model(default_task, hw, registry)
        self.current_selection = selection
        return selection

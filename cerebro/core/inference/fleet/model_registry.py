import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelConfig:
    """Configuration for a single model."""

    id: str
    path: str
    family: str
    params_b: float  # billions of parameters
    quant: str  # e.g., "Q4_K_M", "Q8_0"
    ram_required_gb: float
    vram_required_gb: float
    gpu_layers: int  # -1 = all, 0 = CPU-only
    context_length: int
    capabilities: list[str]  # e.g., ["chat", "code", "reasoning"]
    speed_tokens_per_sec: float


def load_registry(path: Path | None = None) -> list[ModelConfig]:
    """Load model registry from TOML file.

    Args:
        path: Path to models.toml. Defaults to ~/.cerebro/models.toml

    Returns:
        List of ModelConfig objects. Empty list if file doesn't exist.
    """
    if path is None:
        path = Path.home() / ".cerebro" / "models.toml"

    if not path.exists():
        return []

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as e:
        raise ValueError(f"Failed to parse {path}: {e}") from e

    models = []
    for model_dict in data.get("models", []):
        model = ModelConfig(
            id=model_dict["id"],
            path=model_dict["path"],
            family=model_dict["family"],
            params_b=model_dict["params_b"],
            quant=model_dict["quant"],
            ram_required_gb=model_dict["ram_required_gb"],
            vram_required_gb=model_dict["vram_required_gb"],
            gpu_layers=model_dict["gpu_layers"],
            context_length=model_dict["context_length"],
            capabilities=model_dict.get("capabilities", []),
            speed_tokens_per_sec=model_dict.get("speed_tokens_per_sec", 0.0),
        )
        models.append(model)

    return models


def create_default_registry_template(path: Path | None = None) -> str:
    """Return a default models.toml template.

    This can be written to ~/.cerebro/models.toml by the user.
    """
    return """# Cerebro Local Model Registry
# Place this file at ~/.cerebro/models.toml
# Only models that exist on disk will be used.

[[models]]
id = "qwen2.5-7b-q4"
path = "~/.cerebro/models/qwen2.5-7b-instruct-q4_k_m.gguf"
family = "qwen2.5"
params_b = 7.0
quant = "Q4_K_M"
ram_required_gb = 5.5
vram_required_gb = 4.8
gpu_layers = 33
context_length = 8192
capabilities = ["chat", "code", "reasoning"]
speed_tokens_per_sec = 45.0

[[models]]
id = "qwen2.5-7b-q8"
path = "~/.cerebro/models/qwen2.5-7b-instruct-q8_0.gguf"
family = "qwen2.5"
params_b = 7.0
quant = "Q8_0"
ram_required_gb = 9.0
vram_required_gb = 8.5
gpu_layers = 33
context_length = 8192
capabilities = ["chat", "code", "reasoning"]
speed_tokens_per_sec = 35.0

[[models]]
id = "qwen2.5-32b-q4"
path = "~/.cerebro/models/qwen2.5-32b-q4_k_m.gguf"
family = "qwen2.5"
params_b = 32.0
quant = "Q4_K_M"
ram_required_gb = 22.0
vram_required_gb = 20.0
gpu_layers = 64
context_length = 32768
capabilities = ["chat", "code", "reasoning", "analysis"]
speed_tokens_per_sec = 12.0

[[models]]
id = "smollm2-360m-q8"
path = "~/.cerebro/models/smollm2-360m-q8_0.gguf"
family = "smollm2"
params_b = 0.36
quant = "Q8_0"
ram_required_gb = 0.8
vram_required_gb = 0.7
gpu_layers = -1
context_length = 2048
capabilities = ["chat", "classification"]
speed_tokens_per_sec = 300.0
"""

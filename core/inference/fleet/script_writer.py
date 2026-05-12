import os

from core.inference.fleet.orchestrator import ModelSelection


def build_llamacpp_command(selection: ModelSelection, port: int = 8080) -> list[str]:
    """Build llama-server command line for a model selection.

    Args:
        selection: ModelSelection with chosen model and parameters
        port: Port to listen on

    Returns:
        List of command arguments
    """
    cmd = [
        "./llama-server",
        "--model",
        str(selection.model.path),
        "--port",
        str(port),
        "--ctx-size",
        str(selection.context_length),
        "--n-gpu-layers",
        str(selection.gpu_layers),
        "--threads",
        str(os.cpu_count() or 4),
        "--batch-size",
        "512",
    ]

    # Add flash-attn if supported (doesn't hurt to request)
    cmd.append("--flash-attn")

    return cmd


def build_mlx_command(model_id: str, port: int = 8080) -> list[str]:
    """Build MLX server command line (Apple Silicon).

    Args:
        model_id: Model identifier (e.g., "mistral-7b")
        port: Port to listen on

    Returns:
        List of command arguments
    """
    return [
        "python",
        "-m",
        "mlx_lm.server",
        "--model",
        model_id,
        "--port",
        str(port),
    ]

import platform
import subprocess
from dataclasses import dataclass

import psutil


@dataclass
class HardwareSnapshot:
    """Current hardware state snapshot."""

    ram_total_gb: float
    ram_available_gb: float
    cpu_count: int
    cpu_percent: float
    gpu_backend: str  # "metal", "cuda", "none"
    gpu_vram_total_gb: float
    gpu_vram_available_gb: float
    unified_memory: bool  # True on Apple Silicon


def snapshot() -> HardwareSnapshot:
    """Capture current hardware state."""
    # RAM and CPU from psutil
    vm = psutil.virtual_memory()
    ram_total_gb = vm.total / (1024**3)
    ram_available_gb = vm.available / (1024**3)
    cpu_count = psutil.cpu_count() or 1
    cpu_percent = psutil.cpu_percent(interval=0.1)

    gpu_backend = "none"
    gpu_vram_total_gb = 0.0
    gpu_vram_available_gb = 0.0
    unified_memory = False

    # Detect Apple Silicon (Metal)
    if platform.processor() in ("arm", "arm64"):
        gpu_backend = "metal"
        unified_memory = True
        # On Apple Silicon, GPU memory is unified with RAM
        gpu_vram_total_gb = ram_total_gb
        gpu_vram_available_gb = ram_available_gb
    else:
        # Try NVIDIA GPU detection
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if lines:
                    # If multiple GPUs, use the first one (or could sum them)
                    parts = lines[0].split(",")
                    if len(parts) == 2:
                        gpu_vram_total_gb = float(parts[0].strip()) / 1024
                        gpu_vram_available_gb = float(parts[1].strip()) / 1024
                        gpu_backend = "cuda"
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass

    return HardwareSnapshot(
        ram_total_gb=ram_total_gb,
        ram_available_gb=ram_available_gb,
        cpu_count=cpu_count,
        cpu_percent=cpu_percent,
        gpu_backend=gpu_backend,
        gpu_vram_total_gb=gpu_vram_total_gb,
        gpu_vram_available_gb=gpu_vram_available_gb,
        unified_memory=unified_memory,
    )

from __future__ import annotations

import platform
import sys

import psutil


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def mlx_available() -> bool:
    if platform.system() != "Darwin":
        return False
    if not is_apple_silicon():
        return False
    if psutil.virtual_memory().total < 4 * 1024**3:
        return False
    try:
        import mlx.core  # noqa: F401
        import mlx_lm  # noqa: F401

        return True
    except ImportError:
        return False
